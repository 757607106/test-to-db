"""
澄清代理 (Clarification Agent)

核心职责:
1. 检测用户查询中的模糊性和不明确之处
2. 生成针对性的澄清问题（优先选择题）
3. 整合用户回复，生成增强查询

检测的模糊类型:
- 时间范围模糊：如"最近的销售"、"上个月的数据"
- 字段/指标模糊：如"查看订单"（哪些字段？）
- 筛选条件模糊：如"大客户"（什么标准？）
- 分组维度模糊：如"按地区统计"（省/市/区？）
- 排序/限制模糊：如"前几名"（多少个？）

使用说明:
- quick_clarification_check: 快速检测是否需要澄清
- 结果包含 needs_clarification 和 questions 字段
- questions 为澄清问题列表，包含选择题或文本题
"""
from typing import Dict, Any, List, Optional
import logging
import json
import uuid

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

# 配置日志
logger = logging.getLogger(__name__)


# ============================================================================
# 澄清检测提示词
# ============================================================================

CLARIFICATION_CHECK_PROMPT = """你是一个专业的数据查询意图分析专家。请分析以下用户查询，判断是否存在模糊或不明确的地方。

用户查询: {query}

数据库连接ID: {connection_id}

请检测以下类型的模糊性:
1. **时间范围模糊**: 如"最近"、"近期"、"上个月"等没有明确日期的表述
2. **字段/指标模糊**: 如"查看订单"但没说明需要哪些字段（金额、数量、状态？）
3. **筛选条件模糊**: 如"大客户"、"热销产品"等主观描述
4. **分组维度模糊**: 如"按地区"但不明确是省、市还是区
5. **排序/数量模糊**: 如"前几名"、"一些"等不明确的数量

**重要判断原则**:
- 如果查询已经足够明确，可以直接生成SQL，则不需要澄清
- 只有当模糊性会显著影响查询结果时才需要澄清
- 简单查询（如"查询所有用户"）通常不需要澄清
- 包含具体时间、具体数值、具体条件的查询不需要澄清

请以JSON格式返回分析结果:
{{
    "needs_clarification": true/false,
    "reason": "需要/不需要澄清的原因",
    "ambiguities": [
        {{
            "type": "时间范围|字段选择|筛选条件|分组维度|排序数量",
            "description": "具体描述模糊之处",
            "severity": "high|medium|low"
        }}
    ]
}}

只返回JSON，不要其他内容。"""


QUESTION_GENERATION_PROMPT = """基于以下模糊性分析，生成澄清问题。

用户原始查询: {query}

模糊性分析:
{ambiguities}

请生成最多3个澄清问题，优先生成选择题（更便于用户回答）。

对于每个问题，请提供:
1. 一个唯一的问题ID（如 q1, q2, q3）
2. 清晰的问题描述
3. 问题类型: choice（选择题）或 text（文本题）
4. 如果是选择题，提供3-5个选项

请以JSON格式返回:
{{
    "questions": [
        {{
            "id": "q1",
            "question": "您想查看哪个时间范围的数据？",
            "type": "choice",
            "options": ["最近7天", "最近30天", "最近3个月", "今年", "自定义时间段"],
            "related_ambiguity": "时间范围模糊"
        }},
        {{
            "id": "q2",
            "question": "您关注哪些具体指标？",
            "type": "choice",
            "options": ["销售总额", "订单数量", "平均客单价", "全部"],
            "related_ambiguity": "字段选择模糊"
        }}
    ]
}}

只返回JSON，不要其他内容。"""


# ============================================================================
# 内部函数（不使用 @tool 装饰器，避免 LangGraph 的工具流式处理）
# ============================================================================

