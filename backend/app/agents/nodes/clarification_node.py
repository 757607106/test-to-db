"""
澄清节点 (Clarification Node) - LangGraph标准模式

基于LangGraph官方interrupt()模式实现澄清功能。
参考: https://context7.com/langchain-ai/langgraph/llms.txt

核心特性:
- 使用interrupt()暂停执行，等待用户确认
- 遵循LangGraph标准节点签名
- 简化状态管理，由LangGraph自动处理
- 通过Command(resume=...)恢复执行

工作流程:
1. 检测用户查询是否需要澄清
2. 如需澄清，使用interrupt()暂停执行并返回问题给用户
3. 用户回复后，LangGraph自动恢复执行
4. 整合用户回复，生成增强查询
"""
from typing import Dict, Any
import logging

from langgraph.types import interrupt

from app.core.state import SQLMessageState
from app.agents.agents.clarification_agent import (
    _quick_clarification_check_impl as quick_clarification_check,
    _enrich_query_with_clarification_impl as enrich_query_with_clarification,
    format_clarification_questions,
    parse_user_clarification_response,
    should_skip_clarification,
)

# 配置日志
logger = logging.getLogger(__name__)


def clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    澄清节点 - LangGraph标准interrupt()模式
    
    遵循LangGraph官方示例: https://context7.com/langchain-ai/langgraph/llms.txt
    
    节点签名标准:
    - 接收 state: SQLMessageState (TypedDict)
    - 返回 dict (部分状态更新，LangGraph自动合并)
    - 使用 interrupt() 暂停执行等待用户输入
    
    缓存感知逻辑:
    - 语义命中 (semantic): 检测是否需要澄清，澄清后基于缓存模板生成SQL
    - 未命中: 正常澄清流程
    - 精确命中: 不会进入此节点 (已在cache_check_node结束)
    
    性能优化 (2026-01-22):
    - 如果已有澄清回复，跳过 LLM 检测直接处理回复
    - 避免 interrupt 恢复后重复调用 LLM
    
    Args:
        state: 当前SQL消息状态
        
    Returns:
        Dict[str, Any]: 状态更新
            - enriched_query: 增强后的查询
            - original_query: 原始查询
            - clarification_responses: 用户回复
            - current_stage: 当前阶段
            - cached_sql_template: 缓存的SQL模板 (语义命中时保留)
    """
    logger.info("=== 澄清节点 (LangGraph标准模式) ===")
    
    # ✅ 性能优化: 检查是否已经有澄清回复（从 interrupt 恢复）
    # 如果已经确认过澄清，直接跳过，避免重复 LLM 调用
    if state.get("clarification_confirmed", False):
        logger.info("✓ 澄清已确认，跳过重复检测")
        return {"current_stage": "schema_analysis"}
    
    # 检查缓存命中类型
    cache_hit_type = state.get("cache_hit_type")
    cached_sql_template = state.get("cached_sql_template")
    cache_similarity = state.get("cache_similarity", 0)
    cache_matched_query = state.get("cache_matched_query")
    
    if cache_hit_type == "semantic":
        logger.info(f"语义缓存命中 (相似度: {cache_similarity:.1%})，检查是否需要澄清差异")
    
    # 1. 提取用户查询
    messages = state.get("messages", [])
    if not messages:
        logger.warning("无消息，跳过澄清")
        return {"current_stage": "schema_analysis"}
    
    user_query = None
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break
    
    if not user_query:
        logger.warning("无法提取用户查询，跳过澄清")
        return {"current_stage": "schema_analysis"}
    
    # 2. 规范化查询内容
    if isinstance(user_query, list):
        user_query = user_query[0].get("text", "") if user_query else ""
    
    logger.info(f"用户查询: {user_query[:100]}...")
    
    # 3. 快速预检查 (性能优化)
    if should_skip_clarification(user_query):
        logger.info("查询明确，快速跳过澄清")
        base_result = {
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
        # 如果有语义缓存命中，保留SQL模板
        if cache_hit_type == "semantic" and cached_sql_template:
            base_result["cached_sql_template"] = cached_sql_template
            base_result["enriched_query"] = user_query  # 使用原查询，不修改
        return base_result
    
    # 4. LLM检测是否需要澄清
    connection_id = state.get("connection_id", 15)
    
    try:
        # 如果是语义命中，可以将匹配的原查询作为上下文
        check_context = {}
        if cache_hit_type == "semantic" and cache_matched_query:
            check_context["matched_similar_query"] = cache_matched_query
        
        check_result = quick_clarification_check(
            query=user_query,
            connection_id=connection_id
        )
    except Exception as e:
        logger.error(f"澄清检测失败: {e}", exc_info=True)
        base_result = {
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
        if cache_hit_type == "semantic" and cached_sql_template:
            base_result["cached_sql_template"] = cached_sql_template
            base_result["enriched_query"] = user_query
        return base_result
    
    needs_clarification = check_result.get("needs_clarification", False)
    questions = check_result.get("questions", [])
    
    if not needs_clarification or not questions:
        logger.info(f"不需要澄清: {check_result.get('reason', '')}")
        base_result = {
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
        if cache_hit_type == "semantic" and cached_sql_template:
            base_result["cached_sql_template"] = cached_sql_template
            base_result["enriched_query"] = user_query
        return base_result
    
    # 5. 格式化澄清问题
    formatted_questions = format_clarification_questions(questions)
    
    logger.info(f"需要澄清，生成 {len(formatted_questions)} 个问题，使用interrupt()暂停执行")
    
    # ✅ 6. 使用interrupt()暂停执行，等待用户确认 (LangGraph标准模式)
    # 如果是语义命中，告知用户这是基于相似查询
    interrupt_data = {
        "type": "clarification_request",
        "questions": formatted_questions,
        "reason": check_result.get("reason", "查询存在模糊性，需要澄清"),
        "original_query": user_query
    }
    
    if cache_hit_type == "semantic":
        interrupt_data["semantic_match"] = {
            "similarity": cache_similarity,
            "matched_query": cache_matched_query
        }
    
    user_response = interrupt(interrupt_data)
    
    # 执行到这里说明用户已经回复了
    logger.info(f"收到用户澄清回复: {user_response}")
    
    # 7. 解析用户回复
    parsed_answers = parse_user_clarification_response(
        user_response, 
        formatted_questions
    )
    
    # 8. 整合用户回复到查询
    if parsed_answers:
        try:
            enrich_result = enrich_query_with_clarification(
                original_query=user_query,
                clarification_responses=parsed_answers
            )
            enriched_query = enrich_result.get("enriched_query", user_query)
        except Exception as e:
            logger.error(f"查询增强失败: {e}")
            enriched_query = user_query
    else:
        enriched_query = user_query
    
    logger.info(f"增强后查询: {enriched_query[:100]}...")
    
    # ✅ 9. 返回状态更新 (LangGraph标准 - 只返回需要更新的字段)
    result = {
        "clarification_responses": parsed_answers,
        "enriched_query": enriched_query,
        "original_query": user_query,
        "current_stage": "schema_analysis",
        "clarification_confirmed": True  # ✅ 标记澄清已完成，避免重复检测
    }
    
    # 如果是语义命中，保留SQL模板供sql_generator_agent使用
    if cache_hit_type == "semantic" and cached_sql_template:
        result["cached_sql_template"] = cached_sql_template
        logger.info("保留缓存SQL模板供后续SQL生成参考")
    
    return result


def should_enter_clarification(state: SQLMessageState) -> bool:
    """
    条件边函数：判断是否应该进入澄清节点
    
    Args:
        state: 当前状态
        
    Returns:
        bool - 是否进入澄清节点
    """
    # 如果路由决策是闲聊，不进入澄清
    route_decision = state.get("route_decision", "data_query")
    if route_decision == "general_chat":
        return False
    
    # 如果已经确认过，不再澄清
    if state.get("clarification_confirmed", False):
        return False
    
    # 如果已经有增强查询，不再澄清
    if state.get("enriched_query"):
        return False
    
    return True


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "clarification_node",
    "should_enter_clarification",
]
