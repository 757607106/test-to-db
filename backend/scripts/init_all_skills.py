#!/usr/bin/env python3
"""
批量初始化 Skills 脚本

为三个进销存数据库创建针对性的 Skills 配置：
- inventory_demo (connection_id=10): 16张表简化版
- erp_inventory (connection_id=7): 34张表完整版
- erp_business (connection_id=13): 33张表多分公司版

使用方法:
    cd backend
    python -m scripts.init_all_skills

参数:
    --force: 覆盖已存在的同名 Skill
    --dry-run: 仅验证不实际导入
    --database: 指定单个数据库 (inventory_demo / erp_inventory / erp_business)
"""

import sys
import os
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.skill_service import skill_service
from app.schemas.skill import SkillCreate


# 数据库配置
DATABASES = {
    "inventory_demo": {
        "connection_id": 10,
        "tenant_id": 1,
        "config_file": "skills_inventory_demo.json",
        "description": "16张表简化版进销存"
    },
    "erp_inventory": {
        "connection_id": 7,
        "tenant_id": 1,
        "config_file": "skills_erp_inventory.json",
        "description": "34张表完整版ERP进销存"
    },
    "erp_business": {
        "connection_id": 13,
        "tenant_id": 1,
        "config_file": "skills_erp_business.json",
        "description": "33张表多分公司版ERP (PostgreSQL)"
    }
}


def load_skills_config(config_file: str) -> Dict[str, Any]:
    """加载 Skills 配置文件"""
    file_path = Path(__file__).parent / config_file
    
    if not file_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_skill_config(skill_data: Dict[str, Any]) -> List[str]:
    """验证单个 Skill 配置"""
    errors = []
    
    # 必填字段
    required_fields = ["name", "display_name"]
    for field in required_fields:
        if not skill_data.get(field):
            errors.append(f"缺少必填字段: {field}")
    
    # name 格式检查
    name = skill_data.get("name", "")
    if name and (not name.islower() or not name.replace("_", "").isalnum()):
        errors.append(f"name 必须是小写字母和下划线: {name}")
    
    # keywords 检查
    keywords = skill_data.get("keywords", [])
    if not keywords:
        errors.append("keywords 不能为空")
    
    # table_names 或 table_patterns 至少需要一个
    if not skill_data.get("table_names") and not skill_data.get("table_patterns"):
        errors.append("table_names 或 table_patterns 至少需要配置一个")
    
    return errors


async def import_skill(
    skill_data: Dict[str, Any], 
    connection_id: int, 
    tenant_id: int,
    force: bool = False
) -> Dict[str, Any]:
    """导入单个 Skill"""
    skill_name = skill_data["name"]
    
    # 检查是否已存在
    existing = await skill_service.get_skill_by_name(skill_name, connection_id)
    
    if existing:
        if force:
            # 删除旧的
            await skill_service.delete_skill(existing.id)
            print(f"      删除已存在的 Skill: {skill_name}")
        else:
            return {
                "name": skill_name,
                "status": "skipped",
                "message": "已存在，使用 --force 覆盖"
            }
    
    # 创建 SkillCreate 对象
    create_data = SkillCreate(
        name=skill_data["name"],
        display_name=skill_data["display_name"],
        description=skill_data.get("description"),
        keywords=skill_data.get("keywords", []),
        intent_examples=skill_data.get("intent_examples", []),
        table_patterns=skill_data.get("table_patterns", []),
        table_names=skill_data.get("table_names", []),
        business_rules=skill_data.get("business_rules"),
        common_patterns=skill_data.get("common_patterns", []),
        join_rules=skill_data.get("join_rules", []),
        priority=skill_data.get("priority", 0),
        is_active=True,
        icon=skill_data.get("icon"),
        color=skill_data.get("color"),
        connection_id=connection_id
    )
    
    # 创建 Skill
    skill = await skill_service.create_skill(create_data, tenant_id=tenant_id)
    
    return {
        "name": skill_name,
        "status": "created",
        "id": skill.id,
        "message": f"成功创建 (ID: {skill.id})"
    }


