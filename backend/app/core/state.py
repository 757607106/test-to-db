"""
LangGraph 状态管理模块 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 TypedDict 定义状态
2. 使用 Annotated + add_messages reducer 管理消息历史
3. 状态字段分层：核心字段 + 扩展字段
4. 使用 dataclass 定义结构化数据

官方文档参考:
- https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
- https://langchain-ai.github.io/langgraph/reference/graphs/#add_messages
"""
from typing import Dict, Any, List, Optional, Literal, Annotated, Sequence
from dataclasses import dataclass, field
from typing_extensions import TypedDict
import re

from langchain_core.messages import BaseMessage, AnyMessage
from langgraph.graph.message import add_messages


# ============================================================================
# 结构化数据类型 (使用 dataclass)
# ============================================================================

@dataclass
class SQLExecutionResult:
    """SQL执行结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    rows_affected: Optional[int] = None


@dataclass
class SchemaInfo:
    """数据库模式信息"""
    tables: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    value_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class SQLValidationResult:
    """SQL验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# ============================================================================
# 核心状态定义 (遵循 LangGraph 官方模式)
# ============================================================================

class SQLMessageState(TypedDict, total=False):
    """
    SQL 消息状态 - LangGraph 官方推荐模式
    
    使用 add_messages reducer 自动管理消息历史，包括:
    - 追加新消息
    - 基于 ID 更新现有消息
    - 正确处理 ToolCall/ToolMessage 配对
    
    状态分层:
    1. 核心字段 (必需): messages, connection_id, current_stage
    2. 查询处理字段: schema_info, generated_sql, execution_result
    3. 流程控制字段: retry_count, error_history, route_decision
    4. 缓存相关字段: cache_hit, cache_hit_type
    5. 快速模式字段: fast_mode, skip_*
    6. 澄清机制字段: needs_clarification, clarification_*
    """
    
    # ==========================================
    # 核心字段 (使用 add_messages reducer)
    # ==========================================
    messages: Annotated[Sequence[AnyMessage], add_messages]
    
    # ReAct Agent 必需字段 - 控制代理最大执行步数
    # 参考: https://langchain-ai.github.io/langgraph/reference/agents/#create_react_agent
    remaining_steps: int
    
    # 数据库连接 ID (由用户选择的数据库动态传入)
    connection_id: Optional[int]
    
    # 当前处理阶段
    current_stage: Literal[
        "clarification",      # 澄清阶段
        "cache_check",        # 缓存检查阶段
        "cache_hit",          # 缓存命中阶段
        "schema_analysis",    # 模式分析阶段
        "sample_retrieval",   # 样本检索阶段
        "sql_generation",     # SQL 生成阶段
        "sql_validation",     # SQL 验证阶段
        "sql_execution",      # SQL 执行阶段
        "analysis",           # 分析阶段
        "chart_generation",   # 图表生成阶段
        "error_recovery",     # 错误恢复阶段
        "completed"           # 完成阶段
    ]
    
    # ==========================================
    # 查询处理字段
    # ==========================================
    query_analysis: Optional[Dict[str, Any]]
    schema_info: Optional[SchemaInfo]
    generated_sql: Optional[str]
    validation_result: Optional[SQLValidationResult]
    execution_result: Optional[SQLExecutionResult]
    sample_retrieval_result: Optional[Dict[str, Any]]
    
    # ==========================================
    # 流程控制字段
    # ==========================================
    retry_count: int
    max_retries: int
    error_history: List[Dict[str, Any]]
    route_decision: Literal["general_chat", "data_query"]
    
    # Agent 相关
    agent_id: Optional[int]
    agent_ids: Optional[List[int]]
    agent_messages: Dict[str, Any]
    
    # 会话相关
    thread_id: Optional[str]
    user_id: Optional[str]
    
    # ==========================================
    # 缓存相关字段
    # ==========================================
    cache_hit: bool
    cache_hit_type: Optional[Literal["exact", "semantic", "exact_text", "thread_history"]]
    
    # Thread 历史缓存 (同一对话内相同问题)
    thread_history_hit: bool
    
    # 缓存的 SQL 模板 (语义命中时保存，供澄清后重新生成使用)
    cached_sql_template: Optional[str]
    
    # 语义缓存命中详情
    cache_similarity: Optional[float]  # 语义相似度
    cache_matched_query: Optional[str]  # 匹配的原始查询
    
    # ==========================================
    # 快速模式字段 (借鉴官方简洁性思想)
    # ==========================================
    fast_mode: bool
    skip_sample_retrieval: bool
    skip_chart_generation: bool
    enable_query_checker: bool
    sql_check_passed: bool
    
    # ==========================================
    # 澄清机制字段
    # ==========================================
    needs_clarification: bool
    pending_clarification: bool
    clarification_history: List[Dict[str, Any]]
    clarification_round: int
    max_clarification_rounds: int
    clarification_questions: List[Dict[str, Any]]
    clarification_responses: Optional[List[Dict[str, Any]]]
    clarification_confirmed: bool
    original_query: Optional[str]
    enriched_query: Optional[str]
    conversation_id: Optional[str]
    
    # ==========================================
    # 分析与可视化字段
    # ==========================================
    analyst_insights: Optional[Dict[str, Any]]
    needs_analysis: bool
    similar_queries: Optional[List[Dict[str, Any]]]
    chart_config: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]


