"""
结果聚合节点 (Result Aggregator Node)

P2.1 阶段核心节点：聚合多步执行的子任务结果。

职责：
1. 收集所有子任务的执行结果
2. 合并数据集
3. 生成综合分析摘要
4. 准备数据供 Data Analyst 分析
"""
from typing import Dict, Any, List, Optional
import logging
import time

from langgraph.config import get_stream_writer
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import SQLMessageState, SQLExecutionResult
from app.schemas.stream_events import create_sql_step_event
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


async def result_aggregator_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    结果聚合节点
    
    聚合多步执行的子任务结果，为 Data Analyst 准备综合数据。
    
    输出状态:
        - execution_result: 聚合后的执行结果
        - aggregated_summary: 聚合摘要
        - current_stage: execution_done (进入分析阶段)
    """
    start_time = time.time()
    
    # 获取 stream writer
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None
    
    # 发送聚合开始事件
    if writer:
        writer(create_sql_step_event(
            step="result_aggregator",
            status="running",
            result="正在聚合子任务结果...",
            time_ms=0
        ))
    
    try:
        sub_task_results = state.get("sub_task_results", [])
        original_query = state.get("original_query", "")
        
        if not sub_task_results:
            logger.warning("没有子任务结果可聚合")
            return {
                "current_stage": "execution_done",
                "multi_step_completed": True,
            }
        
        logger.info(f"开始聚合 {len(sub_task_results)} 个子任务结果")
        
        # 聚合数据
        aggregated_result = _aggregate_results(sub_task_results)
        
        # 生成聚合摘要（可选：使用 LLM）
        summary = await _generate_aggregation_summary(
            original_query,
            sub_task_results,
            aggregated_result
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 发送完成事件
        if writer:
            writer(create_sql_step_event(
                step="result_aggregator",
                status="completed",
                result=f"聚合完成: {len(sub_task_results)} 个子任务, {aggregated_result.get('total_rows', 0)} 行数据",
                time_ms=elapsed_ms
            ))
        
        logger.info(f"结果聚合完成 [{elapsed_ms}ms]")
        
        # 构建聚合后的执行结果
        execution_result = SQLExecutionResult(
            success=True,
            data=aggregated_result.get("merged_data", []),
            error=None,
            execution_time=elapsed_ms / 1000,
            rows_affected=aggregated_result.get("total_rows", 0)
        )
        
        return {
            "execution_result": execution_result,
            "aggregated_summary": summary,
            "current_stage": "execution_done",  # 进入 data_analyst
            "multi_step_completed": True,
            # 保存各子任务的 SQL 供展示
            "multi_step_sqls": [r.get("sql") for r in sub_task_results if r.get("sql")],
        }
        
    except Exception as e:
        logger.error(f"结果聚合失败: {e}")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if writer:
            writer(create_sql_step_event(
                step="result_aggregator",
                status="error",
                result=str(e),
                time_ms=elapsed_ms
            ))
        
        # 失败时使用最后一个子任务的结果
        sub_task_results = state.get("sub_task_results", [])
        if sub_task_results:
            last_result = sub_task_results[-1]
            return {
                "execution_result": last_result.get("execution_result"),
                "current_stage": "execution_done",
                "multi_step_completed": True,
            }
        
        return {
            "current_stage": "execution_done",
            "multi_step_completed": True,
        }


def _aggregate_results(sub_task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    聚合子任务结果
    
    策略：
    - 如果所有子任务返回相同结构的数据，合并为一个数据集
    - 如果结构不同，保持为分组数据
    """
    all_data = []
    columns_set = set()
    task_summaries = []
    
    for result in sub_task_results:
        exec_result = result.get("execution_result")
        if not exec_result:
            continue
        
        # 提取数据
        data = None
        if isinstance(exec_result, dict):
            data = exec_result.get("data", [])
        elif hasattr(exec_result, 'data'):
            data = getattr(exec_result, 'data', [])
        
        if not data:
            continue
        
        # 收集列名
        if data and isinstance(data, list) and data:
            first_row = data[0]
            if isinstance(first_row, dict):
                columns_set.update(first_row.keys())
        
        # 添加任务标识
        task_id = result.get("task_id", "unknown")
        task_query = result.get("task_query", "")
        
        for row in data:
            if isinstance(row, dict):
                row_with_task = {**row, "_task_id": task_id}
                all_data.append(row_with_task)
            else:
                all_data.append(row)
        
        task_summaries.append({
            "task_id": task_id,
            "task_query": task_query,
            "row_count": len(data) if data else 0,
        })
    
    return {
        "merged_data": all_data,
        "total_rows": len(all_data),
        "columns": list(columns_set),
        "task_count": len(sub_task_results),
        "task_summaries": task_summaries,
    }


async def _generate_aggregation_summary(
    original_query: str,
    sub_task_results: List[Dict[str, Any]],
    aggregated_result: Dict[str, Any]
) -> str:
    """
    生成聚合摘要
    
    使用 LLM 生成人类可读的聚合摘要（可选）
    """
    task_summaries = aggregated_result.get("task_summaries", [])
    
    # 简单摘要（不调用 LLM）
    summary_parts = [
        f"原始查询: {original_query}",
        f"执行了 {len(sub_task_results)} 个子任务:",
    ]
    
    for ts in task_summaries:
        summary_parts.append(f"  - {ts['task_id']}: {ts['task_query'][:50]}... ({ts['row_count']} 行)")
    
    summary_parts.append(f"总计: {aggregated_result.get('total_rows', 0)} 行数据")
    
    return "\n".join(summary_parts)


__all__ = ["result_aggregator_node"]
