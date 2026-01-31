"""
多轮对话上下文改写模块 (Context Rewriter)

P4 阶段核心功能：将跟进查询改写为完整的独立查询。

功能：
1. 检测跟进查询（指代词、修改词、短查询）
2. 提取对话上下文
3. 使用 LLM 改写为完整查询

示例：
- 历史: "查询库存最多的前5个产品" → 当前: "我要前20条" → 改写: "查询库存最多的前20个产品"
- 历史: "统计各部门销售额" → 当前: "按月份显示" → 改写: "按月份统计各部门销售额"
"""
from typing import Dict, Any, List, Optional
import logging
import re

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

logger = logging.getLogger(__name__)


# ============================================================================
# 跟进查询检测
# ============================================================================

def is_follow_up_query(query: str) -> bool:
    """
    检测查询是否是跟进查询（需要结合上下文理解）
    
    跟进查询的特征：
    - 包含指代词（这个、那个、它、上面、刚才等）
    - 包含修改词（改成、换成、要、不要等）
    - 查询过短且缺乏完整语义
    - 纯数量修改请求（如"前20条"、"我要20个"）
    - 纯修饰请求（如"按月份显示"、"按地区分组"）
    
    注意：
    - "查询库存最多的前5个产品" 是完整查询，不是跟进查询
    - "我要前20条" 是跟进查询，因为缺乏查询主体
    """
    query_lower = query.lower().strip()
    
    # 指代词
    reference_words = [
        "这个", "那个", "它", "它们", "上面", "刚才", "之前", "前面",
        "这些", "那些", "该", "此", "其", "上述",
        "this", "that", "it", "them", "above", "previous"
    ]
    
    # 修改词
    modification_words = [
        "改成", "换成", "改为", "换为", "变成",
        "不要", "加上", "去掉", "删除", "添加",
        "更多", "更少", "增加", "减少",
        "change", "modify", "add", "remove", "more", "less"
    ]
    
    # 完整查询的关键词（表示这是一个独立的查询，不是跟进）
    complete_query_keywords = [
        "查询", "统计", "列出", "获取", "分析", "计算", "汇总",
        "哪些", "多少", "什么", "谁", "哪个",
        "select", "query", "show", "list", "get", "find", "count"
    ]
    
    # 纯修饰模式（通常是跟进查询）
    # 如 "按月份显示"、"按地区分组"、"只显示前10条"
    modifier_patterns = [
        r'^按.{1,10}(显示|分组|排序|统计)$',  # "按月份显示"
        r'^只(要|显示|看).{1,20}$',           # "只要今天的"
        r'^(显示|看).{1,10}的?$',             # "显示本月的"
    ]
    
    # 检测纯修饰模式
    for pattern in modifier_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # 检测是否是完整查询（包含查询动词或疑问词）
    is_complete_query = any(kw in query_lower for kw in complete_query_keywords)
    
    # 检测指代词
    has_reference = any(word in query_lower for word in reference_words)
    
    # 检测修改词
    has_modification = any(word in query_lower for word in modification_words)
    
    # 检测纯数量修改请求（如"前20条"、"我要20个"，但不是完整查询）
    quantity_pattern = re.search(r'^[我要给看]*\s*[前后]?\s*\d+\s*[条个行项]', query_lower)
    is_pure_quantity_request = bool(quantity_pattern) and not is_complete_query
    
    # 查询过短（少于10个字符且不是完整句子）
    is_too_short = len(query_lower) < 10 and not is_complete_query
    
    # 如果是完整查询，即使包含指代词也不认为是跟进查询
    if is_complete_query and not has_modification:
        return False
    
    return has_reference or has_modification or is_pure_quantity_request or is_too_short


# ============================================================================
# 对话上下文提取
# ============================================================================

def extract_conversation_context(
    messages: List[BaseMessage], 
    max_turns: int = 3
) -> List[Dict[str, str]]:
    """
    提取最近的对话上下文
    
    Args:
        messages: 消息列表
        max_turns: 最大轮数
        
    Returns:
        对话上下文列表 [{"role": "user/assistant", "content": "..."}]
    """
    context = []
    turn_count = 0
    
    # 从后往前遍历，跳过最后一条（当前查询）
    for msg in reversed(messages[:-1] if len(messages) > 1 else []):
        if turn_count >= max_turns * 2:  # 每轮包含 user + assistant
            break
            
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                context.insert(0, {"role": "user", "content": str(content)})
                turn_count += 1
            elif msg.type == 'ai':
                content = msg.content
                if content and not content.startswith("{"):  # 跳过工具调用结果
                    context.insert(0, {"role": "assistant", "content": str(content)[:500]})
                    turn_count += 1
    
    return context


