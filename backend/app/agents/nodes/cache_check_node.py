"""
缓存检查节点 (Cache Check Node)

在 clarification 之后、supervisor 之前检查查询缓存。
如果命中缓存，直接返回结果，跳过后续流程。

工作流程:
1. 从消息中提取用户查询
2. 检查精确匹配缓存（L1）
3. 检查语义匹配缓存（L2）
4. 如果命中，设置结果并标记跳过 supervisor
5. 如果未命中，继续正常流程

缓存策略:
- 精确匹配：相同查询 + 相同连接ID
- 语义匹配：相似度 >= 0.95 的历史 QA 对
"""
import logging
import json
from typing import Dict, Any, Optional

from langchain_core.messages import AIMessage, HumanMessage

from app.core.state import SQLMessageState, SQLExecutionResult
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


def format_cached_response(cache_hit: CacheHit, connection_id: int) -> str:
    """
    格式化缓存命中的响应
    
    Args:
        cache_hit: 缓存命中结果
        connection_id: 数据库连接ID
        
    Returns:
        格式化的响应字符串
    """
    hit_type_label = "精确匹配" if cache_hit.hit_type == "exact" else f"语义匹配 (相似度: {cache_hit.similarity:.1%})"
    
    response_parts = [
        f"✨ **缓存命中** ({hit_type_label})",
        "",
        f"**SQL 查询:**",
        f"```sql",
        f"{cache_hit.sql}",
        f"```",
    ]
    
    # 添加执行结果（如果有）
    if cache_hit.result is not None:
        result = cache_hit.result
        if isinstance(result, dict):
            if result.get("success"):
                raw_data = result.get("data", [])
                
                # ✅ 兼容两种数据格式：
                # 1. 直接列表: [{"col1": val1, ...}, ...]
                # 2. 嵌套格式: {"columns": [...], "data": [[val1, val2, ...], ...]}
                if isinstance(raw_data, dict) and "columns" in raw_data and "data" in raw_data:
                    # 嵌套格式，转换为字典列表
                    columns = raw_data.get("columns", [])
                    rows = raw_data.get("data", [])
                    data = [dict(zip(columns, row)) for row in rows] if columns and rows else []
                elif isinstance(raw_data, list):
                    data = raw_data
                else:
                    data = []
                
                if len(data) > 0:
                    response_parts.extend([
                        "",
                        f"**查询结果:** (共 {len(data)} 条记录)",
                        "",
                    ])
                    # 格式化表格
                    if isinstance(data[0], dict):
                        headers = list(data[0].keys())
                        response_parts.append("| " + " | ".join(headers) + " |")
                        response_parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
                        for row in data[:10]:  # 最多显示10行
                            values = [str(row.get(h, ""))[:30] for h in headers]  # 截断长值
                            response_parts.append("| " + " | ".join(values) + " |")
                        if len(data) > 10:
                            response_parts.append(f"... 还有 {len(data) - 10} 条记录")
                else:
                    response_parts.extend([
                        "",
                        "**查询结果:** 无数据",
                    ])
            else:
                response_parts.extend([
                    "",
                    f"**执行错误:** {result.get('error', '未知错误')}",
                ])
    else:
        response_parts.extend([
            "",
            "📝 *SQL 已从缓存获取，正在执行...*",
        ])
    
    return "\n".join(response_parts)


