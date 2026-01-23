"""
表过滤澄清节点 (Table Filter Clarification Node)

澄清点B：在表过滤后检测是否需要澄清

触发条件：
1. 匹配到多个语义相近的表
2. 过滤置信度低于阈值
3. 没有匹配到任何表

工作流程：
1. 获取所有表信息（表名、表描述）
2. 使用 LLM 进行表过滤，同时评估是否需要澄清
3. 如需澄清，使用 interrupt() 暂停执行
4. 用户确认后继续执行
"""
from typing import Dict, Any, List, Optional
import logging
import json

from langgraph.types import interrupt

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.db.session import SessionLocal
from app import crud

logger = logging.getLogger(__name__)


# ============================================================================
# 表过滤 + 澄清检测提示词
# ============================================================================

TABLE_FILTER_WITH_CLARIFICATION_PROMPT = """你是一个专业的数据库查询分析专家。请根据用户查询，从可用表中选择相关的表，并评估是否需要用户澄清。

**用户查询**: {query}

**可用表列表**:
{tables_info}

**任务1: 表过滤**
从可用表中选择与用户查询相关的表，并为每个表评分（0-10）。

**任务2: 澄清检测**
判断是否需要用户澄清，检测以下情况：
1. **多表歧义**: 多个表都可能与查询相关，需要用户确认使用哪个（如 orders 和 order_history）
2. **低置信度**: 没有明确匹配的表，最高置信度 < 6
3. **无匹配**: 完全没有找到相关表

**注意**：
- 只有当歧义确实会影响查询结果时才需要澄清
- 如果可以根据查询上下文推断，则不需要澄清
- 优先生成选择题，方便用户快速选择

请返回 JSON 格式：
{{
    "filtered_tables": [
        {{
            "table_id": 123,
            "table_name": "表名",
            "description": "表描述",
            "relevance_score": 8.5,
            "reasoning": "相关原因"
        }}
    ],
    "needs_clarification": true | false,
    "clarification_type": "multiple_tables" | "low_confidence" | "no_match" | null,
    "clarification_reason": "需要澄清的原因（如不需要则为null）",
    "clarification_questions": [
        {{
            "id": "q1",
            "question": "您想查询哪个数据表？",
            "type": "choice",
            "options": ["订单表 (orders) - 当前订单数据", "历史订单表 (order_history) - 历史订单归档"]
        }}
    ]
}}

只返回JSON，不要其他内容。"""


# ============================================================================
# 辅助函数
# ============================================================================

def get_all_tables_info(connection_id: int) -> List[Dict[str, Any]]:
    """
    获取数据库连接的所有表信息
    
    Args:
        connection_id: 数据库连接ID
        
    Returns:
        表信息列表，每项包含 id, name, description
    """
    db = SessionLocal()
    try:
        tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
        return [
            {
                "id": table.id,
                "name": table.table_name,
                "description": table.description or ""
            }
            for table in tables
        ]
    finally:
        db.close()


async def filter_tables_with_clarification_check(
    query: str,
    connection_id: int
) -> Dict[str, Any]:
    """
    使用 LLM 进行表过滤，同时检测是否需要澄清
    
    Args:
        query: 用户查询（已改写）
        connection_id: 数据库连接ID
        
    Returns:
        Dict 包含:
        - filtered_tables: 过滤后的表列表
        - needs_clarification: 是否需要澄清
        - clarification_type: 澄清类型
        - clarification_questions: 澄清问题列表
    """
    # 获取所有表
    all_tables = get_all_tables_info(connection_id)
    
    if not all_tables:
        return {
            "filtered_tables": [],
            "needs_clarification": True,
            "clarification_type": "no_tables",
            "clarification_reason": "当前数据库连接没有配置任何表信息",
            "clarification_questions": []
        }
    
    # 准备表信息
    tables_info = "\n".join([
        f"- 表ID: {t['id']} | 表名: {t['name']} | 描述: {t['description'] or '无描述'}"
        for t in all_tables
    ])
    
    # 调用 LLM
    llm = get_default_model()
    prompt = TABLE_FILTER_WITH_CLARIFICATION_PROMPT.format(
        query=query,
        tables_info=tables_info
    )
    
    try:
        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # 清理 markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        logger.info(f"表过滤结果: {len(result.get('filtered_tables', []))} 个表, 需要澄清: {result.get('needs_clarification', False)}")
        
        return {
            "filtered_tables": result.get("filtered_tables", []),
            "needs_clarification": result.get("needs_clarification", False),
            "clarification_type": result.get("clarification_type"),
            "clarification_reason": result.get("clarification_reason"),
            "clarification_questions": result.get("clarification_questions", [])
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"表过滤 JSON 解析失败: {e}")
        # 降级处理：返回所有表，不需要澄清
        return {
            "filtered_tables": [
                {"table_id": t["id"], "table_name": t["name"], "description": t["description"], "relevance_score": 5.0}
                for t in all_tables
            ],
            "needs_clarification": False,
            "clarification_questions": []
        }
    except Exception as e:
        logger.error(f"表过滤失败: {e}", exc_info=True)
        return {
            "filtered_tables": [
                {"table_id": t["id"], "table_name": t["name"], "description": t["description"], "relevance_score": 5.0}
                for t in all_tables
            ],
            "needs_clarification": False,
            "clarification_questions": []
        }


