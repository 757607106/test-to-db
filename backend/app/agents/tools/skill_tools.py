"""
Skill 工具集 (Skill Tools)

为 LangGraph Agent 提供 Skill 相关的工具。

工具列表：
- list_skills: 列出可用的 Skills
- load_skill: 加载指定 Skill 的完整内容

使用方式：
将这些工具添加到 Agent 的工具列表中，Agent 可以根据需要调用。
"""
from typing import Annotated
import json
import logging

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

logger = logging.getLogger(__name__)


@tool
async def list_skills(
    state: Annotated[dict, InjectedState]
) -> str:
    """
    列出当前数据库连接可用的业务领域（Skills）
    
    使用场景：
    - 用户询问"有哪些业务领域"时
    - 需要了解系统支持的查询范围时
    - Agent 不确定使用哪个 Skill 时
    
    Returns:
        str: JSON 格式的 Skills 列表，包含名称、描述、关键词
    """
    from app.services.skill_service import skill_service
    
    try:
        connection_id = state.get("connection_id")
        if not connection_id:
            return json.dumps({
                "success": False,
                "error": "未指定数据库连接"
            }, ensure_ascii=False)
        
        # 获取 Skills 列表
        skills = await skill_service.get_skills_by_connection(connection_id)
        
        if not skills:
            return json.dumps({
                "success": True,
                "message": "当前连接未配置 Skills，将使用默认全库模式",
                "skills": [],
                "mode": "default"
            }, ensure_ascii=False)
        
        # 构建简化的 Skills 信息
        skills_info = []
        for skill in skills:
            skills_info.append({
                "name": skill.name,
                "display_name": skill.display_name,
                "description": skill.description or "",
                "keywords": skill.keywords[:5] if skill.keywords else [],
                "table_count": len(skill.table_names) if skill.table_names else 0,
                "priority": skill.priority
            })
        
        return json.dumps({
            "success": True,
            "skills": skills_info,
            "total": len(skills_info),
            "mode": "skill",
            "hint": "使用 load_skill 工具加载特定领域的详细信息"
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"list_skills 失败: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def load_skill(
    skill_name: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """
    加载指定业务领域（Skill）的完整内容
    
    加载内容包括：
    - 该领域相关的数据库表结构（表名、列、关系）
    - 关联的业务指标定义
    - JOIN 规则
    - 业务规则说明
    - 常用查询模式
    - 枚举字段值
    
    Args:
        skill_name: Skill 标识名称（如 'sales_order', 'inventory'）
        
    Returns:
        str: JSON 格式的 Skill 完整内容
        
    使用场景：
    - 用户查询涉及特定业务领域时
    - 需要获取领域相关的表结构和规则时
    - 生成 SQL 前需要了解业务上下文时
    """
    from app.services.skill_service import skill_service
    
    try:
        connection_id = state.get("connection_id")
        if not connection_id:
            return json.dumps({
                "success": False,
                "error": "未指定数据库连接"
            }, ensure_ascii=False)
        
        # 加载 Skill 内容
        skill_content = await skill_service.load_skill(skill_name, connection_id)
        
        # 格式化输出
        result = {
            "success": True,
            "skill_name": skill_content.skill_name,
            "display_name": skill_content.display_name,
            "description": skill_content.description,
            # Schema 信息
            "tables": skill_content.tables,
            "columns": skill_content.columns,
            "relationships": skill_content.relationships,
            # 语义层信息
            "metrics": skill_content.metrics,
            "join_rules": skill_content.join_rules,
            # 业务上下文
            "business_rules": skill_content.business_rules,
            "common_patterns": skill_content.common_patterns,
            # 值域信息
            "enum_columns": skill_content.enum_columns,
        }
        
        # 添加使用提示
        if skill_content.business_rules:
            result["hint"] = f"请遵循业务规则: {skill_content.business_rules}"
        
        logger.info(f"加载 Skill '{skill_name}': {len(skill_content.tables)} 表, {len(skill_content.columns)} 列")
        
        return json.dumps(result, ensure_ascii=False, default=str)
        
    except ValueError as e:
        # Skill 不存在
        return json.dumps({
            "success": False,
            "error": str(e),
            "hint": "使用 list_skills 工具查看可用的 Skills"
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"load_skill 失败: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def get_skill_business_rules(
    state: Annotated[dict, InjectedState]
) -> str:
    """
    获取当前选中 Skill 的业务规则
    
    从状态中读取已加载的 Skill 业务规则，供 SQL 生成时使用。
    
    Returns:
        str: 业务规则文本，如果未选中 Skill 则返回空
        
    使用场景：
    - SQL 生成前获取业务约束
    - 需要了解数据处理规则时
    """
    try:
        # 从状态中获取已加载的 Skill 信息
        skill_mode_enabled = state.get("skill_mode_enabled", False)
        skill_name = state.get("selected_skill_name")
        business_rules = state.get("skill_business_rules")
        loaded_content = state.get("loaded_skill_content")
        
        if not skill_mode_enabled:
            return json.dumps({
                "success": True,
                "mode": "default",
                "business_rules": None,
                "message": "当前使用默认模式，无特定业务规则"
            }, ensure_ascii=False)
        
        result = {
            "success": True,
            "mode": "skill",
            "skill_name": skill_name,
            "business_rules": business_rules,
        }
        
        # 如果有加载的内容，提取常用模式
        if loaded_content and isinstance(loaded_content, dict):
            result["common_patterns"] = loaded_content.get("common_patterns", [])
        
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"get_skill_business_rules 失败: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# 导出工具列表
SKILL_TOOLS = [list_skills, load_skill, get_skill_business_rules]
