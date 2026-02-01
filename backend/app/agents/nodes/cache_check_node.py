"""
缓存检查节点 (Cache Check Node)

全局缓存检查，是三级缓存策略的第二级和第三级：
1. Thread 历史检查 (thread_history_check_node) - 已在上一节点处理
2. 全局精确缓存 (本节点) - 100% 匹配，直接执行返回
3. 全局语义缓存 (本节点) - >=95% 相似度，保存SQL模板进入澄清

工作流程:
1. 从消息中提取用户查询
2. 检查精确匹配缓存（L1）
3. 检查语义匹配缓存（L2）
4. 精确命中: 执行SQL，发送流式事件，返回结果
5. 语义命中: 保存SQL模板，进入澄清节点
6. 未命中: 进入澄清节点

缓存策略:
- 精确匹配 (exact): 相同查询 + 相同连接ID -> 直接执行返回
- 语义匹配 (semantic): 相似度 >= 0.95 -> 保存模板，进入澄清

LangGraph 官方规范:
- 使用 StreamWriter 参数注入发送流式事件
- 参考: https://langchain-ai.github.io/langgraph/concepts/streaming/
"""
import logging
import json
import time
import re
from typing import Dict, Any, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState, SQLExecutionResult, extract_connection_id
from app.services.query_cache_service import get_cache_service, CacheHit

# 配置日志
logger = logging.getLogger(__name__)


def extract_user_query(messages: list) -> Optional[str]:
    """
    从消息列表中提取最新的用户查询
    
    Args:
        messages: LangChain 消息列表
        
    Returns:
        用户查询字符串，如果没有找到则返回 None
    """
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            return _normalize_query_content(message.content)
        elif isinstance(message, HumanMessage):
            return _normalize_query_content(message.content)
    return None


def _normalize_query_content(content: Any) -> Optional[str]:
    """
    规范化用户查询内容，兼容多模态消息格式
    """
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


def _clean_sql(sql: str) -> str:
    """
    清理可能被污染的 SQL
    
    修复 Milvus 存储时的污染问题
    """
    if not sql:
        return sql
    
    # 移除可能的 JSON 污染: ;", "connection_id": xxx; 或类似模式
    clean_sql = re.sub(r';\s*"\s*,\s*"connection_id"\s*:\s*\d+\s*;?\s*$', ';', sql)
    clean_sql = clean_sql.strip()
    
    # 确保 SQL 以分号结尾
    if clean_sql and not clean_sql.endswith(';'):
        clean_sql += ';'
    
    return clean_sql


def _generate_chart_config(columns: list, rows: list) -> Optional[Dict[str, Any]]:
    """
    根据数据生成图表配置
    """
    if not columns or not rows:
        return None
    
    # 分析列类型
    numeric_columns = []
    category_columns = []
    date_columns = []
    
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ['date', 'time', '日期', '时间', 'day', 'month', 'year']):
            date_columns.append(col)
        elif any(kw in col_lower for kw in ['name', 'type', 'category', '名称', '类型', '分类', 'id']):
            category_columns.append(col)
        else:
            if rows:
                first_val = rows[0].get(col) if isinstance(rows[0], dict) else None
                if isinstance(first_val, (int, float)):
                    numeric_columns.append(col)
                else:
                    category_columns.append(col)
    
    # 决定图表类型
    chart_type = "bar"
    if date_columns:
        x_axis = date_columns[0]
        chart_type = "line"
    elif category_columns:
        x_axis = category_columns[0]
        chart_type = "bar" if len(rows) <= 10 else "line"
    elif numeric_columns:
        x_axis = numeric_columns[0]
    else:
        x_axis = columns[0]
    
    y_axis = numeric_columns[0] if numeric_columns else (columns[1] if len(columns) > 1 else columns[0])
    
    return {
        "type": chart_type,
        "xAxis": x_axis,
        "yAxis": y_axis,
        "dataKey": y_axis,
        "xDataKey": x_axis
    }


