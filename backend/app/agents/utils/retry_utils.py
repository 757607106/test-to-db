"""
重试工具模块

提供指数退避重试策略，用于处理临时性故障（如 LLM API 超时）。

LangGraph 最佳实践: graceful degradation with retry/fallback
"""
import asyncio
import logging
import random
from typing import TypeVar, Callable, Optional, Type, Tuple

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    **kwargs
) -> T:
    """
    指数退避重试策略
    
    当函数执行失败时，按指数增长的延迟时间重试。
    适用于调用外部 API（如 LLM）时的临时性故障处理。
    
    Args:
        func: 要执行的异步函数
        *args: 传递给函数的位置参数
        max_retries: 最大重试次数，默认 3
        base_delay: 基础延迟时间（秒），默认 1.0
        max_delay: 最大延迟时间（秒），默认 30.0
        exponential_base: 指数基数，默认 2.0
        jitter: 是否添加随机抖动（防止惊群效应），默认 True
        retry_exceptions: 需要重试的异常类型，默认 None（重试所有异常）
        **kwargs: 传递给函数的关键字参数
        
    Returns:
        函数执行结果
        
    Raises:
        最后一次重试的异常
        
    Usage:
        result = await retry_with_backoff(
            llm.ainvoke,
            messages,
            max_retries=3,
            base_delay=1.0
        )
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            # 检查是否是需要重试的异常类型
            if retry_exceptions and not isinstance(e, retry_exceptions):
                raise
            
            last_exception = e
            
            # 最后一次重试失败，直接抛出
            if attempt >= max_retries - 1:
                logger.error(f"重试 {max_retries} 次后仍失败: {e}")
                raise
            
            # 计算延迟时间
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            # 添加随机抖动
            if jitter:
                delay = delay * (0.5 + random.random())
            
            logger.warning(
                f"执行失败 (尝试 {attempt + 1}/{max_retries})，"
                f"{delay:.1f}s 后重试: {e}"
            )
            
            await asyncio.sleep(delay)
    
    # 理论上不会执行到这里
    raise last_exception


def retry_with_backoff_sync(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    **kwargs
) -> T:
    """
    同步版本的指数退避重试策略
    
    用于同步函数的重试，参数与异步版本相同。
    """
    import time
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if retry_exceptions and not isinstance(e, retry_exceptions):
                raise
            
            last_exception = e
            
            if attempt >= max_retries - 1:
                logger.error(f"重试 {max_retries} 次后仍失败: {e}")
                raise
            
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            if jitter:
                delay = delay * (0.5 + random.random())
            
            logger.warning(
                f"执行失败 (尝试 {attempt + 1}/{max_retries})，"
                f"{delay:.1f}s 后重试: {e}"
            )
            
            time.sleep(delay)
    
    raise last_exception


class RetryConfig:
    """
    重试配置类
    
    提供预定义的重试配置，便于统一管理。
    
    Usage:
        config = RetryConfig.LLM_CALL
        result = await retry_with_backoff(
            func,
            max_retries=config.max_retries,
            base_delay=config.base_delay
        )
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def to_dict(self) -> dict:
        """转换为字典，用于传递给 retry_with_backoff"""
        return {
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "exponential_base": self.exponential_base,
            "jitter": self.jitter
        }


# 预定义配置
class RetryConfigs:
    """预定义的重试配置"""
    
    # LLM 调用配置：较长延迟，适应 API 限流
    LLM_CALL = RetryConfig(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True
    )
    
    # 数据库查询配置：较短延迟
    DB_QUERY = RetryConfig(
        max_retries=2,
        base_delay=0.5,
        max_delay=5.0,
        exponential_base=2.0,
        jitter=True
    )
    
    # 快速重试配置：用于网络抖动等临时问题
    QUICK = RetryConfig(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
        exponential_base=2.0,
        jitter=True
    )


__all__ = [
    "retry_with_backoff",
    "retry_with_backoff_sync",
    "RetryConfig",
    "RetryConfigs",
]