async def import_database_skills(
    db_name: str,
    db_config: Dict[str, Any],
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """为单个数据库导入 Skills"""
    print(f"\n{'='*60}")
    print(f"  数据库: {db_name}")
    print(f"  {db_config['description']}")
    print(f"  Connection ID: {db_config['connection_id']}")
    print(f"{'='*60}")
    
    # 加载配置
    try:
        config = load_skills_config(db_config["config_file"])
    except FileNotFoundError as e:
        print(f"  [x] 错误: {e}")
        return {"database": db_name, "status": "error", "message": str(e)}
    
    skills_data = config.get("skills", [])
    print(f"\n  发现 {len(skills_data)} 个 Skills 配置")
    
    # 验证所有配置
    print("\n  验证配置...")
    all_valid = True
    for skill_data in skills_data:
        name = skill_data.get("name", "未知")
        errors = validate_skill_config(skill_data)
        if errors:
            print(f"    [x] {name}: {', '.join(errors)}")
            all_valid = False
        else:
            print(f"    [ok] {name}")
    
    if not all_valid:
        return {"database": db_name, "status": "error", "message": "配置验证失败"}
    
    if dry_run:
        print("\n  [Dry Run] 配置验证通过，未实际导入")
        return {"database": db_name, "status": "dry_run", "skills_count": len(skills_data)}
    
    # 导入 Skills
    print("\n  开始导入...")
    results = []
    
    for skill_data in skills_data:
        try:
            result = await import_skill(
                skill_data, 
                db_config["connection_id"], 
                db_config["tenant_id"],
                force
            )
            results.append(result)
            
            status_icon = {
                "created": "+",
                "skipped": "-",
                "error": "x"
            }.get(result["status"], "?")
            
            print(f"    [{status_icon}] {result['name']}: {result['message']}")
            
        except Exception as e:
            results.append({
                "name": skill_data.get("name", "未知"),
                "status": "error",
                "message": str(e)
            })
            print(f"    [x] {skill_data.get('name', '未知')}: 错误 - {e}")
    
    created = len([r for r in results if r["status"] == "created"])
    skipped = len([r for r in results if r["status"] == "skipped"])
    errors = len([r for r in results if r["status"] == "error"])
    
    return {
        "database": db_name,
        "status": "success" if errors == 0 else "partial",
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "results": results
    }


async def main():
    parser = argparse.ArgumentParser(
        description="批量初始化进销存系统 Skills 配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python -m scripts.init_all_skills
    python -m scripts.init_all_skills --force
    python -m scripts.init_all_skills --database inventory_demo
    python -m scripts.init_all_skills --dry-run
        """
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="覆盖已存在的同名 Skill"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="仅验证配置，不实际导入"
    )
    parser.add_argument(
        "--database", "-db",
        type=str,
        choices=list(DATABASES.keys()),
        default=None,
        help="指定单个数据库 (默认处理所有数据库)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "#"*60)
    print("#  进销存系统 Skills 批量初始化工具")
    print("#"*60)
    print(f"\n配置:")
    print(f"  - Force: {args.force}")
    print(f"  - Dry Run: {args.dry_run}")
    print(f"  - Database: {args.database or '全部'}")
    
    # 确定要处理的数据库
    if args.database:
        databases = {args.database: DATABASES[args.database]}
    else:
        databases = DATABASES
    
    # 处理每个数据库
    all_results = []
    for db_name, db_config in databases.items():
        result = await import_database_skills(
            db_name,
            db_config,
            force=args.force,
            dry_run=args.dry_run
        )
        all_results.append(result)
    
    # 汇总
    print("\n" + "="*60)
    print("  汇总")
    print("="*60)
    
    total_created = 0
    total_skipped = 0
    total_errors = 0
    
    for result in all_results:
        db_name = result["database"]
        status = result["status"]
        
        if status == "dry_run":
            print(f"  {db_name}: [Dry Run] {result.get('skills_count', 0)} 个 Skills 待导入")
        elif status == "error":
            print(f"  {db_name}: [失败] {result.get('message', '未知错误')}")
        else:
            created = result.get("created", 0)
            skipped = result.get("skipped", 0)
            errors = result.get("errors", 0)
            
            total_created += created
            total_skipped += skipped
            total_errors += errors
            
            status_str = "成功" if errors == 0 else "部分成功"
            print(f"  {db_name}: [{status_str}] 创建 {created}, 跳过 {skipped}, 错误 {errors}")
    
    if not args.dry_run:
        print(f"\n  总计: 创建 {total_created}, 跳过 {total_skipped}, 错误 {total_errors}")
    
    print("\n完成!")
    
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