def _send_cache_hit_stream_events(
    writer: StreamWriter,
    cache_hit: CacheHit,
    exec_result: Dict[str, Any],
    connection_id: int,
    elapsed_ms: int,
    user_query: str
):
    """
    发送缓存命中时的流式事件（使用注入的 StreamWriter）
    
    遵循 LangGraph 官方规范：使用参数注入的 StreamWriter
    
    包括: cache_hit, intent_analysis, sql_step, data_query
    
    Args:
        writer: LangGraph StreamWriter，用于发送流式事件
        cache_hit: 缓存命中结果
        exec_result: SQL执行结果
        connection_id: 数据库连接ID
        elapsed_ms: 耗时(毫秒)
        user_query: 用户查询
    """
    from app.schemas.stream_events import (
        create_cache_hit_event,
        create_intent_analysis_event,
        create_sql_step_event,
        create_data_query_event
    )
    
    # 1. 发送缓存命中事件
    hit_type = "exact" if cache_hit.hit_type == "exact" else "semantic"
    writer(create_cache_hit_event(
        hit_type=hit_type,
        similarity=cache_hit.similarity,
        original_query=cache_hit.query[:100] if cache_hit.query else None,
        time_ms=elapsed_ms
    ))
    
    # 2. 发送意图解析事件
    # 获取数据集名称
    dataset_name = "默认数据集"
    try:
        from app.db.session import get_db_session
        from app.crud.crud_db_connection import db_connection as crud_connection
        with get_db_session() as db:
            conn = crud_connection.get(db=db, id=connection_id)
            if conn:
                dataset_name = conn.name or conn.database
    except Exception:
        pass
    
    writer(create_intent_analysis_event(
        dataset=dataset_name,
        query_mode="缓存模式",
        metrics=["缓存结果"],
        filters={},
        time_ms=elapsed_ms
    ))
    
    # 3. 发送SQL步骤事件（标记为缓存命中）
    writer(create_sql_step_event(
        step="few_shot",
        status="completed",
        result=f"缓存命中 ({hit_type})",
        time_ms=0
    ))
    
    writer(create_sql_step_event(
        step="llm_parse",
        status="completed",
        result="使用缓存SQL",
        time_ms=0
    ))
    
    writer(create_sql_step_event(
        step="final_sql",
        status="completed",
        result=cache_hit.sql[:100] + "..." if len(cache_hit.sql) > 100 else cache_hit.sql,
        time_ms=elapsed_ms
    ))
    
    # 4. 发送数据查询事件
    if exec_result and exec_result.get("success"):
        data = exec_result.get("data", {})
        columns = data.get("columns", [])
        raw_rows = data.get("data", [])
        row_count = data.get("row_count", len(raw_rows))
        
        # 转换数据格式
        rows = []
        for raw_row in raw_rows:
            if isinstance(raw_row, list) and len(raw_row) == len(columns):
                rows.append(dict(zip(columns, raw_row)))
            elif isinstance(raw_row, dict):
                rows.append(raw_row)
        
        # 生成图表配置
        chart_config = _generate_chart_config(columns, rows)
        
        writer(create_data_query_event(
            columns=columns,
            rows=rows[:100],
            row_count=row_count,
            chart_config=chart_config,
            title=user_query[:50] if user_query else None
        ))
    
    logger.info("✓ 缓存命中流式事件已发送")


