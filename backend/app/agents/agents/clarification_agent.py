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
from app.core.llm_wrapper import LLMWrapper

# 配置日志
logger = logging.getLogger(__name__)


# ============================================================================
# 澄清检测提示词（合并检测和问题生成为一次调用）
# ============================================================================

CLARIFICATION_UNIFIED_PROMPT = """你是一个专业的数据查询意图分析专家。请分析以下用户查询，判断是否存在模糊或不明确的地方，如果需要澄清则同时生成澄清问题。

用户查询: {query}

数据库连接ID: {connection_id}

**检测的模糊类型** (按优先级排序):
1. 时间范围模糊: 如"最近"、"近期"、"上个月"等没有明确日期的表述
2. 筛选条件模糊: 如"大客户"、"热销产品"等主观描述
3. 字段/指标模糊: 如"查看订单"但没说明需要哪些字段（金额、数量、状态？）
4. 分组维度模糊: 如"按地区"但不明确是省、市还是区
5. 排序/数量模糊: 如"前几名"、"一些"等不明确的数量

**重要判断原则**:
- 如果查询已经足够明确，可以直接生成SQL，则不需要澄清
- 只有当模糊性会显著影响查询结果时才需要澄清
- 简单查询（如"查询所有用户"）通常不需要澄清
- 包含具体时间、具体数值、具体条件的查询不需要澄清
- 只处理高/中严重度的模糊性，低严重度可以忽略

**问题生成规则**:
- 最多生成 3 个澄清问题
- 优先级：时间范围 > 筛选条件 > 字段选择 > 分组维度
- 优先生成选择题（更便于用户回答）
- 每个问题需要唯一的ID（如 q1, q2, q3）

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

只返回JSON，不要其他内容。"""


# 结合 Schema 信息的澄清提示词
CLARIFICATION_WITH_SCHEMA_PROMPT = """你是一个专业的数据查询意图分析专家。请结合数据库结构信息，分析用户查询是否存在模糊或不明确的地方。

**用户查询**: {query}

**数据库连接ID**: {connection_id}

**数据库结构信息**:
{schema_context}

**🔴🔴🔴 最重要的规则：澄清选项必须来自上面的数据库结构！**
- 如果要澄清字段选择，选项必须是上面列出的实际字段名
- 如果要澄清筛选条件，选项必须是上面列出的字段可选值
- 如果要澄清时间范围，选项必须基于上面列出的日期字段范围
- 禁止生成数据库中不存在的选项！这会导致查询失败！

**🔴 默认不需要澄清！只有以下情况才需要澄清**:
1. 用户提到的概念在数据库中有多个可能的字段对应，需要确认用哪个
2. 用户使用了主观描述词（如"大客户"），但数据库中有明确的分类字段可以选择
3. 时间范围模糊，且数据库中有日期字段需要确定范围

**🟢 以下情况不需要澄清（直接返回 needs_clarification: false）**:
- 查询意图明确，可以直接映射到数据库字段
- 包含具体数字、具体时间、"所有/全部"等明确词汇
- 数据库结构信息不足以生成有意义的澄清选项

**问题生成规则** (如果确实需要澄清):
- 最多生成 2 个澄清问题
- 选项必须100%来自上面的数据库结构信息
- 使用用户能理解的业务语言描述选项

请以JSON格式返回分析结果:
{{
    "needs_clarification": true/false,
    "reason": "需要/不需要澄清的原因",
    "ambiguities": [
        {{
            "type": "字段选择|筛选条件|时间范围",
            "description": "具体描述模糊之处",
            "severity": "high|medium|low",
            "related_schema": "关联的表名或字段名"
        }}
    ],
    "questions": [
        {{
            "id": "q1",
            "question": "您想查看哪种类型的客户？",
            "type": "choice",
            "options": ["从数据库字段可选值中提取的选项"],
            "related_ambiguity": "筛选条件模糊",
            "source_field": "来源字段名（如 customer_type）"
        }}
    ]
}}

**注意**:
- 默认返回 needs_clarification: false
- 只有 high 严重度且能从数据库结构生成有效选项时才澄清
- 如果数据库结构信息不足，宁可不澄清也不要瞎猜选项

只返回JSON，不要其他内容。"""





# ============================================================================
# 内部函数（不使用 @tool 装饰器，避免 LangGraph 的工具流式处理）
# ============================================================================

