"""
澄清代理 (Clarification Agent)

核心职责：
1. 检测用户查询中的模糊性（基于 Schema 信息）
2. 检测流程中的错误需要用户确认
3. 检测分析需要更多输入
4. 生成澄清问题并暂停流程等待用户确认

触发场景：
- 用户问题模糊（如"最近"、"大客户"）
- SQL 执行报错需用户确认
- 分析深度不足需用户补充信息

设计原则：
- 由 Supervisor 统一调度
- 使用 LLM 决策，不依赖关键词匹配
- 必须在 Schema Agent 之后执行
- 使用 interrupt() 暂停流程等待用户确认
"""
from typing import Dict, Any, List, Optional, Union
import logging
import json

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import interrupt
from langgraph.config import get_stream_writer
from typing_extensions import Annotated

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


# ============================================================================
# 工具函数
# ============================================================================

@tool
def check_clarification_need(
    user_query: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """
    检测用户查询是否需要澄清。
    
    支持两种场景：
    1. 用户查询模糊（如"最近"、"大客户"）
    2. SQL 执行错误需要业务化澄清
    
    Args:
        user_query: 用户的自然语言查询
    """
    try:
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        
        # 从状态中提取上下文
        schema_info = state.get("schema_info", {})
        schema_context = build_schema_context(schema_info)
        clarification_context = state.get("clarification_context", {})
        
        # 判断触发场景
        trigger = clarification_context.get("trigger") if clarification_context else None
        
        # 场景 1: SQL 执行错误 - 业务化澄清
        if trigger == "sql_execution_error":
            return _handle_sql_error_clarification(llm, clarification_context, user_query, schema_context)
        
        # 场景 2: 用户查询模糊 - 传统澄清
        return _handle_ambiguous_query_clarification(llm, user_query, schema_context, clarification_context)
        
    except Exception as e:
        logger.error(f"澄清检测失败: {e}")
        return json.dumps({
            "needs_clarification": False,
            "reason": f"检测失败: {str(e)}",
            "questions": []
        })


def _handle_sql_error_clarification(
    llm, 
    clarification_context: Dict[str, Any], 
    user_query: str,
    schema_context: str
) -> str:
    """
    处理 SQL 错误场景的业务化澄清
    
    原则：
    - 完全基于业务语义表达
    - 严禁暴露表名、字段名、SQL 语句等技术细节
    - 给用户提供可理解的选项
    """
    business_error = clarification_context.get("error", "查询执行遇到问题")
    
    prompt = f"""你是一个专业的业务分析师，需要帮助用户解决查询问题。

**用户的原始需求**：{user_query}

**遇到的问题**：{business_error}

**数据范围信息**（用于生成业务化选项）：
{schema_context}

**你的任务**：
1. 用业务语言（而非技术术语）向用户说明问题
2. 基于数据范围信息，提供 2-3 个可能的调整方案供用户选择
3. **严格禁止**：不要提及表名、字段名、SQL、数据库等技术词汇

**返回格式**（JSON）：
{{
    "needs_clarification": true,
    "reason": "业务化的问题描述（不含技术细节）",
    "questions": [
        {{
            "id": "q1",
            "question": "请选择您想要的调整方式：",
            "type": "choice",
            "options": [
                "重新尝试当前查询",
                "调整查询的时间范围",
                "更换其他数据维度"
            ]
        }}
    ]
}}

**示例（正确）**：
- ✅ "查询的数据维度可能不存在，建议调整查询内容"
- ✅ "当前查询范围可能较大，建议缩小时间范围"

**示例（错误）**：
- ❌ "字段 order_date 不存在"
- ❌ "表 orders 找不到"
- ❌ "SQL语法错误"

只返回 JSON，不要有其他说明。"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


def _handle_ambiguous_query_clarification(
    llm,
    user_query: str, 
    schema_context: str,
    clarification_context: Optional[Dict[str, Any]]
) -> str:
    """处理用户查询模糊的传统澄清场景"""
    # 构建额外上下文
    extra_context = ""
    if clarification_context:
        if clarification_context.get("error"):
            extra_context = f"\n\n**错误信息**：{clarification_context['error']}"
        if clarification_context.get("analysis_need"):
            extra_context = f"\n\n**分析需求**：{clarification_context['analysis_need']}"
    
    prompt = f"""你是一个专业的数据查询意图分析专家。请分析用户查询是否需要澄清。

**用户查询**: {user_query}

**数据库结构信息**:
{schema_context}
{extra_context}

**判断原则**:
1. 如果查询足够明确，可以直接生成 SQL，则不需要澄清
2. 如果存在模糊性（如"最近"、"大客户"），需要澄清
3. 如果有错误信息，需要用户确认修正方案
4. 严禁擅自替用户做决策

**必须澄清的情况**:
- 时间范围模糊：使用"最近"、"近期"等词但没有具体范围
- 筛选条件模糊：使用"大客户"、"核心产品"等主观描述
- 字段不明确：说"查看订单"但没说要哪些字段

**不需要澄清的情况**:
- 查询包含具体日期（如"2023年"）
- 查询包含具体数值（如"大于100"）
- 查询意图已经非常明确

**严禁询问的技术问题（绝对不能问用户这些）**:
- 数据库类型（MySQL、PostgreSQL、SQLite 等）
- 字段的数据类型或存储格式（如日期格式 YYYY-MM-DD、VARCHAR 等）
- 表名、字段名、SQL 语法相关问题
- 任何需要用户了解数据库技术知识才能回答的问题
这些信息应由系统自动从数据库元数据获取，不应询问用户。

请返回 JSON 格式:
{{
    "needs_clarification": true/false,
    "reason": "判断原因",
    "questions": [
        {{
            "id": "q1",
            "question": "问题内容",
            "type": "choice",
            "options": ["选项1", "选项2", "选项3"]
        }}
    ]
}}

注意：
- 如果不需要澄清，questions 为空数组
- 选项必须来自数据库结构信息
- 最多生成 2 个问题

只返回 JSON。"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


@tool
def request_user_clarification(
    questions: List[Dict[str, Any]],
    reason: str,
    original_query: str,
) -> str:
    """
    向用户请求澄清，暂停流程等待用户确认。
    
    Args:
        questions: 澄清问题列表
        reason: 需要澄清的原因
        original_query: 原始用户查询
        
    Returns:
        用户的澄清回复
    """
    # 格式化问题
    formatted_questions = format_clarification_questions(questions)
    
    # 使用 interrupt 暂停流程
    interrupt_data = {
        "type": "clarification_request",
        "questions": formatted_questions,
        "reason": reason,
        "original_query": original_query,
    }
    
    logger.info(f"请求用户澄清: {reason}")
    user_response = interrupt(interrupt_data)
    
    return json.dumps({
        "user_response": user_response,
        "original_query": original_query
    })


@tool
def enrich_query_with_clarification(
    original_query: str,
    clarification_responses: List[Dict[str, str]],
) -> str:
    """
    将用户的澄清回复整合到原始查询中。
    
    Args:
        original_query: 原始用户查询
        clarification_responses: 澄清回复列表
        
    Returns:
        增强后的查询
    """
    if not clarification_responses:
        return json.dumps({
            "enriched_query": original_query,
            "clarification_summary": "无澄清信息"
        })
    
    # 构建澄清信息
    clarification_parts = []
    for resp in clarification_responses:
        answer = resp.get("answer", "")
        if answer:
            clarification_parts.append(answer)
    
    if not clarification_parts:
        return json.dumps({
            "enriched_query": original_query,
            "clarification_summary": "无有效澄清信息"
        })
    
    # 整合到查询中
    clarification_summary = "、".join(clarification_parts)
    enriched_query = f"{original_query}（{clarification_summary}）"
    
    logger.info(f"查询已增强: {enriched_query[:100]}...")
    
    return json.dumps({
        "enriched_query": enriched_query,
        "clarification_summary": clarification_summary
    })


# ============================================================================
# Clarification Agent 类
# ============================================================================

class ClarificationAgent:
    """
    澄清代理 - 负责检测模糊性并请求用户确认
    
    职责边界：
    - 只负责检测是否需要澄清
    - 只负责生成澄清问题
    - 只负责整合用户回复
    - 不负责 SQL 生成、执行等其他工作
    """
    
    def __init__(self):
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [
            check_clarification_need,
            request_user_clarification,
            enrich_query_with_clarification,
        ]
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """创建 ReAct Agent"""
        system_prompt = """你是一个澄清代理，负责检测用户查询是否需要澄清。

**你的职责**：
1. 基于 Schema 信息，检测用户查询是否存在模糊性
2. 如果需要澄清，生成澄清问题并请求用户确认
3. 整合用户的澄清回复，生成增强查询

**工作流程**：
1. 使用 check_clarification_need 检测是否需要澄清
2. 如果需要澄清，使用 request_user_clarification 请求用户确认
3. 收到用户回复后，使用 enrich_query_with_clarification 整合信息

**重要原则**：
- 严禁擅自替用户做决策
- 澄清选项必须来自数据库结构
- 如果不需要澄清，直接返回"无需澄清，可以继续执行"
- 每次最多生成 2 个问题"""

        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            name="clarification_agent",
            state_schema=SQLMessageState,  # 使用自定义 state_schema 以支持 connection_id 等字段
        )
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        处理澄清检测
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 提取用户查询
        user_query = state.get("enriched_query")
        if not user_query:
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, 'type') and msg.type == 'human':
                    user_query = msg.content
                    break
        
        if not user_query:
            return {
                "messages": [AIMessage(content="无法提取用户查询")],
                "current_stage": "sql_generation"
            }
        
        # 构建 Schema 上下文
        schema_info = state.get("schema_info", {})
        schema_context = build_schema_context(schema_info)
        
        # 检查是否有额外的澄清上下文（如错误信息）
        clarification_context = state.get("clarification_context")
        
        # 准备输入消息
        input_msg = f"""请检测以下查询是否需要澄清：

用户查询: {user_query}

Schema 信息和上下文已通过状态注入，请直接使用工具进行检测。"""

        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_thought_event
        writer = get_stream_writer()
        if writer:
            writer(create_thought_event(
                agent="clarification_agent",
                thought="我正在检查您的问题是否存在歧义（如时间范围不明确或业务概念多义）。如果需要，我会请求您进一步补充信息。",
                plan="完成歧义检测后，如果没有问题，我将转交给 SQL 生成专家。"
            ))

        # 调用 Agent
        result = await self.agent.ainvoke(
            {"messages": [HumanMessage(content=input_msg)]}
        )
        
        # 提取结果
        last_message = result.get("messages", [])[-1] if result.get("messages") else None
        
        # 检查是否有增强查询
        if last_message and hasattr(last_message, 'content'):
            content = last_message.content
            # 尝试解析是否有增强查询
            if "enriched_query" in content:
                try:
                    # 可能在工具调用结果中
                    pass
                except:
                    pass
        
        # 更新状态
        state["current_stage"] = "sql_generation"
        
        # 输出流式消息
        writer = get_stream_writer()
        if writer:
            from app.schemas.stream_events import create_stage_message_event
            writer(create_stage_message_event(
                message="澄清检测完成",
                step="clarification_agent"
            ))
        
        return {
            "messages": result.get("messages", []),
            "current_stage": "sql_generation"
        }


