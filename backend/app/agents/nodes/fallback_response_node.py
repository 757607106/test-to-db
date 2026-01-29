"""
兜底响应节点

当所有重试都失败后，使用 LLM 生成一个友好的、有帮助的回复，
确保用户永远不会看到原始错误信息或空白页面。

设计原则:
1. 永远返回有意义的响应
2. 根据错误类型提供针对性建议
3. 保持友好、专业的语气
4. 不暴露技术细节给用户
"""
from typing import Dict, Any, Optional
import logging
import json

from langchain_core.messages import AIMessage, HumanMessage
from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


# ============================================================================
# 错误类型到用户友好消息的映射
# ============================================================================

FALLBACK_TEMPLATES = {
    # SQL 相关错误
    "sql_syntax_error": {
        "title": "查询生成遇到困难",
        "suggestions": [
            "尝试用更简单的方式描述您的需求",
            "提供更具体的筛选条件（如时间范围、产品类别等）",
            "将复杂查询拆分成多个简单问题"
        ]
    },
    "column_validation_failed": {
        "title": "数据字段匹配问题",
        "suggestions": [
            "您查询的某些数据可能不在当前数据库中",
            "尝试使用更通用的描述方式",
            "可以先问我「有哪些数据可以查询」了解可用数据"
        ]
    },
    "mysql_limit_subquery_error": {
        "title": "查询结构过于复杂",
        "suggestions": [
            "尝试将查询拆分成多个步骤",
            "先查询基础数据，再进行筛选",
            "简化排序和限制条件"
        ]
    },
    "connection_error": {
        "title": "数据库连接问题",
        "suggestions": [
            "请稍后再试",
            "如果问题持续，请联系管理员检查数据库连接",
            "您可以先尝试其他不需要数据库的问题"
        ]
    },
    "timeout_error": {
        "title": "查询执行超时",
        "suggestions": [
            "缩小查询的时间范围",
            "减少查询的数据量",
            "添加更多筛选条件"
        ]
    },
    "permission_error": {
        "title": "权限不足",
        "suggestions": [
            "您可能没有访问某些数据的权限",
            "请联系管理员获取相应权限",
            "尝试查询其他可访问的数据"
        ]
    },
    # 默认错误
    "unknown": {
        "title": "处理遇到问题",
        "suggestions": [
            "尝试重新描述您的问题",
            "使用更简单、更具体的表述",
            "如果问题持续，请联系技术支持"
        ]
    }
}


def _get_error_type_from_state(state: SQLMessageState) -> str:
    """从状态中提取错误类型"""
    # 优先从 error_recovery_context 获取
    error_ctx = state.get("error_recovery_context", {})
    if error_ctx:
        error_type = error_ctx.get("error_type", "")
        if error_type:
            return error_type
    
    # 从 error_history 获取最后一个错误
    error_history = state.get("error_history", [])
    if error_history:
        last_error = error_history[-1]
        error_msg = str(last_error.get("error", "")).lower()
        
        # 根据错误消息推断类型
        if "column" in error_msg or "列名" in error_msg:
            return "column_validation_failed"
        if "syntax" in error_msg or "语法" in error_msg:
            return "sql_syntax_error"
        if "connection" in error_msg or "连接" in error_msg:
            return "connection_error"
        if "timeout" in error_msg or "超时" in error_msg:
            return "timeout_error"
        if "permission" in error_msg or "权限" in error_msg:
            return "permission_error"
        if "limit" in error_msg and "subquery" in error_msg:
            return "mysql_limit_subquery_error"
    
    return "unknown"


def _get_user_query_from_state(state: SQLMessageState) -> str:
    """从状态中提取用户原始查询"""
    # 优先使用 original_query
    original_query = state.get("original_query")
    if original_query:
        return original_query
    
    # 从 messages 中提取
    messages = state.get("messages", [])
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'human':
            content = msg.content
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            return content
        if isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    
    return ""


def _generate_fallback_without_llm(
    error_type: str,
    user_query: str,
    retry_count: int
) -> str:
    """
    不使用 LLM 生成兜底响应（当 LLM 也失败时的最终兜底）
    """
    template = FALLBACK_TEMPLATES.get(error_type, FALLBACK_TEMPLATES["unknown"])
    
    response = f"抱歉，{template['title']}。\n\n"
    
    if retry_count > 0:
        response += f"我已经尝试了 {retry_count} 次，但仍未能成功处理您的请求。\n\n"
    
    response += "**建议您可以：**\n"
    for i, suggestion in enumerate(template["suggestions"], 1):
        response += f"{i}. {suggestion}\n"
    
    response += "\n如果您有其他问题，我很乐意继续帮助您。"
    
    return response


