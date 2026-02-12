"""
节点基础工具模块

提供节点间共享的工具函数：
- extract_user_query: 从消息历史提取用户查询
- extract_last_human_message: 提取最后一条用户消息
- get_custom_agent: 获取自定义 Agent（支持 agent_id 或 custom_agents 字典）
- load_custom_agent_by_id: 根据 agent_id 动态加载自定义 Agent
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage

if TYPE_CHECKING:
    from app.core.state import SQLMessageState

logger = logging.getLogger(__name__)


def extract_user_query(messages: List[Any]) -> Optional[str]:
    """
    从消息列表中提取最新的用户查询
    
    Args:
        messages: LangChain 消息列表
        
    Returns:
        用户查询字符串，如果没有找到则返回 None
    """
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            return _normalize_content(message.content)
        elif isinstance(message, HumanMessage):
            return _normalize_content(message.content)
        elif isinstance(message, dict) and message.get('type') == 'human':
            return _normalize_content(message.get('content'))
    return None


def extract_last_human_message(state: "SQLMessageState") -> Optional[str]:
    """
    从状态中提取最后一条用户消息
    
    Args:
        state: SQL 消息状态
        
    Returns:
        用户查询字符串
    """
    messages = state.get("messages", [])
    return extract_user_query(messages)


def _normalize_content(content: Any) -> Optional[str]:
    """规范化消息内容，兼容多模态消息格式"""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(p for p in parts if p).strip() or None
    if isinstance(content, dict):
        if content.get("type") == "text" and content.get("text"):
            return str(content.get("text"))
    return str(content)


def load_custom_agent_by_id(agent_id: int, agent_type: str = "data_analyst") -> Optional[Any]:
    """
    根据 agent_id 动态加载自定义 Agent
    
    从数据库加载 AgentProfile 并创建对应的自定义 Agent。
    在每次需要时动态创建，避免将不可序列化的对象存储到 State。
    
    Args:
        agent_id: AgentProfile 的 ID
        agent_type: Agent 类型（目前支持 data_analyst）
        
    Returns:
        Agent 实例，如果加载失败则返回 None
    """
    if agent_type != "data_analyst":
        return None
    
    try:
        from app.db.session import get_db_session
        from app.crud import agent_profile as crud_agent_profile
        from app.agents.agent_factory import create_custom_analyst_agent
        
        with get_db_session() as db:
            profile = crud_agent_profile.get(db, id=agent_id)
            
            if not profile:
                logger.warning(f"未找到 agent_id={agent_id} 对应的 AgentProfile")
                return None
            
            if not profile.is_active:
                logger.warning(f"AgentProfile {profile.name} 未激活")
                return None
            
            logger.info(f"动态加载 AgentProfile: {profile.name} (id={profile.id})")
            return create_custom_analyst_agent(profile, db)
            
    except Exception as e:
        logger.error(f"动态加载自定义 agent 失败: {e}", exc_info=True)
        return None


def get_custom_agent(
    state: "SQLMessageState",
    agent_type: str,
    default_agent: Any
) -> Any:
    """
    获取自定义 Agent
    
    优先级:
    1. state["custom_agents"][agent_type] - 测试场景注入
    2. 通过 state["agent_id"] 从数据库加载
    3. 默认 Agent
    
    Args:
        state: SQL 消息状态
        agent_type: Agent 类型名称（如 "schema_agent", "data_analyst"）
        default_agent: 默认的 Agent 实例
        
    Returns:
        Agent 实例
    """
    # 方式1: 从 custom_agents 字典获取（测试场景）
    custom_agents = state.get("custom_agents", {})
    if agent_type in custom_agents:
        return custom_agents[agent_type]
    
    # 方式2: 通过 agent_id 从数据库加载
    agent_id = state.get("agent_id")
    if agent_id:
        custom_agent = load_custom_agent_by_id(agent_id, agent_type)
        if custom_agent:
            return custom_agent
    
    # 方式3: 返回默认 Agent
    return default_agent


class ErrorStage:
    SCHEMA_ANALYSIS = "schema_analysis"
    SCHEMA_ENRICHMENT = "schema_enrichment"
    SCHEMA_CLARIFICATION = "schema_clarification"
    SQL_GENERATION = "sql_generation"
    SQL_GENERATION_COLUMN_VALIDATION = "sql_generation_column_validation"
    SQL_PREVALIDATION = "sql_prevalidation"
    SQL_EXECUTION = "sql_execution"
    DATA_ANALYSIS = "data_analysis"
    CHART_GENERATION = "chart_generation"
    ERROR_RECOVERY = "error_recovery"
    SUPERVISOR_SUBGRAPH = "supervisor_subgraph"


def build_error_record(stage: str, error: str) -> Dict[str, Any]:
    """
    构建标准的错误记录
    
    Args:
        stage: 发生错误的阶段
        error: 错误信息
        
    Returns:
        错误记录字典
    """
    import time
    return {
        "stage": stage,
        "error": str(error),
        "timestamp": time.time()
    }


def extract_new_messages_for_parent(
    messages: List[Any],
    tool_call_id: str,
    new_tool_message: ToolMessage
) -> List[Any]:
    """
    提取需要返回给父图的新消息
    
    只返回：
    1. 调用该工具的 AIMessage（包含 tool_call_id 的那个）
    2. 新的 ToolMessage
    
    这样可以避免消息重复，同时保证 AIMessage 不丢失
    
    原理：父图的 add_messages reducer 会自动累积消息，
    如果返回完整消息历史会导致重复。
    """
    new_messages = []
    
    # 从后往前找到调用该工具的 AIMessage
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('id') == tool_call_id:
                    new_messages.insert(0, msg)
                    break
            if new_messages:
                break
    
    # 添加新的 ToolMessage
    new_messages.append(new_tool_message)
    
    return new_messages


__all__ = [
    "extract_user_query",
    "extract_last_human_message",
    "get_custom_agent",
    "load_custom_agent_by_id",
    "ErrorStage",
    "build_error_record",
    "extract_new_messages_for_parent",
]
