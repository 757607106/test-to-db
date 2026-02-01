"""
节点装饰器模块

提供 LangGraph 节点的通用装饰器：
- streaming_node: 支持 StreamWriter 自动化流式事件的装饰器
- safe_node: 异常隔离装饰器
- safe_node_with_fallback: 带回退值的异常隔离装饰器

LangGraph 规范:
- 节点签名: (state, writer) -> dict
- 使用 StreamWriter 参数注入发送流式事件
"""
import functools
import logging
import time
from typing import Callable, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.types import StreamWriter

logger = logging.getLogger(__name__)


def streaming_node(
    step_name: str,
    fallback_stage: str = "error_recovery",
    skip_streaming: bool = False
):
    """
    流式节点装饰器 - 自动化流式事件发送和异常处理
    
    功能:
    - 自动发送 sql_step running 事件（节点开始时）
    - 自动发送 sql_step completed 事件（节点结束时，含 time_ms）
    - 异常时发送 error 事件并更新 error_history
    - 将流程导向错误恢复阶段
    
    Args:
        step_name: 步骤名称，用于流式事件的 step 字段
        fallback_stage: 异常时转移到的阶段，默认 "error_recovery"
        skip_streaming: 是否跳过流式事件发送，默认 False
        
    Usage:
        @streaming_node(step_name="schema_analysis")
        async def schema_agent_node(state: SQLMessageState, writer: StreamWriter):
            return await schema_agent.process(state)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(state: Dict[str, Any], writer: "StreamWriter" = None) -> Dict[str, Any]:
            from app.schemas.stream_events import create_sql_step_event
            
            start_time = time.time()
            node_name = func.__name__
            
            # 发送 running 事件
            if writer and not skip_streaming:
                try:
                    writer(create_sql_step_event(
                        step=step_name,
                        status="running",
                        result=None,
                        time_ms=0
                    ))
                except Exception as e:
                    logger.warning(f"[{node_name}] 发送 running 事件失败: {e}")
            
            try:
                # 执行节点逻辑
                result = await func(state, writer)
                
                # 计算耗时
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # 发送 completed 事件
                if writer and not skip_streaming:
                    try:
                        # 从结果中提取摘要信息
                        result_summary = _extract_result_summary(result, step_name)
                        writer(create_sql_step_event(
                            step=step_name,
                            status="completed",
                            result=result_summary,
                            time_ms=elapsed_ms
                        ))
                    except Exception as e:
                        logger.warning(f"[{node_name}] 发送 completed 事件失败: {e}")
                
                logger.info(f"[{node_name}] 完成 ({elapsed_ms}ms)")
                return result
                
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.error(f"[{node_name}] 节点异常: {e}")
                
                # 发送 error 事件
                if writer and not skip_streaming:
                    try:
                        writer(create_sql_step_event(
                            step=step_name,
                            status="error",
                            result=str(e)[:100],
                            time_ms=elapsed_ms
                        ))
                    except Exception as we:
                        logger.warning(f"[{node_name}] 发送 error 事件失败: {we}")
                
                # 构建错误记录
                error_record = {
                    "stage": node_name,
                    "error": str(e),
                    "timestamp": time.time()
                }
                error_history = state.get("error_history", [])
                
                return {
                    "current_stage": fallback_stage,
                    "error_history": error_history + [error_record]
                }
        
        return async_wrapper
    
    return decorator


def _extract_result_summary(result: Dict[str, Any], step_name: str) -> Optional[str]:
    """从节点结果中提取摘要信息用于流式事件"""
    if not result:
        return None
    
    # 根据步骤类型提取不同的摘要
    if step_name == "schema_analysis":
        schema_info = result.get("schema_info", {})
        tables = schema_info.get("tables", {})
        if isinstance(tables, dict):
            table_count = len(tables)
        elif isinstance(tables, list):
            table_count = len(tables)
        else:
            table_count = 0
        return f"识别到 {table_count} 个相关表"
    
    elif step_name == "sql_generation":
        sql = result.get("generated_sql", "")
        if sql:
            return sql[:100] + "..." if len(sql) > 100 else sql
        return None
    
    elif step_name == "sql_execution":
        exec_result = result.get("execution_result")
        if exec_result:
            if hasattr(exec_result, "rows_affected"):
                return f"返回 {exec_result.rows_affected} 条记录"
            elif isinstance(exec_result, dict):
                data = exec_result.get("data", {})
                row_count = data.get("row_count", 0)
                return f"返回 {row_count} 条记录"
        return "执行完成"
    
    elif step_name == "data_analysis":
        analysis = result.get("analysis_result", "")
        if analysis:
            return analysis[:100] + "..." if len(analysis) > 100 else analysis
        return "分析完成"
    
    elif step_name == "chart_generation":
        chart_config = result.get("chart_config")
        if chart_config:
            chart_type = chart_config.get("type", "unknown")
            return f"生成 {chart_type} 图表"
        return None
    
    return None


def safe_node(
    default_stage: str = "error_recovery",
    log_errors: bool = True,
    include_traceback: bool = False
):
    """
    节点安全装饰器 - 确保异常不会导致图崩溃
    
    功能:
    - 捕获节点执行过程中的所有异常
    - 记录错误到 error_history
    - 返回安全的状态更新，将流程导向错误恢复
    
    Args:
        default_stage: 异常时转移到的阶段，默认 "error_recovery"
        log_errors: 是否记录错误日志，默认 True
        include_traceback: 是否在日志中包含完整堆栈，默认 False
        
    Usage:
        @safe_node(default_stage="error_recovery")
        async def my_node(state: SQLMessageState, writer: StreamWriter):
            # 原有逻辑
            ...
            
    Returns:
        装饰后的节点函数
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            try:
                return await func(state, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(
                        f"[{func.__name__}] 节点异常: {e}",
                        exc_info=include_traceback
                    )
                
                # 构建错误记录
                error_record = {
                    "stage": func.__name__,
                    "error": str(e),
                    "timestamp": time.time()
                }
                
                # 保留现有错误历史
                error_history = state.get("error_history", [])
                
                return {
                    "current_stage": default_stage,
                    "error_history": error_history + [error_record]
                }
        
        @functools.wraps(func)
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            try:
                return func(state, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(
                        f"[{func.__name__}] 节点异常: {e}",
                        exc_info=include_traceback
                    )
                
                error_record = {
                    "stage": func.__name__,
                    "error": str(e),
                    "timestamp": time.time()
                }
                
                error_history = state.get("error_history", [])
                
                return {
                    "current_stage": default_stage,
                    "error_history": error_history + [error_record]
                }
        
        # 根据原函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_node_with_fallback(
    fallback_result: Optional[Dict[str, Any]] = None,
    default_stage: str = "error_recovery"
):
    """
    带回退值的节点安全装饰器
    
    当节点执行失败时，返回指定的回退值而不是错误状态。
    适用于非关键节点（如图表生成、问题推荐等）。
    
    Args:
        fallback_result: 失败时返回的回退值
        default_stage: 回退值中使用的阶段
        
    Usage:
        @safe_node_with_fallback(
            fallback_result={"chart_config": None},
            default_stage="completed"
        )
        async def chart_generator_node(state, writer):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            try:
                return await func(state, *args, **kwargs)
            except Exception as e:
                logger.warning(f"[{func.__name__}] 节点失败，使用回退值: {e}")
                
                result = fallback_result.copy() if fallback_result else {}
                result["current_stage"] = default_stage
                return result
        
        @functools.wraps(func)
        def sync_wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            try:
                return func(state, *args, **kwargs)
            except Exception as e:
                logger.warning(f"[{func.__name__}] 节点失败，使用回退值: {e}")
                
                result = fallback_result.copy() if fallback_result else {}
                result["current_stage"] = default_stage
                return result
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


__all__ = [
    "streaming_node",
    "safe_node",
    "safe_node_with_fallback",
]