async def fallback_response_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    兜底响应节点
    
    当所有重试都失败后，生成一个友好的、有帮助的回复。
    
    流程:
    1. 分析错误类型和用户查询
    2. 尝试使用 LLM 生成个性化的友好回复
    3. 如果 LLM 也失败，使用模板生成回复
    4. 确保永远返回有意义的响应
    """
    # 发送流式事件通知前端
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        if writer:
            writer({
                "type": "node_status",
                "node": "fallback_response",
                "status": "running",
                "message": "正在生成回复...",
            })
    except Exception:
        pass  # 流式事件发送失败不影响主流程
    
    try:
        # 提取上下文信息
        error_type = _get_error_type_from_state(state)
        user_query = _get_user_query_from_state(state)
        retry_count = state.get("retry_count", 0)
        error_history = state.get("error_history", [])
        
        logger.info(f"[兜底响应] 错误类型: {error_type}, 重试次数: {retry_count}")
        
        # 获取错误模板
        template = FALLBACK_TEMPLATES.get(error_type, FALLBACK_TEMPLATES["unknown"])
        
        # 尝试使用 LLM 生成更个性化的回复
        try:
            llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
            
            # 构建 LLM 提示
            prompt = f"""你是一个友好的数据助手。用户的查询处理失败了，你需要生成一个友好、有帮助的回复。

**用户原始问题**: {user_query}

**错误类型**: {template['title']}

**已尝试次数**: {retry_count}

**建议方向**:
{chr(10).join(f"- {s}" for s in template['suggestions'])}

**要求**:
1. 用友好、专业的语气回复
2. 不要暴露技术细节（如 SQL 错误、列名等）
3. 给出 2-3 个具体的、可操作的建议
4. 如果可能，根据用户的问题给出替代查询建议
5. 保持简洁，不超过 150 字
6. 使用中文回复

请直接输出回复内容，不要有任何前缀或解释。"""

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            friendly_message = response.content.strip()
            
            # 验证 LLM 响应是否有效
            if friendly_message and len(friendly_message) > 20:
                logger.info(f"[兜底响应] LLM 生成成功: {friendly_message[:50]}...")
            else:
                raise ValueError("LLM 响应过短或为空")
                
        except Exception as llm_error:
            logger.warning(f"[兜底响应] LLM 生成失败，使用模板: {llm_error}")
            friendly_message = _generate_fallback_without_llm(error_type, user_query, retry_count)
        
        # 构建最终响应
        return {
            "messages": [AIMessage(content=friendly_message)],
            "current_stage": "completed",
            "final_response": {
                "success": False,
                "error_type": error_type,
                "friendly_message": friendly_message,
                "retry_count": retry_count,
                "fallback_used": True
            }
        }
        
    except Exception as e:
        # 最终兜底：即使这个节点也出错，也要返回一个响应
        logger.error(f"[兜底响应] 节点执行失败: {e}")
        
        fallback_message = (
            "抱歉，处理您的请求时遇到了一些问题。\n\n"
            "**建议您可以：**\n"
            "1. 尝试用更简单的方式描述您的需求\n"
            "2. 稍后再试\n"
            "3. 如果问题持续，请联系技术支持\n\n"
            "如果您有其他问题，我很乐意继续帮助您。"
        )
        
        return {
            "messages": [AIMessage(content=fallback_message)],
            "current_stage": "completed",
            "final_response": {
                "success": False,
                "error_type": "fallback_node_error",
                "friendly_message": fallback_message,
                "fallback_used": True
            }
        }


# ============================================================================
# 同步版本（用于某些场景）
# ============================================================================

def fallback_response_node_sync(state: SQLMessageState) -> Dict[str, Any]:
    """
    兜底响应节点（同步版本）
    
    用于不支持异步的场景。
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在异步上下文中，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    fallback_response_node(state)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(fallback_response_node(state))
    except Exception as e:
        logger.error(f"[兜底响应-同步] 执行失败: {e}")
        # 返回最基本的响应
        return {
            "messages": [AIMessage(content="抱歉，处理您的请求时遇到了问题。请稍后再试或尝试简化您的问题。")],
            "current_stage": "completed",
            "final_response": {
                "success": False,
                "fallback_used": True
            }
        }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "fallback_response_node",
    "fallback_response_node_sync",
    "FALLBACK_TEMPLATES",
]
