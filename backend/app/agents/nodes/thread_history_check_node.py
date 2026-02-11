"""
Thread 历史检查节点 (Thread History Check Node)

检查同一对话（thread）内是否有相同问题的历史回答。
如果找到，直接返回历史结果，跳过完整执行流程。

这是三级缓存策略的第一级：
1. Thread 历史检查 (本文件) - 同一对话内相同问题
2. 全局精确缓存 - query_cache_service
3. 全局语义缓存 - Milvus 向量检索

工作流程:
1. 从消息历史中提取当前用户查询
2. 遍历历史消息，查找相同问题的 Human-AI 消息对
3. 如果找到，发送流式事件并返回历史结果
4. 如果未找到，继续下一个节点

LangGraph 官方规范:
- 使用 StreamWriter 参数注入发送流式事件
- 参考: https://langchain-ai.github.io/langgraph/concepts/streaming/
"""
import logging
import time
import re
from typing import Dict, Any, Optional, List

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState

logger = logging.getLogger(__name__)


def normalize_query(content: Any) -> str:
    """
    规范化查询内容，用于比较是否是相同问题
    
    处理逻辑:
    1. 提取文本内容（支持字符串、列表、字典格式）
    2. 转小写
    3. 移除多余空格
    4. 移除标点符号（保留中文）
    
    Args:
        content: 消息内容（可能是字符串、列表或字典）
        
    Returns:
        规范化后的查询字符串
    """
    if content is None:
        return ""
    
    # 提取文本内容
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
            elif isinstance(item, str):
                parts.append(item)
        text = " ".join(p for p in parts if p).strip()
    elif isinstance(content, dict):
        if content.get("type") == "text" and content.get("text"):
            text = str(content.get("text"))
        else:
            text = str(content)
    else:
        text = str(content)
    
    # 规范化处理
    text = text.lower().strip()
    
    # 移除多余空格
    text = re.sub(r'\s+', ' ', text)
    
    # 移除常见标点（保留中文字符）
    text = re.sub(r'[,.?!;:\'\"。，？！；：""'']+', '', text)
    
    return text


def extract_current_query(state: SQLMessageState) -> Optional[str]:
    """
    从状态中提取当前用户查询（最新的 Human 消息）
    
    Args:
        state: 当前状态
        
    Returns:
        当前用户查询，如果没有则返回 None
    """
    messages = state.get("messages", [])
    
    # 从后向前查找最新的 Human 消息
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            return normalize_query(msg.content)
        elif isinstance(msg, HumanMessage):
            return normalize_query(msg.content)
    
    return None


def find_historical_response(
    messages: List, 
    query: str,
    current_index: int
) -> Optional[Dict[str, Any]]:
    """
    在历史消息中查找与指定查询相同的问题及其回答
    
    Args:
        messages: 消息列表
        query: 规范化后的当前查询
        current_index: 当前消息的索引（排除它之后的消息）
        
    Returns:
        如果找到，返回包含历史回答信息的字典；否则返回 None
    """
    for i, msg in enumerate(messages[:current_index]):
        # 只检查 Human 消息
        if not (hasattr(msg, 'type') and msg.type == 'human'):
            if not isinstance(msg, HumanMessage):
                continue
        
        # 检查是否是相同问题
        historical_query = normalize_query(msg.content)
        if historical_query != query:
            continue
        
        logger.debug(f"找到历史相同问题: index={i}, query='{query[:50]}...'")
        
        # 查找这个问题之后的 AI 回答
        ai_responses = []
        tool_messages = []
        execution_result = None
        generated_sql = None
        
        for j in range(i + 1, len(messages)):
            next_msg = messages[j]
            
            # 如果遇到下一个 Human 消息，停止搜索
            if hasattr(next_msg, 'type') and next_msg.type == 'human':
                break
            if isinstance(next_msg, HumanMessage):
                break
            
            # 收集 AI 消息
            if hasattr(next_msg, 'type') and next_msg.type == 'ai':
                ai_responses.append(next_msg)
                # 尝试从 AI 消息中提取 SQL
                if hasattr(next_msg, 'content') and '```sql' in str(next_msg.content).lower():
                    sql_match = re.search(r'```sql\s*(.*?)\s*```', str(next_msg.content), re.DOTALL | re.IGNORECASE)
                    if sql_match:
                        generated_sql = sql_match.group(1).strip()
            elif isinstance(next_msg, AIMessage):
                ai_responses.append(next_msg)
                if '```sql' in str(next_msg.content).lower():
                    sql_match = re.search(r'```sql\s*(.*?)\s*```', str(next_msg.content), re.DOTALL | re.IGNORECASE)
                    if sql_match:
                        generated_sql = sql_match.group(1).strip()
            
            # 收集 Tool 消息
            if isinstance(next_msg, ToolMessage):
                tool_messages.append(next_msg)
                # 尝试从 ToolMessage 中提取执行结果
                if getattr(next_msg, 'name', '') == 'execute_sql_query':
                    try:
                        import json
                        tool_content = next_msg.content
                        if isinstance(tool_content, str):
                            parsed = json.loads(tool_content)
                            if isinstance(parsed, dict) and parsed.get("success"):
                                execution_result = parsed
                    except Exception:
                        pass
        
        # 如果找到了 AI 回答
        if ai_responses:
            return {
                "found": True,
                "historical_index": i,
                "ai_responses": ai_responses,
                "tool_messages": tool_messages,
                "execution_result": execution_result,
                "generated_sql": generated_sql
            }
    
    return None


