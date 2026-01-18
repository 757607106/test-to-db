"""
消息历史管理模块

功能：
- 修剪消息历史，防止超出token限制
- 保留重要的系统消息
- 可选的消息摘要功能

使用场景：
- 长对话中自动修剪历史消息
- 控制发送给LLM的消息数量
- 优化token使用和性能
"""
from typing import List, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def trim_message_history(
    messages: List[BaseMessage],
    max_messages: Optional[int] = None,
    preserve_system: bool = True
) -> List[BaseMessage]:
    """
    修剪消息历史，保留最近的N条消息
    
    Args:
        messages: 消息列表
        max_messages: 最大保留消息数（默认从配置读取）
        preserve_system: 是否保留所有系统消息（默认True）
        
    Returns:
        修剪后的消息列表
        
    说明:
        - 如果消息数量未超过限制，直接返回原列表
        - 如果preserve_system=True，所有系统消息会被保留
        - 其他消息按时间顺序保留最近的N条
        
    示例:
        >>> messages = [SystemMessage("系统提示"), HumanMessage("问题1"), 
        ...             AIMessage("回答1"), HumanMessage("问题2")]
        >>> trimmed = trim_message_history(messages, max_messages=3)
        >>> len(trimmed)  # SystemMessage + 最近2条
        3
    """
    if max_messages is None:
        max_messages = settings.MAX_MESSAGE_HISTORY
    
    # 如果消息数量未超过限制，直接返回
    if len(messages) <= max_messages:
        return messages
    
    logger.info(f"修剪消息历史: {len(messages)} -> {max_messages}")
    
    if preserve_system:
        # 分离系统消息和其他消息
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        other_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        
        # 计算可以保留的非系统消息数量
        available_slots = max_messages - len(system_messages)
        
        if available_slots <= 0:
            # 如果系统消息已经超过限制，只保留系统消息
            logger.warning(
                f"系统消息数量({len(system_messages)})超过限制({max_messages})，"
                f"只保留系统消息"
            )
            return system_messages[:max_messages]
        
        # 保留最近的非系统消息
        recent_messages = other_messages[-available_slots:]
        
        # 合并：系统消息 + 最近的其他消息
        # 保持原始顺序
        result = []
        system_idx = 0
        other_idx = 0
        recent_start_idx = len(other_messages) - len(recent_messages)
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append(system_messages[system_idx])
                system_idx += 1
            elif other_idx >= recent_start_idx:
                result.append(other_messages[other_idx])
                other_idx += 1
            else:
                other_idx += 1
        
        logger.info(
            f"保留 {len(system_messages)} 条系统消息 + "
            f"{len(recent_messages)} 条最近消息"
        )
        
        return result
    else:
        # 不保留系统消息，直接保留最近的N条
        result = messages[-max_messages:]
        logger.info(f"保留最近 {len(result)} 条消息")
        return result


def count_message_tokens(messages: List[BaseMessage]) -> int:
    """
    估算消息列表的token数量
    
    Args:
        messages: 消息列表
        
    Returns:
        估算的token数量
        
    说明:
        - 使用简单的字符数估算（1 token ≈ 4 字符）
        - 这是一个粗略估算，实际token数可能有差异
        - 用于快速判断是否需要修剪消息
    """
    total_chars = sum(len(msg.content) for msg in messages if hasattr(msg, 'content'))
    # 粗略估算：1 token ≈ 4 字符（对于中文可能更少）
    estimated_tokens = total_chars // 4
    return estimated_tokens


def should_trim_messages(messages: List[BaseMessage]) -> bool:
    """
    判断是否需要修剪消息历史
    
    Args:
        messages: 消息列表
        
    Returns:
        True表示需要修剪，False表示不需要
        
    说明:
        - 基于消息数量判断
        - 如果超过配置的最大值，返回True
    """
    max_messages = settings.MAX_MESSAGE_HISTORY
    return len(messages) > max_messages


