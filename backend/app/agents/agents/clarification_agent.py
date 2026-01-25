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
from typing import Dict, Any, List, Optional, Union
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
# 澄清检测提示词（合并检测和问题生成为一次调用）
# ============================================================================

CLARIFICATION_UNIFIED_PROMPT = """你是一个专业的数据查询意图分析专家。请分析以下用户查询，判断是否存在模糊或不明确的地方，如果需要澄清则同时生成澄清问题。

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
- 只处理高/中严重度的模糊性，低严重度可以忽略

请以JSON格式返回分析结果（一次性返回检测结果和澄清问题）:
{{
    "needs_clarification": true/false,
    "reason": "需要/不需要澄清的原因",
    "ambiguities": [
        {{
            "type": "时间范围|字段选择|筛选条件|分组维度|排序数量",
            "description": "具体描述模糊之处",
            "severity": "high|medium|low"
        }}
    ],
    "questions": [
        {{
            "id": "q1",
            "question": "您想查看哪个时间范围的数据？",
            "type": "choice",
            "options": ["最近7天", "最近30天", "最近3个月", "今年", "自定义时间段"],
            "related_ambiguity": "时间范围模糊"
        }}
    ]
}}

**注意**:
- 如果 needs_clarification 为 false，questions 数组应为空
- 如果 needs_clarification 为 true，必须提供 questions 数组
- questions 最多3个问题，优先生成选择题（更便于用户回答）
- 每个问题需要唯一的ID（如 q1, q2, q3）

只返回JSON，不要其他内容。"""





# ============================================================================
# 内部函数（不使用 @tool 装饰器，避免 LangGraph 的工具流式处理）
# ============================================================================

