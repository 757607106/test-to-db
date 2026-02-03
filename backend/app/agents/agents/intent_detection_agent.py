"""
意图识别 Agent (Intent Detection Agent)

基于 LangGraph ReAct Agent 模式实现的意图识别代理。

功能：
1. 查询分类：识别查询类型（简单/聚合/对比/趋势/多步/闲聊/Dashboard）
2. 复杂度评估：评估查询复杂度 (1-5)
3. 路由决策：决定后续处理路径

查询类型：
- simple: 简单查询（单表单指标）
- aggregate: 聚合查询（统计汇总）
- comparison: 对比查询（同比/环比/对比）
- trend: 趋势查询（时间序列）
- multi_step: 多步查询（需要多次查询才能回答）
- general_chat: 闲聊（非数据查询）
- dashboard_insight: Dashboard 洞察分析
"""
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import re

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR, CORE_AGENT_ROUTER
from app.core.llm_wrapper import LLMWrapper
from app.core.state import SQLMessageState

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

class QueryType(str, Enum):
    """查询类型枚举"""
    SIMPLE = "simple"               # 简单查询：单表、单指标
    AGGREGATE = "aggregate"         # 聚合查询：统计、汇总
    COMPARISON = "comparison"       # 对比查询：同比、环比、对比
    TREND = "trend"                 # 趋势查询：时间序列分析
    MULTI_STEP = "multi_step"       # 多步查询：需要多次查询
    GENERAL_CHAT = "general_chat"   # 闲聊：非数据查询
    DASHBOARD_INSIGHT = "dashboard_insight"  # Dashboard 洞察分析


@dataclass
class IntentResult:
    """意图识别结果
    
    注意：needs_clarification 已移除，澄清判断应在 Schema Agent 之后基于实际数据结构进行
    """
    query_type: QueryType
    complexity: int                     # 复杂度 1-5
    route: str                          # 路由: sql_supervisor, dashboard_insight, general_chat
    reasoning: str                      # 判断理由
    sub_queries: List[str] = field(default_factory=list)  # 分解后的子查询


# ============================================================================
# 规则判断（快速路径）
# ============================================================================

# 闲聊关键词
CHAT_KEYWORDS = [
    "你好", "谢谢", "帮助", "你是谁", "介绍", "功能",
    "hello", "hi", "thanks", "help", "who are you"
]

# Dashboard 关键词
DASHBOARD_KEYWORDS = [
    "dashboard", "仪表盘", "看板", "洞察", "insight",
    "自动分析", "数据概览", "业务概览"
]

# 复杂查询标志词
COMPLEX_KEYWORDS = [
    # 对比类
    "对比", "比较", "相比", "差异", "变化",
    "同比", "环比", "增长", "下降", "趋势",
    # 多步骤类
    "然后", "接着", "之后", "首先", "分别",
    "以及", "同时", "另外", "还有",
]

# 聚合关键词
AGGREGATE_KEYWORDS = [
    "总", "总计", "合计", "统计", "汇总",
    "平均", "最大", "最小", "数量", "个数",
    "sum", "count", "avg", "max", "min"
]


def quick_intent_check(query: str) -> Optional[IntentResult]:
    """
    极简规则检测（只保留绝对确定的闲聊，移除长度判断）
    """
    query_lower = query.lower().strip()
    
    # 只保留显而易见的闲聊，其他的全部交给 LLM
    if any(query_lower == kw for kw in ["你好", "hello", "hi", "help", "帮助"]):
        return IntentResult(
            query_type=QueryType.GENERAL_CHAT,
            complexity=1,
            route="general_chat",
            reasoning="完全匹配简单招呼语"
        )
    
    # 移除之前的 query_len < 30 判断，那被认为是伪智能
    return None


# ============================================================================
# LLM 意图识别
# ============================================================================

INTENT_DETECTION_PROMPT = """你是一个数据查询意图分析专家。分析用户的查询意图并进行分类。

**查询类型**:
- simple: 简单查询（单表单指标）
- aggregate: 聚合查询（统计汇总）
- comparison: 对比查询（同比/环比/对比）
- trend: 趋势查询（时间序列）
- multi_step: 多步查询（需要多次查询才能回答）
- general_chat: 闲聊（非数据查询）
- dashboard_insight: Dashboard 洞察分析（自动发现数据趋势和异常）

**路由决策**:
- sql_supervisor: 需要生成 SQL 的数据查询
- dashboard_insight: Dashboard 洞察分析
- general_chat: 闲聊或帮助类问题

**复杂度评分** (1-5):
- 1: 直接查询，无条件
- 2: 单表带条件
- 3: 多表关联或聚合
- 4: 复杂条件或计算
- 5: 多步骤或需要业务推理

**分解规则**:
- 如果查询包含"以及"、"同时"、"对比"等词，可能需要分解
- 如果查询涉及多个不相关的指标，需要分解

**重要：不要判断是否需要澄清**，澄清判断应在获取数据库 Schema 之后基于实际数据结构进行。

请返回 JSON 格式:
{{
    "query_type": "类型",
    "complexity": 数字,
    "route": "sql_supervisor|dashboard_insight|general_chat",
    "reasoning": "分类理由",
    "sub_queries": ["子查询1", "子查询2"]
}}

注意: sub_queries 只在 needs_decomposition 时需要填写，否则为空数组。
只返回JSON，不要其他内容。"""


