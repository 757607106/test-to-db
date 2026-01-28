"""
查询规划器 (Query Planner)

P2 阶段核心组件：智能规划复杂查询的执行策略。

功能：
1. 意图分解：将复杂查询分解为多个子任务
2. 查询路由：根据查询类型选择最佳处理路径
3. 执行规划：确定子任务的执行顺序和依赖关系
"""
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

class QueryType(str, Enum):
    """查询类型枚举"""
    SIMPLE = "simple"           # 简单查询：单表、单指标
    AGGREGATE = "aggregate"     # 聚合查询：统计、汇总
    COMPARISON = "comparison"   # 对比查询：同比、环比、对比
    TREND = "trend"             # 趋势查询：时间序列分析
    MULTI_STEP = "multi_step"   # 多步查询：需要多次查询
    GENERAL_CHAT = "general_chat"  # 闲聊：非数据查询


class TaskDependency(str, Enum):
    """任务依赖类型"""
    NONE = "none"               # 无依赖
    SEQUENTIAL = "sequential"   # 顺序依赖
    PARALLEL = "parallel"       # 可并行


@dataclass
class SubTask:
    """子任务定义"""
    id: str
    query: str                          # 子查询
    description: str                     # 任务描述
    dependency: TaskDependency = TaskDependency.NONE
    depends_on: List[str] = field(default_factory=list)  # 依赖的任务ID
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"             # pending, running, completed, error


@dataclass
class QueryPlan:
    """查询执行计划"""
    original_query: str                  # 原始查询
    query_type: QueryType                # 查询类型
    complexity: int                      # 复杂度 (1-5)
    sub_tasks: List[SubTask]             # 子任务列表
    execution_strategy: str              # 执行策略描述
    requires_aggregation: bool           # 是否需要结果聚合
    estimated_steps: int                 # 预估步骤数


class QueryClassification(BaseModel):
    """查询分类结果"""
    query_type: str = Field(description="查询类型：simple/aggregate/comparison/trend/multi_step/general_chat")
    complexity: int = Field(description="复杂度评分 1-5")
    needs_decomposition: bool = Field(description="是否需要分解为多步骤")
    reasoning: str = Field(description="分类理由")
    sub_queries: List[str] = Field(default_factory=list, description="分解后的子查询（如需要）")


# ============================================================================
# 查询分类器
# ============================================================================