def _quick_clarification_check_impl(query: str, connection_id: int = 15) -> Dict[str, Any]:
    """
    快速检测用户查询是否需要澄清（内部实现，不使用 @tool 装饰器）
    
    注意：这个函数使用禁用流式输出的 LLM，确保检测结果不会被
    错误地流式传输到前端。
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        
    Returns:
        Dict包含:
        - needs_clarification: bool - 是否需要澄清
        - questions: List - 澄清问题列表（如果需要澄清）
        - reason: str - 判断原因
    """
    try:
        logger.info(f"开始澄清检测: {query[:50]}...")
        
        # Step 1: 检测模糊性
        # 获取 LLM 并禁用流式输出，防止 JSON 输出被流式传输到前端
        base_llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        # 使用 with_config 禁用流式输出
        llm = base_llm.with_config({"callbacks": []})
        
        check_prompt = CLARIFICATION_CHECK_PROMPT.format(
            query=query,
            connection_id=connection_id
        )
        
        # 使用 invoke 而不是 stream，并且不传递 callbacks
        response = llm.invoke([HumanMessage(content=check_prompt)], config={"callbacks": []})
        
        # 解析响应
        try:
            # 清理响应中的markdown标记
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            check_result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 内容: {response.content[:200]}")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "解析失败，默认不需要澄清"
            }
        
        # 如果不需要澄清，直接返回
        if not check_result.get("needs_clarification", False):
            logger.info(f"查询明确，不需要澄清: {check_result.get('reason', '')}")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": check_result.get("reason", "查询足够明确")
            }
        
        # Step 2: 生成澄清问题
        ambiguities = check_result.get("ambiguities", [])
        if not ambiguities:
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "未检测到具体模糊点"
            }
        
        # 只处理高/中严重度的模糊性
        significant_ambiguities = [
            a for a in ambiguities 
            if a.get("severity") in ["high", "medium"]
        ]
        
        if not significant_ambiguities:
            logger.info("只有低严重度模糊性，不需要澄清")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "模糊性较轻，可以继续执行"
            }
        
        # 生成问题
        question_prompt = QUESTION_GENERATION_PROMPT.format(
            query=query,
            ambiguities=json.dumps(significant_ambiguities, ensure_ascii=False, indent=2)
        )
        
        # 同样禁用流式输出
        question_response = llm.invoke([HumanMessage(content=question_prompt)], config={"callbacks": []})
        
        try:
            content = question_response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            question_result = json.loads(content)
            questions = question_result.get("questions", [])
        except json.JSONDecodeError as e:
            logger.warning(f"问题生成JSON解析失败: {e}")
            questions = []
        
        if not questions:
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "无法生成澄清问题"
            }
        
        logger.info(f"需要澄清，生成了 {len(questions)} 个问题")
        
        return {
            "needs_clarification": True,
            "questions": questions,
            "reason": check_result.get("reason", "查询存在模糊性"),
            "ambiguities": significant_ambiguities
        }
        
    except Exception as e:
        logger.error(f"澄清检测失败: {e}", exc_info=True)
        return {
            "needs_clarification": False,
            "questions": [],
            "reason": f"检测过程出错: {str(e)}"
        }