# ============================================================================
# LLM 改写
# ============================================================================

async def rewrite_query_with_context(
    current_query: str,
    conversation_context: List[Dict[str, str]],
    connection_id: Optional[int] = None
) -> str:
    """
    使用 LLM 结合对话上下文改写查询
    
    Args:
        current_query: 当前用户查询
        conversation_context: 对话上下文
        connection_id: 数据库连接 ID
        
    Returns:
        改写后的完整查询
    """
    from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
    
    if not conversation_context:
        return current_query
    
    # 构建上下文字符串
    context_str = ""
    for turn in conversation_context:
        role = "用户" if turn["role"] == "user" else "助手"
        context_str += f"{role}: {turn['content']}\n"
    
    prompt = f"""你是一个查询改写专家。用户正在进行多轮对话，当前的查询可能是对之前查询的跟进或修改。

**对话历史**:
{context_str}

**当前查询**: {current_query}

**任务**: 
1. 分析当前查询是否是对之前查询的跟进或修改
2. 如果是，将当前查询改写为一个完整、独立、明确的查询
3. 如果当前查询已经是完整的，直接返回原查询

**改写规则**:
- 保留用户的核心意图
- 将指代词（这个、那个、它等）替换为具体内容
- 将修改请求（前20条、更多等）整合到查询中
- 改写后的查询应该是一个完整的数据查询请求

**示例**:
- 历史: "查询库存最多的前5个产品" → 当前: "我要前20条" → 改写: "查询库存最多的前20个产品"
- 历史: "统计各部门销售额" → 当前: "按月份显示" → 改写: "按月份统计各部门销售额"
- 历史: "查询订单列表" → 当前: "只要今天的" → 改写: "查询今天的订单列表"

**输出**: 只输出改写后的查询，不要任何解释。如果不需要改写，直接输出原查询。
"""
    
    try:
        # 使用 LLMWrapper 统一处理重试和超时
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        rewritten = response.content.strip()
        
        # 清理可能的引号
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        if rewritten.startswith("'") and rewritten.endswith("'"):
            rewritten = rewritten[1:-1]
        
        # 验证改写结果
        if len(rewritten) < 3 or rewritten == current_query:
            return current_query
        
        logger.info(f"查询已改写: '{current_query}' → '{rewritten}'")
        return rewritten
        
    except Exception as e:
        logger.error(f"查询改写失败: {e}")
        return current_query


# ============================================================================
# 主入口函数
# ============================================================================

async def process_context_rewrite(
    query: str,
    messages: List[BaseMessage],
    connection_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    处理多轮对话上下文改写
    
    Args:
        query: 当前用户查询
        messages: 完整的消息历史
        connection_id: 数据库连接 ID
        
    Returns:
        {
            "original_query": str,      # 原始查询
            "enriched_query": str,      # 改写后的查询
            "query_rewritten": bool,    # 是否进行了改写
            "context_turns": int        # 使用的上下文轮数
        }
    """
    result = {
        "original_query": query,
        "enriched_query": query,
        "query_rewritten": False,
        "context_turns": 0
    }
    
    # 检测是否是跟进查询
    if not is_follow_up_query(query):
        logger.debug(f"非跟进查询，跳过改写: {query[:50]}...")
        return result
    
    # 检查是否有足够的历史消息
    if len(messages) <= 1:
        logger.debug("消息历史不足，跳过改写")
        return result
    
    logger.info(f"检测到跟进查询: '{query}'，尝试上下文改写")
    
    # 提取对话上下文
    conversation_context = extract_conversation_context(messages, max_turns=3)
    
    if not conversation_context:
        logger.debug("无有效对话上下文，跳过改写")
        return result
    
    result["context_turns"] = len([c for c in conversation_context if c["role"] == "user"])
    
    # 使用 LLM 改写查询
    enriched_query = await rewrite_query_with_context(
        current_query=query,
        conversation_context=conversation_context,
        connection_id=connection_id
    )
    
    if enriched_query != query:
        result["enriched_query"] = enriched_query
        result["query_rewritten"] = True
        logger.info(f"查询改写成功: '{query}' → '{enriched_query}'")
    
    return result


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "is_follow_up_query",
    "extract_conversation_context",
    "rewrite_query_with_context",
    "process_context_rewrite",
]
