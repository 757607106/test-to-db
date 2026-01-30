"""
问题推荐节点 (Question Recommendation Node)

职责：
1. 基于向量检索获取相似问题
2. 使用 LLM 生成推荐问题
3. 结合两种方法返回 3-5 个推荐问题

遵循 LangGraph 官方最佳实践:
- 使用 StreamWriter 进行流式输出
- 完全异步实现
- 并行执行向量检索和 LLM 生成
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.schemas.stream_events import create_similar_questions_event

logger = logging.getLogger(__name__)


async def question_recommendation_node(
    state: SQLMessageState,
    writer: StreamWriter
) -> Dict[str, Any]:
    """
    问题推荐节点
    
    遵循 LangGraph 官方最佳实践：
    - 使用 StreamWriter 参数注入
    - 异步并行执行向量检索和 LLM 生成
    
    策略：
    1. 向量检索：从历史 QA 库中检索相似问题
    2. LLM 生成：基于当前查询和数据库 Schema 生成推荐问题
    3. 合并去重：返回 3-5 个唯一的推荐问题
    
    Args:
        state: 当前状态
        writer: LangGraph StreamWriter
        
    Returns:
        状态更新字典
    """
    start_time = time.time()
    
    try:
        # 提取必要信息
        user_query = _extract_user_query(state)
        connection_id = state.get("connection_id")
        schema_info = state.get("schema_info")
        generated_sql = state.get("generated_sql", "")
        
        if not user_query:
            logger.warning("无法提取用户查询，跳过问题推荐")
            return {}
        
        logger.info(f"开始生成推荐问题 - 查询: '{user_query[:50]}...', 连接ID: {connection_id}")
        
        # 并行执行：向量检索 + LLM 生成
        vector_task = _retrieve_similar_questions(
            user_query=user_query,
            connection_id=connection_id,
            top_k=3
        )
        
        llm_task = _generate_questions_with_llm(
            user_query=user_query,
            schema_info=schema_info,
            generated_sql=generated_sql,
            count=3
        )
        
        # 等待两个任务完成
        vector_questions, llm_questions = await asyncio.gather(
            vector_task,
            llm_task,
            return_exceptions=True
        )
        
        # 处理异常结果
        if isinstance(vector_questions, Exception):
            logger.warning(f"向量检索失败: {vector_questions}")
            vector_questions = []
        
        if isinstance(llm_questions, Exception):
            logger.warning(f"LLM 生成失败: {llm_questions}")
            llm_questions = []
        
        # 合并并去重
        all_questions = _merge_and_deduplicate(
            vector_questions=vector_questions,
            llm_questions=llm_questions,
            original_query=user_query,
            max_count=5
        )
        
        # 计算耗时
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"推荐问题生成完成 - "
                   f"向量检索: {len(vector_questions)}个, "
                   f"LLM生成: {len(llm_questions)}个, "
                   f"最终: {len(all_questions)}个, "
                   f"耗时: {elapsed_ms}ms")
        
        # 发送推荐问题事件
        if all_questions:
            writer(create_similar_questions_event(questions=all_questions))
        
        return {
            "recommended_questions": all_questions,
            "current_stage": "completed"
        }
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"问题推荐失败: {e}, 耗时: {elapsed_ms}ms")
        # 问题推荐失败不影响整体流程
        return {"current_stage": "completed"}


def _extract_user_query(state: SQLMessageState) -> Optional[str]:
    """从状态中提取用户查询"""
    # 优先使用已保存的原始查询
    if state.get("original_query"):
        return state["original_query"]
    
    if state.get("enriched_query"):
        return state["enriched_query"]
    
    # 从消息中提取（取最后一个 HumanMessage）
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            content = msg.content
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            return content
    return None


async def _retrieve_similar_questions(
    user_query: str,
    connection_id: Optional[int],
    top_k: int = 3
) -> List[str]:
    """
    从向量数据库检索相似问题
    
    使用 HybridRetrievalEnginePool 进行快速检索
    """
    if not connection_id:
        return []
    
    try:
        from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
        
        # 使用快速检索 API
        results = await HybridRetrievalEnginePool.quick_retrieve(
            user_query=user_query,
            schema_context={},  # 不需要 schema 上下文进行相似问题检索
            connection_id=connection_id,
            top_k=top_k,
            min_similarity=0.5  # 相似度阈值
        )
        
        # 提取问题
        questions = []
        for result in results:
            question = result.get("question", "")
            if question and question != user_query:
                questions.append(question)
        
        return questions
        
    except Exception as e:
        logger.warning(f"向量检索相似问题失败: {e}")
        return []


async def _generate_questions_with_llm(
    user_query: str,
    schema_info: Optional[Dict[str, Any]],
    generated_sql: str,
    count: int = 3
) -> List[str]:
    """
    使用 LLM 生成推荐问题
    
    基于：
    - 当前用户查询
    - 数据库 Schema 信息
    - 生成的 SQL 结构
    
    优化说明：
    - 提取可用字段供 LLM 参考，减少幻觉
    - 要求不同维度的问题，避免重复
    """
    try:
        llm = get_default_model()
        
        # 提取表名和字段信息
        tables_info, available_fields = _extract_tables_info_enhanced(schema_info, generated_sql)
        
        prompt = f"""你是一个智能查询助手。基于用户当前的查询，推荐 {count} 个相关的后续问题。

【用户当前查询】
{user_query}

【参考 SQL】
{generated_sql[:500] if generated_sql else "无"}

【可用字段】
{available_fields}

【推荐要求】
1. 每个问题应来自不同维度（从下面选择3个）：
   - 金额统计：如汇总、平均、最大/最小
   - 时间分析：如按月统计、趋势变化
   - 排名对比：如 Top 10、最高/最低
   - 分组统计：如按类别、按状态
