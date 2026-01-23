"""
Schema 澄清节点 - 澄清点C

在 schema_agent 获取表结构后、sql_generator 之前进行深度澄清检测。
这是最精准的澄清点，使用纯 LLM 分析以下歧义：

1. 字段歧义：用户提到的概念在多个表/字段中都存在
2. 关系歧义：表之间存在多条关联路径
3. 指标歧义：用户的查询意图可以对应多个不同的计算方式
4. 时间范围歧义：查询涉及时间但未明确范围
5. 聚合方式歧义：统计方式不明确（求和、平均、计数等）

使用 LangGraph interrupt() 机制暂停等待用户确认。

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/
"""
from typing import Dict, Any, List, Optional
import logging
import json

from langgraph.types import interrupt
from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.state import SchemaInfo

logger = logging.getLogger(__name__)


# ============================================================================
# LLM 提示词模板
# ============================================================================

SCHEMA_CLARIFICATION_PROMPT = """你是一个专业的数据库查询分析专家。请根据用户查询和数据库表结构，判断是否存在需要用户澄清的歧义。

**用户查询**: {query}

**数据库表结构**:
{schema_info}

**表关系**:
{relationships}

**分析任务**:
请仔细分析用户查询与数据库结构，检测以下类型的歧义：

1. **字段歧义** - 用户提到的概念可能对应多个字段
   - 例如："金额" 可能指 order_amount、payment_amount、refund_amount
   - 例如："时间" 可能指 create_time、update_time、pay_time

2. **关系歧义** - 表之间存在多条可能的关联路径
   - 例如：用户表和订单表可以通过 user_id 或 operator_id 关联

3. **指标歧义** - 统计指标的计算方式不明确
   - 例如："销售额" 可以是订单金额、实际支付金额、扣除退款后金额
   - 例如："利润" 的计算公式可能有多种

4. **聚合歧义** - 聚合维度或方式不明确
   - 例如："按月统计" 是自然月还是30天周期
   - 例如："平均值" 是简单平均还是加权平均

5. **时间范围歧义** - 涉及时间但范围不明确
   - 例如："最近的订单" 是今天、本周、还是本月
   - 例如："历史数据" 的具体时间范围

**输出要求**:
请返回 JSON 格式的分析结果：

```json
{{
    "needs_clarification": true/false,
    "confidence": 0.0-1.0,
    "ambiguities": [
        {{
            "type": "field_ambiguity|relation_ambiguity|metric_ambiguity|aggregation_ambiguity|time_range_ambiguity",
            "description": "歧义描述",
            "options": ["选项1", "选项2", ...],
            "recommendation": "推荐选项（如果有明显合理的默认值）",
            "question": "向用户提出的澄清问题"
        }}
    ],
    "clarification_questions": [
        {{
            "question_id": "q1",
            "question": "澄清问题",
            "options": ["选项1", "选项2", "选项3"],
            "type": "single_choice|multiple_choice",
            "default": "默认选项（可选）"
        }}
    ],
    "analysis_summary": "分析总结，说明查询意图和潜在问题"
}}
```

**注意事项**:
- 只有当歧义可能导致完全不同的查询结果时，才需要澄清
- 如果有明显合理的默认值，可以设置 recommendation 并降低澄清必要性
- 对于简单明确的查询，设置 needs_clarification: false
- confidence 表示对查询理解的置信度，低于 0.7 通常需要澄清"""


# ============================================================================
# 辅助函数
# ============================================================================

def format_schema_info(schema_info: Optional[SchemaInfo]) -> str:
    """格式化表结构信息供 LLM 使用"""
    if not schema_info:
        return "无表结构信息"
    
    lines = []
    tables = schema_info.tables if hasattr(schema_info, 'tables') else schema_info.get('tables', {})
    
    for table_name, table_info in tables.items():
        if isinstance(table_info, dict):
            description = table_info.get('description', table_info.get('comment', ''))
            columns = table_info.get('columns', [])
        else:
            description = getattr(table_info, 'description', getattr(table_info, 'comment', ''))
            columns = getattr(table_info, 'columns', [])
        
        lines.append(f"\n### 表: {table_name}")
        if description:
            lines.append(f"描述: {description}")
        
        if columns:
            lines.append("字段:")
            for col in columns[:20]:  # 限制字段数量
                if isinstance(col, dict):
                    col_name = col.get('name', col.get('column_name', ''))
                    col_type = col.get('type', col.get('data_type', ''))
                    col_desc = col.get('description', col.get('comment', ''))
                else:
                    col_name = getattr(col, 'name', getattr(col, 'column_name', ''))
                    col_type = getattr(col, 'type', getattr(col, 'data_type', ''))
                    col_desc = getattr(col, 'description', getattr(col, 'comment', ''))
                
                col_line = f"  - {col_name} ({col_type})"
                if col_desc:
                    col_line += f": {col_desc}"
                lines.append(col_line)
    
    return "\n".join(lines) if lines else "无表结构信息"


