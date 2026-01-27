#!/usr/bin/env python3
"""
初始化示例 Skills 脚本

用于将 example_skills.json 中的进销存行业示例 Skills 导入到数据库中。
支持指定 connection_id 和可选的 tenant_id。

使用方法:
    cd backend
    python -m scripts.init_example_skills --connection-id 1

参数:
    --connection-id: 必填，数据库连接 ID
    --tenant-id: 可选，租户 ID
    --force: 可选，覆盖已存在的同名 Skill
    --dry-run: 可选，仅验证不实际导入
"""

import sys
import os
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.skill_service import skill_service
from app.schemas.skill import SkillCreate


def load_example_skills(file_path: str = None) -> Dict[str, Any]:
    """加载示例 Skills 配置文件"""
    if file_path is None:
        file_path = Path(__file__).parent / "example_skills.json"
    
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
    tenant_id: int = None,
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
            print(f"  - 删除已存在的 Skill: {skill_name}")
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


async def main():
    parser = argparse.ArgumentParser(
        description="导入示例 Skills 配置到数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python -m scripts.init_example_skills --connection-id 1
    python -m scripts.init_example_skills --connection-id 1 --force
    python -m scripts.init_example_skills --connection-id 1 --dry-run
        """
    )
    parser.add_argument(
        "--connection-id", "-c",
        type=int,
        required=True,
        help="目标数据库连接 ID"
    )
    parser.add_argument(
        "--tenant-id", "-t",
        type=int,
        default=None,
        help="租户 ID (可选)"
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
        "--file",
        type=str,
        default=None,
        help="指定配置文件路径 (默认: example_skills.json)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  Skills 示例配置导入工具")
    print("=" * 60)
    print(f"\n配置:")
    print(f"  - Connection ID: {args.connection_id}")
    print(f"  - Tenant ID: {args.tenant_id or '无'}")
    print(f"  - Force: {args.force}")
    print(f"  - Dry Run: {args.dry_run}")
    
    # 加载配置
    try:
        config = load_example_skills(args.file)
    except FileNotFoundError:
        print(f"\n错误: 找不到配置文件")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"\n错误: 配置文件 JSON 格式错误: {e}")
        sys.exit(1)
    
    skills_data = config.get("skills", [])
    print(f"\n发现 {len(skills_data)} 个 Skills 配置")
    print(f"配置版本: {config.get('version', '未知')}")
    print(f"配置描述: {config.get('description', '无')}")
    
    # 验证所有配置
    print("\n" + "-" * 40)
    print("验证配置...")
    all_valid = True
    for skill_data in skills_data:
        name = skill_data.get("name", "未知")
        errors = validate_skill_config(skill_data)
        if errors:
            print(f"  [x] {name}: {', '.join(errors)}")
            all_valid = False
        else:
            print(f"  [ok] {name}: 配置有效")
    
    if not all_valid:
        print("\n存在配置错误，请修正后重试")
        sys.exit(1)
    
    if args.dry_run:
        print("\n[Dry Run 模式] 配置验证通过，未实际导入")
        sys.exit(0)
    
    # 导入 Skills
    print("\n" + "-" * 40)
    print("开始导入 Skills...")
    
    results = []
    for skill_data in skills_data:
        try:
            result = await import_skill(
                skill_data, 
                args.connection_id, 
                args.tenant_id,
                args.force
            )
            results.append(result)
            
            status_icon = {
                "created": "+",
                "skipped": "-",
                "error": "x"
            }.get(result["status"], "?")
            
            print(f"  [{status_icon}] {result['name']}: {result['message']}")
            
        except Exception as e:
            results.append({
                "name": skill_data.get("name", "未知"),
                "status": "error",
                "message": str(e)
            })
            print(f"  [x] {skill_data.get('name', '未知')}: 错误 - {e}")
    
    # 汇总
    print("\n" + "=" * 60)
    print("导入完成")
    print("-" * 40)
    
    created = [r for r in results if r["status"] == "created"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]
    
    print(f"  创建: {len(created)}")
    print(f"  跳过: {len(skipped)}")
    print(f"  错误: {len(errors)}")
    
    if created:
        print(f"\n已创建的 Skills:")
        for r in created:
            print(f"  - {r['name']} (ID: {r.get('id', '?')})")
    
    if errors:
        print(f"\n错误详情:")
        for r in errors:
            print(f"  - {r['name']}: {r['message']}")
        sys.exit(1)
    
    print("\n完成!")


if __name__ == "__main__":
    asyncio.run(main())
