"""
SQL执行代理
负责安全地执行SQL查询并处理结果
"""
from typing import Dict, Any, Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.config import get_stream_writer
from langgraph.types import Command

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.schemas.stream_events import create_sql_step_event, create_stage_message_event


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
    try:
        # 从状态获取 connection_id
        connection_id = state.get("connection_id") or extract_connection_id(state)
        if not connection_id:
            return Command(
                graph=Command.PARENT,
                update={
                    "messages": [ToolMessage(
                        content="错误：未指定数据库连接",
                        tool_call_id=tool_call_id
                    )]
                }
            )
        
        # 根据connection_id获取数据库连接并执行查询
        from app.services.db_service import get_db_connection_by_id, execute_query_with_connection

        # 获取数据库连接
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            return Command(
                graph=Command.PARENT,
                update={
                    "messages": [ToolMessage(
                        content=f"找不到连接ID为 {connection_id} 的数据库连接",
                        tool_call_id=tool_call_id
                    )]
                }
            )

        # 执行查询
        result_data = execute_query_with_connection(connection, sql_query)
        
        row_count = len(result_data) if result_data else 0
        
        # 发送 sql_step 事件 - 关键！
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
        
        # 返回 Command 更新父图状态（关键：graph=Command.PARENT）
        return Command(
            graph=Command.PARENT,
            update={
                "query_results": result_data,
                "current_stage": "data_analysis",
                "messages": [ToolMessage(
                    content=f"SQL执行成功，返回 {row_count} 条记录",
                    tool_call_id=tool_call_id
                )]
            }
        )

    except Exception as e:
        # 提取业务化的错误信息
        error_msg = str(e)
        business_error = _extract_business_error(error_msg, sql_query)
        
        # 设置澄清上下文，用于触发业务化澄清
        clarification_context = {
            "trigger": "sql_execution_error",
            "error": business_error,  # 业务化的错误描述
            "technical_error": error_msg,  # 技术错误（仅供日志）
            "sql": sql_query,
            "needs_user_confirmation": True
        }
        
        return Command(
            graph=Command.PARENT,
            update={
                "current_stage": "clarification",  # 触发澄清流程
                "clarification_context": clarification_context,
                "messages": [ToolMessage(
                    content=f"执行遇到问题，需要您的确认",
                    tool_call_id=tool_call_id
                )]
            }
        )


def _extract_business_error(error_msg: str, sql: str) -> str:
    """
    将技术错误转换为业务化描述
    
    原则：
    - 不暴露表名、字段名等技术细节
    - 用业务语言描述问题
    - 给用户可理解的提示
    """
    error_lower = error_msg.lower()
    
    # 字段不存在
    if "unknown column" in error_lower or "column" in error_lower and "not found" in error_lower:
        return "查询的数据维度可能不存在，需要调整查询内容"
    
    # 表不存在
    if "table" in error_lower and ("doesn't exist" in error_lower or "not found" in error_lower):
        return "查询的数据范围可能超出了可访问的范围"
    
    # 语法错误
    if "syntax error" in error_lower or "sql syntax" in error_lower:
        return "查询语句的结构需要调整"
    
    # 权限错误
    if "permission" in error_lower or "denied" in error_lower or "access" in error_lower:
        return "当前没有权限访问相关数据"
    
    # 超时
    if "timeout" in error_lower or "time out" in error_lower:
        return "查询数据量较大，建议缩小查询范围或添加时间限制"
    
    # 连接错误
    if "connection" in error_lower:
        return "数据库连接出现问题，请稍后重试"
    
    # 默认：通用业务化描述
    return "执行查询时遇到了问题，可能需要调整查询条件或数据范围"


class SQLExecutorAgent:
    """SQL执行代理"""

    def __init__(self):
        self.name = "sql_executor_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [execute_sql_query]
        
        # 创建ReAct代理（使用自定义 state_schema 以支持 connection_id 等字段）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name,
            state_schema=SQLMessageState,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        connection_id = extract_connection_id(state)
        """创建系统提示"""
        system_msg = f"""你是一个专业的SQL执行专家。
**重要：当前数据库connection_id是 {connection_id}**
你的任务是：
1. 安全地执行SQL查询（使用 execute_sql_query）

**执行原则（严格）：**
- **只输出执行状态**（如“执行成功”或具体的报错信息）。
- **禁止输出任何对数据的分析或解释。**
- **禁止向用户提供建议。**
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
