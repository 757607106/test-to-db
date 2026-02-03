"""
Worker 节点模块

统一的 Worker Agent 节点定义，使用 streaming_node 装饰器自动化流式事件发送。

节点列表:
- schema_agent_node: Schema 分析节点
- sql_generator_node: SQL 生成节点
- sql_executor_node: SQL 执行节点
- data_analyst_node: 数据分析节点
- chart_generator_node: 图表生成节点
- error_recovery_node: 错误恢复节点
- general_chat_node: 闲聊处理节点

LangGraph 规范:
- 节点签名: async (state, writer) -> dict
- 使用 StreamWriter 参数注入发送流式事件
"""
import logging
import time
from typing import Dict, Any

from langgraph.types import StreamWriter
from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState
from app.agents.utils.node_wrapper import streaming_node
from app.agents.nodes.base import get_custom_agent, build_error_record, ErrorStage

logger = logging.getLogger(__name__)


# ============================================================================
# Schema Agent 节点
# ============================================================================

@streaming_node(step_name="schema_agent")
async def schema_agent_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    Schema Agent 节点 - 分析数据库结构
    
    调用 schema_agent 分析用户查询涉及的表和字段。
    """
    from app.agents.agents.schema_agent import schema_agent
    
    agent = get_custom_agent(state, "schema_agent", schema_agent)
    result = await agent.process(state)
    
    # ✅ 修复：只有在成功时才设置 schema_done，保留 error_recovery 状态
    if result.get("current_stage") != "error_recovery":
        result["current_stage"] = "schema_done"
        if writer:
            from app.schemas.stream_events import create_stage_message_event
            schema_info = result.get("schema_info", {})
            table_count = 0
            tables = schema_info.get("tables")
            if isinstance(tables, dict):
                table_count = len(tables)
            elif isinstance(tables, list):
                table_count = len(tables)
            writer(create_stage_message_event(
                message=f"已完成 Schema 分析，识别到 {table_count} 个相关表，准备生成 SQL。",
                step="schema_agent"
            ))
    
    return result


# ============================================================================
# SQL Generator 节点
# ============================================================================

@streaming_node(step_name="sql_generator")
async def sql_generator_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    SQL Generator 节点 - 生成 SQL 查询
    
    调用 sql_generator_agent 根据 schema 和用户查询生成 SQL。
    """
    from app.agents.agents.sql_generator_agent import sql_generator_agent
    
    agent = get_custom_agent(state, "sql_generator", sql_generator_agent)
    result = await agent.process(state)
    
    # ✅ 修复：只有在成功生成 SQL 时才设置 sql_generated
    # 如果 SQL Generator 返回了 error_recovery，保留该状态
    result_stage = result.get("current_stage")
    logger.info(f"[sql_generator_node] agent 返回的 current_stage: {result_stage}")
    
    if result_stage != "error_recovery":
        result["current_stage"] = "sql_generated"
        logger.info(f"[sql_generator_node] 设置 current_stage 为 sql_generated")
        if writer:
            from app.schemas.stream_events import create_stage_message_event
            sql_preview = result.get("generated_sql", "")
            if sql_preview:
                sql_preview = sql_preview.strip()
            message = "SQL 已生成，准备执行查询。"
            if sql_preview:
                message = f"SQL 已生成：\n{sql_preview}"
            writer(create_stage_message_event(
                message=message,
                step="sql_generator"
            ))
    else:
        logger.info(f"[sql_generator_node] 保留 error_recovery 状态，不覆盖")
    
    return result


# ============================================================================
# SQL Executor 节点
# ============================================================================

