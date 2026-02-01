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