async def cache_check_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    缓存检查节点 - LangGraph 异步节点函数
    
    在 clarification 之后、supervisor 之前检查查询缓存。
    如果命中缓存，直接返回结果，跳过 supervisor。
    
    Args:
        state: 当前的 SQL 消息状态
        
    Returns:
        Dict[str, Any]: 状态更新
            - cache_hit: 是否命中缓存
            - generated_sql: 缓存的 SQL（如果命中）
            - execution_result: 缓存的执行结果（如果有）
            - messages: 添加 AI 响应消息（如果命中）
            
    状态字段:
        读取:
        - messages: 获取用户查询
        - connection_id: 数据库连接ID
        - pending_clarification: 是否正在等待澄清（跳过缓存检查）
        
        更新:
        - cache_hit: 是否命中缓存
        - cache_hit_type: 命中类型 ("exact" / "semantic" / None)
        - generated_sql: SQL 语句
        - execution_result: 执行结果
        - current_stage: 当前阶段
    """
    logger.info("=== 进入缓存检查节点 ===")
    
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
    connection_id = state.get("connection_id", 15)
    
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
        
        if cache_hit:
            logger.info(f"缓存命中! type={cache_hit.hit_type}, similarity={cache_hit.similarity:.3f}")

            # 如果没有执行结果，直接在此节点执行 SQL 并返回结果
            if cache_hit.result is None:
                # ✅ 清理可能被污染的 SQL（修复 Milvus 存储时的污染问题）
                clean_sql = cache_hit.sql
                if clean_sql:
                    # 移除可能的 JSON 污染: ;", "connection_id": xxx; 或类似模式
                    import re
                    # 匹配 SQL 语句末尾的污染部分
                    clean_sql = re.sub(r';\s*"\s*,\s*"connection_id"\s*:\s*\d+\s*;?\s*$', ';', clean_sql)
                    clean_sql = clean_sql.strip()
                    # 确保 SQL 以分号结尾
                    if clean_sql and not clean_sql.endswith(';'):
                        clean_sql += ';'
                
                # ✅ 直接执行 SQL，避免走完整的 supervisor 流程
                try:
                    from app.agents.agents.sql_executor_agent import execute_sql_query
                    
                    exec_result_str = execute_sql_query.invoke({
                        "sql_query": clean_sql,  # 使用清理后的 SQL
                        "connection_id": connection_id,
                        "timeout": 30
                    })
                    
                    # ✅ execute_sql_query 返回的是 JSON 字符串，需要解析
                    exec_result = json.loads(exec_result_str) if isinstance(exec_result_str, str) else exec_result_str
                    
                    if exec_result.get("success"):
                        # 构建执行结果
                        execution_result = SQLExecutionResult(
                            success=True,
                            data=exec_result.get("data"),
                            error=None,
                            execution_time=exec_result.get("execution_time", 0),
                            rows_affected=exec_result.get("data", {}).get("row_count", 0) if isinstance(exec_result.get("data"), dict) else 0
                        )
                        
                        # 构建缓存命中响应
                        cache_hit.result = {
                            "success": True,
                            "data": exec_result.get("data")
                        }
                        response_content = format_cached_response(cache_hit, connection_id)
                        ai_message = AIMessage(content=response_content)
                        
                        return {
                            "cache_hit": True,
                            "cache_hit_type": cache_hit.hit_type,
                            "generated_sql": cache_hit.sql,
                            "execution_result": execution_result,
                            "current_stage": "completed",
                            "messages": list(messages) + [ai_message]
                        }
                    else:
                        # SQL 执行失败，重新开始完整流程（数据库schema可能已变更）
                        logger.warning(f"缓存 SQL 执行失败: {exec_result.get('error')}")
                        logger.info("缓存SQL可能已过时，将重新分析数据库schema并生成新的SQL")
                        
                        # ✅ 清理并验证消息历史，移除不完整的tool_calls
                        from app.core.message_utils import validate_and_fix_message_history
                        clean_messages = validate_and_fix_message_history(list(messages))
                        
                        return {
                            "cache_hit": False,
                            "cache_hit_type": None,  # 标记为完全未命中
                            "current_stage": "schema_analysis",  # 从schema分析重新开始
                            "messages": clean_messages  # 返回清理后的消息历史
                        }
                        
                except Exception as e:
                    logger.error(f"缓存 SQL 执行异常: {e}")
                    logger.info("缓存SQL执行异常，将重新分析数据库schema并生成新的SQL")
                    
                    # ✅ 清理并验证消息历史，移除不完整的tool_calls
                    from app.core.message_utils import validate_and_fix_message_history
                    clean_messages = validate_and_fix_message_history(list(messages))
                    
                    return {
                        "cache_hit": False,
                        "cache_hit_type": None,  # 标记为完全未命中
                        "current_stage": "schema_analysis",  # 从schema分析重新开始
                        "messages": clean_messages  # 返回清理后的消息历史
                    }

            # 有执行结果，直接返回缓存结果并结束
            # ✅ 清理并验证消息历史，移除不完整的tool_calls
            from app.core.message_utils import validate_and_fix_message_history
            clean_messages = validate_and_fix_message_history(list(messages))
            
            response_content = format_cached_response(cache_hit, connection_id)
            ai_message = AIMessage(content=response_content)
            
            updates = {
                "cache_hit": True,
                "cache_hit_type": cache_hit.hit_type,
                "generated_sql": cache_hit.sql,
                "current_stage": "completed",  # ✅ 修复：使用正确的stage值
                "execution_result": SQLExecutionResult(
                    success=cache_hit.result.get("success", True) if isinstance(cache_hit.result, dict) else True,
                    data=cache_hit.result.get("data") if isinstance(cache_hit.result, dict) else cache_hit.result,
                    error=cache_hit.result.get("error") if isinstance(cache_hit.result, dict) else None
                ),
                "messages": clean_messages + [ai_message]  # ✅ 使用清理后的消息历史
            }
            
            return updates
        
        else:
            logger.info("缓存未命中，继续正常流程")
            
            # ✅ 即使缓存未命中，也清理消息历史中的不完整tool_calls
            from app.core.message_utils import validate_and_fix_message_history
            clean_messages = validate_and_fix_message_history(list(messages))
            
            return {
                "cache_hit": False,
                "cache_hit_type": None,
                "messages": clean_messages
            }
            
    except Exception as e:
        logger.error(f"缓存检查失败: {e}")
        
        # ✅ 异常情况下也清理消息历史
        from app.core.message_utils import validate_and_fix_message_history
        messages = state.get("messages", [])
        clean_messages = validate_and_fix_message_history(list(messages))
        
        return {
            "cache_hit": False,
            "cache_hit_type": None,
            "messages": clean_messages
        }


def cache_check_node_sync(state: SQLMessageState) -> Dict[str, Any]:
    """
    缓存检查节点的同步包装器
    
    用于在同步上下文中调用异步的 cache_check_node
    """
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
        # 有运行中的事件循环，使用 run_coroutine_threadsafe
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(cache_check_node(state))
            )
            return future.result(timeout=10)
    except RuntimeError:
        # 没有运行中的事件循环
        return asyncio.run(cache_check_node(state))
