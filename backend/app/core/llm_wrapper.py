"""
统一的 LLM 调用包装器

提供：
1. 统一的重试策略（指数退避）
2. LangSmith 追踪集成
3. 错误分类和处理
4. 性能监控

注意：不设置超时限制，因为复杂任务执行时间无法预估。
重试机制针对可恢复错误（如 429 限流、服务器错误）。

使用方式：
    from app.core.llm_wrapper import LLMWrapper, get_llm_wrapper
    
    # 获取全局包装器
    wrapper = get_llm_wrapper()
    
    # 异步调用
    response = await wrapper.ainvoke(messages)
    
    # 同步调用
    response = wrapper.invoke(messages)
    
    # 带追踪的调用
    response = await wrapper.ainvoke_with_trace(
        messages,
        trace_id="req-123",
        metadata={"user_id": "user-1"}
    )
"""
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from functools import wraps
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.callbacks import CallbackManager
from langchain_core.tracers import LangChainTracer

logger = logging.getLogger(__name__)


# ============================================================================
# 配置
# ============================================================================

@dataclass
class LLMWrapperConfig:
    """LLM 包装器配置"""
    # 重试配置
    max_retries: int = 3
    retry_base_delay: float = 1.0  # 基础延迟（秒）
    retry_max_delay: float = 30.0  # 最大延迟（秒）
    retry_exponential_base: float = 2.0  # 指数基数
    
    # 监控配置
    enable_tracing: bool = True
    enable_metrics: bool = True
    
    # 错误处理（哪些错误类型允许重试）
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True
    
    # 保留 timeout 字段以保持向后兼容（但不再使用）
    timeout: float = None  # 已废弃，不再使用
    connect_timeout: float = None  # 已废弃，不再使用


# 默认配置
DEFAULT_CONFIG = LLMWrapperConfig()


# ============================================================================
# 错误分类
# ============================================================================

class LLMErrorType:
    """LLM 错误类型"""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    INVALID_REQUEST = "invalid_request"
    CONTEXT_LENGTH = "context_length"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> str:
    """
    分类 LLM 错误
    
    Args:
        error: 异常对象
        
    Returns:
        错误类型字符串
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    # 超时错误
    if "timeout" in error_str or "timed out" in error_str:
        return LLMErrorType.TIMEOUT
    
    # 速率限制
    if "rate" in error_str and "limit" in error_str:
        return LLMErrorType.RATE_LIMIT
    if "429" in error_str or "too many requests" in error_str:
        return LLMErrorType.RATE_LIMIT
    
    # 服务器错误
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return LLMErrorType.SERVER_ERROR
    if "server" in error_str and "error" in error_str:
        return LLMErrorType.SERVER_ERROR
    
    # 认证错误
    if "401" in error_str or "403" in error_str:
        return LLMErrorType.AUTH_ERROR
    if "unauthorized" in error_str or "forbidden" in error_str:
        return LLMErrorType.AUTH_ERROR
    if "api key" in error_str or "api_key" in error_str:
        return LLMErrorType.AUTH_ERROR
    
    # 请求无效
    if "400" in error_str or "invalid" in error_str:
        return LLMErrorType.INVALID_REQUEST
    
    # 上下文长度超限
    if "context" in error_str and "length" in error_str:
        return LLMErrorType.CONTEXT_LENGTH
    if "token" in error_str and ("limit" in error_str or "exceed" in error_str):
        return LLMErrorType.CONTEXT_LENGTH
    
    return LLMErrorType.UNKNOWN


def should_retry(error_type: str, config: LLMWrapperConfig) -> bool:
    """
    判断是否应该重试
    
    Args:
        error_type: 错误类型
        config: 配置
        
    Returns:
        是否应该重试
    """
    if error_type == LLMErrorType.TIMEOUT:
        return config.retry_on_timeout
    if error_type == LLMErrorType.RATE_LIMIT:
        return config.retry_on_rate_limit
    if error_type == LLMErrorType.SERVER_ERROR:
        return config.retry_on_server_error
    
    # 以下错误不重试
    if error_type in [LLMErrorType.AUTH_ERROR, LLMErrorType.INVALID_REQUEST, LLMErrorType.CONTEXT_LENGTH]:
        return False
    
    # 未知错误默认重试一次
    return True


# ============================================================================
# 性能指标
# ============================================================================

@dataclass
class LLMMetrics:
    """LLM 调用指标"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_retries: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    
    # 错误统计
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    def record_call(self, success: bool, latency_ms: float, tokens: int = 0, 
                    error_type: str = None, retries: int = 0):
        """记录一次调用"""
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.total_tokens += tokens
        self.total_retries += retries
        
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            if error_type:
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        """平均延迟"""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 4),
            "total_retries": self.total_retries,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "error_counts": self.error_counts
        }


