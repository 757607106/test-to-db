"""
SQL 执行代理

直接执行 SQL 查询，内置缓存机制防止重复执行。
"""
from typing import Dict, Any, Optional
import time
import json
import logging

from langchain_core.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.core.state import SQLMessageState, SQLExecutionResult
from app.schemas.agent_message import ToolResponse

logger = logging.getLogger(__name__)

# ============================================================================
# 全局缓存 - 防止重复执行
# ============================================================================
_execution_cache: Dict[str, ToolResponse] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_lock: Dict[str, bool] = {}

# 缓存配置
CACHE_TTL_SECONDS = 300  # 5分钟
CACHE_MAX_SIZE = 100


def _clean_old_cache():
    """清理过期缓存"""
    current_time = time.time()
    expired_keys = [
        key for key, timestamp in _cache_timestamps.items()
        if current_time - timestamp > CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        _execution_cache.pop(key, None)
        _cache_timestamps.pop(key, None)
    
    # 如果还是超过最大容量，删除最旧的一半
    if len(_execution_cache) > CACHE_MAX_SIZE:
        sorted_keys = sorted(_cache_timestamps.items(), key=lambda x: x[1])
        keys_to_delete = [k for k, v in sorted_keys[:CACHE_MAX_SIZE // 2]]
        for key in keys_to_delete:
            _execution_cache.pop(key, None)
            _cache_timestamps.pop(key, None)


# ============================================================================
# SQL 执行工具 (遵循 LangChain 工具标准)
# ============================================================================

@tool
def execute_sql_query(
    sql_query: str,
    connection_id: int,
    timeout: int = 30
) -> str:
    """执行 SQL 查询并返回 JSON 格式结果"""
    sql_query = (sql_query or "").strip()
    if not sql_query:
        return json.dumps({
            "success": False,
            "error": "SQL 语句为空",
            "from_cache": False
        }, ensure_ascii=False)

    try:
        timeout_seconds = int(timeout)
    except Exception:
        timeout_seconds = 30
    timeout_seconds = max(1, min(timeout_seconds, 300))

    sql_to_execute = sql_query
    db_type = "mysql"

    try:
        from app.services.db_service import get_db_connection_by_id
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            return json.dumps({
                "success": False,
                "error": f"找不到连接 ID 为 {connection_id} 的数据库连接",
                "from_cache": False
            }, ensure_ascii=False)
        if getattr(connection, "db_type", None):
            db_type = str(connection.db_type).lower()

        from app.services.sql_validator import sql_validator
        validation = sql_validator.validate(
            sql=sql_query,
            schema_context=None,
            db_type=db_type,
            allow_write=False
        )
        if not validation.is_valid:
            return json.dumps({
                "success": False,
                "error": "; ".join(validation.errors)[:500],
                "from_cache": False
            }, ensure_ascii=False)

        if validation.fixed_sql:
            sql_to_execute = validation.fixed_sql
    except Exception as e:
        logger.error(f"SQL 执行前置校验失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"SQL 执行前置校验失败: {str(e)[:200]}",
            "from_cache": False
        }, ensure_ascii=False)

    # 生成缓存键
    cache_key = f"{connection_id}:{hash(sql_to_execute)}"
    is_modification = False
    
    # 检查缓存（只对查询操作使用缓存，且未过期）
    if not is_modification and cache_key in _execution_cache:
        cache_age = time.time() - _cache_timestamps.get(cache_key, 0)
        if cache_age < CACHE_TTL_SECONDS:
            cached_result = _execution_cache[cache_key]
            logger.info(f"SQL 执行缓存命中 (age: {int(cache_age)}s)")
            # 返回 JSON 字符串
            result_dict = {
                "success": cached_result.status == "success",
                "data": cached_result.data,
                "error": cached_result.error,
                "from_cache": True,
                "cache_age_seconds": int(cache_age)
            }
            return json.dumps(result_dict, ensure_ascii=False, default=str)
    
    # 检查是否正在执行（防止并发重复）
    if cache_key in _cache_lock:
        time.sleep(0.5)
        if cache_key in _execution_cache:
            cached = _execution_cache[cache_key]
            return json.dumps({
                "success": cached.status == "success",
                "data": cached.data,
                "error": cached.error,
                "from_cache": True
            }, ensure_ascii=False, default=str)
        return json.dumps({
            "success": False,
            "error": "查询正在执行中，请稍后重试",
            "from_cache": False
        }, ensure_ascii=False)
    
    # 标记正在执行
    _cache_lock[cache_key] = True
    
    try:
        from app.services.db_service import execute_query_with_connection
        
        # 执行查询
        start_time = time.time()
        result_data = execute_query_with_connection(
            connection=connection,
            query=sql_to_execute,
            timeout_seconds=timeout_seconds
        )
        execution_time = time.time() - start_time
        
        # 构建结果
        result = ToolResponse(
            status="success",
            data={
                "columns": list(result_data[0].keys()) if result_data else [],
                "data": [list(row.values()) for row in result_data],
                "row_count": len(result_data),
                "column_count": len(result_data[0].keys()) if result_data else 0
            },
            metadata={
                "execution_time": execution_time,
                "rows_affected": len(result_data),
                "from_cache": False
            }
        )
        
        # 缓存结果（只缓存查询操作）
        if not is_modification:
            _clean_old_cache()
            _execution_cache[cache_key] = result
            _cache_timestamps[cache_key] = time.time()
        
        # 返回 JSON 字符串
        return json.dumps({
            "success": True,
            "data": result.data,
            "execution_time": execution_time,
            "from_cache": False
        }, ensure_ascii=False, default=str)
        
    except Exception as e:
        logger.error(f"SQL 执行失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "from_cache": False
        }, ensure_ascii=False)
    finally:
        # 移除执行锁
        _cache_lock.pop(cache_key, None)


# ============================================================================
# SQL 执行节点
# ============================================================================

sql_executor_tool_node = ToolNode(
    tools=[execute_sql_query],
    handle_tool_errors=True
)


class SQLExecutorAgent:
    """SQL 执行代理"""
    
    def __init__(self):
        self.name = "sql_executor_agent"
        self.tools = [execute_sql_query]
        self.tool_node = sql_executor_tool_node
        self._create_compatible_agent()
    
    def _create_compatible_agent(self):
        """创建兼容现有接口的 agent"""
        from langgraph.prebuilt import create_react_agent
        from app.core.llms import get_default_model
        
        self.llm = get_default_model()
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个 SQL 执行专家。

**核心职责**: 执行 SQL 查询，返回原始数据

**执行规则**:
1. 使用 execute_sql_query 工具执行 SQL 查询（仅执行一次）
2. 返回工具执行的原始结果
3. 禁止生成查询结果的总结或解读
4. 禁止重复调用工具

**错误处理**:
- 执行失败时，错误信息会自动传递给错误恢复模块
- 不要尝试自行修复 SQL

**输出格式**: 只返回工具调用结果，不添加任何文字"""
    
    async def execute(self, state: SQLMessageState) -> Dict[str, Any]:
        """执行 SQL 查询"""
        import time
        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_sql_step_event, create_data_query_event
        
        # 获取 stream writer
        try:
            writer = get_stream_writer()
        except Exception:
            writer = None
        
        try:
            # 获取生成的 SQL
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要执行的 SQL 语句")
            
            connection_id = state.get("connection_id")
            if not connection_id:
                raise ValueError("没有指定数据库连接 ID")
            
            logger.info(f"执行 SQL: {sql_query[:100]}...")
            
            # 发送 final_sql 步骤开始事件
            step_start_time = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="final_sql",
                    status="running",
                    result=sql_query[:100] + "..." if len(sql_query) > 100 else sql_query,
                    time_ms=0
                ))
            
            # 直接调用工具，不经过 LLM
            result_json = execute_sql_query.invoke({
                "sql_query": sql_query,
                "connection_id": connection_id,
                "timeout": 30
            })
            
            # 解析结果
            result = json.loads(result_json)
            
            # 计算执行耗时
            elapsed_ms = int((time.time() - step_start_time) * 1000)
            
            # 发送 final_sql 步骤完成事件
            if writer:
                if result.get("success"):
                    row_count = result.get("data", {}).get("row_count", 0)
                    writer(create_sql_step_event(
                        step="final_sql",
                        status="completed",
                        result=f"查询成功，返回 {row_count} 条记录",
                        time_ms=elapsed_ms
                    ))
                else:
                    writer(create_sql_step_event(
                        step="final_sql",
                        status="error",
                        result=result.get("error", "执行失败"),
                        time_ms=elapsed_ms
                    ))
            
            # 创建执行结果
            execution_result = SQLExecutionResult(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
                execution_time=result.get("execution_time", 0),
                rows_affected=result.get("data", {}).get("row_count", 0) if result.get("success") else 0
            )
            
            # ✅ 新增：执行结果验证
            result_validation = None
            if result.get("success"):
                try:
                    from app.services.result_validator import result_validator
                    
                    user_query = self._extract_user_query(state)
                    result_validation = result_validator.validate(
                        result=execution_result,
                        sql=sql_query,
                        user_query=user_query
                    )
                    
                    # 记录验证结果
                    if result_validation.has_issues:
                        logger.info(f"结果验证发现问题: {result_validation.message}")
                        for warning in result_validation.warnings:
                            logger.info(f"  警告: {warning}")
                        
                        # 如果是空结果，在流式事件中提示
                        if result_validation.row_count == 0 and writer:
                            writer(create_sql_step_event(
                                step="final_sql",
                                status="completed",
                                result=f"查询成功但结果为空。{result_validation.message or ''}",
                                time_ms=elapsed_ms
                            ))
                except ImportError:
                    pass  # result_validator 模块不存在时跳过
                except Exception as e:
                    logger.warning(f"结果验证异常: {e}")
            
            # 如果执行成功，发送数据查询事件
            if result.get("success") and writer:
                data_result = result.get("data", {})
                columns = data_result.get("columns", [])
                raw_rows = data_result.get("data", [])  # 这是值列表的列表
                row_count = data_result.get("row_count", 0)
                
                # 将值列表转换为字典列表（前端需要字典格式）
                rows = []
                for raw_row in raw_rows:
                    if isinstance(raw_row, list) and len(raw_row) == len(columns):
                        rows.append(dict(zip(columns, raw_row)))
                    elif isinstance(raw_row, dict):
                        rows.append(raw_row)
                
                # 生成图表配置
                chart_config = self._generate_chart_config(columns, rows)
                
                # 发送数据查询事件（限制返回行数避免数据过大）
                user_query = self._extract_user_query(state)
                writer(create_data_query_event(
                    columns=columns,
                    rows=rows[:100],  # 最多返回100行
                    row_count=row_count,
                    chart_config=chart_config,
                    title=user_query[:50] if user_query else None
                ))
            
            # 创建消息用于状态更新 - 遵循 LangGraph SDK 标准
            from app.core.message_utils import generate_tool_call_id
            
            tool_call_id = generate_tool_call_id("execute_sql_query", {
                "sql_query": sql_query,
                "connection_id": connection_id
            })
            
            # AIMessage 包含 tool_calls 数组
            ai_message = AIMessage(
                content="",  # 状态通过 QueryPipeline 组件展示，不需要文字
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
            
            # ToolMessage 必须包含 tool_call_id 与上面的 tool_call 匹配
            tool_message = ToolMessage(
                content=result_json,
                tool_call_id=tool_call_id,
                name="execute_sql_query"
            )
            
            messages = [ai_message, tool_message]
            
            # 确定下一阶段
            if execution_result.success:
                # 执行成功，总是进入数据分析阶段
                # 流程：sql_execution → analysis → chart_generation → completed
                # 快速模式只影响是否生成图表，不影响数据分析
                return {
                    "messages": messages,
                    "execution_result": execution_result,
                    "current_stage": "analysis"  # 总是进入数据分析阶段
                }
            else:
                # ✅ 修复：SQL 执行失败时，必须添加 error_history 和 error_recovery_context
                # 这样 sql_generator 在重试时能知道之前的错误并获取完整的表列表
                error_msg = result.get("error", "SQL 执行失败")
                logger.warning(f"SQL 执行失败（工具返回错误）: {error_msg[:100]}")
                
                # ✅ 关键修复：从 state 中获取 schema_info，构建列名白名单
                schema_info = state.get("schema_info", {})
                available_columns_hint = ""
                column_whitelist = {}
                
                if schema_info:
                    columns_list = schema_info.get("columns", [])
                    if columns_list:
                        # 构建列名白名单
                        for col in columns_list:
                            table_name = col.get("table_name", "")
                            col_name = col.get("column_name", "")
                            if table_name and col_name:
                                if table_name not in column_whitelist:
                                    column_whitelist[table_name] = []
                                column_whitelist[table_name].append(col_name)
                        
                        # 构建可用列提示
                        available_columns_info = []
                        for table_name, cols in column_whitelist.items():
                            available_columns_info.append(f"表 `{table_name}` 的可用列: {', '.join(cols)}")
                        available_columns_hint = "\n".join(available_columns_info)
                        
                        logger.info(f"[SQL执行失败] 构建列名白名单: {len(column_whitelist)} 个表")
                
                # ✅ 关键修复：构建 error_recovery_context，包含列名白名单
                error_recovery_context = {
                    "failed_sql": sql_query,
                    "error_message": error_msg,
                    "error_type": "sql_execution_failed",
                    "recovery_steps": ["检查列名是否正确", "检查表名是否存在", "简化 SQL 结构"],
                    # ✅ 新增：传递列名白名单信息
                    "available_columns_hint": available_columns_hint,
                    "column_whitelist": column_whitelist,
                }
                
                # ✅ 如果错误是 Unknown column，构建详细的修复提示
                if "unknown column" in error_msg.lower() and available_columns_hint:
                    error_recovery_context["fix_prompt"] = f"""
【严重错误】SQL 执行失败，使用了不存在的列名！

错误信息: {error_msg}

【正确的列名信息 - 请严格使用以下列名】
{available_columns_hint}

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
4. 如果需要计算某个指标，请使用实际存在的列进行计算
"""
                
                return {
                    "messages": messages,
                    "execution_result": execution_result,
                    "current_stage": "error_recovery",
                    "error_recovery_context": error_recovery_context,  # ✅ 传递错误上下文
                    "error_history": state.get("error_history", []) + [{
                        "stage": "sql_execution",
                        "error": error_msg,
                        "sql_query": sql_query,
                        "retry_count": state.get("retry_count", 0),
                        "timestamp": time.time(),
                        # ✅ 新增：在 error_history 中也保存列名白名单
                        "column_whitelist": column_whitelist,
                        "available_columns": available_columns_hint
                    }]
                }
            
        except Exception as e:
            logger.error(f"SQL 执行失败: {str(e)}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="final_sql",
                    status="error",
                    result=str(e),
                    time_ms=0
                ))
            
            execution_result = SQLExecutionResult(
                success=False,
                error=str(e)
            )
            
            # ✅ 关键修复：从 state 中获取 schema_info，构建列名白名单
            error_msg = str(e)
            schema_info = state.get("schema_info", {})
            available_columns_hint = ""
            column_whitelist = {}
            
            if schema_info:
                columns_list = schema_info.get("columns", [])
                if columns_list:
                    for col in columns_list:
                        table_name = col.get("table_name", "")
                        col_name = col.get("column_name", "")
                        if table_name and col_name:
                            if table_name not in column_whitelist:
                                column_whitelist[table_name] = []
                            column_whitelist[table_name].append(col_name)
                    
                    available_columns_info = []
                    for table_name, cols in column_whitelist.items():
                        available_columns_info.append(f"表 `{table_name}` 的可用列: {', '.join(cols)}")
                    available_columns_hint = "\n".join(available_columns_info)
            
            # ✅ 关键修复：构建 error_recovery_context，包含列名白名单
            error_recovery_context = {
                "failed_sql": state.get("generated_sql", ""),
                "error_message": error_msg,
                "error_type": "sql_execution_exception",
                "recovery_steps": ["检查 SQL 语法", "检查表名和列名", "简化查询结构"],
                "available_columns_hint": available_columns_hint,
                "column_whitelist": column_whitelist,
            }
            
            # 如果错误是 Unknown column，构建详细的修复提示
            if "unknown column" in error_msg.lower() and available_columns_hint:
                error_recovery_context["fix_prompt"] = f"""
【严重错误】SQL 执行失败，使用了不存在的列名！

错误信息: {error_msg}

【正确的列名信息 - 请严格使用以下列名】
{available_columns_hint}

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
"""
            
            return {
                "messages": [AIMessage(content=f"SQL 执行失败: {error_msg}")],
                "execution_result": execution_result,
                "current_stage": "error_recovery",
                "error_recovery_context": error_recovery_context,
                "error_history": state.get("error_history", []) + [{
                    "stage": "sql_execution",
                    "error": error_msg,
                    "sql_query": state.get("generated_sql"),
                    "retry_count": state.get("retry_count", 0),
                    "column_whitelist": column_whitelist,
                    "available_columns": available_columns_hint
                }]
            }
    
    def _generate_chart_config(self, columns: list, rows: list) -> Dict[str, Any]:
        """
        根据数据生成 Recharts 图表配置
        """
        if not columns or not rows:
            return None
        
        # 分析列类型
        numeric_columns = []
        category_columns = []
        date_columns = []
        
        for col in columns:
            col_lower = col.lower()
            # 检测日期列
            if any(kw in col_lower for kw in ['date', 'time', '日期', '时间', 'day', 'month', 'year']):
                date_columns.append(col)
            # 检测分类列
            elif any(kw in col_lower for kw in ['name', 'type', 'category', '名称', '类型', '分类', 'id']):
                category_columns.append(col)
            else:
                # 检查第一行数据是否为数字
                if rows:
                    first_val = rows[0].get(col)
                    if isinstance(first_val, (int, float)):
                        numeric_columns.append(col)
                    else:
                        category_columns.append(col)
        
        # 决定图表类型
        chart_type = "line"  # 默认折线图
        if date_columns:
            x_axis = date_columns[0]
            chart_type = "line"
        elif category_columns:
            x_axis = category_columns[0]
            if len(rows) <= 10:
                chart_type = "bar"
            else:
                chart_type = "line"
        elif numeric_columns:
            x_axis = numeric_columns[0]
        else:
            x_axis = columns[0]
        
        # Y 轴选择数字列
        y_axis = numeric_columns[0] if numeric_columns else (columns[1] if len(columns) > 1 else columns[0])
        
        return {
            "type": chart_type,
            "xAxis": x_axis,
            "yAxis": y_axis,
            "dataKey": y_axis,
            "xDataKey": x_axis
        }
    
    def _extract_user_query(self, state: SQLMessageState) -> str:
        """从状态中提取用户原始查询（取最后一个 HumanMessage）"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                return content
        return ""
    
    async def _analyze_result(
        self,
        user_query: str,
        sql_query: str,
        result_data: Dict[str, Any]
    ) -> AIMessage:
        """
        使用 LLM 分析查询结果并生成自然语言回答
        """
        from langchain_core.messages import HumanMessage
        
        columns = result_data.get("columns", [])
        data = result_data.get("data", [])
        row_count = result_data.get("row_count", 0)
        
        # 构建数据摘要（限制数据量避免 token 过多）
        data_preview = data[:10] if len(data) > 10 else data
        
        prompt = f"""请根据以下查询结果，用简洁的自然语言回答用户的问题。

用户问题: {user_query}

执行的 SQL:
```sql
{sql_query}
```

查询结果:
- 列名: {columns}
- 数据行数: {row_count}
- 数据预览 (最多10行): {json.dumps(data_preview, ensure_ascii=False, default=str)}

请用简洁、专业的语言回答用户的问题，包括：
1. 直接回答用户的问题
2. 关键数据的总结
3. 如果数据为空，说明可能的原因

注意：不要重复输出完整的查询结果数据，只做总结分析。"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return AIMessage(content=response.content)
        except Exception as e:
            logger.warning(f"结果分析失败: {e}")
            # 回退到简单摘要
            if row_count == 0:
                summary = f"查询执行成功，但没有找到符合条件的数据。"
            else:
                summary = f"查询执行成功，共返回 {row_count} 条记录。"
            return AIMessage(content=summary)
    
    # 兼容旧接口
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """兼容旧的 process 接口"""
        return await self.execute(state)


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def sql_executor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    SQL 执行节点函数 - 用于 LangGraph 图
    
    这是一个独立的节点函数，可以直接在图中使用。
    不需要通过 Agent 类。
    """
    executor = SQLExecutorAgent()
    return await executor.execute(state)


# ============================================================================
# 导出
# ============================================================================

# 创建全局实例（兼容现有代码）
sql_executor_agent = SQLExecutorAgent()

__all__ = [
    "sql_executor_agent",
    "sql_executor_tool_node",
    "sql_executor_node",
    "execute_sql_query",
    "SQLExecutorAgent",
]