async def detect_intent_with_llm(query: str) -> IntentResult:
    """使用 LLM 进行深度意图识别（结构化输出版）"""
    try:
        from pydantic import BaseModel, Field
        
        class IntentResponse(BaseModel):
            query_type: str = Field(description="simple, aggregate, comparison, trend, multi_step, general_chat, dashboard_insight")
            complexity: int = Field(description="1-5")
            route: str = Field(description="sql_supervisor, dashboard_insight, general_chat")
            reasoning: str = Field(description="理由")
            sub_queries: List[str] = Field(default_factory=list, description="如果是多步查询，分解后的子查询")

        # 使用 LLMWrapper 统一处理重试和超时
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        
        # 尝试使用结构化输出（如果模型支持）
        try:
            structured_llm = llm.llm.with_structured_output(IntentResponse)
            result = await structured_llm.ainvoke([
                SystemMessage(content="你是一个数据查询意图分析专家。请分析用户的查询意图。"),
                HumanMessage(content=query)
            ])
            return IntentResult(
                query_type=QueryType(result.query_type),
                complexity=result.complexity,
                route=result.route,
                reasoning=result.reasoning,
                sub_queries=result.sub_queries
            )
        except Exception:
            # 降级到 JSON 解析模式
            messages = [
                SystemMessage(content=INTENT_DETECTION_PROMPT),
                HumanMessage(content=f"请分析以下查询:\n\n{query}")
            ]
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            # ... (保留原有的 JSON 提取逻辑作为降级)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result_dict = json.loads(json_match.group())
                return IntentResult(
                    query_type=QueryType(result_dict.get("query_type", "simple")),
                    complexity=result_dict.get("complexity", 3),
                    route=result_dict.get("route", "sql_supervisor"),
                    reasoning=result_dict.get("reasoning", "LLM 分析"),
                    sub_queries=result_dict.get("sub_queries", [])
                )
            raise
        
    except Exception as e:
        logger.error(f"LLM 意图识别失败: {e}")
        return IntentResult(
            query_type=QueryType.SIMPLE,
            complexity=3,
            route="sql_supervisor",
            reasoning=f"LLM 调用失败: {str(e)}"
        )


# ============================================================================
# Agent 工具定义
# ============================================================================

@tool
async def detect_query_intent(query: str) -> str:
    """
    检测用户查询的意图类型。
    
    分析用户查询，识别其类型（简单/聚合/对比/趋势/多步/闲聊/Dashboard），
    评估复杂度，并决定后续处理路径。
    
    Args:
        query: 用户的自然语言查询
        
    Returns:
        JSON 格式的意图识别结果
    """
    # 先尝试快速检测
    quick_result = quick_intent_check(query)
    if quick_result:
        logger.info(f"快速意图检测: {quick_result.query_type.value} -> {quick_result.route}")
        return json.dumps({
            "query_type": quick_result.query_type.value,
            "complexity": quick_result.complexity,
            "route": quick_result.route,
            "reasoning": quick_result.reasoning,
            "sub_queries": quick_result.sub_queries
        }, ensure_ascii=False)
    
    # 使用 LLM 深度分析
    result = await detect_intent_with_llm(query)
    logger.info(f"LLM 意图检测: {result.query_type.value} -> {result.route}")
    
    return json.dumps({
        "query_type": result.query_type.value,
        "complexity": result.complexity,
        "route": result.route,
        "reasoning": result.reasoning,
        "sub_queries": result.sub_queries
    }, ensure_ascii=False)


# ============================================================================
# Agent 创建
# ============================================================================

class IntentDetectionAgent:
    """意图识别代理"""
    
    def __init__(self):
        # 获取原生 LLM（create_react_agent 需要原生 LLM）
        self._raw_llm = get_agent_llm(CORE_AGENT_ROUTER)
        self.tools = [detect_query_intent]
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """创建 ReAct Agent"""
        system_prompt = """你是一个专业的查询意图分析助手。
        
你的任务是：
1. 分析用户查询的意图类型
2. 评估查询复杂度
3. 决定最佳的处理路由

使用 detect_query_intent 工具来分析用户查询。"""
        
        return create_react_agent(
            model=self._raw_llm,
            tools=self.tools,
            prompt=system_prompt,
            name="intent_detection_agent",
            state_schema=SQLMessageState,  # 使用自定义 state_schema 以支持 connection_id 等字段
        )
    
    async def detect(self, query: str) -> IntentResult:
        """检测查询意图"""
        # 先尝试快速检测
        quick_result = quick_intent_check(query)
        if quick_result:
            return quick_result
        
        # 使用 LLM 深度分析
        return await detect_intent_with_llm(query)


# ============================================================================
# 便捷函数
# ============================================================================

# 全局实例
_intent_agent = None

def get_intent_agent() -> IntentDetectionAgent:
    """获取全局意图识别代理"""
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentDetectionAgent()
    return _intent_agent


async def detect_intent(query: str) -> IntentResult:
    """检测查询意图的便捷函数"""
    agent = get_intent_agent()
    return await agent.detect(query)


def detect_intent_fast(query: str) -> Optional[IntentResult]:
    """快速检测意图（规则，不调用 LLM）"""
    return quick_intent_check(query)


# 创建全局 agent 实例
intent_detection_agent = IntentDetectionAgent()

__all__ = [
    "IntentDetectionAgent",
    "IntentResult",
    "QueryType",
    "detect_intent",
    "detect_intent_fast",
    "intent_detection_agent",
]