class QueryClassifier:
    """
    查询分类器
    
    使用规则 + LLM 混合方式对查询进行分类：
    - 规则：快速过滤简单场景（闲聊、简单查询）
    - LLM：处理复杂场景的意图识别和分解
    """
    
    # 闲聊关键词
    CHAT_KEYWORDS = [
        "你好", "谢谢", "帮助", "你是谁", "介绍", "功能",
        "hello", "hi", "thanks", "help", "who are you"
    ]
    
    # 复杂查询标志词
    COMPLEX_KEYWORDS = [
        # 对比类
        "对比", "比较", "相比", "差异", "变化",
        "同比", "环比", "增长", "下降", "趋势",
        # 多步骤类
        "然后", "接着", "之后", "首先", "分别",
        "以及", "同时", "另外", "还有",
        # 条件复杂类
        "如果", "假设", "当", "满足", "排除",
    ]
    
    # 聚合关键词
    AGGREGATE_KEYWORDS = [
        "总", "总计", "合计", "统计", "汇总",
        "平均", "最大", "最小", "数量", "个数",
        "sum", "count", "avg", "max", "min"
    ]
    
    def __init__(self):
        self.llm = None
    
    def _get_llm(self):
        """延迟加载 LLM"""
        if self.llm is None:
            self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        return self.llm
    
    def classify_fast(self, query: str) -> Optional[QueryClassification]:
        """
        快速规则分类（不调用 LLM）
        
        Returns:
            分类结果，如果需要 LLM 则返回 None
        """
        query_lower = query.lower().strip()
        
        # 1. 闲聊检测
        if any(kw in query_lower for kw in self.CHAT_KEYWORDS) and len(query) < 50:
            return QueryClassification(
                query_type="general_chat",
                complexity=1,
                needs_decomposition=False,
                reasoning="检测到闲聊关键词",
                sub_queries=[]
            )
        
        # 2. 简单查询检测（短查询，无复杂关键词）
        has_complex_kw = any(kw in query_lower for kw in self.COMPLEX_KEYWORDS)
        has_aggregate_kw = any(kw in query_lower for kw in self.AGGREGATE_KEYWORDS)
        
        if len(query) < 30 and not has_complex_kw:
            query_type = "aggregate" if has_aggregate_kw else "simple"
            return QueryClassification(
                query_type=query_type,
                complexity=2 if has_aggregate_kw else 1,
                needs_decomposition=False,
                reasoning="简单查询，无复杂关键词",
                sub_queries=[]
            )
        
        # 需要 LLM 进一步分析
        return None
    
    async def classify(self, query: str) -> QueryClassification:
        """
        完整分类（规则 + LLM）
        """
        # 先尝试快速分类
        fast_result = self.classify_fast(query)
        if fast_result:
            logger.info(f"快速分类: {fast_result.query_type} (复杂度: {fast_result.complexity})")
            return fast_result
        
        # 使用 LLM 进行深度分类
        return await self._classify_with_llm(query)
    
    async def _classify_with_llm(self, query: str) -> QueryClassification:
        """使用 LLM 进行查询分类"""
        llm = self._get_llm()
        
        system_prompt = """你是一个数据查询分析专家。分析用户的查询意图并进行分类。

**查询类型**:
- simple: 简单查询（单表单指标）
- aggregate: 聚合查询（统计汇总）
- comparison: 对比查询（同比/环比/对比）
- trend: 趋势查询（时间序列）
- multi_step: 多步查询（需要多次查询才能回答）
- general_chat: 闲聊（非数据查询）

**复杂度评分** (1-5):
- 1: 直接查询，无条件
- 2: 单表带条件
- 3: 多表关联或聚合
- 4: 复杂条件或计算
- 5: 多步骤或需要业务推理

**分解规则**:
- 如果查询包含"以及"、"同时"、"对比"等词，可能需要分解
- 如果查询涉及多个不相关的指标，需要分解
- 如果查询需要先查A再用A的结果查B，需要分解

**子查询依赖关系**:
- 如果子查询包含"结果"、"上述"、"之后"等词，则依赖前一个任务
- 否则子查询可以并行执行

请返回 JSON 格式:
{
    "query_type": "类型",
    "complexity": 数字,
    "needs_decomposition": true/false,
    "reasoning": "分类理由",
    "sub_queries": ["子查询1", "子查询2"]
}

注意: sub_queries 只在 needs_decomposition 为 true 时需要填写"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"请分析以下查询:\n\n{query}")
            ]
            
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result_dict = json.loads(json_match.group())
                return QueryClassification(**result_dict)
            
            # 解析失败，返回默认分类
            logger.warning(f"LLM 分类结果解析失败: {content[:200]}")
            return QueryClassification(
                query_type="simple",
                complexity=3,
                needs_decomposition=False,
                reasoning="LLM 分类结果解析失败，使用默认值",
                sub_queries=[]
            )
            
        except Exception as e:
            logger.error(f"LLM 分类失败: {e}")
            return QueryClassification(
                query_type="simple",
                complexity=3,
                needs_decomposition=False,
                reasoning=f"LLM 调用失败: {str(e)}",
                sub_queries=[]
            )


# ============================================================================
# 查询规划器
# ============================================================================

class QueryPlanner:
    """
    查询规划器
    
    根据分类结果生成执行计划。
    """
    
    def __init__(self):
        self.classifier = QueryClassifier()
    
    async def create_plan(self, query: str) -> QueryPlan:
        """
        创建查询执行计划
        
        Args:
            query: 用户查询
            
        Returns:
            查询执行计划
        """
        # 1. 分类查询
        classification = await self.classifier.classify(query)
        logger.info(f"查询分类: {classification.query_type}, 复杂度: {classification.complexity}")
        
        # 2. 根据分类创建计划
        if classification.needs_decomposition and classification.sub_queries:
            # 多步骤查询
            return self._create_multi_step_plan(query, classification)
        else:
            # 单步查询
            return self._create_single_step_plan(query, classification)
    
    def _create_single_step_plan(
        self,
        query: str,
        classification: QueryClassification
    ) -> QueryPlan:
        """创建单步执行计划"""
        sub_task = SubTask(
            id="task_1",
            query=query,
            description="执行用户查询",
            dependency=TaskDependency.NONE,
            depends_on=[]
        )
        
        return QueryPlan(
            original_query=query,
            query_type=QueryType(classification.query_type),
            complexity=classification.complexity,
            sub_tasks=[sub_task],
            execution_strategy="单步执行：直接处理用户查询",
            requires_aggregation=False,
            estimated_steps=1
        )
    
    def _create_multi_step_plan(
        self,
        query: str,
        classification: QueryClassification
    ) -> QueryPlan:
        """创建多步执行计划"""
        sub_tasks = []
        
        for i, sub_query in enumerate(classification.sub_queries):
            # 分析依赖关系
            dependency = TaskDependency.PARALLEL
            depends_on = []
            
            # 简单规则：如果子查询包含"结果"、"上述"等词，则依赖前一个任务
            if i > 0 and any(kw in sub_query for kw in ["结果", "上述", "之后", "然后"]):
                dependency = TaskDependency.SEQUENTIAL
                depends_on = [f"task_{i}"]
            
            sub_task = SubTask(
                id=f"task_{i + 1}",
                query=sub_query,
                description=f"子任务 {i + 1}: {sub_query[:50]}...",
                dependency=dependency,
                depends_on=depends_on
            )
            sub_tasks.append(sub_task)
        
        # 添加聚合任务
        if len(sub_tasks) > 1:
            aggregation_task = SubTask(
                id="task_aggregate",
                query="汇总上述查询结果",
                description="聚合所有子任务结果",
                dependency=TaskDependency.SEQUENTIAL,
                depends_on=[t.id for t in sub_tasks]
            )
            sub_tasks.append(aggregation_task)
        
        # ✅ 保留原始查询类型（comparison/trend 等），而不是强制改为 MULTI_STEP
        # 这样可以确保对比查询和趋势查询仍然使用增强分析模式
        original_query_type = QueryType(classification.query_type)
        
        # 只有当原始类型是 simple/aggregate 时才改为 multi_step
        if original_query_type in (QueryType.SIMPLE, QueryType.AGGREGATE):
            final_query_type = QueryType.MULTI_STEP
        else:
            final_query_type = original_query_type
        
        return QueryPlan(
            original_query=query,
            query_type=final_query_type,
            complexity=classification.complexity,
            sub_tasks=sub_tasks,
            execution_strategy=f"多步执行：分解为 {len(classification.sub_queries)} 个子任务",
            requires_aggregation=len(classification.sub_queries) > 1,
            estimated_steps=len(sub_tasks)
        )


# ============================================================================
# 查询路由器
# ============================================================================

class QueryRouter:
    """
    查询路由器
    
    根据查询计划决定处理路径。
    """
    
    # 路由映射
    ROUTE_MAP = {
        QueryType.GENERAL_CHAT: "general_chat",
        QueryType.SIMPLE: "standard",
        QueryType.AGGREGATE: "standard",
        QueryType.COMPARISON: "analysis_enhanced",
        QueryType.TREND: "analysis_enhanced",
        QueryType.MULTI_STEP: "multi_step",
    }
    
    def route(self, plan: QueryPlan) -> str:
        """
        根据计划决定路由
        
        Returns:
            路由标识: general_chat, standard, analysis_enhanced, multi_step
        """
        return self.ROUTE_MAP.get(plan.query_type, "standard")
    
    def get_route_config(self, route: str) -> Dict[str, Any]:
        """
        获取路由配置
        
        Returns:
            路由配置字典
        """
        configs = {
            "general_chat": {
                "skip_sql": True,
                "skip_analysis": True,
                "skip_chart": True,
                "fast_mode": True
            },
            "standard": {
                "skip_sql": False,
                "skip_analysis": False,
                "skip_chart": False,
                "fast_mode": False
            },
            "analysis_enhanced": {
                "skip_sql": False,
                "skip_analysis": False,
                "skip_chart": False,
                "fast_mode": False,
                "enhanced_analysis": True  # 增强分析模式
            },
            "multi_step": {
                "skip_sql": False,
                "skip_analysis": False,
                "skip_chart": True,  # 多步骤默认跳过图表
                "fast_mode": False,
                "multi_step_mode": True
            }
        }
        return configs.get(route, configs["standard"])


# ============================================================================
# 创建全局实例
# ============================================================================

query_classifier = QueryClassifier()
query_planner = QueryPlanner()
query_router = QueryRouter()


# ============================================================================
# 便捷函数
# ============================================================================

async def plan_query(query: str) -> QueryPlan:
    """规划查询的便捷函数"""
    return await query_planner.create_plan(query)


async def classify_query(query: str) -> QueryClassification:
    """分类查询的便捷函数"""
    return await query_classifier.classify(query)


def route_query(plan: QueryPlan) -> str:
    """路由查询的便捷函数"""
    return query_router.route(plan)