def format_relationships(schema_info: Optional[SchemaInfo]) -> str:
    """格式化表关系信息"""
    if not schema_info:
        return "无关系信息"
    
    relationships = []
    if hasattr(schema_info, 'relationships'):
        relationships = schema_info.relationships
    elif isinstance(schema_info, dict):
        relationships = schema_info.get('relationships', [])
    
    if not relationships:
        return "无关系信息"
    
    lines = []
    for rel in relationships[:15]:  # 限制关系数量
        if isinstance(rel, dict):
            from_table = rel.get('from_table', rel.get('source_table', ''))
            from_col = rel.get('from_column', rel.get('source_column', ''))
            to_table = rel.get('to_table', rel.get('target_table', ''))
            to_col = rel.get('to_column', rel.get('target_column', ''))
            rel_type = rel.get('relationship_type', rel.get('type', 'FK'))
        else:
            from_table = getattr(rel, 'from_table', getattr(rel, 'source_table', ''))
            from_col = getattr(rel, 'from_column', getattr(rel, 'source_column', ''))
            to_table = getattr(rel, 'to_table', getattr(rel, 'target_table', ''))
            to_col = getattr(rel, 'to_column', getattr(rel, 'target_column', ''))
            rel_type = getattr(rel, 'relationship_type', getattr(rel, 'type', 'FK'))
        
        lines.append(f"- {from_table}.{from_col} → {to_table}.{to_col} ({rel_type})")
    
    return "\n".join(lines) if lines else "无关系信息"


