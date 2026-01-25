"""
Schema 分析代理 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 InjectedState 注入状态参数
2. 工具返回标准格式 (字符串或 JSON)
3. 使用 ToolNode 配合 ReAct Agent

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/tool-calling
- https://langchain-ai.github.io/langgraph/reference/agents
"""
from typing import Dict, Any, Annotated
import json
import logging

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.core.message_utils import generate_tool_call_id
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, get_value_mappings, analyze_query_with_llm

logger = logging.getLogger(__name__)


# ============================================================================
# 工具定义 (使用 InjectedState 注入状态)
# ============================================================================

@tool
def analyze_user_query(query: str) -> str:
    """
    分析用户的自然语言查询，提取关键实体和意图
    
    Args:
        query: 用户的自然语言查询
        
    Returns:
        str: JSON 格式的分析结果，包含实体、关系和查询意图
    """
    try:
        analysis = analyze_query_with_llm(query)
        return json.dumps({
            "success": True,
            "analysis": analysis
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"查询分析失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
def retrieve_database_schema(
    query: str,
    state: Annotated[dict, InjectedState]
) -> str:
    """
    根据查询获取相关的数据库表结构信息
    
    Args:
        query: 用户查询
        state: 注入的状态 (自动从 LangGraph 状态获取 connection_id)
        
    Returns:
        str: JSON 格式的表结构和值映射信息
        
    注意:
        使用 InjectedState 自动获取 connection_id，无需显式传递
    """
    try:
        # 从状态中获取 connection_id
        connection_id = state.get("connection_id")
        if not connection_id:
            return json.dumps({
                "success": False,
                "error": "未指定数据库连接 ID"
            }, ensure_ascii=False)
        
        logger.info(f"检索数据库 schema, connection_id={connection_id}")
        
        from app.db.session import get_db_session
        with get_db_session() as db:
            # 获取相关表结构
            schema_context = retrieve_relevant_schema(
                db=db,
                connection_id=connection_id,
                query=query
            )
            
            # 获取值映射
            value_mappings = get_value_mappings(db, schema_context)
            
            return json.dumps({
                "success": True,
                "schema_context": schema_context,
                "value_mappings": value_mappings,
                "connection_id": connection_id
            }, ensure_ascii=False, default=str)
            
    except Exception as e:
        logger.error(f"Schema 检索失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# Schema 分析代理类
# ============================================================================

class SchemaAnalysisAgent:
    """
    Schema 分析代理 - 使用 InjectedState 优化
    
    重要变更:
    - retrieve_database_schema 工具现在使用 InjectedState 获取 connection_id
    - 无需在提示词中显式传递 connection_id
    """
    
    def __init__(self):
        self.name = "schema_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_user_query, retrieve_database_schema]
        
        # 创建 ReAct 代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name,
            state_schema=SQLMessageState  # 指定状态 schema，让 InjectedState 能正确注入
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的数据库模式分析专家。

**核心职责**: 分析用户查询，获取相关的数据库表结构信息

**工作流程**:
1. 使用 analyze_user_query 工具分析用户查询意图
2. 使用 retrieve_database_schema 工具获取相关表结构
   - connection_id 会自动从状态中获取，无需手动传递
3. **只返回模式信息，不生成 SQL，不预测结果**

**输出内容**:
- 相关的表和字段信息
- 必要的值映射信息

**禁止的行为**:
- ❌ 不要生成 SQL 语句
- ❌ 不要预测查询结果
- ❌ 不要重复调用工具

**输出格式**: 只返回工具调用结果，包含表结构和值映射信息"""
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        处理 Schema 分析任务 - 返回标准工具调用格式
        
        性能优化 (2026-01-22):
        - 使用异步并行版本 retrieve_relevant_schema_async
        - 批量获取列和关系
        - 预期提升: 20s -> 8-12s
        """
        import time
        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_sql_step_event
        from app.services.text2sql_utils import retrieve_relevant_schema_async, get_value_mappings
        from app.db.session import SessionLocal
        
        try:
            # 获取 stream writer
            try:
                writer = get_stream_writer()
            except Exception:
                writer = None
            
            # 发送 schema_mapping 步骤开始事件
            step_start_time = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="schema_mapping",
                    status="running",
                    result=None,
                    time_ms=0
                ))
            
            # 获取用户查询（优先使用 enriched_query）
            messages = state.get("messages", [])
            user_query = state.get("enriched_query")  # 优先使用增强后的查询
            
            if not user_query:
                # 从消息中获取最后一个 HumanMessage（最新的用户查询）
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        user_query = msg.content
                        if isinstance(user_query, list):
                            user_query = user_query[0].get("text", "") if user_query else ""
                        break
            
            if not user_query:
                raise ValueError("无法获取用户查询")
            
            connection_id = state.get("connection_id")
            
            # ✅ 使用异步并行版本获取 schema（性能优化）
            logger.info(f"异步并行获取 schema 信息, connection_id={connection_id}")
            
            from app.db.session import get_db_session
            with get_db_session() as db:
                # 使用异步并行版本
                schema_context = await retrieve_relevant_schema_async(
                    db=db,
                    connection_id=connection_id,
                    query=user_query
                )
                
                # 获取值映射
                value_mappings = get_value_mappings(db, schema_context)
            
            # 计算耗时并发送完成事件（包含详细的表和列信息）
            elapsed_ms = int((time.time() - step_start_time) * 1000)
            tables_list = schema_context.get("tables", [])
            columns_list = schema_context.get("columns", [])
            
            # 构建详细的 schema 信息用于前端展示
            schema_detail = {
                "summary": f"获取到 {len(tables_list)} 个相关表, {len(columns_list)} 个列",
                "tables": []
            }
            
            # 按表组织列信息
            table_columns_map = {}
            for col in columns_list:
                table_name = col.get("table_name", "unknown")
                if table_name not in table_columns_map:
                    table_columns_map[table_name] = []
                table_columns_map[table_name].append({
                    "name": col.get("column_name", ""),
                    "type": col.get("data_type", ""),
                    "comment": col.get("column_comment", "")
                })
            
            # 构建表信息列表
            for table in tables_list:
                table_name = table.get("table_name", "")
                schema_detail["tables"].append({
                    "name": table_name,
                    "comment": table.get("table_comment", ""),
                    "columns": table_columns_map.get(table_name, [])
                })
            
            if writer:
                writer(create_sql_step_event(
                    step="schema_mapping",
                    status="completed",
                    result=json.dumps(schema_detail, ensure_ascii=False),
                    time_ms=elapsed_ms
                ))
            
            logger.info(f"Schema 获取成功 (并行优化): {len(tables_list)} 个表, {len(columns_list)} 个列 [{elapsed_ms}ms]")
            
            # 构建 schema_info 存储到状态
            schema_info = {
                "tables": schema_context,  # 完整的 schema 上下文
                "value_mappings": value_mappings,
                "connection_id": connection_id
            }
            
            # ✅ 创建标准工具调用消息格式
            tool_call_id = generate_tool_call_id("retrieve_database_schema", {
                "query": user_query,
                "connection_id": connection_id
            })
            
            # AIMessage 包含 tool_calls
            ai_message = AIMessage(
                content="",  # 状态通过 QueryPipeline 组件展示，不需要文字
                tool_calls=[{
                    "name": "retrieve_database_schema",
                    "args": {
                        "query": user_query,
                        "connection_id": connection_id
                    },
                    "id": tool_call_id,
                    "type": "tool_call"
                }]
            )
            
            # ToolMessage 包含工具执行结果
            table_names = [t.get("name", "") for t in tables_list]
            tool_result = {
                "status": "success",
                "data": {
                    "table_count": len(tables_list),
                    "column_count": len(columns_list),
                    "tables": table_names,
                    "has_value_mappings": bool(value_mappings)
                },
                "metadata": {
                    "connection_id": connection_id,
                    "elapsed_ms": elapsed_ms
                }
            }
            
            tool_message = ToolMessage(
                content=json.dumps(tool_result, ensure_ascii=False),
                tool_call_id=tool_call_id,
                name="retrieve_database_schema"
            )
            
            return {
                "messages": [ai_message, tool_message],
                "schema_info": schema_info,
                "current_stage": "sql_generation"
            }
            
        except Exception as e:
            logger.error(f"Schema 分析失败: {str(e)}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="schema_mapping",
                    status="error",
                    result=str(e),
                    time_ms=0
                ))
            
            # 错误时也返回标准格式
            error_tool_call_id = generate_tool_call_id("retrieve_database_schema", {"error": str(e)})
            
            ai_message = AIMessage(
                content="",  # 状态通过 QueryPipeline 组件展示，不需要文字
                tool_calls=[{
                    "name": "retrieve_database_schema",
                    "args": {},
                    "id": error_tool_call_id,
                    "type": "tool_call"
                }]
            )
            
            tool_message = ToolMessage(
                content=json.dumps({
                    "status": "error",
                    "error": str(e)
                }, ensure_ascii=False),
                tool_call_id=error_tool_call_id,
                name="retrieve_database_schema"
            )
            
            return {
                "messages": [ai_message, tool_message],
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "schema_analysis",
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0)
                }]
            }


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def schema_analysis_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema 分析节点函数 - 用于 LangGraph 图
    """
    agent = SchemaAnalysisAgent()
    return await agent.process(state)


# ============================================================================
# 导出
# ============================================================================

# 创建全局实例（兼容现有代码）
schema_agent = SchemaAnalysisAgent()

__all__ = [
    "schema_agent",
    "schema_analysis_node",
    "analyze_user_query",
    "retrieve_database_schema",
    "SchemaAnalysisAgent",
]
