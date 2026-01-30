"""
Skill 路由工具 (Skill Routing Utils)

为 chat_graph.py 提供清晰的 Skill 路由接口。

设计原则：
1. 简单清晰 - 单一职责，易于理解
2. 零配置兼容 - 未配置 Skill 时返回空结果
3. 支持多 Skill 合并 - 复杂查询可匹配多个 Skill
4. LLM 降级路由 - 关键词失败时使用 LLM
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkillRoutingResult:
    """
    Skill 路由结果
    
    设计为不可变数据类，便于传递和调试
    """
    # 是否启用 Skill 模式
    enabled: bool = False
    
    # 匹配的 Skill 列表（支持多 Skill 合并）
    matched_skills: List[Dict[str, Any]] = field(default_factory=list)
    
    # 加载的 Schema 信息（合并后的表结构）
    schema_info: Dict[str, Any] = field(default_factory=dict)
    
    # 业务规则（合并后）
    business_rules: Optional[str] = None
    
    # JOIN 规则（合并后）
    join_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    # 路由策略
    strategy_used: str = "none"
    
    # 路由原因（用于调试）
    reasoning: str = ""
    
    @property
    def primary_skill_name(self) -> Optional[str]:
        """主 Skill 名称"""
        if self.matched_skills:
            return self.matched_skills[0].get("name")
        return None


async def perform_skill_routing(
    query: str,
    connection_id: int,
    max_skills: int = 2
) -> SkillRoutingResult:
    """
    执行 Skill 路由
    
    流程：
    1. 检查是否配置了 Skills
    2. 尝试关键词匹配
    3. 如果关键词匹配失败，尝试 LLM 路由
    4. 合并多个 Skill 的内容
    
    Args:
        query: 用户查询
        connection_id: 数据库连接 ID
        max_skills: 最多合并的 Skill 数量（默认2个）
        
    Returns:
        SkillRoutingResult: 路由结果
    """
    from app.services.skill_router import (
        skill_router, 
        RoutingStrategy,
        should_use_skill_mode
    )
    from app.services.skill_service import skill_service
    
    # 1. 检查是否配置了 Skills
    try:
        has_skills = await should_use_skill_mode(connection_id)
    except Exception as e:
        logger.warning(f"检查 Skill 配置失败: {e}")
        return SkillRoutingResult(reasoning="检查配置失败")
    
    if not has_skills:
        return SkillRoutingResult(reasoning="未配置 Skills，使用全库模式")
    
    # 2. 尝试关键词路由
    try:
        routing_result = await skill_router.route(
            query=query,
            connection_id=connection_id,
            strategy=RoutingStrategy.KEYWORD
        )
    except Exception as e:
        logger.error(f"Skill 路由失败: {e}")
        return SkillRoutingResult(reasoning=f"路由失败: {e}")
    
    # 3. 关键词匹配失败，尝试 LLM 路由
    if routing_result.fallback_to_default:
        logger.info("关键词匹配无结果，尝试 LLM 路由")
        try:
            routing_result = await skill_router.route(
                query=query,
                connection_id=connection_id,
                strategy=RoutingStrategy.LLM
            )
        except Exception as e:
            logger.warning(f"LLM 路由失败: {e}")
    
    # 4. 仍然没有匹配，返回空结果
    if not routing_result.selected_skill and not routing_result.all_matches:
        return SkillRoutingResult(
            strategy_used=routing_result.strategy_used,
            reasoning="无匹配 Skill，使用全库模式"
        )
    
    # 5. 加载匹配的 Skill 内容（支持多 Skill）
    skills_to_load = routing_result.all_matches[:max_skills]
    if not skills_to_load and routing_result.selected_skill:
        skills_to_load = [routing_result.selected_skill]
    
    matched_skills = []
    all_tables = []
    all_columns = []
    all_relationships = []
    all_join_rules = []
    business_rules_parts = []
    
    for skill_match in skills_to_load:
        try:
            skill_content = await skill_service.load_skill(
                skill_match.skill_name, 
                connection_id
            )
            
            matched_skills.append({
                "name": skill_match.skill_name,
                "display_name": skill_match.display_name,
                "confidence": skill_match.confidence,
                "matched_keywords": skill_match.matched_keywords
            })
            
            # 合并 Schema
            all_tables.extend(skill_content.tables)
            all_columns.extend(skill_content.columns)
            all_relationships.extend(skill_content.relationships)
            all_join_rules.extend(skill_content.join_rules)
            
            # 合并业务规则
            if skill_content.business_rules:
                business_rules_parts.append(
                    f"[{skill_match.display_name}] {skill_content.business_rules}"
                )
                
        except Exception as e:
            logger.warning(f"加载 Skill {skill_match.skill_name} 失败: {e}")
    
    if not matched_skills:
        return SkillRoutingResult(
            strategy_used=routing_result.strategy_used,
            reasoning="Skill 加载失败，使用全库模式"
        )
    
    # 6. 去重
    unique_tables = _deduplicate_by_key(all_tables, "table_name")
    unique_columns = _deduplicate_by_key(all_columns, "id")
    unique_join_rules = _deduplicate_join_rules(all_join_rules)
    
    # 7. 构建结果
    return SkillRoutingResult(
        enabled=True,
        matched_skills=matched_skills,
        schema_info={
            "tables": unique_tables,
            "columns": unique_columns,
            "relationships": all_relationships,
        },
        business_rules="\n".join(business_rules_parts) if business_rules_parts else None,
        join_rules=unique_join_rules,
        strategy_used=routing_result.strategy_used,
        reasoning=f"匹配 {len(matched_skills)} 个 Skill: {', '.join(s['display_name'] for s in matched_skills)}"
    )


def _deduplicate_by_key(items: List[Dict], key: str) -> List[Dict]:
    """按指定 key 去重"""
    seen = set()
    result = []
    for item in items:
        k = item.get(key)
        if k and k not in seen:
            seen.add(k)
            result.append(item)
    return result


def _deduplicate_join_rules(rules: List[Dict]) -> List[Dict]:
    """JOIN 规则去重"""
    seen = set()
    result = []
    for rule in rules:
        key = (
            rule.get("left_table"),
            rule.get("left_column"),
            rule.get("right_table"),
            rule.get("right_column")
        )
        if key not in seen:
            seen.add(key)
            result.append(rule)
    return result


def format_skill_context_for_prompt(result: SkillRoutingResult) -> str:
    """
    将 Skill 上下文格式化为 LLM 提示词片段
    
    用于注入到 sql_generator_agent 的 prompt 中
    """
    if not result.enabled:
        return ""
    
    lines = ["## 业务领域上下文 (Skill Context)\n"]
    
    # 匹配的 Skill
    skill_names = [s["display_name"] for s in result.matched_skills]
    lines.append(f"当前业务领域: {', '.join(skill_names)}\n")
    
    # 业务规则
    if result.business_rules:
        lines.append("### 业务规则")
        lines.append(result.business_rules)
        lines.append("")
    
    # JOIN 规则
    if result.join_rules:
        lines.append("### JOIN 规则")
        for rule in result.join_rules[:5]:  # 最多5条
            left = f"{rule.get('left_table')}.{rule.get('left_column')}"
            right = f"{rule.get('right_table')}.{rule.get('right_column')}"
            join_type = rule.get('join_type', 'JOIN')
            desc = rule.get('description', '')
            lines.append(f"- {left} {join_type} {right}")
            if desc:
                lines.append(f"  说明: {desc}")
        lines.append("")
    
    return "\n".join(lines)


__all__ = [
    "SkillRoutingResult",
    "perform_skill_routing",
    "format_skill_context_for_prompt",
]