async def analyze_schema_clarification(
    query: str,
    schema_info: Optional[SchemaInfo]
) -> Dict[str, Any]:
    """
    使用 LLM 分析是否需要基于表结构的澄清
    
    Args:
        query: 用户查询
        schema_info: 数据库表结构信息
        
    Returns:
        包含澄清分析结果的字典
    """
    llm = get_default_model()
    
    # 格式化信息
    schema_str = format_schema_info(schema_info)
    relationships_str = format_relationships(schema_info)
    
    # 构建提示词
    prompt = SCHEMA_CLARIFICATION_PROMPT.format(
        query=query,
        schema_info=schema_str,
        relationships=relationships_str
    )
    
    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        
        # 提取 JSON
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        else:
            # 尝试直接解析
            json_str = content.strip()
        
        result = json.loads(json_str)
        
        logger.info(f"Schema 澄清分析结果: needs_clarification={result.get('needs_clarification')}, "
                   f"confidence={result.get('confidence')}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"解析 LLM 返回的 JSON 失败: {e}")
        return {
            "needs_clarification": False,
            "confidence": 0.8,
            "ambiguities": [],
            "clarification_questions": [],
            "analysis_summary": "分析完成，未发现明显歧义"
        }
    except Exception as e:
        logger.error(f"Schema 澄清分析失败: {e}")
        return {
            "needs_clarification": False,
            "confidence": 0.5,
            "ambiguities": [],
            "clarification_questions": [],
            "analysis_summary": f"分析过程中发生错误: {str(e)}"
        }


def process_user_clarification_response(
    user_response: Dict[str, Any],
    original_query: str,
    ambiguities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    处理用户对澄清问题的回复，生成增强后的查询
    
    Args:
        user_response: 用户的回复
        original_query: 原始查询
        ambiguities: 检测到的歧义列表
        
    Returns:
        处理后的结果，包含增强查询
    """
    clarifications = []
    
    # 提取用户选择
    answers = user_response.get("answers", {})
    
    for amb in ambiguities:
        amb_type = amb.get("type", "")
        question = amb.get("question", "")
        
        # 查找对应的答案
        for q_id, answer in answers.items():
            clarifications.append(f"- {question}: {answer}")
    
    # 构建增强查询
    if clarifications:
        enhanced_query = f"{original_query}\n\n【用户补充说明】:\n" + "\n".join(clarifications)
    else:
        enhanced_query = original_query
    
    return {
        "enhanced_query": enhanced_query,
        "clarifications": clarifications
    }


# ============================================================================
# 主节点函数
# ============================================================================

async def schema_clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema 澄清节点 - 澄清点C
    
    在获取表结构后、生成 SQL 前进行深度语义分析，
    检测字段、关系、指标等层面的歧义。
    
    使用 interrupt() 暂停等待用户确认。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info("=== 执行 schema_clarification_node (澄清点C) ===")
    
    # 检查是否已确认（用户回复后继续执行）
    if state.get("schema_clarification_confirmed", False):
        logger.info("Schema 澄清已确认，继续执行")
        return {"current_stage": "sql_generation"}
    
    # 获取查询和表结构
    query = state.get("enriched_query") or state.get("original_query")
    if not query:
        # 从消息中提取
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                query = content
                break
    
    if not query:
        logger.warning("未找到用户查询，跳过 Schema 澄清")
        return {"current_stage": "sql_generation"}
    
    schema_info = state.get("schema_info")
    if not schema_info:
        logger.warning("未找到表结构信息，跳过 Schema 澄清")
        return {"current_stage": "sql_generation"}
    
    # 检查澄清轮次
    clarification_round = state.get("schema_clarification_round", 0)
    max_rounds = state.get("max_clarification_rounds", 2)
    
    if clarification_round >= max_rounds:
        logger.info(f"已达到最大澄清轮次 ({max_rounds})，继续执行")
        return {"current_stage": "sql_generation"}
    
    # 使用 LLM 分析是否需要澄清
    analysis_result = await analyze_schema_clarification(query, schema_info)
    
    needs_clarification = analysis_result.get("needs_clarification", False)
    confidence = analysis_result.get("confidence", 1.0)
    clarification_questions = analysis_result.get("clarification_questions", [])
    ambiguities = analysis_result.get("ambiguities", [])
    
    # 判断是否需要澄清
    if not needs_clarification or confidence >= 0.85 or not clarification_questions:
        logger.info(f"Schema 分析完成，无需澄清 (confidence={confidence})")
        return {
            "current_stage": "sql_generation",
            "schema_analysis_result": analysis_result
        }
    
    logger.info(f"检测到 {len(ambiguities)} 个歧义，需要用户澄清")
    
    # 构建澄清消息
    clarification_message = "为了更准确地理解您的查询，请帮我确认以下信息：\n\n"
    
    for i, q in enumerate(clarification_questions, 1):
        question = q.get("question", "")
        options = q.get("options", [])
        default = q.get("default")
        
        clarification_message += f"**问题 {i}**: {question}\n"
        for j, opt in enumerate(options, 1):
            marker = "→" if opt == default else " "
            clarification_message += f"  {marker} {j}. {opt}\n"
        clarification_message += "\n"
    
    # 使用 interrupt 暂停等待用户回复
    user_response = interrupt({
        "type": "schema_clarification",
        "stage": "schema_analysis",
        "message": clarification_message,
        "questions": clarification_questions,
        "ambiguities": ambiguities,
        "analysis_summary": analysis_result.get("analysis_summary", ""),
        "confidence": confidence,
        "round": clarification_round + 1
    })
    
    # 处理用户回复
    logger.info(f"收到用户 Schema 澄清回复: {user_response}")
    
    # 处理回复并增强查询
    processed = process_user_clarification_response(
        user_response, 
        query,
        ambiguities
    )
    
    # 更新状态
    return {
        "enriched_query": processed["enhanced_query"],
        "schema_clarification_confirmed": True,
        "schema_clarification_round": clarification_round + 1,
        "schema_clarification_history": state.get("schema_clarification_history", []) + [{
            "round": clarification_round + 1,
            "questions": clarification_questions,
            "response": user_response,
            "ambiguities": ambiguities
        }],
        "current_stage": "sql_generation",
        "messages": [AIMessage(content=f"感谢您的确认！我已理解您的需求，正在生成查询...")],
    }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "schema_clarification_node",
    "analyze_schema_clarification",
]
