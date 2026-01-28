"""
架构修复测试

测试内容：
1. LLM 包装器（重试、超时、错误分类）
2. Checkpointer V2（异步初始化、健康检查）
3. 请求追踪（trace_id 生成、上下文管理）
4. LangSmith 集成（配置验证）

运行方式：
    pytest backend/tests/test_architecture_fixes.py -v
"""
import asyncio
import pytest
import time
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================================
# LLM 包装器测试
# ============================================================================

class TestLLMWrapper:
    """LLM 包装器测试"""
    
    def test_error_classification(self):
        """测试错误分类"""
        from app.core.llm_wrapper import classify_error, LLMErrorType
        
        # 超时错误
        assert classify_error(Exception("Connection timed out")) == LLMErrorType.TIMEOUT
        assert classify_error(Exception("Request timeout")) == LLMErrorType.TIMEOUT
        
        # 速率限制
        assert classify_error(Exception("Rate limit exceeded")) == LLMErrorType.RATE_LIMIT
        assert classify_error(Exception("Error 429: Too many requests")) == LLMErrorType.RATE_LIMIT
        
        # 服务器错误
        assert classify_error(Exception("Internal server error 500")) == LLMErrorType.SERVER_ERROR
        assert classify_error(Exception("502 Bad Gateway")) == LLMErrorType.SERVER_ERROR
        
        # 认证错误
        assert classify_error(Exception("401 Unauthorized")) == LLMErrorType.AUTH_ERROR
        assert classify_error(Exception("Invalid API key")) == LLMErrorType.AUTH_ERROR
        
        # 上下文长度
        assert classify_error(Exception("Context length exceeded")) == LLMErrorType.CONTEXT_LENGTH
        assert classify_error(Exception("Token limit exceeded")) == LLMErrorType.CONTEXT_LENGTH
        
        # 未知错误
        assert classify_error(Exception("Some random error")) == LLMErrorType.UNKNOWN
    
    def test_should_retry(self):
        """测试重试判断"""
        from app.core.llm_wrapper import should_retry, LLMErrorType, LLMWrapperConfig
        
        config = LLMWrapperConfig()
        
        # 应该重试的错误
        assert should_retry(LLMErrorType.TIMEOUT, config) == True
        assert should_retry(LLMErrorType.RATE_LIMIT, config) == True
        assert should_retry(LLMErrorType.SERVER_ERROR, config) == True
        
        # 不应该重试的错误
        assert should_retry(LLMErrorType.AUTH_ERROR, config) == False
        assert should_retry(LLMErrorType.INVALID_REQUEST, config) == False
        assert should_retry(LLMErrorType.CONTEXT_LENGTH, config) == False
    
    def test_delay_calculation(self):
        """测试延迟计算（指数退避）"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        
        config = LLMWrapperConfig(
            retry_base_delay=1.0,
            retry_exponential_base=2.0,
            retry_max_delay=30.0
        )
        wrapper = LLMWrapper(config=config)
        
        # 验证指数退避
        assert wrapper._calculate_delay(0) == 1.0  # 1 * 2^0 = 1
        assert wrapper._calculate_delay(1) == 2.0  # 1 * 2^1 = 2
        assert wrapper._calculate_delay(2) == 4.0  # 1 * 2^2 = 4
        assert wrapper._calculate_delay(3) == 8.0  # 1 * 2^3 = 8
        
        # 验证最大延迟限制
        assert wrapper._calculate_delay(10) == 30.0  # 超过最大值，返回最大值
    
    def test_metrics_recording(self):
        """测试指标记录"""
        from app.core.llm_wrapper import LLMMetrics, LLMErrorType
        
        metrics = LLMMetrics()
        
        # 记录成功调用
        metrics.record_call(success=True, latency_ms=100, tokens=50, retries=0)
        metrics.record_call(success=True, latency_ms=200, tokens=100, retries=1)
        
        # 记录失败调用
        metrics.record_call(
            success=False, 
            latency_ms=300, 
            error_type=LLMErrorType.TIMEOUT, 
            retries=3
        )
        
        # 验证指标
        assert metrics.total_calls == 3
        assert metrics.successful_calls == 2
        assert metrics.failed_calls == 1
        assert metrics.total_retries == 4
        assert metrics.total_tokens == 150
        assert metrics.success_rate == 2/3
        assert metrics.avg_latency_ms == 200.0
        assert metrics.error_counts[LLMErrorType.TIMEOUT] == 1
    
    @pytest.mark.asyncio
    async def test_async_invoke_success(self):
        """测试异步调用成功"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        from langchain_core.messages import HumanMessage, AIMessage
        
        # 创建 mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Test response"))
        
        config = LLMWrapperConfig(timeout=5.0, max_retries=2)
        wrapper = LLMWrapper(llm=mock_llm, config=config)
        
        # 调用
        messages = [HumanMessage(content="Hello")]
        response = await wrapper.ainvoke(messages, trace_id="test-123")
        
        # 验证
        assert response.content == "Test response"
        assert wrapper.metrics.successful_calls == 1
        assert wrapper.metrics.failed_calls == 0
    
    @pytest.mark.asyncio
    async def test_async_invoke_retry(self):
        """测试异步调用重试"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        from langchain_core.messages import HumanMessage, AIMessage
        
        # 创建 mock LLM，前两次失败，第三次成功
        mock_llm = AsyncMock()
        call_count = 0
        
        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Server error 500")
            return AIMessage(content="Success after retry")
        
        mock_llm.ainvoke = mock_ainvoke
        
        config = LLMWrapperConfig(
            timeout=5.0, 
            max_retries=3,
            retry_base_delay=0.1  # 快速重试
        )
        wrapper = LLMWrapper(llm=mock_llm, config=config)
        
        # 调用
        messages = [HumanMessage(content="Hello")]
        response = await wrapper.ainvoke(messages, trace_id="test-retry")
        
        # 验证
        assert response.content == "Success after retry"
        assert call_count == 3
        assert wrapper.metrics.total_retries == 2


# ============================================================================
# Checkpointer V2 测试
# ============================================================================

class TestCheckpointerV2:
    """Checkpointer V2 测试"""
    
    @pytest.mark.asyncio
    async def test_disabled_mode(self):
        """测试禁用模式"""
        from app.core.checkpointer_v2 import CheckpointerManager
        
        with patch('app.core.checkpointer_v2.settings') as mock_settings:
            mock_settings.CHECKPOINT_MODE = "none"
            
            # 重置单例
            CheckpointerManager._instance = None
            
            checkpointer = await CheckpointerManager.initialize()
            
            assert checkpointer is None
            
            # 清理
            await CheckpointerManager.shutdown()
    
    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """测试未初始化时的健康检查"""
        from app.core.checkpointer_v2 import CheckpointerManager
        
        # 重置单例
        CheckpointerManager._instance = None
        
        with patch('app.core.checkpointer_v2.settings') as mock_settings:
            mock_settings.CHECKPOINT_MODE = "none"
            
            result = await CheckpointerManager.health_check()
            
            # 未初始化时应该先初始化
            assert result["status"] in ["not_initialized", "disabled"]
    
    def test_password_masking(self):
        """测试密码隐藏"""
        from app.core.checkpointer_v2 import CheckpointerManager
        
        manager = CheckpointerManager()
        
        # 测试正常 URI
        uri = "postgresql://user:password123@localhost:5432/db"
        masked = manager._mask_password(uri)
        assert "password123" not in masked
        assert "user:****@" in masked
        
        # 测试无密码 URI
        uri_no_pass = "postgresql://localhost:5432/db"
        masked_no_pass = manager._mask_password(uri_no_pass)
        assert masked_no_pass == uri_no_pass


# ============================================================================
# 请求追踪测试
# ============================================================================

class TestTracing:
    """请求追踪测试"""
    
    def test_trace_id_generation(self):
        """测试 trace_id 生成"""
        from app.core.tracing import generate_trace_id
        
        # 生成多个 ID
        ids = [generate_trace_id() for _ in range(100)]
        
        # 验证唯一性
        assert len(set(ids)) == 100
        
        # 验证格式
        for trace_id in ids:
            assert trace_id.startswith("req-")
            parts = trace_id.split("-")
            assert len(parts) == 3
    
    def test_trace_id_with_prefix(self):
        """测试自定义前缀"""
        from app.core.tracing import generate_trace_id
        
        trace_id = generate_trace_id(prefix="sql")
        assert trace_id.startswith("sql-")
    
    def test_trace_context(self):
        """测试追踪上下文"""
        from app.core.tracing import TraceContext, get_trace_id
        
        # 上下文外部
        assert get_trace_id() is None
        
        # 进入上下文
        with TraceContext() as ctx:
            assert get_trace_id() == ctx.trace_id
            assert ctx.trace_id is not None
            
            # 添加元数据
            ctx.add_metadata("user_id", "user-123")
            assert ctx.metadata["user_id"] == "user-123"
        
        # 退出上下文
        assert get_trace_id() is None
    
    def test_child_span(self):
        """测试子操作追踪"""
        from app.core.tracing import TraceContext
        
        with TraceContext() as ctx:
            # 创建子 span
            with ctx.create_child_span("sql_generation") as span:
                assert span.trace_id == ctx.trace_id
                assert span.parent_span_id == ctx.span_id
                assert span.name == "sql_generation"
                
                time.sleep(0.01)  # 模拟操作
            
            # 验证 span 完成
            assert span.status == "completed"
            assert span.duration_ms is not None
            assert span.duration_ms >= 10
            
            # 验证 span 被记录
            assert len(ctx.spans) == 1
    
    def test_span_error_handling(self):
        """测试 span 错误处理"""
        from app.core.tracing import TraceContext
        
        with TraceContext() as ctx:
            try:
                with ctx.create_child_span("failing_operation") as span:
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            # 验证错误被记录
            assert span.status == "error"
            assert "Test error" in span.error
    
    def test_to_dict(self):
        """测试转换为字典"""
        from app.core.tracing import TraceContext
        
        with TraceContext() as ctx:
            ctx.add_metadata("key", "value")
            
            with ctx.create_child_span("test_span"):
                pass
        
        result = ctx.to_dict()
        
        assert "trace_id" in result
        assert "span_id" in result
        assert "metadata" in result
        assert result["metadata"]["key"] == "value"
        assert len(result["spans"]) == 1
    
    def test_inject_trace_to_state(self):
        """测试注入追踪到 state"""
        from app.core.tracing import TraceContext, inject_trace_to_state
        
        state = {"messages": [], "connection_id": 1}
        
        with TraceContext() as ctx:
            ctx.add_metadata("user_id", "user-123")
            
            updated_state = inject_trace_to_state(state)
            
            assert updated_state["trace_id"] == ctx.trace_id
            assert "trace_metadata" in updated_state


# ============================================================================
# LangSmith 配置测试
# ============================================================================

class TestLangSmithConfig:
    """LangSmith 配置测试"""
    
    def test_config_loading(self):
        """测试配置加载"""
        from app.core.config import settings
        
        # 验证配置字段存在
        assert hasattr(settings, 'LANGCHAIN_TRACING_V2')
        assert hasattr(settings, 'LANGCHAIN_ENDPOINT')
        assert hasattr(settings, 'LANGCHAIN_API_KEY')
        assert hasattr(settings, 'LANGCHAIN_PROJECT')
    
    def test_tracing_disabled_by_default(self):
        """测试 LangSmith 追踪已启用"""
        from app.core.config import settings
        
        # 验证 LangSmith 配置已写死启用
        assert settings.LANGCHAIN_TRACING_V2 == True
        # API key 应从环境变量读取，不硬编码
        assert hasattr(settings, 'LANGCHAIN_API_KEY')
        assert settings.LANGCHAIN_PROJECT == "chatbi-production"


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_llm_wrapper_with_tracing(self):
        """测试 LLM 包装器与追踪集成"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        from app.core.tracing import TraceContext, get_trace_id
        from langchain_core.messages import HumanMessage, AIMessage
        
        # 创建 mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))
        
        config = LLMWrapperConfig(timeout=5.0)
        wrapper = LLMWrapper(llm=mock_llm, config=config)
        
        # 在追踪上下文中调用
        with TraceContext() as ctx:
            trace_id = get_trace_id()
            
            response = await wrapper.ainvoke(
                [HumanMessage(content="Hello")],
                trace_id=trace_id
            )
            
            assert response.content == "Response"
    
    @pytest.mark.asyncio
    async def test_full_request_flow(self):
        """测试完整请求流程"""
        from app.core.tracing import TraceContext, inject_trace_to_state
        from app.core.llm_wrapper import get_llm_wrapper, reset_llm_wrapper
        from langchain_core.messages import HumanMessage, AIMessage
        
        # 重置全局包装器
        reset_llm_wrapper()
        
        # 模拟请求处理
        with TraceContext() as ctx:
            ctx.add_metadata("user_id", "test-user")
            ctx.add_metadata("connection_id", 1)
            
            # 创建 state
            state = {
                "messages": [HumanMessage(content="查询销售数据")],
                "connection_id": 1
            }
            
            # 注入追踪
            state = inject_trace_to_state(state)
            
            # 验证 state 包含追踪信息
            assert state["trace_id"] == ctx.trace_id
            assert "trace_metadata" in state
            
            # 创建子 span 模拟各阶段
            with ctx.create_child_span("schema_analysis"):
                pass
            
            with ctx.create_child_span("sql_generation"):
                pass
            
            with ctx.create_child_span("sql_execution"):
                pass
            
            # 验证所有 span 被记录
            assert len(ctx.spans) == 3


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