# ============================================================================
# 状态初始化工厂函数
# ============================================================================

def create_initial_state(
    connection_id: Optional[int] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> SQLMessageState:
    """
    创建初始状态
    
    Args:
        connection_id: 数据库连接 ID
        thread_id: 会话线程 ID
        user_id: 用户 ID
        
    Returns:
        SQLMessageState: 初始化的状态对象
    """
    return SQLMessageState(
        messages=[],
        remaining_steps=25,  # ReAct Agent 默认最大步数
        connection_id=connection_id,
        current_stage="schema_analysis",
        retry_count=0,
        max_retries=3,
        error_history=[],
        route_decision="data_query",
        agent_messages={},
        thread_id=thread_id,
        user_id=user_id,
        cache_hit=False,
        fast_mode=False,
        skip_sample_retrieval=False,
        skip_chart_generation=False,
        enable_query_checker=True,
        sql_check_passed=False,
        needs_clarification=False,
        pending_clarification=False,
        clarification_history=[],
        clarification_round=0,
        max_clarification_rounds=2,
        clarification_questions=[],
        clarification_confirmed=False,
        needs_analysis=False,
    )


# ============================================================================
# 辅助函数
# ============================================================================

def extract_connection_id(state: SQLMessageState) -> Optional[int]:
    """
    从状态中提取数据库连接 ID
    
    优先从 state 直接获取，如果没有则从消息中提取
    """
    # 优先使用 state 中的值
    if state.get("connection_id"):
        return state["connection_id"]
    
    # 从消息中提取
    messages = state.get("messages", [])
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    return msg_connection_id
    
    return None


def extract_user_query(state: SQLMessageState) -> Optional[str]:
    """
    从状态中提取用户查询
    """
    messages = state.get("messages", [])
    for message in messages:
        if hasattr(message, 'type') and message.type == 'human':
            content = message.content
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            return content
    return None


def detect_fast_mode(query: str) -> Dict[str, Any]:
    """
    检测查询是否适合快速模式
    
    借鉴官方 LangGraph SQL Agent 的简洁性思想：
    - 简单查询使用快速模式，跳过样本检索和图表生成
    - 复杂查询使用完整模式，包含所有功能
    
    Args:
        query: 用户查询字符串
        
    Returns:
        Dict 包含:
        - fast_mode: 是否启用快速模式
        - skip_sample_retrieval: 是否跳过样本检索
        - skip_chart_generation: 是否跳过图表生成
        - enable_query_checker: 是否启用 SQL 检查
        - reason: 决策原因
    """
    from app.core.config import settings
    
    # 默认结果：完整模式
    result = {
        "fast_mode": False,
        "skip_sample_retrieval": False,
        "skip_chart_generation": False,
        "enable_query_checker": True,
        "reason": ""
    }
    
    # 检查是否启用自动检测
    if not settings.FAST_MODE_AUTO_DETECT:
        result["reason"] = "快速模式自动检测已禁用"
        return result
    
    query_lower = query.lower().strip()
    
    # 检查禁用关键词（需要可视化或分析）
    disable_keywords = [kw.strip().lower() for kw in settings.FAST_MODE_DISABLE_KEYWORDS.split(',')]
    for keyword in disable_keywords:
        if keyword and keyword in query_lower:
            result["reason"] = f"查询包含关键词 '{keyword}'，使用完整模式"
            return result
    
    # 检查查询复杂度
    is_simple = True
    reasons = []
    
    # 1. 查询长度检查
    if len(query) > settings.FAST_MODE_QUERY_LENGTH_THRESHOLD:
        is_simple = False
        reasons.append(f"查询长度({len(query)}) > 阈值({settings.FAST_MODE_QUERY_LENGTH_THRESHOLD})")
    
    # 2. 检查是否包含复杂查询指示词
    complex_indicators = [
        r'\b(join|left join|right join|inner join|outer join)\b',
        r'\b(group by|having|union|intersect|except)\b',
        r'\b(subquery|子查询|嵌套)\b',
        r'\b(window|over|partition)\b',
        r'最近.*(\d+).*(天|周|月|年)',
        r'(排名|前\d+|大于|小于|介于)',
    ]
    
    for pattern in complex_indicators:
        if re.search(pattern, query_lower, re.IGNORECASE):
            is_simple = False
            reasons.append(f"包含复杂查询模式: {pattern[:20]}...")
            break
    
    # 3. 检查是否是简单查询模式
    simple_patterns = [
        r'^(查询|获取|显示|列出|统计|计算).{0,20}(数量|总数|有多少)',
        r'^(查询|获取|显示|列出).{0,30}(信息|数据|记录)$',
        r'^.{0,20}(是什么|是哪个|有哪些)\??$',
    ]
    
    for pattern in simple_patterns:
        if re.match(pattern, query_lower):
            is_simple = True
            reasons = ["匹配简单查询模式"]
            break
    
    # 决定是否使用快速模式
    if is_simple:
        result["fast_mode"] = True
        result["skip_sample_retrieval"] = settings.FAST_MODE_SKIP_SAMPLE_RETRIEVAL
        result["skip_chart_generation"] = settings.FAST_MODE_SKIP_CHART_GENERATION
        result["enable_query_checker"] = settings.FAST_MODE_ENABLE_QUERY_CHECKER
        result["reason"] = f"简单查询，启用快速模式: {', '.join(reasons) if reasons else '查询简短明确'}"
    else:
        result["reason"] = f"复杂查询，使用完整模式: {', '.join(reasons)}"
    
    return result


def apply_fast_mode_to_state(state: SQLMessageState, query: str) -> SQLMessageState:
    """
    将快速模式检测结果应用到状态
    
    Args:
        state: 当前状态
        query: 用户查询
        
    Returns:
        更新后的状态
    """
    detection = detect_fast_mode(query)
    
    state["fast_mode"] = detection["fast_mode"]
    state["skip_sample_retrieval"] = detection["skip_sample_retrieval"]
    state["skip_chart_generation"] = detection["skip_chart_generation"]
    state["enable_query_checker"] = detection["enable_query_checker"]
    
    return state


# ============================================================================
# 状态更新辅助函数
# ============================================================================

def update_stage(state: SQLMessageState, stage: str) -> Dict[str, Any]:
    """
    更新当前阶段（返回状态更新字典）
    
    这是 LangGraph 推荐的状态更新方式：
    节点返回 dict，由图自动合并到状态
    """
    return {"current_stage": stage}


def add_error_to_history(
    state: SQLMessageState, 
    stage: str, 
    error: str, 
    sql_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    添加错误到历史记录（返回状态更新字典）
    """
    error_info = {
        "stage": stage,
        "error": error,
        "sql_query": sql_query,
        "retry_count": state.get("retry_count", 0)
    }
    
    current_history = state.get("error_history", [])
    return {
        "error_history": current_history + [error_info],
        "current_stage": "error_recovery"
    }