def _quick_clarification_check_impl(
    query: str, 
    connection_id: Optional[int] = None,
    schema_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    快速检测用户查询是否需要澄清（内部实现，不使用 @tool 装饰器）
    
    优化版：结合 Schema 信息进行智能澄清
    - 根据实际表结构生成澄清问题
    - 根据字段枚举值生成选项
    - 根据日期字段范围生成时间选项
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        schema_info: Schema 信息（包含 tables、columns、semantic_layer 等）
        
    Returns:
        Dict包含:
        - needs_clarification: bool - 是否需要澄清
        - questions: List - 澄清问题列表（如果需要澄清）
        - reason: str - 判断原因
    """
    try:
        logger.info(f"开始澄清检测: {query[:50]}...")
        
        # 使用 LLMWrapper 统一处理重试和超时
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        
        # 构建 Schema 上下文
        schema_context = _build_schema_context_for_clarification(schema_info)
        
        # 使用结合 Schema 的提示词
        prompt = CLARIFICATION_WITH_SCHEMA_PROMPT.format(
            query=query,
            connection_id=connection_id,
            schema_context=schema_context
        )
        
        # 使用 invoke 进行同步调用（LLMWrapper 支持）
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 解析响应
        try:
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
        
        # ✅ 只处理 high 严重度的模糊性
        significant_ambiguities = [
            a for a in ambiguities 
            if a.get("severity") == "high"
        ]
        
        if not significant_ambiguities:
            logger.info("无高严重度模糊性，不需要澄清")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "模糊性较轻，可以继续执行"
            }
        
        questions = result.get("questions", [])
        
        if not questions:
            logger.warning("需要澄清但未生成问题，跳过澄清")
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": "无法生成澄清问题"
            }
        
        # ✅ 验证问题选项是否来自 Schema（防止越界）
        if schema_info:
            questions = _validate_clarification_options(questions, schema_info)
            if not questions:
                logger.warning("澄清选项验证失败，跳过澄清")
                return {
                    "needs_clarification": False,
                    "questions": [],
                    "reason": "无法生成有效的澄清选项"
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


def _build_schema_context_for_clarification(schema_info: Optional[Dict[str, Any]]) -> str:
    """
    构建用于澄清的 Schema 上下文
    
    重要：这个上下文决定了澄清选项的边界！
    澄清问题的选项必须100%来自这里的信息，不能凭空生成。
    
    Args:
        schema_info: Schema 信息
        
    Returns:
        格式化的 Schema 上下文字符串
    """
    if not schema_info:
        return "（无 Schema 信息，无法生成澄清选项，请直接执行查询）"
    
    lines = []
    
    # 1. 表信息 - 列出所有可用的表（不限制数量）
    tables = schema_info.get("tables", [])
    if tables:
        lines.append("【可用的数据表】（澄清时只能涉及这些表）:")
        for t in tables:
            table_name = t.get("table_name", t.get("name", ""))
            description = t.get("description", t.get("comment", ""))
            if description:
                lines.append(f"  - {table_name}: {description}")
            else:
                lines.append(f"  - {table_name}")
    
    # 2. 字段信息 - 按表分组，列出所有字段（不限制数量）
    columns = schema_info.get("columns", [])
    if columns:
        lines.append("\n【可用的字段】（澄清字段选择时只能从这里选）:")
        # 按表分组
        table_columns = {}
        for c in columns:
            table_name = c.get("table_name", "")
            if table_name not in table_columns:
                table_columns[table_name] = []
            table_columns[table_name].append(c)
        
        for table_name, cols in table_columns.items():
            col_names = []
            for c in cols:
                col_name = c.get("column_name", c.get("name", ""))
                description = c.get("description", c.get("comment", ""))
                if description:
                    col_names.append(f"{col_name}({description})")
                else:
                    col_names.append(col_name)
            lines.append(f"  - {table_name}: {', '.join(col_names)}")
    
    # 3. 枚举值 - 列出所有枚举字段（不限制数量）
    semantic_layer = schema_info.get("semantic_layer", {})
    enum_columns = semantic_layer.get("enum_columns", [])
    if enum_columns:
        lines.append("\n【字段可选值】（澄清筛选条件时只能用这些值作为选项）:")
        for enum_col in enum_columns:
            table_name = enum_col.get("table_name", "")
            col_name = enum_col.get("column_name", "")
            values = enum_col.get("values", [])
            if values:
                # 显示所有值，让 LLM 知道边界
                values_str = ", ".join(str(v) for v in values)
                lines.append(f"  - {table_name}.{col_name}: [{values_str}]")
    
    # 4. 日期字段范围 - 列出所有日期字段（不限制数量）
    date_columns = semantic_layer.get("date_columns", [])
    if date_columns:
        lines.append("\n【日期字段及数据范围】（澄清时间范围时参考）:")
        for date_col in date_columns:
            table_name = date_col.get("table_name", "")
            col_name = date_col.get("column_name", "")
            date_min = date_col.get("date_min", "")
            date_max = date_col.get("date_max", "")
            if date_min or date_max:
                lines.append(f"  - {table_name}.{col_name}: 数据范围 {date_min} ~ {date_max}")
    
    if not lines:
        return "（Schema 信息不足，无法生成有效的澄清选项，请直接执行查询）"
    
    # 添加强调说明
    lines.append("\n⚠️ 重要：澄清问题的所有选项必须来自上述信息，禁止生成不存在的选项！")
    
    return "\n".join(lines)


def _validate_clarification_options(
    questions: List[Dict[str, Any]], 
    schema_info: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    验证澄清问题的选项是否来自 Schema 信息
    
    防止 LLM 生成数据库中不存在的选项，导致查询失败。
    
    Args:
        questions: LLM 生成的澄清问题列表
        schema_info: Schema 信息
        
    Returns:
        验证通过的问题列表（移除无效选项的问题）
    """
    if not questions or not schema_info:
        return questions
    
    # 收集所有有效的值
    valid_values = set()
    
    # 1. 收集表名
    tables = schema_info.get("tables", [])
    for t in tables:
        table_name = t.get("table_name", t.get("name", ""))
        if table_name:
            valid_values.add(table_name.lower())
    
    # 2. 收集字段名和描述
    columns = schema_info.get("columns", [])
    for c in columns:
        col_name = c.get("column_name", c.get("name", ""))
        description = c.get("description", c.get("comment", ""))
        if col_name:
            valid_values.add(col_name.lower())
        if description:
            valid_values.add(description.lower())
    
    # 3. 收集枚举值（最重要！）
    semantic_layer = schema_info.get("semantic_layer", {})
    enum_columns = semantic_layer.get("enum_columns", [])
    for enum_col in enum_columns:
        values = enum_col.get("values", [])
        for v in values:
            if v is not None:
                valid_values.add(str(v).lower())
    
    # 4. 添加通用时间选项（这些是安全的）
    safe_time_options = [
        "最近7天", "最近30天", "本月", "上月", "本季度", "本年", 
        "今年", "去年", "最近3个月", "最近6个月", "全部"
    ]
    for opt in safe_time_options:
        valid_values.add(opt.lower())
    
    # 验证每个问题
    validated_questions = []
    for q in questions:
        q_type = q.get("type", "text")
        
        # 文本题不需要验证选项
        if q_type != "choice":
            validated_questions.append(q)
            continue
        
        options = q.get("options", [])
        if not options:
            # 没有选项的选择题，跳过
            logger.warning(f"选择题没有选项，跳过: {q.get('question', '')}")
            continue
        
        # 检查选项是否有效
        # 宽松验证：只要选项中的关键词在 valid_values 中出现即可
        valid_options = []
        for opt in options:
            opt_lower = str(opt).lower()
            # 检查选项本身或其中的关键词是否有效
            is_valid = opt_lower in valid_values
            if not is_valid:
                # 检查选项中是否包含有效值
                for valid_val in valid_values:
                    if valid_val in opt_lower or opt_lower in valid_val:
                        is_valid = True
                        break
            
            if is_valid:
                valid_options.append(opt)
            else:
                logger.warning(f"澄清选项不在 Schema 中，移除: {opt}")
        
        # 如果有效选项少于2个，这个问题没意义
        if len(valid_options) < 2:
            logger.warning(f"有效选项不足，跳过问题: {q.get('question', '')}")
            continue
        
        # 更新选项
        q["options"] = valid_options
        validated_questions.append(q)
    
    return validated_questions


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
    
    简化版 (2026-01-28): 
    - 只过滤极端情况（空查询、纯闲聊）
    - 其他情况交给 LLM 根据实际情况判断
    - 不依赖复杂的关键词匹配
    
    Args:
        query: 用户查询
        
    Returns:
        bool - 是否跳过澄清（True=跳过，False=需要LLM判断）
    """
    query_lower = query.lower().strip()
    query_len = len(query)
    
    # 1. 空查询或极短查询（小于5个字符）- 跳过澄清
    if query_len < 5:
        return True
    
    # 2. 纯闲聊 - 跳过澄清
    chat_keywords = ['你好', 'hello', 'hi', '谢谢', 'thanks', '再见', 'bye', '帮助', 'help']
    if query_lower in chat_keywords:
        return True
    
    # 3. 其他情况 - 交给 LLM 判断
    return False


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
