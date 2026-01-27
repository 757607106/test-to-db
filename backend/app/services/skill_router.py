"""
Skill 路由服务 (Skill Router Service)

Skills-SQL-Assistant 架构的路由决策引擎。

核心职责：
1. 分析用户查询，匹配最相关的 Skill
2. 支持多种匹配策略（关键词、语义、LLM）
3. 零配置兼容 - 无 Skill 配置时返回 None
4. 与现有 query_planning 流程整合

路由策略：
- 快速路由：关键词匹配，延迟 < 10ms
- 语义路由：向量相似度匹配
- 智能路由：LLM 分析（复杂查询）
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
import re
from enum import Enum

from app.services.skill_service import skill_service
from app.schemas.skill import Skill

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """路由策略"""
    KEYWORD = "keyword"      # 关键词匹配
    SEMANTIC = "semantic"    # 语义相似度
    LLM = "llm"              # LLM 分析
    HYBRID = "hybrid"        # 混合策略


@dataclass
class SkillMatch:
    """Skill 匹配结果"""
    skill_name: str
    display_name: str
    confidence: float  # 0.0 - 1.0
    match_type: str    # keyword, semantic, llm
    matched_keywords: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class RoutingResult:
    """路由决策结果"""
    has_skills: bool
    selected_skill: Optional[SkillMatch] = None
    all_matches: List[SkillMatch] = field(default_factory=list)
    strategy_used: str = "none"
    fallback_to_default: bool = False
    reasoning: str = ""


class SkillRouter:
    """
    Skill 路由器
    
    决定用户查询应该使用哪个 Skill（或不使用 Skill）
    """
    
    # 路由配置
    KEYWORD_CONFIDENCE_THRESHOLD = 0.3  # 关键词匹配最低置信度
    SEMANTIC_CONFIDENCE_THRESHOLD = 0.7  # 语义匹配最低置信度
    MIN_KEYWORD_MATCHES = 1             # 最少匹配关键词数
    
    def __init__(self):
        self._embedding_model = None
    
    async def route(
        self, 
        query: str, 
        connection_id: int,
        strategy: RoutingStrategy = RoutingStrategy.KEYWORD
    ) -> RoutingResult:
        """
        执行路由决策
        
        Args:
            query: 用户查询
            connection_id: 数据库连接 ID
            strategy: 路由策略
            
        Returns:
            RoutingResult: 路由决策结果
        """
        # 检查是否有配置 Skill（零配置兼容）
        has_skills = await skill_service.has_skills_configured(connection_id)
        
        if not has_skills:
            return RoutingResult(
                has_skills=False,
                fallback_to_default=True,
                reasoning="未配置 Skills，使用默认模式"
            )
        
        # 获取所有活跃的 Skills
        skills = await skill_service.get_skills_by_connection(connection_id)
        
        if not skills:
            return RoutingResult(
                has_skills=False,
                fallback_to_default=True,
                reasoning="无可用的 Skills"
            )
        
        # 根据策略执行路由
        if strategy == RoutingStrategy.KEYWORD:
            return await self._route_by_keywords(query, skills)
        elif strategy == RoutingStrategy.SEMANTIC:
            return await self._route_by_semantic(query, skills)
        elif strategy == RoutingStrategy.LLM:
            return await self._route_by_llm(query, skills)
        elif strategy == RoutingStrategy.HYBRID:
            return await self._route_hybrid(query, skills)
        else:
            return await self._route_by_keywords(query, skills)
    
    async def _route_by_keywords(
        self, 
        query: str, 
        skills: List[Skill]
    ) -> RoutingResult:
        """
        关键词路由（快速）
        
        匹配逻辑：
        1. 分词并提取关键词
        2. 与每个 Skill 的 keywords 匹配
        3. 计算匹配度得分
        4. 选择得分最高的 Skill
        """
        query_lower = query.lower()
        matches: List[SkillMatch] = []
        
        for skill in skills:
            matched_keywords = []
            score = 0.0
            
            # 匹配关键词
            for keyword in (skill.keywords or []):
                keyword_lower = keyword.lower()
                if keyword_lower in query_lower:
                    matched_keywords.append(keyword)
                    # 关键词权重：更长的关键词权重更高
                    score += len(keyword) / 10.0
            
            # 匹配表名（如果用户提到了表名）
            for table_name in (skill.table_names or []):
                table_lower = table_name.lower()
                # 检查表名或其简化形式
                if table_lower in query_lower or self._simplify_table_name(table_lower) in query_lower:
                    matched_keywords.append(f"table:{table_name}")
                    score += 0.5
            
            # 匹配意图示例（部分匹配）
            for example in (skill.intent_examples or []):
                similarity = self._simple_similarity(query_lower, example.lower())
                if similarity > 0.5:
                    score += similarity * 0.3
            
            if matched_keywords or score > 0:
                # 归一化置信度
                max_possible = len(skill.keywords or []) * 0.5 + len(skill.table_names or []) * 0.5 + 1.0
                confidence = min(score / max_possible, 1.0) if max_possible > 0 else 0.0
                
                # 应用优先级加成
                confidence = min(confidence * (1 + skill.priority * 0.01), 1.0)
                
                if confidence >= self.KEYWORD_CONFIDENCE_THRESHOLD or len(matched_keywords) >= self.MIN_KEYWORD_MATCHES:
                    matches.append(SkillMatch(
                        skill_name=skill.name,
                        display_name=skill.display_name,
                        confidence=confidence,
                        match_type="keyword",
                        matched_keywords=matched_keywords,
                        reasoning=f"匹配关键词: {', '.join(matched_keywords[:5])}"
                    ))
        
        # 按置信度排序
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        if matches:
            return RoutingResult(
                has_skills=True,
                selected_skill=matches[0],
                all_matches=matches[:3],  # 最多返回 3 个候选
                strategy_used="keyword",
                reasoning=f"关键词匹配选中 '{matches[0].display_name}'"
            )
        else:
            return RoutingResult(
                has_skills=True,
                fallback_to_default=True,
                strategy_used="keyword",
                reasoning="关键词匹配无结果，退化到默认模式"
            )
    
    async def _route_by_semantic(
        self, 
        query: str, 
        skills: List[Skill]
    ) -> RoutingResult:
        """
        语义路由（基于向量相似度）
        
        TODO: 集成 embedding 模型进行语义匹配
        当前使用关键词路由作为 fallback
        """
        # 暂时使用关键词路由
        logger.info("语义路由暂未实现，使用关键词路由")
        return await self._route_by_keywords(query, skills)
    
    async def _route_by_llm(
        self, 
        query: str, 
        skills: List[Skill]
    ) -> RoutingResult:
        """
        LLM 智能路由
        
        使用 LLM 分析查询意图，选择最合适的 Skill
        适用于复杂查询或关键词匹配不确定的情况
        """
        try:
            from app.core.llm_factory import create_llm
            
            # 构建 Skill 描述
            skill_descriptions = []
            for i, skill in enumerate(skills, 1):
                keywords_str = ", ".join(skill.keywords[:5]) if skill.keywords else "无"
                skill_descriptions.append(
                    f"{i}. {skill.name} ({skill.display_name}): {skill.description or '无描述'}\n"
                    f"   关键词: {keywords_str}"
                )
            
            prompt = f"""分析用户查询，判断应该使用哪个业务领域（Skill）来处理。

