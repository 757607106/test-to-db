"""
SQL执行代理
负责安全地执行SQL查询并处理结果
"""
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.core.llms import get_default_model
from app.db.db_manager import db_manager, ensure_db_connection
from app.schemas.agent_message import ToolResponse

# 全局缓存 - 防止重复执行
import time
_execution_cache = {}
_cache_timestamps = {}
_cache_lock = {}  # 防止并发重复执行


@tool
def execute_sql_query(sql_query: str, connection_id, timeout: int = 30) -> ToolResponse:
    """
    执行SQL查询 - 带缓存防止重复执行

    Args:
        sql_query: SQL查询语句
        connection_id: 数据库连接ID
        timeout: 超时时间（秒）

    Returns:
        ToolResponse: 统一格式的查询执行结果
    """
    # 生成缓存键
    cache_key = f"{connection_id}:{hash(sql_query)}"
    
    # 检查是否是修改操作（不缓存修改操作）
    sql_upper = sql_query.upper().strip()
    is_modification = any(keyword in sql_upper for keyword in 
                         ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE'])
    
    # 检查缓存（只对查询操作使用缓存，且未过期）
    if not is_modification and cache_key in _execution_cache:
        cache_age = time.time() - _cache_timestamps.get(cache_key, 0)
        if cache_age < 300:  # 5分钟内的缓存有效
            cached_result = _execution_cache[cache_key]
            # 更新缓存元数据
            if cached_result.metadata is None:
                cached_result.metadata = {}
            cached_result.metadata["from_cache"] = True
            cached_result.metadata["cache_age_seconds"] = int(cache_age)
            return cached_result
    
    # 检查是否正在执行（防止并发重复）
    if cache_key in _cache_lock:
        # 等待一小段时间后返回提示
        time.sleep(0.5)
        if cache_key in _execution_cache:
            return _execution_cache[cache_key]
        return ToolResponse(
            status="error",
            error="查询正在执行中，请稍后重试"
        )
    
    # 标记正在执行
    _cache_lock[cache_key] = True
    
    try:
        
        # 根据connection_id获取数据库连接并执行查询
        from app.services.db_service import get_db_connection_by_id, execute_query_with_connection

        # 获取数据库连接
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            return ToolResponse(
                status="error",
                error=f"找不到连接ID为 {connection_id} 的数据库连接",
                metadata={"connection_id": connection_id}
            )

        # 执行查询
        result_data = execute_query_with_connection(connection, sql_query)

        result = ToolResponse(
            status="success",
            data={
                "columns": list(result_data[0].keys()) if result_data else [],
                "data": [list(row.values()) for row in result_data],
                "row_count": len(result_data),
                "column_count": len(result_data[0].keys()) if result_data else 0
            },
            metadata={
                "execution_time": 0,  # TODO: 添加执行时间计算
                "rows_affected": len(result_data),
                "from_cache": False
            }
        )
        
        # 缓存结果（只缓存查询操作）
        if not is_modification:
            _execution_cache[cache_key] = result
            _cache_timestamps[cache_key] = time.time()
            
            # 清理旧缓存（保持缓存大小）
            if len(_execution_cache) > 100:
                # 删除最旧的一半
                sorted_keys = sorted(_cache_timestamps.items(), key=lambda x: x[1])
                keys_to_delete = [k for k, v in sorted_keys[:50]]
                for key in keys_to_delete:
                    _execution_cache.pop(key, None)
                    _cache_timestamps.pop(key, None)
        
        return result

    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e),
            metadata={
                "execution_time": 0,
                "from_cache": False
            }
        )
    finally:
        # 移除执行锁
        _cache_lock.pop(cache_key, None)


