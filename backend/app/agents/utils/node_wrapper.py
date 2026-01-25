"""
节点安全装饰器

提供节点级别的异常隔离，确保单个节点的异常不会导致整个图崩溃。

LangGraph 最佳实践: 多层错误处理（节点、图、应用）
参考: https://www.swarnendu.de/blog/langgraph-best-practices/
"""
import functools
import logging
import time
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)


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
    "safe_node",
    "safe_node_with_fallback",
]