# ============================================================================
# LLM 包装器
# ============================================================================

class LLMWrapper:
    """
    统一的 LLM 调用包装器
    
    特性：
    - 指数退避重试
    - 超时控制
    - 错误分类
    - 性能监控
    - LangSmith 追踪集成
    """
    
    def __init__(
        self,
        llm: BaseChatModel = None,
        config: LLMWrapperConfig = None,
        name: str = "default"
    ):
        """
        初始化包装器
        
        Args:
            llm: LLM 模型实例（如果为 None，将延迟加载）
            config: 配置
            name: 包装器名称（用于日志和监控）
        """
        self._llm = llm
        self.config = config or DEFAULT_CONFIG
        self.name = name
        self.metrics = LLMMetrics()
        self._tracer = None
    
    @property
    def llm(self) -> BaseChatModel:
        """延迟加载 LLM"""
        if self._llm is None:
            from app.core.llms import get_default_model
            self._llm = get_default_model(caller=f"LLMWrapper:{self.name}")
        return self._llm
    
    def _get_tracer(self) -> Optional[LangChainTracer]:
        """获取 LangSmith tracer"""
        if not self.config.enable_tracing:
            return None
        
        if self._tracer is None:
            try:
                import os
                if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
                    self._tracer = LangChainTracer(
                        project_name=os.getenv("LANGCHAIN_PROJECT", "chatbi")
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith tracer: {e}")
        
        return self._tracer
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟（指数退避）
        
        Args:
            attempt: 当前尝试次数（从 0 开始）
            
        Returns:
            延迟秒数
        """
        delay = self.config.retry_base_delay * (self.config.retry_exponential_base ** attempt)
        return min(delay, self.config.retry_max_delay)
    
    async def ainvoke(
        self,
        messages: List[BaseMessage],
        trace_id: str = None,
        metadata: Dict[str, Any] = None,
        **kwargs
    ) -> AIMessage:
        """
        异步调用 LLM（带重试机制，无超时限制）
        
        Args:
            messages: 消息列表
            trace_id: 追踪 ID（用于日志关联）
            metadata: 额外元数据
            **kwargs: 传递给 LLM 的额外参数
            
        Returns:
            AI 响应消息
            
        Raises:
            Exception: 当所有重试都失败时
            
        Note:
            不设置超时限制，因为复杂任务执行时间无法预估。
            重试机制针对可恢复错误（如 429 限流、服务器错误）。
        """
        trace_id = trace_id or str(uuid.uuid4())[:8]
        
        last_error = None
        retries = 0
        start_time = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # 直接调用，不设置超时限制
                response = await self.llm.ainvoke(messages, **kwargs)
                
                # 记录成功
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_call(
                    success=True,
                    latency_ms=latency_ms,
                    retries=retries
                )
                
                logger.debug(
                    f"[{trace_id}] LLM call succeeded: "
                    f"latency={latency_ms:.0f}ms, retries={retries}"
                )
                
                return response
                
            except Exception as e:
                last_error = e
                error_type = classify_error(e)
                logger.warning(
                    f"[{trace_id}] LLM call failed: "
                    f"attempt={attempt + 1}/{self.config.max_retries + 1}, "
                    f"error_type={error_type}, error={str(e)[:100]}"
                )
            
            # 判断是否重试
            if attempt < self.config.max_retries and should_retry(error_type, self.config):
                retries += 1
                delay = self._calculate_delay(attempt)
                logger.info(f"[{trace_id}] Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
            else:
                break
        
        # 所有重试都失败
        latency_ms = (time.time() - start_time) * 1000
        self.metrics.record_call(
            success=False,
            latency_ms=latency_ms,
            error_type=error_type,
            retries=retries
        )
        
        logger.error(
            f"[{trace_id}] LLM call failed after {retries} retries: "
            f"error_type={error_type}, error={str(last_error)}"
        )
        
        raise last_error
    
    def invoke(
        self,
        messages: List[BaseMessage],
        trace_id: str = None,
        metadata: Dict[str, Any] = None,
        **kwargs
    ) -> AIMessage:
        """
        同步调用 LLM（带重试机制，无超时限制）
        
        注意：在异步环境中请使用 ainvoke
        """
        trace_id = trace_id or str(uuid.uuid4())[:8]
        
        last_error = None
        retries = 0
        start_time = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.llm.invoke(messages, **kwargs)
                
                # 记录成功
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_call(
                    success=True,
                    latency_ms=latency_ms,
                    retries=retries
                )
                
                logger.debug(
                    f"[{trace_id}] LLM call succeeded: "
                    f"latency={latency_ms:.0f}ms, retries={retries}"
                )
                
                return response
                
            except Exception as e:
                last_error = e
                error_type = classify_error(e)
                logger.warning(
                    f"[{trace_id}] LLM call failed: "
                    f"attempt={attempt + 1}/{self.config.max_retries + 1}, "
                    f"error_type={error_type}, error={str(e)[:100]}"
                )
                
                # 判断是否重试
                if attempt < self.config.max_retries and should_retry(error_type, self.config):
                    retries += 1
                    delay = self._calculate_delay(attempt)
                    logger.info(f"[{trace_id}] Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    break
        
        # 所有重试都失败
        latency_ms = (time.time() - start_time) * 1000
        self.metrics.record_call(
            success=False,
            latency_ms=latency_ms,
            error_type=error_type,
            retries=retries
        )
        
        logger.error(
            f"[{trace_id}] LLM call failed after {retries} retries: "
            f"error_type={error_type}, error={str(last_error)}"
        )
        
        raise last_error
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.metrics.to_dict()
    
    def reset_metrics(self):
        """重置性能指标"""
        self.metrics = LLMMetrics()


# ============================================================================
# 全局实例
# ============================================================================

_global_wrapper: Optional[LLMWrapper] = None


def get_llm_wrapper(
    llm: BaseChatModel = None,
    config: LLMWrapperConfig = None,
    name: str = "default"
) -> LLMWrapper:
    """
    获取 LLM 包装器实例
    
    Args:
        llm: LLM 模型实例（可选）
        config: 配置（可选）
        name: 包装器名称
        
    Returns:
        LLMWrapper 实例
    """
    global _global_wrapper
    
    if llm is not None or config is not None:
        # 创建新实例
        return LLMWrapper(llm=llm, config=config, name=name)
    
    # 返回全局实例
    if _global_wrapper is None:
        _global_wrapper = LLMWrapper(name="global")
    
    return _global_wrapper


def reset_llm_wrapper():
    """重置全局包装器"""
    global _global_wrapper
    _global_wrapper = None


# ============================================================================
# 便捷函数
# ============================================================================

async def llm_ainvoke(
    messages: List[BaseMessage],
    trace_id: str = None,
    **kwargs
) -> AIMessage:
    """
    便捷的异步 LLM 调用函数
    
    Args:
        messages: 消息列表
        trace_id: 追踪 ID
        **kwargs: 额外参数
        
    Returns:
        AI 响应消息
    """
    wrapper = get_llm_wrapper()
    return await wrapper.ainvoke(messages, trace_id=trace_id, **kwargs)


def llm_invoke(
    messages: List[BaseMessage],
    trace_id: str = None,
    **kwargs
) -> AIMessage:
    """
    便捷的同步 LLM 调用函数
    
    Args:
        messages: 消息列表
        trace_id: 追踪 ID
        **kwargs: 额外参数
        
    Returns:
        AI 响应消息
    """
    wrapper = get_llm_wrapper()
    return wrapper.invoke(messages, trace_id=trace_id, **kwargs)


__all__ = [
    "LLMWrapper",
    "LLMWrapperConfig",
    "LLMMetrics",
    "LLMErrorType",
    "get_llm_wrapper",
    "reset_llm_wrapper",
    "llm_ainvoke",
    "llm_invoke",
    "classify_error",
    "should_retry",
]