async def sql_executor_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    SQL Executor 节点 - 执行 SQL 查询
    
    执行生成的 SQL 并处理结果。需要特殊处理执行失败的情况。
    """
    from app.schemas.stream_events import create_sql_step_event, create_stage_message_event
    from app.agents.agents.sql_executor_agent import sql_executor_agent
    
    logger.info("[Worker] sql_executor 开始执行")
    start_time = time.time()
    
    writer(create_sql_step_event(
        step="sql_executor",
        status="running",
        result="正在执行 SQL 查询...",
        time_ms=0
    ))
    
    try:
        agent = get_custom_agent(state, "sql_executor", sql_executor_agent)
        result = await agent.process(state)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 检查执行结果
        exec_result = result.get("execution_result")
        if exec_result:
            success = getattr(exec_result, 'success', True) if hasattr(exec_result, 'success') else exec_result.get('success', True)
            if not success:
                error_msg = getattr(exec_result, 'error', '') if hasattr(exec_result, 'error') else exec_result.get('error', '')
                writer(create_sql_step_event(
                    step="sql_executor",
                    status="error",
                    result=error_msg,
                    time_ms=elapsed_ms
                ))
                retry_count = state.get("retry_count", 0) + 1
                result["current_stage"] = "error_recovery"
                result["retry_count"] = retry_count
                result["error_history"] = state.get("error_history", []) + [
                    build_error_record(ErrorStage.SQL_EXECUTION, error_msg)
                ]
                return result
        
        # 发送成功事件
        row_count = 0
        if exec_result:
            rows_affected = (
                getattr(exec_result, "rows_affected", None)
                if hasattr(exec_result, "rows_affected")
                else exec_result.get("rows_affected")
            )
            if isinstance(rows_affected, int):
                row_count = rows_affected
            else:
                data = (
                    getattr(exec_result, "data", None)
                    if hasattr(exec_result, "data")
                    else exec_result.get("data")
                )
                if isinstance(data, dict):
                    if isinstance(data.get("row_count"), int):
                        row_count = data["row_count"]
                    elif isinstance(data.get("data"), list):
                        row_count = len(data["data"])
                elif isinstance(data, list):
                    row_count = len(data)
        
        writer(create_sql_step_event(
            step="sql_executor",
            status="completed",
            result=f"查询成功，返回 {row_count} 条数据",
            time_ms=elapsed_ms
        ))
        writer(create_stage_message_event(
            message=f"SQL 执行完成，返回 {row_count} 条数据，准备分析结果。",
            step="sql_executor",
            time_ms=elapsed_ms
        ))
        
        logger.info(f"[Worker] sql_executor 完成 ({elapsed_ms}ms)")
        result["current_stage"] = "execution_done"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] sql_executor 失败: {e}")
        
        writer(create_sql_step_event(
            step="sql_executor",
            status="error",
            result=str(e)[:100],
            time_ms=elapsed_ms
        ))
        
        return {
            "current_stage": "error_recovery",
            "retry_count": state.get("retry_count", 0) + 1,
            "error_history": state.get("error_history", []) + [
                build_error_record(ErrorStage.SQL_EXECUTION, str(e))
            ]
        }


# ============================================================================
# Data Analyst 节点
# ============================================================================

@streaming_node(step_name="data_analyst", fallback_stage="analysis_done")
async def data_analyst_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    Data Analyst 节点 - 分析查询结果
    
    调用 data_analyst_agent 对执行结果进行分析和解读。
    非关键节点，失败时跳过继续执行。
    """
    from app.agents.agents.data_analyst_agent import data_analyst_agent
    
    agent = get_custom_agent(state, "data_analyst", data_analyst_agent)
    result = await agent.process(state, writer=writer)
    
    # ✅ 修复：保留 error_recovery 状态
    if result.get("current_stage") != "error_recovery":
        result["current_stage"] = "analysis_done"
        if writer:
            from app.schemas.stream_events import create_stage_message_event
            summary = result.get("analysis_result") or result.get("analysis_summary") or ""
            message = "分析完成，已生成洞察。"
            if summary:
                message = f"分析完成：\n{summary}"
            writer(create_stage_message_event(
                message=message,
                step="data_analyst"
            ))
    
    return result


# ============================================================================
# Chart Generator 节点
# ============================================================================

