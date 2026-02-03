"""
SQL执行代理 - 简化版
负责安全地执行SQL查询并处理结果

设计原则：
- 只负责执行 SQL，不做复杂的错误分析
- 错误分析交给 error_recovery_agent 和 LLM 处理
"""
from typing import Dict, Any, Annotated, List

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage, BaseMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.config import get_stream_writer
from langgraph.types import Command

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.schemas.stream_events import create_sql_step_event, create_stage_message_event, create_thought_event


def _extract_new_messages_for_parent(
    messages: List[BaseMessage], 
    tool_call_id: str, 
    new_tool_message: ToolMessage
) -> List[BaseMessage]:
    """
    提取需要返回给父图的新消息
    
    只返回：
    1. 调用该工具的 AIMessage（包含 tool_call_id 的那个）
    2. 新的 ToolMessage
    
    这样可以避免消息重复，同时保证 AIMessage 不丢失
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


@tool
def execute_sql_query(
    sql_query: str, 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    执行SQL查询并更新状态

    Args:
        sql_query: SQL查询语句

    Returns:
        Command: 更新父图 query_results 状态的命令
    """
    # 获取当前消息历史（包含 LLM 生成的 AIMessage）
    # 修复：Command.PARENT 需要包含完整消息历史，否则子 Agent 的 AIMessage 会丢失
    current_messages = list(state.get("messages", []))
    
    try:
        # 立即发送 running 状态事件
        writer = get_stream_writer()
        if writer:
            writer(create_sql_step_event(
                step="sql_executor",
                status="running",
                result="正在执行 SQL 查询..."
            ))
            writer(create_thought_event(
                agent="sql_executor",
                thought="我正在连接数据库并执行查询，请稍候...",
                plan="获取查询结果后将进行数据分析"
            ))
        
        # 从状态获取 connection_id
        connection_id = state.get("connection_id") or extract_connection_id(state)
        if not connection_id:
            error_msg = ToolMessage(
                content="错误：未指定数据库连接",
                tool_call_id=tool_call_id
            )
            # 修复：只返回新消息，避免消息重复
            new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, error_msg)
            return Command(
                graph=Command.PARENT,
                update={
                    "messages": new_messages
                }
            )
        
        # 根据connection_id获取数据库连接并执行查询
        from app.services.db_service import get_db_connection_by_id, execute_query_with_connection

        # 获取数据库连接
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            error_msg = ToolMessage(
                content=f"找不到连接ID为 {connection_id} 的数据库连接",
                tool_call_id=tool_call_id
            )
            # 修复：只返回新消息，避免消息重复
            new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, error_msg)
            return Command(
                graph=Command.PARENT,
                update={
                    "messages": new_messages
                }
            )

        # 执行查询
        result_data = execute_query_with_connection(connection, sql_query)
        
        row_count = len(result_data) if result_data else 0
        
        # 发送 sql_step 事件
        writer = get_stream_writer()
        if writer:
            writer(create_sql_step_event(
                step="sql_executor",
                status="completed",
                result=f"SQL执行成功，返回 {row_count} 条记录"
            ))
            writer(create_stage_message_event(
                message=f"SQL执行成功，返回 {row_count} 条记录",
                step="sql_executor"
            ))
        
        # 返回 Command 更新父图状态
        tool_msg = ToolMessage(
            content=f"SQL执行成功，返回 {row_count} 条记录",
            tool_call_id=tool_call_id
        )
        # 修复：只返回新消息，避免消息重复
        new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, tool_msg)
        return Command(
            graph=Command.PARENT,
            update={
                "query_results": result_data,
                "current_stage": "data_analysis",
                "messages": new_messages
            }
        )

    except Exception as e:
        # 记录错误并进入错误恢复流程
        # 不再做硬编码的错误分类，让 error_recovery_agent 使用 LLM 智能分析
        error_msg = str(e)
        
        # 发送错误状态事件
        writer = get_stream_writer()
        if writer:
            writer(create_sql_step_event(
                step="sql_executor",
                status="error",
                result=f"SQL 执行失败"
            ))
        
        # 记录错误到 error_history
        error_info = {
            "stage": "sql_execution",
            "error": error_msg,
            "sql": sql_query
        }
        
        tool_msg = ToolMessage(
            content=f"SQL 执行失败，正在分析错误...",
            tool_call_id=tool_call_id
        )
        # 修复：只返回新消息，避免消息重复
        new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, tool_msg)
        return Command(
            graph=Command.PARENT,
            update={
                "current_stage": "error_recovery",
                "error_history": [error_info],  # 会被合并到现有的 error_history
                "messages": new_messages
            }
        )


class SQLExecutorAgent:
    """SQL执行代理 - 简化版"""

    def __init__(self):
        self.name = "sql_executor_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [execute_sql_query]
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name,
            state_schema=SQLMessageState,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        connection_id = extract_connection_id(state)
        system_msg = f"""你是一个专业的SQL执行专家。
**重要：当前数据库connection_id是 {connection_id}**

你的任务是：
1. 使用 execute_sql_query 工具执行 SQL 查询
2. 只输出执行状态（成功或失败）

**执行原则：**
- 只输出执行状态
- 禁止输出任何对数据的分析或解释
- 禁止向用户提供建议
"""
        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL执行任务"""
        try:
            # 获取验证通过的SQL
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要执行的SQL语句")
            
            # 检查验证结果
            validation_result = state.get("validation_result")
            if validation_result and not validation_result.is_valid:
                raise ValueError("SQL验证未通过，无法执行")
            
            connection_id = extract_connection_id(state) or state.get("connection_id")
            if not connection_id:
                raise ValueError("未指定数据库连接，请先在界面中选择一个数据库")
            
            raw_result = await execute_sql_query.ainvoke({
                "sql_query": sql_query,
                "connection_id": connection_id,
                "timeout": 30
            })

            if not isinstance(raw_result, dict):
                raise ValueError("SQL执行结果格式异常")

            execution_result = SQLExecutionResult(
                success=raw_result.get("success", False),
                data=raw_result.get("data"),
                error=raw_result.get("error"),
                execution_time=raw_result.get("execution_time"),
                rows_affected=raw_result.get("rows_affected")
            )
            
            # 更新状态
            state["execution_result"] = execution_result
            if execution_result.success:
                state["current_stage"] = "completed"
            else:
                state["current_stage"] = "error_recovery"
            
            state["agent_messages"]["sql_executor"] = raw_result
            
            return {
                "messages": [AIMessage(content="SQL执行成功")] if execution_result.success else [AIMessage(content="SQL执行失败")],
                "execution_result": execution_result,
                "current_stage": state["current_stage"]
            }
            
        except Exception as e:
            # 记录错误
            error_info = {
                "stage": "sql_execution",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
            
            # 创建失败的执行结果
            execution_result = SQLExecutionResult(
                success=False,
                error=str(e)
            )
            
            return {
                "messages": [AIMessage(content=f"SQL执行失败: {str(e)}")],
                "execution_result": execution_result,
                "current_stage": "error_recovery"
            }
    
# 创建全局实例
sql_executor_agent = SQLExecutorAgent()
