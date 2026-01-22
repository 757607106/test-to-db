"""
SQL 执行代理 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 ToolNode 替代 ReAct Agent (SQL 执行不需要推理)
2. 直接执行工具，避免不必要的 LLM 调用
3. 内置缓存机制防止重复执行

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/tool-calling
- https://langchain-ai.github.io/langgraph/reference/prebuilt/#toolnode
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
    """
    执行 SQL 查询 - 带缓存防止重复执行
    
    Args:
        sql_query: SQL 查询语句
        connection_id: 数据库连接 ID
        timeout: 超时时间（秒）
        
    Returns:
        str: JSON 格式的查询执行结果
        
    注意:
        - 工具返回 JSON 字符串，符合 LangChain 标准
        - 内置缓存机制，防止重复执行
        - 只缓存 SELECT 查询，不缓存修改操作
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
        from app.services.db_service import get_db_connection_by_id, execute_query_with_connection
        
        # 获取数据库连接
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            return json.dumps({
                "success": False,
                "error": f"找不到连接 ID 为 {connection_id} 的数据库连接",
                "from_cache": False
            }, ensure_ascii=False)
        
        # 执行查询
        start_time = time.time()
        result_data = execute_query_with_connection(connection, sql_query)
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
# SQL 执行节点 (使用 ToolNode - 官方推荐)
# ============================================================================

# 创建 ToolNode - 官方推荐用于不需要推理的工具调用
sql_executor_tool_node = ToolNode(
    tools=[execute_sql_query],
    handle_tool_errors=True  # 自动处理工具错误
)


class SQLExecutorAgent:
    """
    SQL 执行代理 - 使用 ToolNode 实现
    
    重要变更 (2026-01):
    - 移除了 ReAct Agent，改用 ToolNode
    - SQL 执行不需要推理，直接调用工具即可
    - 大幅减少 LLM 调用次数
    
    官方推荐:
    - 对于简单的工具调用场景，使用 ToolNode
    - 只有需要推理的场景才使用 ReAct Agent
    """
    
    def __init__(self):
        self.name = "sql_executor_agent"
        self.tools = [execute_sql_query]
        # 使用 ToolNode 而不是 ReAct Agent
        self.tool_node = sql_executor_tool_node
        
        # 为了兼容现有的 supervisor 接口，创建一个伪 agent
        # 实际执行时会直接调用工具
        self._create_compatible_agent()
    
    def _create_compatible_agent(self):
        """
        创建兼容现有 supervisor 接口的 agent
        
        注意: 这是为了向后兼容。在完成 supervisor 重构后可以移除。
        """
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
        """创建系统提示 - 只负责执行，不负责总结"""
        return """你是一个 SQL 执行专家。

**核心职责**: 执行 SQL 查询，返回原始数据

**执行规则**:
1. 使用 execute_sql_query 工具执行 SQL 查询（仅一次）
2. 返回工具执行的原始结果
3. **禁止生成查询结果的总结或解读**
4. **禁止重复调用工具**

**禁止的行为**:
- ❌ 不要生成"根据查询结果..."这样的总结
- ❌ 不要解读或分析查询数据
- ❌ 不要重复调用工具
- ❌ 不要添加任何额外说明

**你的输出**: 只返回工具调用结果，不添加任何文字"""
    
    async def execute(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        执行 SQL 查询 - 直接调用工具，避免 LLM 推理
        
        这是推荐的执行方式，不经过 ReAct 循环。
        执行成功后会调用 LLM 分析结果并生成自然语言回答。
        """
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
                # 执行成功，进入数据分析阶段
                # 流程：sql_execution → analysis → chart_generation → completed
                skip_chart = state.get("skip_chart_generation", False)
                if skip_chart:
                    # 快速模式：跳过数据分析和图表生成，直接做简单分析
                    user_query = self._extract_user_query(state)
                    analysis_message = await self._analyze_result(
                        user_query=user_query,
                        sql_query=sql_query,
                        result_data=result.get("data", {})
                    )
                    messages.append(analysis_message)
                    next_stage = "completed"
                else:
                    # 标准模式：进入数据分析阶段（由 DataAnalystAgent 处理）
                    next_stage = "analysis"
            else:
                next_stage = "error_recovery"
            
            return {
                "messages": messages,
                "execution_result": execution_result,
                "current_stage": next_stage
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
            
            return {
                "messages": [AIMessage(content=f"SQL 执行失败: {str(e)}")],
                "execution_result": execution_result,
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "sql_execution",
                    "error": str(e),
                    "sql_query": state.get("generated_sql"),
                    "retry_count": state.get("retry_count", 0)
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
        """从状态中提取用户原始查询"""
        messages = state.get("messages", [])
        for msg in messages:
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
