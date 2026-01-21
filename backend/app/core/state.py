from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from langgraph.graph.message import MessagesState
from langgraph.prebuilt.chat_agent_executor import AgentState
import re

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

class SQLMessageState(AgentState):
    # 增强的SQL消息状态，支持多代理协作
    # 数据库连接信息
    connection_id: Optional[int] = None  # 由用户选择的数据库动态传入，不硬编码默认值
    # 智能体ID
    agent_id: Optional[int] = None
    agent_ids: Optional[List[int]] = None
    
    # 查询分析结果
    query_analysis: Optional[Dict[str, Any]] = None

    # 模式信息
    schema_info: Optional[SchemaInfo] = None

    # 生成的SQL
    generated_sql: Optional[str] = None

    # SQL验证结果
    validation_result: Optional[SQLValidationResult] = None

    # 执行结果
    execution_result: Optional[SQLExecutionResult] = None

    # 样本检索结果
    sample_retrieval_result: Optional[Dict[str, Any]] = None

    # 错误重试计数
    retry_count: int = 0
    max_retries: int = 3

    # 当前处理阶段
    current_stage: Literal[
        "clarification",        # 新增：澄清阶段
        "cache_check",          # 新增：缓存检查阶段
        "cache_hit",            # 新增：缓存命中阶段
        "schema_analysis",
        "sample_retrieval",
        "sql_generation",
        "sql_validation",
        "sql_execution",
        "analysis",            # 新增：分析阶段
        "chart_generation",
        "error_recovery",
        "completed"
    ] = "schema_analysis"

    # 代理间通信
    agent_messages: Dict[str, Any] = field(default_factory=dict)

    # 错误历史
    error_history: List[Dict[str, Any]] = field(default_factory=list)

    # 澄清机制相关字段
    clarification_history: List[Dict[str, Any]] = field(default_factory=list)
    clarification_round: int = 0
    max_clarification_rounds: int = 2
    needs_clarification: bool = False
    pending_clarification: bool = False  # 标记是否等待用户澄清回复
    clarification_questions: List[Dict[str, Any]] = field(default_factory=list)
    clarification_responses: Optional[List[Dict[str, Any]]] = None
    clarification_confirmed: bool = False
    conversation_id: Optional[str] = None
    original_query: Optional[str] = None
    enriched_query: Optional[str] = None

    # 分析师相关字段
    analyst_insights: Optional[Dict[str, Any]] = None
    needs_analysis: bool = False

    # 相似问题
    similar_queries: Optional[List[Dict[str, Any]]] = None

    # 路由决策
    route_decision: Literal["general_chat", "data_query"] = "data_query"

    # 图表配置
    chart_config: Optional[Dict[str, Any]] = None
    
    # 分析结果
    analysis_result: Optional[Dict[str, Any]] = None
    
    # 会话线程ID
    thread_id: Optional[str] = None
    
    # 用户ID
    user_id: Optional[str] = None
    
    # 缓存相关字段
    cache_hit: bool = False
    cache_hit_type: Optional[Literal["exact", "semantic", "exact_text"]] = None

    # ==========================================
    # 快速模式相关字段 (Fast Mode)
    # ==========================================
    # 借鉴官方 LangGraph SQL Agent 的简洁性思想
    # 对于简单查询，跳过样本检索、图表生成等步骤，提升响应速度
    # ==========================================
    fast_mode: bool = False  # 是否启用快速模式
    skip_sample_retrieval: bool = False  # 是否跳过样本检索
    skip_chart_generation: bool = False  # 是否跳过图表生成
    enable_query_checker: bool = True  # 是否启用 SQL Query Checker
    sql_check_passed: bool = False  # SQL 检查是否通过


def extract_connection_id(state: SQLMessageState) -> int:
    """从状态中提取数据库连接ID"""
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
    connection_id = None  # 默认值
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    print(f"从消息中提取到连接ID: {connection_id}")
                    break
    state['connection_id'] = connection_id
    return connection_id


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
        # 长查询可能复杂，但不一定
        is_simple = False
        reasons.append(f"查询长度({len(query)}) > 阈值({settings.FAST_MODE_QUERY_LENGTH_THRESHOLD})")
    
    # 2. 检查是否包含复杂查询指示词
    complex_indicators = [
        r'\b(join|left join|right join|inner join|outer join)\b',  # 连接查询
        r'\b(group by|having|union|intersect|except)\b',  # 分组/集合操作
        r'\b(subquery|子查询|嵌套)\b',  # 子查询
        r'\b(window|over|partition)\b',  # 窗口函数
        r'最近.*(\d+).*(天|周|月|年)',  # 时间范围查询
        r'(排名|前\d+|大于|小于|介于)',  # 排名/过滤查询
    ]
    
    for pattern in complex_indicators:
        if re.search(pattern, query_lower, re.IGNORECASE):
            is_simple = False
            reasons.append(f"包含复杂查询模式: {pattern[:20]}...")
            break
    
    # 3. 检查是否是简单查询模式
    simple_patterns = [
        r'^(查询|获取|显示|列出|统计|计算).{0,20}(数量|总数|有多少)',  # 简单计数
        r'^(查询|获取|显示|列出).{0,30}(信息|数据|记录)$',  # 简单查询
        r'^.{0,20}(是什么|是哪个|有哪些)\??$',  # 简单疑问
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
