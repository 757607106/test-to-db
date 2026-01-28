"""
请求追踪模块

提供统一的请求追踪功能：
1. 生成唯一的 trace_id
2. 在日志中自动添加 trace_id
3. 与 LangSmith 集成
4. 支持跨 Agent 追踪

使用方式：
    from app.core.tracing import TraceContext, get_trace_id
    
    # 在请求处理开始时创建上下文
    with TraceContext() as ctx:
        logger.info(f"[{ctx.trace_id}] 开始处理请求")
        # ... 处理逻辑
    
    # 或者在 state 中使用
    state["trace_id"] = generate_trace_id()
"""
import uuid
import time
import logging
import contextvars
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


# ============================================================================
# Context Variables（线程/协程安全）
# ============================================================================

_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'trace_id', default=None
)
_trace_context_var: contextvars.ContextVar[Optional['TraceContext']] = contextvars.ContextVar(
    'trace_context', default=None
)


# ============================================================================
# Trace ID 生成
# ============================================================================

def generate_trace_id(prefix: str = "req") -> str:
    """
    生成唯一的追踪 ID
    
    格式: {prefix}-{timestamp_hex}-{random_hex}
    示例: req-18d5a2b3-a1b2c3d4
    
    Args:
        prefix: ID 前缀
        
    Returns:
        唯一的追踪 ID
    """
    timestamp_hex = hex(int(time.time() * 1000))[-8:]
    random_hex = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp_hex}-{random_hex}"


def get_trace_id() -> Optional[str]:
    """
    获取当前上下文的 trace_id
    
    Returns:
        当前的 trace_id，如果不在追踪上下文中则返回 None
    """
    return _trace_id_var.get()


def set_trace_id(trace_id: str):
    """
    设置当前上下文的 trace_id
    
    Args:
        trace_id: 追踪 ID
    """
    _trace_id_var.set(trace_id)


# ============================================================================
# Trace Context
# ============================================================================

