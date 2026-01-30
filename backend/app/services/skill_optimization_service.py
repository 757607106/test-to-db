"""
Skill 智能优化服务 (Skill Optimization Service)

基于用户查询历史分析，生成 Skill 配置优化建议。

核心功能：
1. 分析查询历史，统计关键词和表使用情况
2. 识别路由失败的查询模式
3. 生成可执行的优化建议
4. 支持管理员审批后应用

设计原则：
- 建议需管理员确认，避免误改
- 支持定期批量生成 + 手动触发
- 建议分类型，便于快速决策
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class SuggestionType(str, Enum):
    """优化建议类型"""
    ADD_KEYWORD = "add_keyword"          # 添加关键词
    ADD_TABLE = "add_table"              # 添加关联表
    CREATE_SKILL = "create_skill"        # 创建新 Skill
    MERGE_SKILLS = "merge_skills"        # 合并 Skills
    ADD_BUSINESS_RULE = "add_rule"       # 添加业务规则
    ADD_JOIN_RULE = "add_join"           # 添加 JOIN 规则


class SuggestionPriority(str, Enum):
    """建议优先级"""
    HIGH = "high"       # 高频失败，需立即处理
    MEDIUM = "medium"   # 可改进性能
    LOW = "low"         # 可选优化


@dataclass
class OptimizationSuggestion:
    """
    优化建议
    
    设计为可持久化的结构，便于管理员审批
    """
    id: str
    type: SuggestionType
    priority: SuggestionPriority
    
    # 目标 Skill（对于修改现有 Skill）
    skill_name: Optional[str] = None
    skill_id: Optional[int] = None
    
    # 建议内容
    title: str = ""
    description: str = ""
    reasoning: str = ""
    
    # 操作数据
    action_data: Dict[str, Any] = field(default_factory=dict)
    
    # 统计依据
    query_count: int = 0           # 相关查询数量
    failure_count: int = 0         # 路由失败数量
    confidence: float = 0.0        # 置信度 0.0-1.0
    
    # 示例查询
    example_queries: List[str] = field(default_factory=list)
    
    # 状态
    status: str = "pending"        # pending, approved, rejected, applied
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class QueryAnalysisResult:
    """查询分析结果"""
    total_queries: int = 0
    routed_queries: int = 0         # 成功路由
    fallback_queries: int = 0       # 退化到全库
    
    # 关键词统计
    keyword_frequency: Dict[str, int] = field(default_factory=dict)
    
    # 表使用统计
    table_usage: Dict[str, int] = field(default_factory=dict)
    
    # 未命中的查询模式
    unmatched_patterns: List[Dict[str, Any]] = field(default_factory=list)


class SkillOptimizationService:
    """
    Skill 优化服务
    
    分析查询历史，生成配置优化建议
    """
    
    # 配置
    MIN_QUERY_COUNT_FOR_SUGGESTION = 3   # 最少查询数才生成建议
    MIN_KEYWORD_FREQUENCY = 2            # 最少出现次数
    KEYWORD_PATTERN = re.compile(r'[\u4e00-\u9fa5a-zA-Z]{2,10}')
    
    def __init__(self):
        self._suggestions_cache: Dict[int, List[OptimizationSuggestion]] = {}
    
    async def analyze_and_suggest(
        self,
        connection_id: int,
        days: int = 7,
        force_refresh: bool = False
    ) -> List[OptimizationSuggestion]:
        """
        分析查询历史并生成优化建议
        
        Args:
            connection_id: 数据库连接 ID
            days: 分析最近几天的数据
            force_refresh: 是否强制刷新缓存
            
        Returns:
            优化建议列表
        """
        # 检查缓存
        if not force_refresh and connection_id in self._suggestions_cache:
            cached = self._suggestions_cache[connection_id]
            # 缓存有效期 1 小时
            if cached and (datetime.now() - cached[0].created_at).seconds < 3600:
                return cached
        
        # 1. 获取查询历史
        query_logs = await self._get_query_logs(connection_id, days)
        
        if not query_logs:
            return []
        
        # 2. 分析查询模式
        analysis = await self._analyze_queries(query_logs, connection_id)
        
        # 3. 生成建议
        suggestions = await self._generate_suggestions(analysis, connection_id)
        
        # 4. 缓存结果
        self._suggestions_cache[connection_id] = suggestions
        
        return suggestions
    
    async def _get_query_logs(
        self, 
        connection_id: int, 
        days: int
    ) -> List[Dict[str, Any]]:
        """
        获取查询日志
        
        从 query_history 表或日志中获取
        """
        try:
            from app.db.session import get_db_session
            from sqlalchemy import text
            
            since = datetime.now() - timedelta(days=days)
            
            with get_db_session() as db:
                # 尝试从 chat_history 或类似表获取
                # 如果没有专门的日志表，返回空
                result = db.execute(text("""
                    SELECT 
                        user_message as query,
                        created_at,
                        metadata
                    FROM chat_history
                    WHERE connection_id = :connection_id
                    AND created_at >= :since
                    ORDER BY created_at DESC
                    LIMIT 1000
                """), {
                    "connection_id": connection_id,
                    "since": since
                })
                
                logs = []
                for row in result:
                    logs.append({
                        "query": row.query,
                        "created_at": row.created_at,
                        "metadata": row.metadata or {}
                    })
                
                return logs
                
        except Exception as e:
            logger.warning(f"获取查询日志失败: {e}")
            return []
    
    async def _analyze_queries(
        self, 
        query_logs: List[Dict[str, Any]],
        connection_id: int
    ) -> QueryAnalysisResult:
        """分析查询模式"""
        from app.services.skill_router import skill_router, RoutingStrategy
        
        result = QueryAnalysisResult(total_queries=len(query_logs))
        keyword_counter = defaultdict(int)
        table_counter = defaultdict(int)
        unmatched = []
        
        for log in query_logs:
            query = log.get("query", "")
            metadata = log.get("metadata", {})
            
            # 提取关键词
            keywords = self.KEYWORD_PATTERN.findall(query)
            for kw in keywords:
                keyword_counter[kw.lower()] += 1
            
            # 检查是否有路由信息
            skill_used = metadata.get("skill_used")
            if skill_used:
                result.routed_queries += 1
            else:
                # 记录未命中的查询
                result.fallback_queries += 1
                unmatched.append({
                    "query": query,
                    "keywords": keywords,
                    "created_at": log.get("created_at")
                })
        
        # 过滤低频关键词
        result.keyword_frequency = {
            k: v for k, v in keyword_counter.items() 
            if v >= self.MIN_KEYWORD_FREQUENCY
        }
        
        result.unmatched_patterns = unmatched
        
        return result
    
    async def _generate_suggestions(
        self,
        analysis: QueryAnalysisResult,
        connection_id: int
    ) -> List[OptimizationSuggestion]:
        """生成优化建议"""
        from app.services.skill_service import skill_service
        
        suggestions = []
        
        # 获取现有 Skills
        existing_skills = await skill_service.get_skills_by_connection(connection_id)
        existing_keywords = set()
        for skill in existing_skills:
            for kw in (skill.keywords or []):
                existing_keywords.add(kw.lower())
        
        # 1. 分析缺失的关键词
        missing_keywords = []
        for kw, count in analysis.keyword_frequency.items():
            if kw not in existing_keywords and count >= self.MIN_KEYWORD_FREQUENCY:
                missing_keywords.append((kw, count))
        
        # 生成添加关键词建议
        if missing_keywords:
            missing_keywords.sort(key=lambda x: x[1], reverse=True)
            top_missing = missing_keywords[:5]
            
            # 尝试匹配到现有 Skill
            for kw, count in top_missing:
                best_skill = self._find_best_skill_for_keyword(kw, existing_skills)
                
                if best_skill:
                    suggestions.append(OptimizationSuggestion(
                        id=f"add_kw_{kw}_{connection_id}",
                        type=SuggestionType.ADD_KEYWORD,
                        priority=SuggestionPriority.MEDIUM,
                        skill_name=best_skill.name,
                        skill_id=best_skill.id,
                        title=f"为 [{best_skill.display_name}] 添加关键词 '{kw}'",
                        description=f"关键词 '{kw}' 在最近查询中出现 {count} 次，但未被现有 Skill 匹配。",
                        reasoning=f"建议添加到 '{best_skill.display_name}' 以提高路由命中率。",
                        action_data={"keyword": kw, "skill_id": best_skill.id},
                        query_count=count,
                        confidence=min(count / 10.0, 0.9),
                        example_queries=self._find_example_queries(kw, analysis.unmatched_patterns)
                    ))
        
        # 2. 分析是否需要创建新 Skill
        if analysis.fallback_queries > analysis.total_queries * 0.3:
            # 超过 30% 的查询无法路由
            # 聚类未匹配查询，建议创建新 Skill
            clusters = self._cluster_unmatched_queries(analysis.unmatched_patterns)
            
            for cluster_name, queries in clusters.items():
                if len(queries) >= self.MIN_QUERY_COUNT_FOR_SUGGESTION:
                    suggestions.append(OptimizationSuggestion(
                        id=f"create_skill_{cluster_name}_{connection_id}",
                        type=SuggestionType.CREATE_SKILL,
                        priority=SuggestionPriority.HIGH,
                        title=f"建议创建新 Skill: {cluster_name}",
                        description=f"发现 {len(queries)} 个相关查询无法被现有 Skill 匹配。",
                        reasoning="这些查询具有相似的关键词模式，建议创建专门的 Skill。",
                        action_data={
                            "suggested_name": cluster_name,
                            "suggested_keywords": list(set(q.get("keywords", [])[:3] for q in queries)),
                        },
                        query_count=len(queries),
                        failure_count=len(queries),
                        confidence=0.7,
                        example_queries=[q.get("query", "") for q in queries[:3]]
                    ))
        
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: (priority_order.get(x.priority.value, 99), -x.query_count))
        
        return suggestions
    
    def _find_best_skill_for_keyword(self, keyword: str, skills) -> Optional[Any]:
        """为关键词找到最匹配的 Skill"""
        best_score = 0
        best_skill = None
        
        for skill in skills:
            score = 0
            # 检查表名相似度
            for table in (skill.table_names or []):
                if keyword in table.lower():
                    score += 2
            # 检查描述相似度
            if skill.description and keyword in skill.description.lower():
                score += 1
            # 检查显示名
            if skill.display_name and keyword in skill.display_name.lower():
                score += 1
                
            if score > best_score:
                best_score = score
                best_skill = skill
        
        return best_skill if best_score > 0 else (skills[0] if skills else None)
    
    def _find_example_queries(
        self, 
        keyword: str, 
        unmatched: List[Dict]
    ) -> List[str]:
        """找到包含关键词的示例查询"""
        examples = []
        for item in unmatched:
            if keyword in item.get("query", "").lower():
                examples.append(item["query"])
                if len(examples) >= 3:
                    break
        return examples
    
    def _cluster_unmatched_queries(
        self, 
        unmatched: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        聚类未匹配的查询
        
        简单实现：基于共同关键词分组
        """
        clusters = defaultdict(list)
        
        for item in unmatched:
            keywords = item.get("keywords", [])
            if keywords:
                # 使用最常见关键词作为聚类名
                primary_kw = keywords[0].lower() if keywords else "other"
                clusters[primary_kw].append(item)
        
        return dict(clusters)
    
    async def apply_suggestion(
        self,
        suggestion_id: str,
        connection_id: int,
        approved_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        应用优化建议
        
        Args:
            suggestion_id: 建议 ID
            connection_id: 连接 ID
            approved_by: 审批人 ID
            
        Returns:
            应用结果
        """
        from app.services.skill_service import skill_service
        
        # 查找建议
        suggestions = self._suggestions_cache.get(connection_id, [])
        suggestion = next((s for s in suggestions if s.id == suggestion_id), None)
        
        if not suggestion:
            return {"success": False, "error": "建议不存在或已过期"}
        
        try:
            if suggestion.type == SuggestionType.ADD_KEYWORD:
                # 添加关键词
                skill_id = suggestion.action_data.get("skill_id")
                keyword = suggestion.action_data.get("keyword")
                
                await skill_service.add_keyword(skill_id, keyword)
                suggestion.status = "applied"
                
                return {
                    "success": True,
                    "message": f"已为 Skill 添加关键词 '{keyword}'"
                }
                
            elif suggestion.type == SuggestionType.CREATE_SKILL:
                # 创建新 Skill 需要更多信息，返回预填数据
                return {
                    "success": True,
                    "action": "create_skill_form",
                    "prefill_data": suggestion.action_data,
                    "message": "请在管理界面创建新 Skill"
                }
                
            else:
                return {
                    "success": False,
                    "error": f"暂不支持自动应用类型: {suggestion.type}"
                }
                
        except Exception as e:
            logger.error(f"应用建议失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_optimization_summary(
        self,
        connection_id: int
    ) -> Dict[str, Any]:
        """
        获取优化摘要
        
        用于管理后台展示
        """
        suggestions = await self.analyze_and_suggest(connection_id)
        
        summary = {
            "total_suggestions": len(suggestions),
            "by_priority": {
                "high": len([s for s in suggestions if s.priority == SuggestionPriority.HIGH]),
                "medium": len([s for s in suggestions if s.priority == SuggestionPriority.MEDIUM]),
                "low": len([s for s in suggestions if s.priority == SuggestionPriority.LOW]),
            },
            "by_type": {},
            "top_suggestions": []
        }
        
        # 按类型统计
        for s in suggestions:
            t = s.type.value
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
        
        # 前5个建议
        for s in suggestions[:5]:
            summary["top_suggestions"].append({
                "id": s.id,
                "type": s.type.value,
                "priority": s.priority.value,
                "title": s.title,
                "query_count": s.query_count,
            })
        
        return summary


# 全局实例
skill_optimization_service = SkillOptimizationService()