@streaming_node(step_name="chart_generator", fallback_stage="chart_done")
async def chart_generator_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    Chart Generator 节点 - 生成图表配置并发送数据查询事件
    
    调用 chart_generator_agent 根据数据生成 Recharts 图表配置。
    非关键节点，失败时返回空配置继续执行。
    
    重要：此节点负责发送 data_query 事件，前端 DataChartDisplay 组件依赖此事件渲染图表。
    """
    from app.agents.agents.chart_generator_agent import chart_generator_agent
    from app.schemas.stream_events import create_stage_message_event, create_data_query_event
    
    start_time = time.time()
    agent = get_custom_agent(state, "chart_generator", chart_generator_agent)
    result = await agent.process(state, writer=writer)
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    # ✅ 修复：保留 error_recovery 状态
    if result.get("current_stage") != "error_recovery":
        result["current_stage"] = "chart_done"
        
        if writer:
            # 1. 发送阶段消息
            chart_config = result.get("chart_config") or state.get("chart_config")
            message = "图表配置已生成。"
            if isinstance(chart_config, dict):
                chart_type = chart_config.get("type")
                if chart_type:
                    message = f"图表配置已生成：{chart_type} 图。"
            writer(create_stage_message_event(
                message=message,
                step="chart_generator",
                time_ms=elapsed_ms
            ))
            
            # 2. 发送 data_query 事件（前端 DataChartDisplay 依赖此事件）
            _send_data_query_event(state, result, writer)
    
    return result


def _send_data_query_event(state: SQLMessageState, result: Dict[str, Any], writer: StreamWriter):
    """
    发送 data_query 事件到前端
    
    此事件是前端 DataChartDisplay 组件渲染图表的数据源。
    从 execution_result 中提取数据并生成图表配置。
    """
    from app.schemas.stream_events import create_data_query_event
    
    try:
        # 获取执行结果（优先使用 query_results，兼容 execution_result）
        data = state.get("query_results")
        if not data:
            exec_result = state.get("execution_result")
            if exec_result:
                if hasattr(exec_result, 'data'):
                    data = exec_result.data
                else:
                    data = exec_result.get('data', {})
        
        if not data:
            logger.warning("[chart_generator_node] 无执行结果，跳过 data_query 事件")
            return
        
        # 提取 columns 和 rows
        # query_results 可能是列表格式 [{"col1": v1, ...}, ...] 或 {"columns": [...], "data": [...]}
        if isinstance(data, list) and len(data) > 0:
            # 列表格式，直接使用
            if isinstance(data[0], dict):
                columns = list(data[0].keys())
                rows = data
                row_count = len(data)
            else:
                logger.warning("[chart_generator_node] 数据格式不支持，跳过 data_query 事件")
                return
        elif isinstance(data, dict):
            columns = data.get("columns", [])
            raw_rows = data.get("data", [])
            row_count = data.get("row_count", len(raw_rows))
            
            if not columns:
                logger.warning("[chart_generator_node] 无列信息，跳过 data_query 事件")
                return
            
            # 转换数据格式：数组数组 -> 对象数组
            rows = []
            for raw_row in raw_rows:
                if isinstance(raw_row, list) and len(raw_row) == len(columns):
                    rows.append(dict(zip(columns, raw_row)))
                elif isinstance(raw_row, dict):
                    rows.append(raw_row)
        else:
            logger.warning("[chart_generator_node] 数据格式不支持，跳过 data_query 事件")
            return
        
        if not columns or not rows:
            logger.warning("[chart_generator_node] 无有效数据，跳过 data_query 事件")
            return
        
        # 获取图表配置（优先使用结果中的，其次使用状态中的，最后自动生成）
        chart_config = result.get("chart_config") or state.get("chart_config")
        if not chart_config and columns and rows:
            chart_config = _generate_chart_config_for_data(columns, rows)
        
        # 发送事件
        writer(create_data_query_event(
            columns=columns,
            rows=rows[:100],  # 限制前100行，避免数据量过大
            row_count=row_count,
            chart_config=chart_config,
            title=None  # 可以后续从 user_query 中提取
        ))
        
        logger.info(f"[chart_generator_node] data_query 事件已发送: {len(columns)} 列, {row_count} 行")
        
    except Exception as e:
        logger.error(f"[chart_generator_node] 发送 data_query 事件失败: {e}")


def _generate_chart_config_for_data(columns: list, rows: list) -> Dict[str, Any]:
    """
    根据数据自动生成图表配置
    """
    if not columns or not rows:
        return None
    
    # 分析列类型
    numeric_columns = []
    category_columns = []
    date_columns = []
    
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ['date', 'time', '日期', '时间', 'day', 'month', 'year']):
            date_columns.append(col)
        elif any(kw in col_lower for kw in ['name', 'type', 'category', '名称', '类型', '分类', 'id']):
            category_columns.append(col)
        else:
            if rows:
                first_val = rows[0].get(col) if isinstance(rows[0], dict) else None
                if isinstance(first_val, (int, float)):
                    numeric_columns.append(col)
                else:
                    category_columns.append(col)
    
    # 决定图表类型
    chart_type = "bar"
    if date_columns:
        x_axis = date_columns[0]
        chart_type = "line"
    elif category_columns:
        x_axis = category_columns[0]
        chart_type = "bar" if len(rows) <= 10 else "line"
    elif numeric_columns:
        x_axis = numeric_columns[0]
    else:
        x_axis = columns[0]
    
    y_axis = numeric_columns[0] if numeric_columns else (columns[1] if len(columns) > 1 else columns[0])
    
    return {
        "type": chart_type,
        "xAxis": x_axis,
        "yAxis": y_axis,
        "dataKey": y_axis,
        "xDataKey": x_axis
    }


# ============================================================================
# Error Recovery 节点
# ============================================================================

@streaming_node(step_name="error_recovery", fallback_stage="completed")
async def error_recovery_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    Error Recovery 节点 - 错误恢复处理
    
    调用 error_recovery_agent 分析错误并尝试恢复。
    """
    from app.agents.agents.error_recovery_agent import error_recovery_agent
    
    start_time = time.time()
    if writer:
        from app.schemas.stream_events import create_stage_message_event
        writer(create_stage_message_event(
            message="检测到错误，正在尝试自动恢复。",
            step="error_recovery",
            time_ms=0
        ))
    
    result = await error_recovery_agent.process(state)
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    if writer:
        from app.schemas.stream_events import create_stage_message_event
        recovery_successful = result.get("recovery_successful")
        next_stage = result.get("next_stage") or state.get("current_stage")
        if recovery_successful:
            message = f"错误恢复成功，继续执行 {next_stage} 阶段。"
        else:
            if state.get("current_stage") == "terminated":
                message = "错误恢复失败，已达到最大重试次数。"
            else:
                message = "错误恢复未成功，准备重试。"
        writer(create_stage_message_event(
            message=message,
            step="error_recovery",
            time_ms=elapsed_ms
        ))
    return result