@dataclass
class TraceContext:
    """
    追踪上下文
    
    记录请求的完整追踪信息，包括：
    - trace_id: 唯一追踪 ID
    - span_id: 当前操作 ID
    - parent_span_id: 父操作 ID
    - start_time: 开始时间
    - metadata: 额外元数据
    - spans: 子操作列表
    """
    trace_id: str = field(default_factory=lambda: generate_trace_id())
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    spans: list = field(default_factory=list)
    
    # 内部状态
    _token: Optional[contextvars.Token] = field(default=None, repr=False)
    _id_token: Optional[contextvars.Token] = field(default=None, repr=False)
    
    def __enter__(self) -> 'TraceContext':
        """进入上下文"""
        self._token = _trace_context_var.set(self)
        self._id_token = _trace_id_var.set(self.trace_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if self._token is not None:
            _trace_context_var.reset(self._token)
        if self._id_token is not None:
            _trace_id_var.reset(self._id_token)
        
        # 记录追踪完成
        if exc_type is not None:
            logger.warning(
                f"[{self.trace_id}] 请求异常完成: "
                f"duration={self.duration_ms:.0f}ms, "
                f"error={exc_type.__name__}"
            )
        else:
            logger.debug(
                f"[{self.trace_id}] 请求完成: "
                f"duration={self.duration_ms:.0f}ms"
            )
        
        return False  # 不抑制异常
    
    def create_child_span(self, name: str) -> 'SpanContext':
        """
        创建子操作追踪
        
        Args:
            name: 操作名称
            
        Returns:
            SpanContext 实例
        """
        span = SpanContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=self.span_id,
            name=name
        )
        self.spans.append(span)
        return span
    
    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "duration_ms": getattr(self, 'duration_ms', None),
            "metadata": self.metadata,
            "spans": [s.to_dict() for s in self.spans]
        }
    
    def to_langsmith_metadata(self) -> Dict[str, Any]:
        """
        转换为 LangSmith 元数据格式
        
        Returns:
            LangSmith 兼容的元数据字典
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            **self.metadata
        }


@dataclass
class SpanContext:
    """
    操作追踪上下文（子操作）
    """
    trace_id: str
    span_id: str
    parent_span_id: str
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __enter__(self) -> 'SpanContext':
        """进入上下文"""
        logger.debug(f"[{self.trace_id}] Span 开始: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is not None:
            self.status = "error"
            self.error = str(exc_val)
            logger.warning(
                f"[{self.trace_id}] Span 异常: {self.name}, "
                f"duration={self.duration_ms:.0f}ms, "
                f"error={exc_type.__name__}"
            )
        else:
            self.status = "completed"
            logger.debug(
                f"[{self.trace_id}] Span 完成: {self.name}, "
                f"duration={self.duration_ms:.0f}ms"
            )
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata
        }


# ============================================================================
# 装饰器
# ============================================================================

def traced(name: str = None):
    """
    追踪装饰器
    
    自动为函数创建追踪上下文
    
    Args:
        name: 操作名称（默认使用函数名）
        
    使用方式：
        @traced("sql_generation")
        async def generate_sql(query: str):
            ...
    """
    def decorator(func):
        operation_name = name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            ctx = _trace_context_var.get()
            
            if ctx is not None:
                # 在现有上下文中创建子 span
                with ctx.create_child_span(operation_name):
                    return await func(*args, **kwargs)
            else:
                # 创建新的追踪上下文
                with TraceContext() as new_ctx:
                    new_ctx.add_metadata("operation", operation_name)
                    return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            ctx = _trace_context_var.get()
            
            if ctx is not None:
                with ctx.create_child_span(operation_name):
                    return func(*args, **kwargs)
            else:
                with TraceContext() as new_ctx:
                    new_ctx.add_metadata("operation", operation_name)
                    return func(*args, **kwargs)
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# 日志格式化
# ============================================================================

class TraceLogFilter(logging.Filter):
    """
    日志过滤器：自动添加 trace_id
    
    使用方式：
        handler.addFilter(TraceLogFilter())
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = get_trace_id()
        record.trace_id = trace_id or "-"
        return True


def setup_trace_logging(logger_name: str = None):
    """
    设置追踪日志格式
    
    Args:
        logger_name: 日志器名称（None 表示根日志器）
    """
    target_logger = logging.getLogger(logger_name)
    
    # 添加过滤器
    trace_filter = TraceLogFilter()
    for handler in target_logger.handlers:
        handler.addFilter(trace_filter)
    
    # 更新格式
    formatter = logging.Formatter(
        '[%(asctime)s] [%(trace_id)s] %(levelname)s %(name)s: %(message)s'
    )
    for handler in target_logger.handlers:
        handler.setFormatter(formatter)


# ============================================================================
# 工具函数
# ============================================================================

def get_current_context() -> Optional[TraceContext]:
    """获取当前追踪上下文"""
    return _trace_context_var.get()


def inject_trace_to_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    将追踪信息注入到 LangGraph state
    
    Args:
        state: LangGraph 状态字典
        
    Returns:
        更新后的状态字典
    """
    trace_id = get_trace_id()
    if trace_id:
        state["trace_id"] = trace_id
    
    ctx = get_current_context()
    if ctx:
        state["trace_metadata"] = ctx.to_langsmith_metadata()
    
    return state


def extract_trace_from_state(state: Dict[str, Any]) -> Optional[str]:
    """
    从 LangGraph state 提取追踪 ID
    
    Args:
        state: LangGraph 状态字典
        
    Returns:
        追踪 ID
    """
    return state.get("trace_id")


__all__ = [
    "TraceContext",
    "SpanContext",
    "generate_trace_id",
    "get_trace_id",
    "set_trace_id",
    "get_current_context",
    "traced",
    "TraceLogFilter",
    "setup_trace_logging",
    "inject_trace_to_state",
    "extract_trace_from_state",
]
