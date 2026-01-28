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
    
    Phase 4 优化说明:
    - 标记了部分低使用率字段为 [DEPRECATED]
    - 这些字段保留向后兼容，但新代码不应依赖
    - 未来版本可能移除
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
    
    # 前端传递的上下文信息 (包含 connectionId 等)
    context: Optional[Dict[str, Any]]
    
    # 当前处理阶段
    current_stage: Literal[
        "init",               # 初始阶段
        "planning_done",      # 规划完成
        "clarification",      # 澄清阶段
        "clarification_done", # 澄清完成
        "cache_check",        # 缓存检查阶段
        "cache_hit",          # 缓存命中阶段
        "schema_analysis",    # 模式分析阶段
        "schema_done",        # Schema 分析完成
        "sample_retrieval",   # 样本检索阶段
        "sql_generation",     # SQL 生成阶段
        "sql_generated",      # SQL 生成完成
        "sql_validation",     # SQL 验证阶段
        "sql_execution",      # SQL 执行阶段
        "execution_done",     # 执行完成
        "analysis",           # 分析阶段
        "analysis_done",      # 分析完成
        "chart_generation",   # 图表生成阶段
        "chart_done",         # 图表完成
        "recommendation_done", # 推荐完成
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
    
    # 错误恢复上下文（传递给 sql_generator 用于生成修复后的 SQL）
    error_recovery_context: Optional[Dict[str, Any]]
    
    # Agent 相关
    agent_id: Optional[int]
    agent_ids: Optional[List[int]]
    agent_messages: Dict[str, Any]
    
    # 自定义 Agent 实例（支持动态替换默认 agent）
    # 格式: {"schema_agent": agent, "sql_generator": agent, "data_analyst": agent, ...}
    custom_agents: Optional[Dict[str, Any]]
    
    # 会话相关
    thread_id: Optional[str]
    user_id: Optional[str]
    tenant_id: Optional[int]  # 多租户支持: 当前用户所属租户ID
    
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
    # Phase 4: 简化流程下部分字段可能不使用
    # ==========================================
    needs_clarification: bool
    pending_clarification: bool  # [DEPRECATED] Phase 4: 使用 clarification_confirmed 替代
    clarification_history: List[Dict[str, Any]]
    clarification_round: int  # [DEPRECATED] Phase 4: 简化流程不使用多轮澄清
    max_clarification_rounds: int  # [DEPRECATED] Phase 4: 简化流程不使用多轮澄清
    clarification_questions: List[Dict[str, Any]]
    clarification_responses: Optional[List[Dict[str, Any]]]
    clarification_confirmed: bool
    clarification_skipped: bool  # 用户是否跳过了澄清
    original_query: Optional[str]
    enriched_query: Optional[str]
    query_rewritten: bool  # P4: 查询是否经过上下文改写
    conversation_id: Optional[str]
    
    # ==========================================
    # 表过滤字段 (澄清点B)
    # [DEPRECATED] Phase 4: 简化流程不使用表过滤澄清
    # ==========================================
    filtered_tables: Optional[List[Dict[str, Any]]]  # 过滤后的表列表
    table_filter_confirmed: bool  # 表过滤是否已确认
    
    # ==========================================
    # Schema 澄清字段 (澄清点C)
    # [DEPRECATED] Phase 4: 简化流程不使用 Schema 澄清
    # ==========================================
    schema_clarification_confirmed: bool  # Schema 澄清是否已确认
    schema_clarification_round: int  # Schema 澄清轮次
    schema_clarification_history: List[Dict[str, Any]]  # Schema 澄清历史
    schema_analysis_result: Optional[Dict[str, Any]]  # Schema 分析结果
    
    # ==========================================
    # 分析与可视化字段
    # ==========================================
    analyst_insights: Optional[Dict[str, Any]]
    needs_analysis: bool
    similar_queries: Optional[List[Dict[str, Any]]]
    chart_config: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    
    # ==========================================
    # P2: 智能规划相关字段
    # ==========================================
    # 查询规划
    query_plan: Optional[Dict[str, Any]]  # 查询执行计划
    query_type: Optional[str]  # 查询类型: simple, aggregate, comparison, trend, multi_step
    
    # 多步执行
    multi_step_mode: bool  # 是否为多步执行模式
    current_sub_task_index: int  # 当前执行的子任务索引
    sub_task_results: List[Dict[str, Any]]  # 子任务结果列表
    multi_step_completed: bool  # 多步执行是否完成
    
    # 意图驱动图表
    analysis_intent: Optional[str]  # 分析意图: trend, structure, comparison, correlation
    
    # ==========================================
    # Skills-SQL-Assistant 相关字段
    # Phase 3: 默认禁用，通过 SKILL_MODE_ENABLED 控制
    # ==========================================
    # Skill 模式控制
    skill_mode_enabled: bool  # 是否启用 Skill 模式（零配置兼容）
    selected_skill_name: Optional[str]  # 选中的 Skill 名称
    skill_confidence: float  # Skill 匹配置信度 (0.0 - 1.0)
    
    # Skill 内容（按需加载）
    loaded_skill_content: Optional[Dict[str, Any]]  # 加载的 Skill 完整内容
    skill_business_rules: Optional[str]  # 业务规则（注入到 SQL 生成）
    
    # Skill 路由信息
    skill_routing_strategy: Optional[str]  # 使用的路由策略: keyword, semantic, llm, hybrid
    skill_routing_reasoning: Optional[str]  # 路由决策原因


# ============================================================================
# 状态初始化工厂函数
# ============================================================================

def create_initial_state(
    connection_id: Optional[int] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[int] = None
) -> SQLMessageState:
    """
    创建初始状态
    
    Phase 5 优化: 精简初始化字段，只初始化核心字段
    废弃字段不再初始化，使用时按需检查
    
    Args:
        connection_id: 数据库连接 ID
        thread_id: 会话线程 ID
        user_id: 用户 ID
        tenant_id: 租户 ID (多租户隔离)
        
    Returns:
        SQLMessageState: 初始化的状态对象
    """
    return SQLMessageState(
        # ==========================================
        # 核心字段（必须初始化）
        # ==========================================
        messages=[],
        remaining_steps=25,  # ReAct Agent 默认最大步数
        connection_id=connection_id,
        current_stage="init",
        
        # ==========================================
        # 流程控制字段
        # ==========================================
        retry_count=0,
        max_retries=3,
        error_history=[],
        route_decision="data_query",
        
        # ==========================================
        # 会话相关
        # ==========================================
        thread_id=thread_id,
        user_id=user_id,
        tenant_id=tenant_id,
        
        # ==========================================
        # 缓存相关（Phase 6 简化）
        # ==========================================
        cache_hit=False,
        thread_history_hit=False,
        
        # ==========================================
        # 快速模式
        # ==========================================
        fast_mode=False,
        skip_sample_retrieval=False,
        skip_chart_generation=False,
        enable_query_checker=True,
        
        # ==========================================
        # 澄清机制（Phase 4 简化后的核心字段）
        # ==========================================
        clarification_confirmed=False,
        clarification_skipped=False,
        
        # ==========================================
        # Skill 模式（Phase 3 默认禁用）
        # ==========================================
        skill_mode_enabled=False,
        
        # ==========================================
        # 智能规划（P2）
        # ==========================================
        multi_step_mode=False,
        current_sub_task_index=0,
        sub_task_results=[],
        multi_step_completed=False,
    )


# ============================================================================
# 辅助函数
# ============================================================================

def extract_connection_id(state: SQLMessageState) -> Optional[int]:
    """
    从状态中提取数据库连接 ID
    
    统一读取逻辑（优先级从高到低）：
    1. state.connection_id - 直接存储的值
    2. state.context.connectionId - 前端通过 context 传递的值
    3. message.additional_kwargs.connection_id - 消息中携带的值
    
    修复 (2026-01-23): 统一前端两种传递方式的读取逻辑
    """
    # 1. 优先使用 state 中直接存储的值
    if state.get("connection_id"):
        return state["connection_id"]
    
    # 2. 检查 context 中的 connectionId (前端通过 context 传递)
    context = state.get("context")
    if context and isinstance(context, dict):
        context_conn_id = context.get("connectionId")
        if context_conn_id:
            return context_conn_id
    
    # 3. 从消息的 additional_kwargs 中提取
    messages = state.get("messages", [])
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    return msg_connection_id
    
    return None


def extract_tenant_id(state: SQLMessageState) -> Optional[int]:
    """
    从状态中提取租户 ID
    
    统一读取逻辑（优先级从高到低）：
    1. state.tenant_id - 直接存储的值
    2. state.context.tenantId - 前端通过 context 传递的值
    
    多租户安全: 用于确保所有数据操作都在正确的租户范围内
    """
    # 1. 优先使用 state 中直接存储的值
    if state.get("tenant_id"):
        return state["tenant_id"]
    
    # 2. 检查 context 中的 tenantId (前端通过 context 传递)
    context = state.get("context")
    if context and isinstance(context, dict):
        context_tenant_id = context.get("tenantId")
        if context_tenant_id:
            return context_tenant_id
    
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


def is_skill_mode_enabled(state: SQLMessageState) -> bool:
    """
    判断是否启用了 Skill 模式
    
    零配置兼容：未配置 Skill 时返回 False
    """
    return state.get("skill_mode_enabled", False)


def get_skill_context(state: SQLMessageState) -> Dict[str, Any]:
    """
    获取 Skill 上下文信息
    
    返回当前会话的 Skill 相关信息，供 Agent 使用
    """
    return {
        "skill_mode_enabled": state.get("skill_mode_enabled", False),
        "selected_skill_name": state.get("selected_skill_name"),
        "skill_confidence": state.get("skill_confidence", 0.0),
        "skill_business_rules": state.get("skill_business_rules"),
        "loaded_skill_content": state.get("loaded_skill_content"),
    }


# ============================================================================
# Phase 5: 状态字段统计辅助函数
# ============================================================================

def get_state_field_usage() -> Dict[str, Any]:
    """
    获取状态字段使用情况统计
    
    Phase 5 优化: 用于分析哪些字段实际被使用，指导后续精简
    
    Returns:
        Dict 包含:
        - core_fields: 核心字段列表
        - deprecated_fields: 废弃字段列表
        - optional_fields: 可选字段列表
    """
    return {
        "core_fields": [
            "messages",
            "connection_id", 
            "current_stage",
            "retry_count",
            "error_history",
            "generated_sql",
            "execution_result",
            "schema_info",
        ],
        "deprecated_fields": [
            "pending_clarification",  # 使用 clarification_confirmed 替代
            "clarification_round",    # 简化流程不使用多轮澄清
            "max_clarification_rounds",
            "filtered_tables",        # 简化流程不使用表过滤澄清
            "table_filter_confirmed",
            "schema_clarification_confirmed",
            "schema_clarification_round",
            "schema_clarification_history",
            "schema_analysis_result",
        ],
        "optional_fields": [
            "fast_mode",
            "skip_sample_retrieval",
            "skip_chart_generation",
            "cache_hit",
            "thread_history_hit",
            "skill_mode_enabled",
            "multi_step_mode",
        ],
        "phase_info": {
            "phase_3": "Skill 功能默认禁用 (SKILL_MODE_ENABLED=false)",
            "phase_4": "简化流程启用 (SIMPLIFIED_FLOW_ENABLED=true)",
            "phase_5": "状态字段精简，移除废弃字段初始化",
            "phase_6": "缓存简化模式 (CACHE_MODE=simple)",
        }
    }


def get_optimization_summary() -> Dict[str, Any]:
    """
    获取优化总结
    
    Returns:
        Dict 包含各 Phase 的优化内容
    """
    return {
        "phase_1": {
            "name": "Schema 数据格式统一",
            "status": "completed",
            "changes": [
                "创建 SchemaContext Pydantic 模型",
                "添加 normalize_schema_info() 自动转换",
                "统一 schema_info 输出格式",
            ]
        },
        "phase_2": {
            "name": "SQL 生成准确性增强",
            "status": "completed", 
            "changes": [
                "添加 validate_sql_syntax() 语法检查",
                "添加 check_mysql_antipatterns() 反模式检测",
                "添加 prevalidate_sql() 整合验证",
                "验证失败时阻止执行并触发重新生成",
            ]
        },
        "phase_3": {
            "name": "Skill 功能降级为可选",
            "status": "completed",
            "changes": [
                "添加 SKILL_MODE_ENABLED 配置，默认 false",
                "query_planning_node 检查全局开关",
                "schema_agent 检查全局开关",
            ]
        },
        "phase_4": {
            "name": "架构精简",
            "status": "completed",
            "changes": [
                "添加 SIMPLIFIED_FLOW_ENABLED 配置",
                "添加 _is_clear_query() 判断查询明确性",
                "明确查询跳过澄清节点",
                "标记废弃状态字段",
            ]
        },
        "phase_5": {
            "name": "状态字段精简",
            "status": "completed",
            "changes": [
                "精简 create_initial_state() 初始化字段",
                "移除废弃字段的默认初始化",
                "添加状态字段使用统计函数",
            ]
        },
        "phase_6": {
            "name": "缓存机制简化",
            "status": "completed",
            "changes": [
                "添加 CACHE_MODE 配置 (simple/full)",
                "简化模式只使用精确缓存",
                "跳过 Milvus 语义检索，减少延迟",
            ]
        }
    }