@tool
def analyze_query_performance(sql_query: str, execution_result: Dict[str, Any]) -> ToolResponse:
    """
    分析查询性能
    
    Args:
        sql_query: SQL查询语句
        execution_result: 执行结果
        
    Returns:
        ToolResponse: 性能分析结果
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
        
        return ToolResponse(
            status="success",
            data={
                "performance_rating": performance_rating,
                "execution_time": execution_time,
                "row_count": row_count,
                "suggestions": suggestions
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


@tool
def format_query_results(execution_result: Dict[str, Any], format_type: str = "table") -> ToolResponse:
    """
    格式化查询结果
    
    Args:
        execution_result: 执行结果
        format_type: 格式类型 (table, json, csv)
        
    Returns:
        ToolResponse: 格式化后的结果
    """
    try:
        # 检查输入结果的状态
        if not execution_result.get("success") and "status" not in execution_result:
            return ToolResponse(
                status="error",
                error="输入的执行结果无效"
            )
        
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
        
        return ToolResponse(
            status="success",
            data={
                "formatted_result": formatted_result,
                "format_type": format_type,
                "original_data": data
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


class SQLExecutorAgent:
    """SQL执行代理"""

    def __init__(self):
        self.name = "sql_executor_agent"
        self.llm = get_default_model()
        self.tools = [execute_sql_query]
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        connection_id = extract_connection_id(state)
        """创建系统提示 - 强调只执行一次，立即返回"""
        system_msg = f"""你是一个SQL执行专家。当前数据库connection_id是 {connection_id}。

**重要规则 - 必须严格遵守**:
1. 使用 execute_sql_query 工具执行SQL查询 **仅一次**
2. 工具调用完成后，**立即结束**，不要做任何其他事情
3. **绝对不要**重复调用工具
4. **绝对不要**尝试验证或重试
5. 工具返回结果后，**直接结束任务**

执行流程（严格按照此流程）:
Step 1: 调用 execute_sql_query 工具一次
Step 2: 立即结束任务

**禁止的行为**:
- ❌ 不要调用工具两次或更多次
- ❌ 不要在工具调用后继续思考
- ❌ 不要尝试验证结果
- ❌ 不要尝试重试
- ❌ 不要做任何额外的操作

记住：调用工具一次后，立即结束！
"""
        return [{"role": "system", "content": system_msg}] + state["messages"]

    # 2. 使用 analyze_query_performance 分析性能
    # 3. 使用 format_query_results 格式化结果
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL执行任务 - 直接调用工具，避免 ReAct 重复调用
        
        注意：简化流程后，不再检查验证结果，直接执行SQL
        修复：不使用 ReAct agent，直接调用工具，避免重复执行
        """
        try:
            import json
            
            # 获取生成的SQL
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要执行的SQL语句")
            
            connection_id = state.get("connection_id", 15)
            
            # 直接调用工具，不经过 LLM 推理（避免重复调用）
            result = execute_sql_query.invoke({
                "sql_query": sql_query,
                "connection_id": connection_id,
                "timeout": 30
            })
            
            # 创建执行结果
            execution_result = SQLExecutionResult(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
                execution_time=result.get("execution_time", 0),
                rows_affected=result.get("rows_affected", 0)
            )
            
            # 更新状态
            state["execution_result"] = execution_result
            if execution_result.success:
                state["current_stage"] = "completed"
            else:
                # 增强错误信息 - 包含SQL查询
                error_info = {
                    "stage": "sql_execution",
                    "error": execution_result.error,
                    "sql_query": sql_query,
                    "retry_count": state.get("retry_count", 0)
                }
                state["error_history"].append(error_info)
                state["current_stage"] = "error_recovery"
            
            # 创建消息用于前端显示（模拟 ReAct 的消息格式）
            tool_call_id = f"call_{abs(hash(sql_query))}"
            
            ai_message = AIMessage(
                content="",
                tool_calls=[{
                    "name": "execute_sql_query",
                    "args": {
                        "sql_query": sql_query,
                        "connection_id": connection_id,
                        "timeout": 30
                    },
                    "id": tool_call_id,
                    "type": "tool_call"
                }]
            )
            
            # 创建对应的 tool message
            tool_message = ToolMessage(
                content=result.model_dump_json(),  # ✅ 使用 Pydantic 标准序列化
                tool_call_id=tool_call_id,
                name="execute_sql_query",
                status=result.status  # ✅ 直接使用 ToolResponse.status
            )
            
            # 保存到 agent_messages
            state["agent_messages"]["sql_executor"] = {
                "messages": [ai_message, tool_message]
            }
            
            return {
                "messages": [ai_message, tool_message],
                "execution_result": execution_result,
                "current_stage": state["current_stage"]
            }
            
        except Exception as e:
            # 详细的错误记录 - 包含所有必需字段
            error_info = {
                "stage": "sql_execution",
                "error": str(e),
                "sql_query": state.get("generated_sql"),
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