def _quick_clarification_check_impl(query: str, connection_id: Optional[int] = None) -> Dict[str, Any]:
    """
    快速检测用户查询是否需要澄清（内部实现，不使用 @tool 装饰器）
    
    优化版：使用单次LLM调用同时完成检测和问题生成，减少延迟
    
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
        
        # 获取 LLM 并禁用流式输出，防止 JSON 输出被流式传输到前端
        base_llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        # 使用 with_config 禁用流式输出
        llm = base_llm.with_config({"callbacks": []})
        
        # 优化：使用统一提示词，一次LLM调用同时完成检测和问题生成
        unified_prompt = CLARIFICATION_UNIFIED_PROMPT.format(
            query=query,
            connection_id=connection_id
        )
        
        # 使用 invoke 而不是 stream，并且不传递 callbacks
        response = llm.invoke([HumanMessage(content=unified_prompt)], config={"callbacks": []})
        
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
            
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 内容: {response.content[:200]}")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "解析失败，默认不需要澄清"
            }
        
        # 检查是否需要澄清
        needs_clarification = result.get("needs_clarification", False)
        
        if not needs_clarification:
            logger.info(f"查询明确，不需要澄清: {result.get('reason', '')}")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": result.get("reason", "查询足够明确")
            }
        
        # 获取模糊性分析
        ambiguities = result.get("ambiguities", [])
        
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
        
        # 获取澄清问题（已在同一次调用中生成）
        questions = result.get("questions", [])
        
        if not questions:
            logger.warning("需要澄清但未生成问题，跳过澄清")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "无法生成澄清问题"
            }
        
        logger.info(f"需要澄清，生成了 {len(questions)} 个问题")
        
        return {
            "needs_clarification": True,
            "questions": questions,
            "reason": result.get("reason", "查询存在模糊性"),
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


def parse_user_clarification_response(
    user_response: Union[str, Dict[str, Any]], 
    questions: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    解析用户对澄清问题的回复
    
    支持两种格式：
    1. 字符串格式：用户直接输入的文本
       - 单个数字：如 "1"，表示选择第一个选项
       - 多个数字：如 "1, 2"，表示第一题选1，第二题选2
       - 直接文本：如 "最近7天的销售额"
       - "跳过"：跳过澄清
    2. 字典格式：前端提交的结构化数据
       {
         "session_id": "...",
         "answers": [
           {"question_id": "q1", "answer": "总销售额"},
           {"question_id": "q2", "answer": "最近30天"}
         ]
       }
    
    Args:
        user_response: 用户的回复（字符串或字典）
        questions: 澄清问题列表
        
    Returns:
        解析后的回答列表，每项包含 question_id 和 answer
    """
    if not user_response or not questions:
        return []
    
    # ====================================================================
    # 处理字典格式（前端提交的结构化数据）
    # ====================================================================
    if isinstance(user_response, dict):
        # 检查是否包含answers字段
        if "answers" in user_response:
            answers = user_response["answers"]
            if isinstance(answers, list) and answers:
                logger.info(f"解析结构化回复: {len(answers)}个答案")
                return answers
        
        # 如果是其他字典格式，尝试将整个字典作为第一个问题的答案
        if questions:
            logger.warning(f"未知字典格式，将整个字典作为答案: {user_response}")
            return [{
                "question_id": questions[0]["id"],
                "answer": str(user_response)
            }]
        return []
    
    # ====================================================================
    # 处理字符串格式
    # ====================================================================
    if not isinstance(user_response, str):
        logger.warning(f"不支持的回复类型: {type(user_response)}")
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
    快速判断是否可以跳过澄清检测
    
    简化版本：只保留核心规则，减少复杂度
    原则：既不过度澄清，也不遗漏真正模糊的查询
    
    修复 (2026-01-22): 
    - 调整阈值逻辑，短查询需要额外检查是否包含模糊词
    - 添加更多明确查询的识别模式
    
    Args:
        query: 用户查询
        
    Returns:
        bool - 是否跳过澄清
    """
    import re
    
    query_lower = query.lower().strip()
    query_len = len(query)
    
    # ============================================
    # 1. 短查询的特殊处理
    # ============================================
    if query_len < 8:
        # 非常短的查询，检查是否是数据查询意图
        query_intent_words = ['查询', '统计', '显示', '列出', '获取', '查一下', '查看', '找', '搜', '数据']
        if any(word in query for word in query_intent_words):
            # 如 "查一下数据" - 太短且模糊，需要澄清
            return False
        # 如 "你好" - 可能是闲聊，跳过澄清
        return True
    
    # 8-20 字符的查询需要更细致的判断
    if query_len < 20:
        # 检查是否包含明确的条件
        has_specific_condition = any([
            re.search(r'\d+', query),  # 包含数字
            re.search(r'[=><]', query),  # 包含比较运算符
            re.search(r'(ID|编号|名称)', query, re.IGNORECASE),  # 包含ID等关键词
        ])
        if has_specific_condition:
            return True
        
        # 检查是否是模糊查询
        ambiguous_words = ['最近', '一些', '几个', '前几', '大概', '差不多', '左右']
        if any(word in query for word in ambiguous_words):
            return False  # 包含模糊词，需要澄清
    
    # ============================================
    # 2. 包含具体日期 - 跳过澄清
    # ============================================
    date_patterns = [
        r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}',  # 2024-01-01
        r'今[天日]|昨[天日]|前[天日]',       # 今天、昨天
        r'本[周月季年]|上[周月季年]',        # 本周、上月
        r'最近\d+[天周月年]',                # 最近30天
        r'\d+月\d+[日号]',                   # 1月1日
    ]
    if any(re.search(p, query) for p in date_patterns):
        return True
    
    # ============================================
    # 3. 包含具体数量 - 跳过澄清
    # ============================================
    quantity_patterns = [
        r'前\d+[个名条项]',    # 前10个
        r'top\s*\d+',           # top 10
        r'limit\s*\d+',         # limit 10
        r'\d+[条个项]',         # 10条
        r'第\d+',               # 第5
    ]
    if any(re.search(p, query_lower) for p in quantity_patterns):
        return True
    
    # ============================================
    # 4. 简单聚合查询 - 跳过澄清
    # ============================================
    if re.search(r'^(统计|计算|求|查询).*(总数|总量|总额|平均|最大|最小|数量)', query):
        return True
    
    # ============================================
    # 5. 查询所有/全部 - 跳过澄清
    # ============================================
    if re.search(r'^(查[询看]|显示|列出|获取)(所有|全部|所有的)', query):
        return True
    
    # ============================================
    # 6. 包含明确条件 - 跳过澄清
    # ============================================
    # 包含ID/编号条件
    if re.search(r'(ID|编号|订单号|用户名)\s*[=为是:：]?\s*[\w\d]+', query, re.IGNORECASE):
        return True
    
    # 包含具体名称/值（引号内的内容）
    if re.search(r'["\'""].*?["\'""]', query):
        return True
    
    # 包含比较条件
    if re.search(r'(大于|小于|等于|超过|低于|不少于|不超过)\s*\d+', query):
        return True
    
    # ============================================
    # 7. 包含明确模糊词 - 需要澄清
    # ============================================
    high_ambiguity_words = [
        '最近的', '近期的', '一些', '某些', '部分',
        '大客户', '小客户', '热门', '冷门',
        '高价值', '低价值', '重要的', '主要的'
    ]
    if any(word in query for word in high_ambiguity_words):
        return False  # 明确需要澄清
    
    # ============================================
    # 8. 默认：中等长度查询跳过澄清
    # ============================================
    # 如果到这里还没有决定，默认跳过澄清
    # （让 LLM 澄清检测做最终判断）
    return False


# 已移除 _contains_ambiguous_words 函数，逻辑已集成到 should_skip_clarification 中


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 内部函数（直接调用，避免流式传输）
    "_quick_clarification_check_impl",
    "_enrich_query_with_clarification_impl",
    # 辅助函数
    "format_clarification_questions",
    "parse_user_clarification_response",
    "should_skip_clarification",
]