# ============================================================================
# 节点函数
# ============================================================================

async def table_filter_clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    表过滤澄清节点 - 澄清点B
    
    功能：
    1. 获取所有表信息
    2. 使用 LLM 进行表过滤
    3. 检测是否需要用户澄清（多表歧义/低置信度/无匹配）
    4. 如需澄清，使用 interrupt() 暂停执行
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新，包含:
        - filtered_tables: 过滤后的表列表
        - table_filter_confirmed: 是否已确认
        - current_stage: 下一阶段
    """
    logger.info("=== 表过滤澄清节点 (澄清点B) ===")
    
    # 检查是否已经确认过表过滤
    if state.get("table_filter_confirmed", False):
        logger.info("✓ 表过滤已确认，跳过重复检测")
        return {"current_stage": "schema_analysis"}
    
    # 获取用户查询（优先使用改写后的查询）
    user_query = state.get("enriched_query") or state.get("original_query")
    
    if not user_query:
        # 从消息中提取
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content
                if isinstance(user_query, list):
                    user_query = user_query[0].get("text", "") if user_query else ""
                break
    
    if not user_query:
        logger.warning("无法提取用户查询，跳过表过滤")
        return {"current_stage": "schema_analysis"}
    
    # 获取数据库连接ID
    connection_id = state.get("connection_id")
    if not connection_id:
        logger.warning("无数据库连接ID，跳过表过滤")
        return {"current_stage": "schema_analysis"}
    
    logger.info(f"执行表过滤: query='{user_query[:50]}...', connection_id={connection_id}")
    
    # 执行表过滤 + 澄清检测
    filter_result = await filter_tables_with_clarification_check(
        query=user_query,
        connection_id=connection_id
    )
    
    filtered_tables = filter_result.get("filtered_tables", [])
    needs_clarification = filter_result.get("needs_clarification", False)
    clarification_type = filter_result.get("clarification_type")
    clarification_questions = filter_result.get("clarification_questions", [])
    clarification_reason = filter_result.get("clarification_reason")
    
    logger.info(f"表过滤结果: {len(filtered_tables)} 个表, 需要澄清: {needs_clarification}")
    
    # 如果需要澄清，使用 interrupt 暂停
    if needs_clarification and clarification_questions:
        logger.info(f"触发表过滤澄清 ({clarification_type}), {len(clarification_questions)} 个问题")
        
        from app.agents.agents.clarification_agent import format_clarification_questions
        formatted_questions = format_clarification_questions(clarification_questions)
        
        # 使用 interrupt 暂停执行
        user_response = interrupt({
            "type": "clarification_request",
            "stage": "table_filter",
            "clarification_type": clarification_type,
            "questions": formatted_questions,
            "reason": clarification_reason or "需要确认查询涉及的数据表",
            "original_query": user_query,
            "candidate_tables": [
                {"id": t.get("table_id"), "name": t.get("table_name"), "description": t.get("description")}
                for t in filtered_tables[:5]  # 最多显示5个候选表
            ]
        })
        
        # 用户回复后继续
        logger.info(f"收到表过滤澄清回复: {user_response}")
        
        # 解析用户回复
        from app.agents.agents.clarification_agent import parse_user_clarification_response
        parsed_answers = parse_user_clarification_response(user_response, formatted_questions)
        
        # 根据用户选择更新过滤结果
        if parsed_answers:
            # 用户选择了特定的表，更新 filtered_tables
            selected_tables = []
            for answer in parsed_answers:
                answer_text = answer.get("answer", "")
                # 尝试从回答中提取表名
                for table in filtered_tables:
                    table_name = table.get("table_name", "")
                    if table_name and table_name in answer_text:
                        selected_tables.append(table)
                        break
            
            if selected_tables:
                filtered_tables = selected_tables
                logger.info(f"用户选择了 {len(selected_tables)} 个表")
    
    # 返回状态更新
    return {
        "filtered_tables": filtered_tables,
        "table_filter_confirmed": True,
        "current_stage": "schema_analysis"
    }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "table_filter_clarification_node",
    "filter_tables_with_clarification_check",
    "get_all_tables_info",
]