用户查询: {query}

可用的业务领域:
{chr(10).join(skill_descriptions)}

请分析查询意图，返回最匹配的领域编号（1-{len(skills)}）。
如果没有匹配的领域，返回 0。

只返回数字，不要解释。"""

            llm = create_llm(temperature=0)
            response = await llm.ainvoke(prompt)
            
            # 解析响应
            response_text = response.content.strip()
            match = re.search(r'\d+', response_text)
            
            if match:
                skill_index = int(match.group()) - 1
                if 0 <= skill_index < len(skills):
                    selected = skills[skill_index]
                    return RoutingResult(
                        has_skills=True,
                        selected_skill=SkillMatch(
                            skill_name=selected.name,
                            display_name=selected.display_name,
                            confidence=0.8,
                            match_type="llm",
                            reasoning="LLM 智能匹配"
                        ),
                        strategy_used="llm",
                        reasoning=f"LLM 分析选中 '{selected.display_name}'"
                    )
            
            # 无匹配
            return RoutingResult(
                has_skills=True,
                fallback_to_default=True,
                strategy_used="llm",
                reasoning="LLM 分析无匹配结果"
            )
            
        except Exception as e:
            logger.warning(f"LLM 路由失败: {e}，退化到关键词路由")
            return await self._route_by_keywords(query, skills)
    
    async def _route_hybrid(
        self, 
        query: str, 
        skills: List[Skill]
    ) -> RoutingResult:
        """
        混合路由策略
        
        1. 先尝试关键词快速匹配
        2. 如果置信度不够高，使用 LLM 确认
        """
        # 先尝试关键词匹配
        keyword_result = await self._route_by_keywords(query, skills)
        
        # 如果置信度足够高，直接返回
        if (keyword_result.selected_skill and 
            keyword_result.selected_skill.confidence >= 0.7):
            return keyword_result
        
        # 置信度不够，使用 LLM 确认
        logger.info("关键词匹配置信度不足，使用 LLM 确认")
        llm_result = await self._route_by_llm(query, skills)
        llm_result.strategy_used = "hybrid"
        
        return llm_result
    
    def _simplify_table_name(self, table_name: str) -> str:
        """简化表名（去除前缀和下划线）"""
        # 移除常见前缀
        prefixes = ['t_', 'tb_', 'tbl_', 'sys_', 'biz_']
        for prefix in prefixes:
            if table_name.startswith(prefix):
                table_name = table_name[len(prefix):]
                break
        
        # 将下划线替换为空格或移除
        return table_name.replace('_', '')
    
    def _simple_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度计算（基于词重叠）"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0


# 辅助函数

async def get_skill_routing_context(
    query: str,
    connection_id: int,
    strategy: RoutingStrategy = RoutingStrategy.KEYWORD
) -> Dict[str, Any]:
    """
    获取 Skill 路由上下文（供 State 使用）
    
    返回值可直接合并到 SQLMessageState
    """
    router = skill_router
    result = await router.route(query, connection_id, strategy)
    
    context = {
        "skill_mode_enabled": result.has_skills and not result.fallback_to_default,
        "selected_skill_name": result.selected_skill.skill_name if result.selected_skill else None,
        "skill_confidence": result.selected_skill.confidence if result.selected_skill else 0.0,
        "skill_routing_strategy": result.strategy_used,
        "skill_routing_reasoning": result.reasoning,
    }
    
    # 如果选中了 Skill，加载其内容
    if result.selected_skill:
        try:
            skill_content = await skill_service.load_skill(
                result.selected_skill.skill_name,
                connection_id
            )
            context["loaded_skill_content"] = skill_content.model_dump()
        except Exception as e:
            logger.warning(f"加载 Skill 内容失败: {e}")
            context["loaded_skill_content"] = None
    
    return context


async def should_use_skill_mode(connection_id: int) -> bool:
    """
    判断是否应该使用 Skill 模式
    
    零配置兼容的核心判断点
    """
    return await skill_service.has_skills_configured(connection_id)


# 全局实例
skill_router = SkillRouter()