async def summarize_message_history(
    messages: List[BaseMessage],
    llm: Optional[any] = None,
    threshold: Optional[int] = None
) -> List[BaseMessage]:
    """
    当消息数超过阈值时，生成摘要（高级功能）
    
    Args:
        messages: 消息列表
        llm: LLM实例（用于生成摘要）
        threshold: 触发摘要的消息数（默认从配置读取）
        
    Returns:
        包含摘要的消息列表
        
    说明:
        - 这是一个高级功能，需要调用LLM生成摘要
        - 如果未启用或LLM未提供，回退到简单修剪
        - 摘要会作为SystemMessage插入到消息列表开头
        
    注意:
        - 此功能需要额外的LLM调用，会增加延迟和成本
        - 建议在长对话场景中使用
        - 需要在配置中启用: ENABLE_MESSAGE_SUMMARY=true
    """
    if threshold is None:
        threshold = settings.SUMMARY_THRESHOLD
    
    # 检查是否启用摘要功能
    if not settings.ENABLE_MESSAGE_SUMMARY:
        logger.info("消息摘要功能未启用，使用简单修剪")
        return trim_message_history(messages)
    
    # 如果消息数量未超过阈值，直接返回
    if len(messages) <= threshold:
        return messages
    
    # 如果未提供LLM，回退到简单修剪
    if llm is None:
        logger.warning("未提供LLM实例，无法生成摘要，使用简单修剪")
        return trim_message_history(messages)
    
    logger.info(f"生成消息历史摘要: {len(messages)} 条消息")
    
    try:
        # 分离旧消息和最近消息
        old_messages = messages[:-threshold]
        recent_messages = messages[-threshold:]
        
        # 格式化旧消息用于摘要
        formatted_messages = []
        for msg in old_messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"助手: {msg.content}")
            elif isinstance(msg, SystemMessage):
                formatted_messages.append(f"系统: {msg.content}")
        
        messages_text = "\n".join(formatted_messages)
        
        # 生成摘要
        summary_prompt = f"""
请总结以下对话历史的关键信息：

{messages_text}

总结应包括：
1. 用户的主要查询意图
2. 已执行的SQL查询（如果有）
3. 重要的上下文信息
4. 关键的讨论点

请用简洁的语言总结，不超过200字。
"""
        
        summary_response = await llm.ainvoke(summary_prompt)
        summary_content = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
        
        # 创建摘要消息
        summary_message = SystemMessage(
            content=f"对话历史摘要（{len(old_messages)}条消息）：\n{summary_content}"
        )
        
        # 返回：摘要 + 最近的消息
        result = [summary_message] + recent_messages
        
        logger.info(
            f"摘要生成成功: {len(old_messages)} 条旧消息 -> 1 条摘要 + "
            f"{len(recent_messages)} 条最近消息"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"生成摘要失败: {str(e)}，回退到简单修剪")
        return trim_message_history(messages)


def get_message_stats(messages: List[BaseMessage]) -> dict:
    """
    获取消息统计信息
    
    Args:
        messages: 消息列表
        
    Returns:
        统计信息字典
        
    说明:
        - 统计各类型消息的数量
        - 估算token使用
        - 用于监控和调试
    """
    stats = {
        "total": len(messages),
        "system": sum(1 for m in messages if isinstance(m, SystemMessage)),
        "human": sum(1 for m in messages if isinstance(m, HumanMessage)),
        "ai": sum(1 for m in messages if isinstance(m, AIMessage)),
        "other": 0,
        "estimated_tokens": count_message_tokens(messages)
    }
    
    stats["other"] = stats["total"] - stats["system"] - stats["human"] - stats["ai"]
    
    return stats


# 便捷函数

def auto_trim_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    自动修剪消息（如果需要）
    
    Args:
        messages: 消息列表
        
    Returns:
        修剪后的消息列表（如果不需要修剪则返回原列表）
        
    说明:
        - 自动判断是否需要修剪
        - 如果需要，调用trim_message_history
        - 这是最常用的便捷函数
    """
    if should_trim_messages(messages):
        return trim_message_history(messages)
    return messages


# 测试和调试

if __name__ == "__main__":
    """测试消息历史管理功能"""
    
    # 创建测试消息
    test_messages = [
        SystemMessage(content="你是一个SQL助手"),
        HumanMessage(content="查询所有客户"),
        AIMessage(content="SELECT * FROM customers"),
        HumanMessage(content="只要前10个"),
        AIMessage(content="SELECT * FROM customers LIMIT 10"),
        HumanMessage(content="按名字排序"),
        AIMessage(content="SELECT * FROM customers ORDER BY name LIMIT 10"),
    ]
    
    print("原始消息数量:", len(test_messages))
    print("消息统计:", get_message_stats(test_messages))
    
    # 测试修剪
    trimmed = trim_message_history(test_messages, max_messages=5)
    print("\n修剪后消息数量:", len(trimmed))
    print("修剪后统计:", get_message_stats(trimmed))
    
    # 打印修剪后的消息
    print("\n修剪后的消息:")
    for i, msg in enumerate(trimmed, 1):
        msg_type = type(msg).__name__
        content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
        print(f"{i}. [{msg_type}] {content}")
