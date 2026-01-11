"""
SQL执行代理
负责安全地执行SQL查询并处理结果
"""
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.core.llms import get_default_model
from app.db.db_manager import db_manager, ensure_db_connection

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
            "execution_time": 0,  # TODO: 添加执行时间计算
            "rows_affected": len(result_data)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "execution_time": 0
        }

@tool
def analyze_query_performance(sql_query: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析查询性能
    
    Args:
        sql_query: SQL查询语句
        execution_result: 执行结果
        
    Returns:
        性能分析结果
    """
    try:
        execution_time = execution_result.get("execution_time", 0)
        row_count = execution_result.get("rows_affected", 0)
        
        # 性能评估
        performance_rating = "excellent"
        if execution_time > 5:
            performance_rating = "poor"
        elif execution_time > 2:
            performance_rating = "fair"
        elif execution_time > 1:
            performance_rating = "good"
        
        # 生成性能建议
        suggestions = []
        if execution_time > 2:
            suggestions.append("查询执行时间较长，考虑添加索引或优化查询")
        if row_count > 10000:
            suggestions.append("返回行数较多，考虑添加分页或更严格的过滤条件")
        
        return {
            "success": True,
            "performance_rating": performance_rating,
            "execution_time": execution_time,
            "row_count": row_count,
            "suggestions": suggestions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def format_query_results(execution_result: Dict[str, Any], format_type: str = "table") -> Dict[str, Any]:
    """
    格式化查询结果
    
    Args:
        execution_result: 执行结果
        format_type: 格式类型 (table, json, csv)
        
    Returns:
        格式化后的结果
    """
    try:
        if not execution_result.get("success"):
            return execution_result
        
        data = execution_result.get("data", {})
        columns = data.get("columns", [])
        rows = data.get("data", [])
        
        if format_type == "table":
            # 创建表格格式
            if not columns or not rows:
                formatted_result = "查询结果为空"
            else:
                # 创建简单的表格格式
                header = " | ".join(columns)
                separator = "-" * len(header)
                row_strings = []
                for row in rows[:10]:  # 限制显示前10行
                    row_str = " | ".join(str(cell) for cell in row)
                    row_strings.append(row_str)
                
                formatted_result = f"{header}\n{separator}\n" + "\n".join(row_strings)
                if len(rows) > 10:
                    formatted_result += f"\n... 还有 {len(rows) - 10} 行"
        
        elif format_type == "json":
            # JSON格式
            if columns and rows:
                json_data = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    json_data.append(row_dict)
                formatted_result = json_data
            else:
                formatted_result = []
        
        elif format_type == "csv":
            # CSV格式
            if columns and rows:
                csv_lines = [",".join(columns)]
                for row in rows:
                    csv_line = ",".join(str(cell) for cell in row)
                    csv_lines.append(csv_line)
                formatted_result = "\n".join(csv_lines)
            else:
                formatted_result = ""
        
        else:
            formatted_result = str(data)

        
        return {
            "success": True,
            "formatted_result": formatted_result,
            "format_type": format_type,
            "original_data": data
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
# fmt: off  Mi80OmFIVnBZMlhva3JMbW5iN21ucGM2ZEhGc2R3PT06Yjc3OTQxN2Q=

class SQLExecutorAgent:
    """SQL执行代理"""

    def __init__(self):
        self.name = "sql_executor_agent"  # 添加name属性
        self.llm = get_default_model()
        self.tools = [execute_sql_query]    #, analyze_query_performance, format_query_results]
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        connection_id = extract_connection_id(state)
        """创建系统提示"""
        system_msg = f"""你是一个专业的SQL执行专家。
        **重要：当前数据库connection_id是 {connection_id}**
        你的任务是：
            1. 安全地执行SQL查询
            2. 分析查询性能
            3. 格式化查询结果
            
            执行流程：
            使用 execute_sql_query 执行SQL查询
            
            执行原则：
            - 确保查询安全性
            - 监控执行性能
            - 提供清晰的结果展示
            - 处理执行错误
            
            如果执行失败，请提供详细的错误信息和解决建议。
"""
        return [{"role": "system", "content": system_msg}] + state["messages"]

    # 2. 使用 analyze_query_performance 分析性能
    # 3. 使用 format_query_results 格式化结果
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
            
            # 准备输入消息
            messages = [
                HumanMessage(content=f"""
请执行以下SQL查询并分析结果：

SQL语句:
{sql_query}

请执行查询、分析性能并格式化结果。
""")
            ]
            
            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 创建执行结果
            execution_result = self._create_execution_result(result)
            
            # 更新状态
            state["execution_result"] = execution_result
            if execution_result.success:
                state["current_stage"] = "completed"
            else:
                state["current_stage"] = "error_recovery"
            
            state["agent_messages"]["sql_executor"] = result
            
            return {
                "messages": result["messages"],
                "execution_result": execution_result,
                "current_stage": state["current_stage"]
            }
# type: ignore  My80OmFIVnBZMlhva3JMbW5iN21ucGM2ZEhGc2R3PT06Yjc3OTQxN2Q=
            
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
    
    def _create_execution_result(self, result: Dict[str, Any]) -> SQLExecutionResult:
        """从代理结果创建执行结果对象"""
        # 简化实现，实际应该解析代理的详细输出
        messages = result.get("messages", [])
        
        success = True
        data = None
        error = None
        execution_time = 0
        rows_affected = 0
        
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content
                if "错误" in content or "失败" in content:
                    success = False
                    error = content
                elif "执行时间" in content:
                    # 尝试提取执行时间
                    import re
                    time_match = re.search(r'(\d+\.?\d*)\s*秒', content)
                    if time_match:
                        execution_time = float(time_match.group(1))
                elif "行数" in content:
                    # 尝试提取行数
                    import re
                    rows_match = re.search(r'(\d+)\s*行', content)
                    if rows_match:
                        rows_affected = int(rows_match.group(1))
        
        return SQLExecutionResult(
            success=success,
            data=data,
            error=error,
            execution_time=execution_time,
            rows_affected=rows_affected
        )

# 创建全局实例
sql_executor_agent = SQLExecutorAgent()