def _enrich_query_with_clarification_impl(
    original_query: str, 
    clarification_responses: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    将用户的澄清回复整合到原始查询中，生成增强查询（内部实现）
    
    Args:
        original_query: 原始用户查询
        clarification_responses: 澄清回复列表，每项包含 question_id 和 answer
        
    Returns:
        Dict包含:
        - enriched_query: str - 增强后的查询
        - clarification_summary: str - 澄清信息摘要
    """
    try:
        if not clarification_responses:
            return {
                "enriched_query": original_query,
                "clarification_summary": "无澄清信息"
            }
        
        # 构建澄清信息
        clarification_parts = []
        for resp in clarification_responses:
            answer = resp.get("answer", "")
            if answer:
                clarification_parts.append(answer)
        
        if not clarification_parts:
            return {
                "enriched_query": original_query,
                "clarification_summary": "无有效澄清信息"
            }
        
        # 整合到查询中
        clarification_summary = "、".join(clarification_parts)
        enriched_query = f"{original_query}（{clarification_summary}）"
        
        logger.info(f"查询已增强: {enriched_query[:100]}...")
        
        return {
            "enriched_query": enriched_query,
            "clarification_summary": clarification_summary
        }
        
    except Exception as e:
        logger.error(f"查询增强失败: {e}", exc_info=True)
        return {
            "enriched_query": original_query,
            "clarification_summary": f"处理失败: {str(e)}"
        }


# ============================================================================
# 辅助函数
# ============================================================================

def format_clarification_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    格式化澄清问题，确保符合数据结构
    
    Args:
        questions: 原始问题列表
        
    Returns:
        格式化后的问题列表
    """
    formatted = []
    for i, q in enumerate(questions):
        formatted_q = {
            "id": q.get("id", f"q{i+1}"),
            "question": q.get("question", ""),
            "type": q.get("type", "text"),
        }
        
        if formatted_q["type"] == "choice":
            formatted_q["options"] = q.get("options", [])
        
        if q.get("related_ambiguity"):
            formatted_q["related_ambiguity"] = q["related_ambiguity"]
        
        formatted.append(formatted_q)
    
    return formatted


def format_clarification_text(
    questions: List[Dict[str, Any]], 
    reason: str = "",
    round_num: int = 1,
    max_rounds: int = 2
) -> str:
    """
    将澄清问题格式化为纯文本，用于聊天显示
    
    用户可以：
    - 输入选项对应的数字来选择
    - 直接输入内容来回答
    
    Args:
        questions: 格式化后的问题列表
        reason: 需要澄清的原因
        round_num: 当前澄清轮次
        max_rounds: 最大澄清轮次
        
    Returns:
        格式化的文本消息
    """
    lines = []
    
    # 标题
    lines.append("🤔 **需要澄清一些信息**")
    lines.append("")
    lines.append("为了更准确地理解您的需求，请回答以下问题：")
    
    # 原因（如果有）
    if reason:
        lines.append(f"")
        lines.append(f"原因: {reason}")
    
    # 轮次信息
    lines.append(f"")
    lines.append(f"澄清轮次: {round_num}/{max_rounds}")
    lines.append("")
    
    # 问题列表
    for i, q in enumerate(questions):
        question_num = i + 1
        lines.append(f"**{question_num}. {q['question']}**")
        
        if q.get("type") == "choice" and q.get("options"):
            # 选择题：显示选项
            for j, option in enumerate(q["options"]):
                option_num = j + 1
                lines.append(f"   {option_num}) {option}")
        else:
            # 文本题：提示直接输入
            lines.append(f"   请直接输入您的回答")
        
        lines.append("")
    
    # 使用提示
    lines.append("---")
    lines.append("💡 **回复方式**：")
    lines.append("- 输入数字选择对应选项（如：1）")
    lines.append("- 或直接输入您的具体需求")
    lines.append("- 输入「跳过」可跳过澄清直接查询")
    
    return "\n".join(lines)


def parse_user_clarification_response(
    user_response: str, 
    questions: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    解析用户对澄清问题的回复
    
    支持的回复格式：
    - 单个数字：如 "1"，表示选择第一个选项
    - 多个数字：如 "1, 2"，表示第一题选1，第二题选2
    - 直接文本：如 "最近7天的销售额"
    - "跳过"：跳过澄清
    
    Args:
        user_response: 用户的回复文本
        questions: 澄清问题列表
        
    Returns:
        解析后的回答列表，每项包含 question_id 和 answer
    """
    if not user_response or not questions:
        return []
    
    response_text = user_response.strip()
    
    # 检查是否跳过
    skip_keywords = ["跳过", "skip", "算了", "直接查询", "不用了"]
    if response_text.lower() in skip_keywords:
        logger.info("用户选择跳过澄清")
        return []
    
    answers = []
    
    # 尝试解析数字回复
    import re
    
    # 检查是否是纯数字回复（可能包含逗号分隔）
    number_pattern = r'^[\d,，\s]+$'
    if re.match(number_pattern, response_text):
        # 分割数字
        numbers = re.findall(r'\d+', response_text)
        
        for i, q in enumerate(questions):
            if i < len(numbers):
                num = int(numbers[i])
                
                if q.get("type") == "choice" and q.get("options"):
                    # 选择题：将数字转换为选项
                    options = q["options"]
                    if 1 <= num <= len(options):
                        answer_text = options[num - 1]
                    else:
                        # 数字超出范围，使用原始数字
                        answer_text = str(num)
                else:
                    # 文本题：使用原始数字
                    answer_text = str(num)
                
                answers.append({
                    "question_id": q["id"],
                    "answer": answer_text
                })
            else:
                # 没有足够的数字，后续问题使用空字符串
                break
        
        if answers:
            logger.info(f"解析数字回复: {answers}")
            return answers
    
    # 非数字回复：将整个回复作为第一个问题的答案
    # 或者智能匹配到最相关的问题
    if questions:
        first_question = questions[0]
        
        # 检查回复是否匹配某个选项
        if first_question.get("type") == "choice" and first_question.get("options"):
            for option in first_question["options"]:
                if option.lower() in response_text.lower() or response_text.lower() in option.lower():
                    answers.append({
                        "question_id": first_question["id"],
                        "answer": option
                    })
                    logger.info(f"匹配到选项: {option}")
                    return answers
        
        # 默认：将回复作为第一个问题的答案
        answers.append({
            "question_id": first_question["id"],
            "answer": response_text
        })
        logger.info(f"使用回复作为第一个问题的答案: {response_text[:50]}...")
    
    return answers


def should_skip_clarification(query: str) -> bool:
    """
    快速判断是否可以跳过澄清检测（用于优化性能）
    
    对于某些明显明确的查询，可以直接跳过LLM检测
    
    Args:
        query: 用户查询
        
    Returns:
        bool - 是否跳过澄清
    """
    # 包含具体日期的查询通常不需要澄清
    import re
    
    # 检测具体日期格式
    date_patterns = [
        r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}',  # 2024-01-01, 2024年1月1日
        r'\d{4}[-/年]\d{1,2}[-/月]',           # 2024-01, 2024年1月
        r'今[天日]|昨[天日]|前[天日]',          # 今天、昨天
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, query):
            logger.debug(f"查询包含具体日期，跳过澄清: {query[:30]}")
            return True
    
    # 非常简单的查询可能不需要澄清
    simple_patterns = [
        r'^查[询看]所有',
        r'^显示全部',
        r'^列出.*表',
        r'ID[=为是]\d+',
    ]
    
    for pattern in simple_patterns:
        if re.search(pattern, query):
            logger.debug(f"查询模式简单，跳过澄清: {query[:30]}")
            return True
    
    return False


# ============================================================================
# @tool 包装函数（保留以供代理系统使用）
# ============================================================================

@tool
def quick_clarification_check(query: str, connection_id: int = 15) -> Dict[str, Any]:
    """快速检测用户查询是否需要澄清（工具版本）"""
    return _quick_clarification_check_impl(query, connection_id)


@tool
def enrich_query_with_clarification(
    original_query: str, 
    clarification_responses: List[Dict[str, str]]
) -> Dict[str, Any]:
    """将用户的澄清回复整合到原始查询中（工具版本）"""
    return _enrich_query_with_clarification_impl(original_query, clarification_responses)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 内部函数（直接调用，避免流式传输）
    "_quick_clarification_check_impl",
    "_enrich_query_with_clarification_impl",
    # 工具版本（供代理系统使用）
    "quick_clarification_check",
    "enrich_query_with_clarification",
    # 辅助函数
    "format_clarification_questions",
    "format_clarification_text",
    "parse_user_clarification_response",
    "should_skip_clarification",
]
