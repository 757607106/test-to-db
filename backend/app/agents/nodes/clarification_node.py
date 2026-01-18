"""
澄清节点 (Clarification Node)

使用多轮对话机制实现澄清功能。
当检测到用户查询模糊时，生成 AI 消息询问用户，用户在聊天框中回复。

工作流程:
1. 检查是否需要澄清（调用 clarification_agent）
2. 如果需要，生成 AI 消息显示澄清问题
3. 设置状态等待用户回复
4. 用户发送新消息后，检测是否是对澄清问题的回答
5. 整合信息到查询中，继续后续流程

使用说明:
- 澄清问题以纯文本格式显示，用户可以输入数字选择或直接输入
- 支持多轮对话，用户的回复会自动被识别和处理
"""
from typing import Dict, Any, List, Optional
import logging

from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState
from app.agents.agents.clarification_agent import (
    # 使用内部函数，避免 @tool 装饰器导致的流式传输问题
    _quick_clarification_check_impl as quick_clarification_check,
    _enrich_query_with_clarification_impl as enrich_query_with_clarification,
    format_clarification_questions,
    format_clarification_text,
    parse_user_clarification_response,
    should_skip_clarification,
)

# 配置日志
logger = logging.getLogger(__name__)


def clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    澄清节点 - LangGraph 节点函数
    
    检测用户查询是否需要澄清，如需要则生成 AI 消息询问用户。
    用户可以在聊天框中输入数字选择或直接输入内容来回答。
    
    Args:
        state: 当前的 SQL 消息状态
        
    Returns:
        Dict[str, Any]: 状态更新
            - 如果不需要澄清: 直接返回，流程继续
            - 如果需要澄清: 生成 AI 消息，设置等待状态
            - 如果用户已回复: 整合信息，继续流程
            
    状态字段:
        读取:
        - messages: 获取用户查询
        - connection_id: 数据库连接ID
        - clarification_round: 当前澄清轮次
        - max_clarification_rounds: 最大澄清轮次
        - clarification_confirmed: 是否已确认（跳过澄清）
        - pending_clarification: 是否有待处理的澄清问题
        
        更新:
        - needs_clarification: 是否需要澄清
        - clarification_questions: 澄清问题列表
        - clarification_responses: 用户回复
        - clarification_round: 更新澄清轮次
        - enriched_query: 增强后的查询
        - original_query: 保存原始查询
        - current_stage: 更新阶段
        - pending_clarification: 是否等待用户澄清回复
    """
    logger.info("=== 进入澄清节点 ===")
    
    # 0. 获取消息列表
    messages = state.get("messages", [])
    if not messages:
        logger.warning("没有消息，跳过澄清")
        return {"current_stage": "schema_analysis"}
    
    # 1. 检查是否有待处理的澄清（用户回复了澄清问题）
    pending_clarification = state.get("pending_clarification", False)
    pending_questions = state.get("clarification_questions", [])
    
    if pending_clarification and pending_questions:
        logger.info("检测到有待处理的澄清，尝试解析用户回复")
        
        # 获取最后一条人类消息作为用户的澄清回复
        user_response = None
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_response = msg.content
                break
        
        if user_response:
            if isinstance(user_response, list):
                user_response = user_response[0].get("text", "") if user_response else ""
            
            logger.info(f"用户澄清回复: {user_response[:100]}...")
            
            # 解析用户回复
            parsed_answers = parse_user_clarification_response(user_response, pending_questions)
            
            if parsed_answers:
                logger.info(f"成功解析用户回复: {parsed_answers}")
                
                # 获取原始查询
                original_query = state.get("original_query", "")
                
                # 整合用户回复到查询
                try:
                    enrich_result = enrich_query_with_clarification(
                        original_query=original_query,
                        clarification_responses=parsed_answers
                    )
                    enriched_query = enrich_result.get("enriched_query", original_query)
                except Exception as e:
                    logger.error(f"查询增强失败: {e}")
                    enriched_query = original_query
                
                logger.info(f"增强后查询: {enriched_query[:100]}...")
                
                current_round = state.get("clarification_round", 0)
                
                return {
                    "needs_clarification": False,
                    "pending_clarification": False,
                    "clarification_responses": parsed_answers,
                    "clarification_round": current_round + 1,
                    "clarification_confirmed": True,
                    "enriched_query": enriched_query,
                    "current_stage": "schema_analysis"
                }
    
    # 2. 获取用户的原始查询（第一条人类消息或尚未处理的消息）
    user_query = None
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break
    
    if not user_query:
        logger.warning("无法获取用户查询，跳过澄清")
        return {"current_stage": "schema_analysis"}
    
    # 处理内容格式
    if isinstance(user_query, list):
        user_query = user_query[0].get("text", "") if user_query else ""
    
    logger.info(f"用户查询: {user_query[:100]}...")
    
    # 3. 检查是否已经确认跳过澄清
    if state.get("clarification_confirmed", False):
        logger.info("用户已确认，跳过澄清检测")
        return {
            "needs_clarification": False,
            "current_stage": "schema_analysis"
        }
    
    # 4. 检查是否已经有增强查询（说明澄清已完成）
    if state.get("enriched_query"):
        logger.info(f"已有增强查询，跳过澄清检测: {state.get('enriched_query')[:50]}...")
        return {
            "needs_clarification": False,
            "current_stage": "schema_analysis"
        }
    
    # 5. 检查澄清轮次限制
    current_round = state.get("clarification_round", 0)
    max_rounds = state.get("max_clarification_rounds", 2)
    
    if current_round >= max_rounds:
        logger.info(f"已达到最大澄清轮次 ({max_rounds})，继续执行")
        return {
            "needs_clarification": False,
            "clarification_confirmed": True,
            "current_stage": "schema_analysis"
        }
    
    # 6. 快速预检查（性能优化）
    if should_skip_clarification(user_query):
        logger.info("查询明确，快速跳过澄清")
        return {
            "needs_clarification": False,
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
    
    # 7. 执行澄清检测
    connection_id = state.get("connection_id", 15)
    
    try:
        check_result = quick_clarification_check(
            query=user_query,
            connection_id=connection_id
        )
    except Exception as e:
        logger.error(f"澄清检测失败: {e}", exc_info=True)
        return {
            "needs_clarification": False,
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
    
    # 8. 判断是否需要澄清
    needs_clarification = check_result.get("needs_clarification", False)
    questions = check_result.get("questions", [])
    
    if not needs_clarification or not questions:
        logger.info(f"不需要澄清: {check_result.get('reason', '')}")
        return {
            "needs_clarification": False,
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
    
    # 9. 格式化问题
    formatted_questions = format_clarification_questions(questions)
    
    logger.info(f"需要澄清，生成 {len(formatted_questions)} 个问题")
    
    # 10. 生成纯文本格式的澄清消息
    clarification_text = format_clarification_text(
        questions=formatted_questions,
        reason=check_result.get("reason", "查询存在模糊性，需要澄清"),
        round_num=current_round + 1,
        max_rounds=max_rounds
    )
    
    # 11. 创建 AI 消息
    clarification_message = AIMessage(content=clarification_text)
    
    logger.info(f"生成澄清消息: {clarification_text[:200]}...")
    
    # 12. 返回状态，设置等待用户回复
    return {
        "messages": [clarification_message],
        "needs_clarification": True,
        "pending_clarification": True,  # 标记等待用户回复
        "clarification_questions": formatted_questions,
        "clarification_round": current_round,
        "original_query": user_query,
        "current_stage": "awaiting_clarification"  # 特殊阶段，表示等待澄清
    }


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