# ============================================================================
# 辅助函数
# ============================================================================

def build_schema_context(schema_info: Optional[Dict[str, Any]]) -> str:
    """构建用于澄清的 Schema 上下文"""
    if not schema_info:
        return "（无 Schema 信息）"
    
    lines = []
    
    # 表信息
    tables = schema_info.get("tables", [])
    if tables:
        lines.append("【可用的数据表】:")
        for t in tables:
            table_name = t.get("table_name", t.get("name", ""))
            description = t.get("description", t.get("comment", ""))
            if description:
                lines.append(f"  - {table_name}: {description}")
            else:
                lines.append(f"  - {table_name}")
    
    # 字段信息
    columns = schema_info.get("columns", [])
    if columns:
        lines.append("\n【可用的字段】:")
        table_columns = {}
        for c in columns:
            table_name = c.get("table_name", "")
            if table_name not in table_columns:
                table_columns[table_name] = []
            table_columns[table_name].append(c)
        
        for table_name, cols in table_columns.items():
            col_names = [c.get("column_name", c.get("name", "")) for c in cols]
            lines.append(f"  - {table_name}: {', '.join(col_names)}")
    
    # 枚举值
    semantic_layer = schema_info.get("semantic_layer", {})
    enum_columns = semantic_layer.get("enum_columns", [])
    if enum_columns:
        lines.append("\n【字段可选值】:")
        for enum_col in enum_columns:
            table_name = enum_col.get("table_name", "")
            col_name = enum_col.get("column_name", "")
            values = enum_col.get("values", [])
            if values:
                values_str = ", ".join(str(v) for v in values[:10])
                lines.append(f"  - {table_name}.{col_name}: [{values_str}]")
    
    # 日期字段
    date_columns = semantic_layer.get("date_columns", [])
    if date_columns:
        lines.append("\n【日期字段】:")
        for date_col in date_columns:
            table_name = date_col.get("table_name", "")
            col_name = date_col.get("column_name", "")
            date_min = date_col.get("date_min", "")
            date_max = date_col.get("date_max", "")
            if date_min or date_max:
                lines.append(f"  - {table_name}.{col_name}: {date_min} ~ {date_max}")
    
    return "\n".join(lines) if lines else "（Schema 信息不足）"