# ============================================================================
# General Chat 节点
# ============================================================================

async def general_chat_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    General Chat 节点 - 处理闲聊
    
    使用默认 LLM 处理非数据查询的对话。
    """
    from app.schemas.stream_events import create_sql_step_event, create_stage_message_event
    from app.core.llm_wrapper import get_llm_wrapper
    from app.agents.nodes.base import extract_user_query
    
    logger.info("[Worker] general_chat 开始执行")
    
    writer(create_sql_step_event(
        step="general_chat",
        status="running",
        result="正在处理对话...",
        time_ms=0
    ))
    
    messages = state.get("messages", [])
    user_query = extract_user_query(messages) or ""
    
    # 使用 LLMWrapper 统一处理重试和超时
    llm = get_llm_wrapper(name="general_chat")
    response = await llm.ainvoke([
        {"role": "system", "content": "你是一个友好的数据分析助手。请用简洁的中文回答用户的问题。"},
        {"role": "user", "content": user_query}
    ])
    
    writer(create_sql_step_event(
        step="general_chat",
        status="completed",
        result="对话处理完成",
        time_ms=0
    ))
    
    return {
        "messages": [AIMessage(content=response.content)],
        "current_stage": "completed",
        "route_decision": "general_chat"
    }


# ============================================================================
# Clarification 节点包装器
# ============================================================================

async def clarification_node_wrapper(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    澄清节点包装器 - 调用现有的 clarification_node
    
    支持 interrupt 机制，暂停等待用户输入。
    """
    from app.schemas.stream_events import create_sql_step_event
    from app.agents.nodes.clarification_node import clarification_node
    
    logger.info("[Worker] clarification 开始执行")
    start_time = time.time()
    
    writer(create_sql_step_event(
        step="clarification",
        status="running",
        result="正在分析是否需要澄清...",
        time_ms=0
    ))
    
    try:
        result = clarification_node(state)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        if result.get("current_stage") != "schema_analysis":
            result["current_stage"] = "clarification_done"
            writer(create_sql_step_event(
                step="clarification",
                status="completed",
                result="澄清完成",
                time_ms=0
            ))
            writer(create_stage_message_event(
                message="澄清完成，继续进行 Schema 分析。",
                step="clarification",
                time_ms=elapsed_ms
            ))
        else:
            writer(create_stage_message_event(
                message="无需澄清，继续进行 Schema 分析。",
                step="clarification",
                time_ms=elapsed_ms
            ))
        
        return result
        
    except Exception as e:
        # interrupt 会抛出特殊异常，需要重新抛出
        if "interrupt" in str(type(e).__name__).lower():
            raise
        logger.error(f"[Worker] clarification 失败: {e}")
        writer(create_sql_step_event(
            step="clarification",
            status="error",
            result=str(e)[:100],
            time_ms=0
        ))
        return {"current_stage": "clarification_done"}


__all__ = [
    "schema_agent_node",
    "sql_generator_node",
    "sql_executor_node",
    "data_analyst_node",
    "chart_generator_node",
    "error_recovery_node",
    "general_chat_node",
    "clarification_node_wrapper",
]
