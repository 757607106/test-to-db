from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from langgraph.graph.message import MessagesState
from langgraph.prebuilt.chat_agent_executor import AgentState


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
    """增强的SQL消息状态，支持多代理协作"""
    # 数据库连接信息（必须由前端传入，不设默认值）
    connection_id: Optional[int] = None
    
    # 数据库类型（mysql/postgresql/sqlite/sqlserver/oracle）
    db_type: str = "mysql"

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
    
    # 查询结果数据（原始数据记录）
    query_results: Optional[List[Dict[str, Any]]] = None

    # 样本检索结果
    sample_retrieval_result: Optional[Dict[str, Any]] = None

    # 错误重试计数
    retry_count: int = 0
    max_retries: int = 3

    # ===== 状态可视化相关字段 =====
    # 当前 Agent 的思考过程 (Thought)
    thought: Optional[str] = None
    
    # 下一步计划 (Plan)
    next_plan: Optional[str] = None
    
    # 已完成的步骤详细信息 (用于时间线展示)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    # 当前处理阶段
    current_stage: Literal[
        "schema_analysis",
        "sample_retrieval",
        "sql_generation",
        "sql_validation",
        "sql_execution",
        "error_recovery",
        "completed"
    ] = "schema_analysis"

    # 代理间通信
    agent_messages: Dict[str, Any] = field(default_factory=dict)

    # 错误历史
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # ===== 防护机制相关字段 =====
    # Supervisor 调用轮次计数
    supervisor_turn_count: int = 0
    
    # 上一个调用的 Agent
    last_agent_called: Optional[str] = None
    
    # Agent 调用历史（用于循环检测）
    agent_call_history: List[str] = field(default_factory=list)
    
    # 已完成的阶段列表
    completed_stages: List[str] = field(default_factory=list)
    
    # ===== 澄清上下文 =====
    # 用于在 SQL 错误等场景下触发澄清
    clarification_context: Optional[Dict[str, Any]] = None
    
    # 增强后的查询（整合了澄清信息）
    enriched_query: Optional[str] = None

def extract_connection_id(state: SQLMessageState) -> int:
    """从状态中提取数据库连接ID
    
    提取优先级：
    1. state 顶层的 connection_id
    2. 消息的 additional_kwargs.connection_id
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 优先从顶层 state 获取
    if isinstance(state, dict):
        top_level_id = state.get("connection_id")
        if top_level_id:
            logger.info(f"从顶层 state 获取 connection_id: {top_level_id}")
            return top_level_id
    
    # 从消息中提取
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
    connection_id = None
    
    for message in reversed(messages):
        # 支持多种消息格式
        msg_type = None
        additional_kwargs = None
        
        if hasattr(message, 'type'):
            msg_type = message.type
            additional_kwargs = getattr(message, 'additional_kwargs', None)
        elif isinstance(message, dict):
            msg_type = message.get('type') or message.get('role')
            additional_kwargs = message.get('additional_kwargs')
        
        if msg_type in ('human', 'user'):
            if additional_kwargs and isinstance(additional_kwargs, dict):
                msg_connection_id = additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    logger.info(f"从消息 additional_kwargs 提取 connection_id: {connection_id}")
                    break
    
    # 更新到 state
    if connection_id and isinstance(state, dict):
        state['connection_id'] = connection_id
    
    return connection_id


def create_initial_state(
    query: Optional[str] = None,
    connection_id: Optional[int] = None,
    db_type: str = "mysql",
    thread_id: Optional[str] = None,
    tenant_id: Optional[int] = None
) -> Dict[str, Any]:
    """创建初始状态的便捷函数，用于测试和外部调用"""
    from langchain_core.messages import HumanMessage
    
    messages = []
    if query:
        kwargs = {}
        if connection_id:
            kwargs["connection_id"] = connection_id
        messages.append(HumanMessage(content=query, additional_kwargs=kwargs))
    
    state = {
        "messages": messages,
        "connection_id": connection_id,
        "db_type": db_type,
        "current_stage": "schema_analysis",
        "retry_count": 0,
        "max_retries": 3,
        "error_history": [],
        "agent_messages": {},
        "completed_stages": [],
        "agent_call_history": [],
        "supervisor_turn_count": 0,
    }
    
    if thread_id:
        state["thread_id"] = thread_id
    if tenant_id:
        state["tenant_id"] = tenant_id
        
    return state


def is_skill_mode_enabled(state: Dict[str, Any]) -> bool:
    """判断 Skill 模式是否启用"""
    skill_context = state.get("skill_context", {})
    return skill_context.get("enabled", False)


def get_skill_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """获取 Skill 上下文"""
    return state.get("skill_context", {"enabled": False})