async def cache_check_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    缓存检查节点 - LangGraph 异步节点函数
    
    遵循 LangGraph 官方规范：
    - 使用 StreamWriter 参数注入发送流式事件
    - 节点签名: (state, writer) -> dict
    - 参考: https://langchain-ai.github.io/langgraph/concepts/streaming/
    
    三级缓存策略的第二/三级：
    - 精确命中 (100%): 执行SQL，发送流式事件，直接返回结果
    - 语义命中 (>=95%): 保存SQL模板，进入澄清节点确认
    - 未命中: 进入澄清节点，走完整流程
    
    Args:
        state: 当前的 SQL 消息状态
        writer: LangGraph StreamWriter，用于发送流式事件
        
    Returns:
        Dict[str, Any]: 状态更新
            - cache_hit: 是否命中缓存
            - cache_hit_type: 命中类型 ("exact" / "semantic" / None)
            - generated_sql: 缓存的 SQL（精确命中时）
            - cached_sql_template: SQL 模板（语义命中时）
            - execution_result: 执行结果（精确命中时）
    """
    logger.info("=== 进入全局缓存检查节点 ===")
    
    start_time = time.time()
    
    # 0. 检查是否正在等待澄清回复
    pending_clarification = state.get("pending_clarification", False)
    if pending_clarification:
        logger.info("正在等待用户澄清回复，跳过缓存检查")
        return {
            "cache_hit": False,
            "cache_hit_type": None
        }
    
    # 1. 获取消息和连接ID
    messages = state.get("messages", [])
    connection_id = state.get("connection_id") or extract_connection_id(state)
    
    # 多租户安全: 无连接ID则跳过缓存检查
    if not connection_id:
        logger.warning("未指定 connection_id，跳过缓存检查")
        return {
            "cache_hit": False,
            "cache_hit_type": None
        }
    
    # 提取用户查询
    user_query = extract_user_query(messages)
    if not user_query:
        logger.warning("无法提取用户查询，跳过缓存检查")
        return {
            "cache_hit": False,
            "cache_hit_type": None
        }
    
    logger.info(f"缓存检查: query='{user_query[:50]}...', connection_id={connection_id}")
    
    # 2. 检查缓存
    try:
        cache_service = get_cache_service()
        cache_hit = await cache_service.check_cache(user_query, connection_id)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if not cache_hit:
            logger.info(f"缓存未命中 (耗时: {elapsed_ms}ms)")
            
            # 清理消息历史
            from app.core.message_utils import validate_and_fix_message_history
            clean_messages = validate_and_fix_message_history(list(messages))
            
            return {
                "cache_hit": False,
                "cache_hit_type": None,
                "messages": clean_messages
            }
        
        logger.info(f"缓存命中! type={cache_hit.hit_type}, similarity={cache_hit.similarity:.3f}")
        
        # ====================================================================
        # 区分精确命中和语义命中
        # ====================================================================
        
        is_exact_hit = (
            cache_hit.hit_type == "exact" or 
            cache_hit.hit_type == "exact_text" or
            cache_hit.similarity >= 1.0
        )
        
        if is_exact_hit:
            # ================================================================
            # 精确命中: 执行SQL，发送流式事件，直接返回结果
            # ================================================================
            logger.info("精确缓存命中，执行SQL并返回结果")
            
            clean_sql = _clean_sql(cache_hit.sql)
            
            # 执行 SQL
            exec_result = None
            if cache_hit.result is None:
                try:
                    from app.agents.agents.sql_executor_agent import execute_sql_query
                    
                    exec_result_str = execute_sql_query.invoke({
                        "sql_query": clean_sql,
                        "connection_id": connection_id,
                        "timeout": 30
                    })
                    
                    exec_result = json.loads(exec_result_str) if isinstance(exec_result_str, str) else exec_result_str
                    
                    if not exec_result.get("success"):
                        # SQL 执行失败，可能是schema变更，降级为未命中
                        logger.warning(f"缓存 SQL 执行失败: {exec_result.get('error')}")
                        
                        from app.core.message_utils import validate_and_fix_message_history
                        clean_messages = validate_and_fix_message_history(list(messages))
                        
                        return {
                            "cache_hit": False,
                            "cache_hit_type": None,
                            "messages": clean_messages
                        }
                        
                except Exception as e:
                    logger.error(f"缓存 SQL 执行异常: {e}")
                    
                    from app.core.message_utils import validate_and_fix_message_history
                    clean_messages = validate_and_fix_message_history(list(messages))
                    
                    return {
                        "cache_hit": False,
                        "cache_hit_type": None,
                        "messages": clean_messages
                    }
            else:
                exec_result = cache_hit.result
            
            # 发送流式事件（使用注入的 StreamWriter）
            _send_cache_hit_stream_events(
                writer=writer,
                cache_hit=cache_hit,
                exec_result=exec_result,
                connection_id=connection_id,
                elapsed_ms=elapsed_ms,
                user_query=user_query
            )
            
            # 构建执行结果
            execution_result = SQLExecutionResult(
                success=True,
                data=exec_result.get("data") if isinstance(exec_result, dict) else exec_result,
                error=None,
                execution_time=exec_result.get("execution_time", 0) if isinstance(exec_result, dict) else 0,
                rows_affected=exec_result.get("data", {}).get("row_count", 0) if isinstance(exec_result, dict) else 0
            )
            
            # 构建 AI 消息
            response_content = f"""✨ **缓存命中** (精确匹配)

**SQL 查询:**
```sql
{cache_hit.sql}
```

查询已执行，结果已通过图表展示。"""
            
            ai_message = AIMessage(content=response_content)
            
            from app.core.message_utils import validate_and_fix_message_history
            clean_messages = validate_and_fix_message_history(list(messages))
            
            return {
                "cache_hit": True,
                "cache_hit_type": "exact",
                "generated_sql": cache_hit.sql,
                "execution_result": execution_result,
                "current_stage": "completed",
                "messages": clean_messages + [ai_message]
            }
        
        else:
            # ================================================================
            # 语义命中: 保存SQL模板，进入澄清节点确认
            # ================================================================
            logger.info(f"语义缓存命中 (相似度: {cache_hit.similarity:.1%})，保存SQL模板进入澄清")
            
            # 发送语义命中事件（使用注入的 StreamWriter）
            from app.schemas.stream_events import create_cache_hit_event
            
            writer(create_cache_hit_event(
                hit_type="semantic",
                similarity=cache_hit.similarity,
                original_query=cache_hit.query[:100] if cache_hit.query else None,
                time_ms=elapsed_ms
            ))
            
            from app.core.message_utils import validate_and_fix_message_history
            clean_messages = validate_and_fix_message_history(list(messages))
            
            return {
                "cache_hit": True,
                "cache_hit_type": "semantic",
                "cached_sql_template": cache_hit.sql,  # 保存模板供后续使用
                "cache_similarity": cache_hit.similarity,
                "cache_matched_query": cache_hit.query,
                "messages": clean_messages
            }
            
    except Exception as e:
        logger.error(f"缓存检查失败: {e}")
        
        from app.core.message_utils import validate_and_fix_message_history
        messages = state.get("messages", [])
        clean_messages = validate_and_fix_message_history(list(messages))
        
        return {
            "cache_hit": False,
            "cache_hit_type": None,
            "messages": clean_messages
        }