def thread_history_check_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    Thread 历史检查节点 - LangGraph 标准节点函数
    
    遵循 LangGraph 官方规范：
    - 使用 StreamWriter 参数注入发送流式事件
    - 节点签名: (state, writer) -> dict
    - 参考: https://langchain-ai.github.io/langgraph/concepts/streaming/
    
    检查同一 thread 内是否有相同问题的历史回答。
    如果找到，直接返回历史结果，避免重复执行。
    
    Args:
        state: 当前的 SQL 消息状态
        writer: LangGraph StreamWriter，用于发送流式事件
        
    Returns:
        Dict[str, Any]: 状态更新
            - thread_history_hit: 是否命中历史
            - cached_response: 历史回答内容（如果命中）
            - current_stage: 如果命中则为 "completed"
            
    状态字段:
        读取:
        - messages: 消息历史
        - connection_id: 数据库连接ID
        
        更新:
        - thread_history_hit: 是否命中历史
        - generated_sql: 历史生成的 SQL（如果有）
        - execution_result: 历史执行结果（如果有）
    """
    logger.info("=== 进入 Thread 历史检查节点 ===")
    
    start_time = time.time()
    
    # 1. 提取当前查询
    current_query = extract_current_query(state)
    if not current_query:
        logger.warning("无法提取当前查询，跳过历史检查")
        return {"thread_history_hit": False}
    
    logger.debug(f"当前查询: '{current_query[:50]}...'")
    
    # 2. 获取消息历史
    messages = state.get("messages", [])
    if len(messages) <= 1:
        logger.info("消息历史不足，跳过历史检查")
        return {"thread_history_hit": False}
    
    # 3. 查找当前消息的索引（最后一个 Human 消息）
    current_index = len(messages) - 1
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if hasattr(msg, 'type') and msg.type == 'human':
            current_index = i
            break
        if isinstance(msg, HumanMessage):
            current_index = i
            break
    
    # 4. 在历史中查找相同问题
    historical = find_historical_response(messages, current_query, current_index)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    if not historical or not historical.get("found"):
        logger.info(f"Thread 历史未命中 (耗时: {elapsed_ms}ms)")
        return {"thread_history_hit": False}
    
    # 5. 命中历史，发送流式事件（使用注入的 StreamWriter）
    logger.info(f"Thread 历史命中! 找到历史回答 (耗时: {elapsed_ms}ms)")
    
    from app.schemas.stream_events import create_cache_hit_event, create_data_query_event
    
    # 使用注入的 writer 发送缓存命中事件
    writer(create_cache_hit_event(
        hit_type="thread_history",
        similarity=1.0,
        original_query=current_query[:100],
        time_ms=elapsed_ms
    ))
    
    # 如果有执行结果，发送数据查询事件
    exec_result = historical.get("execution_result")
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
        
        writer(create_data_query_event(
            columns=columns,
            rows=rows[:100],
            row_count=row_count,
            chart_config=None,
            title="历史查询结果"
        ))
    
    # 6. 构建返回结果
    # 复制历史 AI 回答到当前消息
    ai_responses = historical.get("ai_responses", [])
    tool_messages = historical.get("tool_messages", [])
    
    # 创建一个新的 AI 消息，表明这是从历史中获取的
    if ai_responses:
        last_ai = ai_responses[-1]
        content = last_ai.content if hasattr(last_ai, 'content') else ""
        
        # 添加历史回答标记
        history_note = "\n\n> 💡 *此回答来自历史对话记录*"
        if isinstance(content, str) and history_note not in content:
            content = content + history_note
        
        new_ai_message = AIMessage(content=content)
        
        # 优化：截断 execution_result 数据，减少 checkpoint 存储
        MAX_CHECKPOINT_ROWS = 100
        historical_exec_result = historical.get("execution_result")
        if historical_exec_result and isinstance(historical_exec_result, dict):
            raw_data = historical_exec_result.get("data")
            if raw_data:
                truncated_data = None
                if isinstance(raw_data, dict):
                    truncated_data = {
                        "columns": raw_data.get("columns", []),
                        "data": raw_data.get("data", [])[:MAX_CHECKPOINT_ROWS],
                        "row_count": raw_data.get("row_count", 0)
                    }
                elif isinstance(raw_data, list):
                    truncated_data = raw_data[:MAX_CHECKPOINT_ROWS]
                else:
                    truncated_data = raw_data
                historical_exec_result = {**historical_exec_result, "data": truncated_data}
        
        return {
            "thread_history_hit": True,
            "messages": [new_ai_message],
            "generated_sql": historical.get("generated_sql"),
            "execution_result": historical_exec_result,
            "current_stage": "completed"
        }
    
    # 如果没有找到 AI 回答，仍然标记为未命中
    logger.warning("找到历史问题但没有 AI 回答，标记为未命中")
    return {"thread_history_hit": False}


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "thread_history_check_node",
    "normalize_query",
    "extract_current_query",
    "find_historical_response",
]
