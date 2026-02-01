"""
SQL执行代理
负责安全地执行SQL查询并处理结果
"""
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR


@tool
def execute_sql_query(sql_query: str, connection_id, timeout: int = 30) -> Dict[str, Any]:
    """
    执行SQL查询

    Args:
        sql_query: SQL查询语句
        connection_id: 数据库连接ID
        timeout: 超时时间（秒）

    Returns:
        查询执行结果
    """
    try:
        # 根据connection_id获取数据库连接并执行查询
        from app.services.db_service import get_db_connection_by_id, execute_query_with_connection

        # 获取数据库连接
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            return {
                "success": False,
                "error": f"找不到连接ID为 {connection_id} 的数据库连接"
            }

        # 执行查询
        result_data = execute_query_with_connection(connection, sql_query)

        return {
            "success": True,
            "data": {
                "columns": list(result_data[0].keys()) if result_data else [],
                "data": [list(row.values()) for row in result_data],
                "row_count": len(result_data),
                "column_count": len(result_data[0].keys()) if result_data else 0
            },
            "error": None,
            "execution_time": 0,
            "rows_affected": len(result_data)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "execution_time": 0
        }


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