2. 问题必须能用上述字段回答
3. 问题要简洁，不超过15字

【输出格式】
直接输出{count}个问题，每行一个，不要编号："""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # 解析响应
        content = response.content.strip()
        questions = []
        
        for line in content.split('\n'):
            line = line.strip()
            # 移除可能的编号前缀
            if line and not line.startswith('#'):
                # 移除常见的编号格式：1. 2. 3. 或 1) 2) 3) 或 - 
                import re
                cleaned = re.sub(r'^[\d]+[.)\s]+', '', line).strip()
                cleaned = re.sub(r'^[-\*\u2022]\s*', '', cleaned).strip()
                if cleaned and len(cleaned) > 5 and len(cleaned) < 50:  # 确保问题有一定长度且不过长
                    questions.append(cleaned)
        
        return questions[:count]
        
    except Exception as e:
        logger.warning(f"LLM 生成推荐问题失败: {e}")
        return []


def _extract_tables_info_enhanced(
    schema_info: Optional[Dict[str, Any]],
    generated_sql: str = ""
) -> tuple:
    """
    增强版表信息提取
    
    从 schema_info 和 generated_sql 中提取可用字段
    
    Returns:
        (tables_info_str, available_fields_str)
    """
    table_lines = []
    field_lines = []
    
    if not schema_info:
        # 尝试从 SQL 中提取表名和字段
        if generated_sql:
            import re
            # 提取 SELECT 字段
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', generated_sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                fields = select_match.group(1)
                field_lines.append(f"查询字段: {fields[:200]}")
            
            # 提取 FROM/JOIN 表名
            table_matches = re.findall(r'(?:FROM|JOIN)\s+`?(\w+)`?', generated_sql, re.IGNORECASE)
            if table_matches:
                table_lines.append(f"涉及表: {', '.join(set(table_matches))}")
        
        tables_info = '\n'.join(table_lines) if table_lines else "无表信息"
        fields_info = '\n'.join(field_lines) if field_lines else "请参考SQL中的字段"
        return tables_info, fields_info
    
    # 从schema_info提取
    tables = []
    columns = []
    
    if isinstance(schema_info, dict):
        tables = schema_info.get('tables', [])
        columns = schema_info.get('columns', [])
    
    # 提取表名
    if isinstance(tables, list) and tables:
        for table in tables[:5]:  # 最多5个表
            if isinstance(table, dict):
                name = table.get('table_name', table.get('name', ''))
                desc = table.get('description', '')
                if name:
                    if desc and 'Auto-discovered' not in desc:
                        table_lines.append(f"- {name}: {desc}")
                    else:
                        table_lines.append(f"- {name}")
    
    # 提取核心字段（按表分组）
    table_columns_map = {}
    if isinstance(columns, list):
        for col in columns:
            if isinstance(col, dict):
                table_name = col.get('table_name', '')
                col_name = col.get('column_name', col.get('name', ''))
                col_type = col.get('data_type', '')
                
                # 只保留核心字段（金额、日期、数量、名称、状态）
                is_core = any(kw in col_name.lower() for kw in 
                    ['amount', 'quantity', 'date', 'name', 'status', 'total', 'price', 'count', 'id'])
                
                if is_core and table_name:
                    if table_name not in table_columns_map:
                        table_columns_map[table_name] = []
                    table_columns_map[table_name].append(col_name)
    
    # 构建字段信息
    for table_name, cols in list(table_columns_map.items())[:4]:
        field_lines.append(f"{table_name}: {', '.join(cols[:8])}")
    
    tables_info = '\n'.join(table_lines) if table_lines else "无表信息"
    fields_info = '\n'.join(field_lines) if field_lines else "请参考SQL中的字段"
    
    return tables_info, fields_info


def _extract_tables_info(schema_info: Optional[Dict[str, Any]]) -> str:
    """
    从schema_info提取表信息（兼容旧接口）
    
    已废弃，请使用 _extract_tables_info_enhanced
    """
    tables_info, _ = _extract_tables_info_enhanced(schema_info, "")
    return tables_info


def _merge_and_deduplicate(
    vector_questions: List[str],
    llm_questions: List[str],
    original_query: str,
    max_count: int = 5
) -> List[str]:
    """
    合并并去重问题
    
    策略：
    1. 优先使用向量检索的问题（更相关）
    2. 补充 LLM 生成的问题
    3. 去除与原始查询过于相似的问题
    4. 限制总数
    """
    seen = set()
    result = []
    
    # 原始查询的简化形式（用于相似度检查）
    original_lower = original_query.lower().strip()
    
    # 优先添加向量检索的问题
    for q in vector_questions:
        q_lower = q.lower().strip()
        # 跳过与原始查询相同或过于相似的
        if q_lower == original_lower:
            continue
        if _is_too_similar(q_lower, original_lower):
            continue
        if q_lower not in seen:
            seen.add(q_lower)
            result.append(q)
            if len(result) >= max_count:
                return result
    
    # 补充 LLM 生成的问题
    for q in llm_questions:
        q_lower = q.lower().strip()
        if q_lower == original_lower:
            continue
        if _is_too_similar(q_lower, original_lower):
            continue
        if q_lower not in seen:
            seen.add(q_lower)
            result.append(q)
            if len(result) >= max_count:
                return result
    
    return result


def _is_too_similar(q1: str, q2: str, threshold: float = 0.8) -> bool:
    """
    简单的相似度检查
    使用 Jaccard 相似度
    """
    words1 = set(q1.split())
    words2 = set(q2.split())
    
    if not words1 or not words2:
        return False
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    similarity = intersection / union if union > 0 else 0
    return similarity > threshold


__all__ = [
    "question_recommendation_node",
]