def format_clarification_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化澄清问题"""
    formatted = []
    for i, q in enumerate(questions):
        formatted_q = {
            "id": q.get("id", f"q{i+1}"),
            "question": q.get("question", ""),
            "type": q.get("type", "text"),
        }
        if formatted_q["type"] == "choice":
            formatted_q["options"] = q.get("options", [])
        formatted.append(formatted_q)
    return formatted


def parse_user_clarification_response(
    user_response: Union[str, Dict[str, Any]], 
    questions: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """解析用户对澄清问题的回复"""
    if not user_response or not questions:
        return []
    
    # 处理字典格式
    if isinstance(user_response, dict):
        if "answers" in user_response:
            return user_response["answers"]
        return []
    
    # 处理字符串格式
    if not isinstance(user_response, str):
        return []
    
    response_text = user_response.strip()
    
    # 检查是否跳过
    skip_keywords = ["跳过", "skip", "算了", "直接查询"]
    if response_text.lower() in skip_keywords:
        return []
    
    # 将回复作为第一个问题的答案
    if questions:
        return [{
            "question_id": questions[0]["id"],
            "answer": response_text
        }]
    
    return []


def should_skip_clarification(query: str) -> bool:
    """快速判断是否可以跳过澄清检测"""
    query_lower = query.lower().strip()
    
    # 空查询或极短查询
    if len(query) < 5:
        return True
    
    # 纯闲聊
    chat_keywords = ['你好', 'hello', 'hi', '谢谢', 'thanks', '帮助', 'help']
    if query_lower in chat_keywords:
        return True
    
    return False


# ============================================================================
# 创建全局实例
# ============================================================================

clarification_agent = ClarificationAgent()


# ============================================================================
# 向后兼容的别名（供 clarification_node.py 使用）
# ============================================================================

def _quick_clarification_check_impl(
    query: str, 
    connection_id: Optional[int] = None,
    schema_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    向后兼容：快速检测用户查询是否需要澄清
    
    注意：这是为了兼容旧代码。新代码应该使用 ClarificationAgent。
    """
    try:
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR, use_wrapper=True)
        
        schema_context = build_schema_context(schema_info)
        
        prompt = f"""你是一个专业的数据查询意图分析专家。请分析用户查询是否需要澄清。

**用户查询**: {query}

**数据库连接ID**: {connection_id}

**数据库结构信息**:
{schema_context}

**最重要的规则：澄清选项必须来自上面的数据库结构！**

**判断原则**:
1. 如果查询足够明确，可以直接生成 SQL，则不需要澄清
2. 如果存在模糊性（如"最近"、"大客户"），需要澄清
3. 严禁擅自替用户做决策

**必须检测并澄清以下情况**:
1. 时间范围模糊：用户使用"最近"、"近期"等词汇，但没有指定具体天数/范围。
2. 筛选条件模糊：用户提到"大客户"、"优质客户"等主观描述。
3. 字段/维度不明确：用户说"按地区"但库里有省、市、区。

**以下情况不需要澄清**:
- 查询意图已经非常明确，包含了具体的日期、数值或枚举值。

请以JSON格式返回:
{{
    "needs_clarification": true/false,
    "reason": "判断原因",
    "ambiguities": [],
    "questions": [
        {{
            "id": "q1",
            "question": "问题内容",
            "type": "choice",
            "options": ["选项1", "选项2", "选项3", "选项4"]
        }}
    ]
}}

注意：
- 如果不需要澄清，questions 为空数组
- 每个问题必须包含 type 和 options 字段
- type 为 "choice" 表示选择题，options 为可选项数组
- 选项必须来自数据库结构信息，至少提供 3-5 个有意义的选项
- 最多生成 2 个问题

只返回JSON。"""

        response = llm.invoke([HumanMessage(content=prompt)])
        
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        needs_clarification = result.get("needs_clarification", False)
        
        if not needs_clarification:
            return {
                "needs_clarification": False,
                "questions": [],
                "reason": result.get("reason", "查询足够明确")
            }
        
        # 只处理 high 严重度
        ambiguities = result.get("ambiguities", [])
        significant = [a for a in ambiguities if a.get("severity") == "high"]
        
        if not significant and ambiguities:
            # 如果没有标记 severity，默认认为需要澄清
            significant = ambiguities
        
        questions = result.get("questions", [])
        
        return {
            "needs_clarification": bool(questions),
            "questions": questions,
            "reason": result.get("reason", "查询存在模糊性"),
            "ambiguities": significant
        }
        
    except Exception as e:
        logger.error(f"澄清检测失败: {e}")
        return {
            "needs_clarification": False,
            "questions": [],
            "reason": f"检测失败: {str(e)}"
        }


def _enrich_query_with_clarification_impl(
    original_query: str, 
    clarification_responses: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    向后兼容：将用户的澄清回复整合到原始查询中
    """
    if not clarification_responses:
        return {
            "enriched_query": original_query,
            "clarification_summary": "无澄清信息"
        }
    
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
    
    clarification_summary = "、".join(clarification_parts)
    enriched_query = f"{original_query}（{clarification_summary}）"
    
    return {
        "enriched_query": enriched_query,
        "clarification_summary": clarification_summary
    }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "ClarificationAgent",
    "clarification_agent",
    "format_clarification_questions",
    "parse_user_clarification_response",
    "should_skip_clarification",
    "build_schema_context",
    # 向后兼容
    "_quick_clarification_check_impl",
    "_enrich_query_with_clarification_impl",
]
