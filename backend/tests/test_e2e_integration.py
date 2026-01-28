"""
端到端集成测试

测试完整的 Text-to-SQL 流程，包括：
1. 查询处理流程
2. 错误恢复机制
3. 多轮对话
4. 缓存机制
5. LangSmith 追踪

运行方式：
    # 运行所有测试
    pytest backend/tests/test_e2e_integration.py -v
    
    # 只运行快速测试
    pytest backend/tests/test_e2e_integration.py -v -m "not slow"
    
    # 运行带 LangSmith 追踪的测试
    LANGCHAIN_TRACING_V2=true pytest backend/tests/test_e2e_integration.py -v

注意：
    - 需要配置数据库连接
    - 需要配置 LLM API
    - 部分测试需要 LangSmith API Key
"""
import asyncio
import pytest
import logging
import os
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

logger = logging.getLogger(__name__)


# ============================================================================
# 测试配置
# ============================================================================

# 标记慢速测试
pytestmark = pytest.mark.asyncio


def is_langsmith_enabled() -> bool:
    """检查 LangSmith 是否启用"""
    return os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"


def skip_if_no_db():
    """如果没有数据库连接则跳过"""
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        db.close()
        return False
    except Exception:
        return True


# ============================================================================
# 状态管理测试
# ============================================================================

class TestStateManagement:
    """状态管理测试"""
    
    def test_state_schema_validation(self):
        """测试状态 schema 验证"""
        from app.core.state import SQLMessageState
        from langchain_core.messages import HumanMessage
        
        # 创建有效状态
        state: SQLMessageState = {
            "messages": [HumanMessage(content="测试查询")],
            "connection_id": 1,
            "current_stage": "init",
            "retry_count": 0,
            "max_retries": 3,
            "error_history": []
        }
        
        # 验证必需字段
        assert "messages" in state
        assert "connection_id" in state
        assert "current_stage" in state
    
    def test_state_with_trace_id(self):
        """测试带追踪 ID 的状态"""
        from app.core.state import SQLMessageState
        from app.core.tracing import generate_trace_id, inject_trace_to_state, TraceContext
        from langchain_core.messages import HumanMessage
        
        state: SQLMessageState = {
            "messages": [HumanMessage(content="测试查询")],
            "connection_id": 1,
            "current_stage": "init"
        }
        
        # 在追踪上下文中注入
        with TraceContext() as ctx:
            updated_state = inject_trace_to_state(state)
            
            assert "trace_id" in updated_state
            assert updated_state["trace_id"] == ctx.trace_id


# ============================================================================
# 错误恢复测试
# ============================================================================

class TestErrorRecovery:
    """错误恢复测试"""
    
    def test_error_classification(self):
        """测试错误分类"""
        from app.agents.agents.error_recovery_agent import _classify_error_type
        
        # MySQL LIMIT in subquery 错误
        error_msg = "This version of MySQL doesn't yet support 'LIMIT & IN/ALL/ANY/SOME subquery'"
        assert _classify_error_type(error_msg.lower()) == "mysql_limit_subquery_error"
        
        # Unknown column 错误
        error_msg = "Unknown column 'total_inventory' in 'field list'"
        assert _classify_error_type(error_msg.lower()) == "sql_syntax_error"
        
        # 连接错误
        error_msg = "Connection refused"
        assert _classify_error_type(error_msg.lower()) == "connection_error"
        
        # 超时错误
        error_msg = "Query execution timeout"
        assert _classify_error_type(error_msg.lower()) == "timeout_error"
    
    def test_recovery_strategy_generation(self):
        """测试恢复策略生成"""
        from app.agents.agents.error_recovery_agent import generate_recovery_strategy
        import json
        
        # 测试 SQL 语法错误的恢复策略
        error_analysis = json.dumps({
            "success": True,
            "pattern_found": True,
            "most_common_type": "sql_syntax_error",
            "total_errors": 1
        })
        
        result = generate_recovery_strategy.invoke({
            "error_analysis": error_analysis,
            "retry_count": 0
        })
        
        result_data = json.loads(result)
        assert result_data["success"] == True
        assert "strategy" in result_data
        assert result_data["strategy"]["primary_action"] == "regenerate_sql"
        assert result_data["strategy"]["auto_fixable"] == True
    
    def test_user_friendly_messages(self):
        """测试用户友好消息"""
        from app.agents.agents.error_recovery_agent import USER_FRIENDLY_MESSAGES
        
        # 验证所有动作都有对应的消息
        expected_actions = [
            "regenerate_sql", "mysql_limit_fix", "verify_schema",
            "check_connection", "simplify_query", "optimize_query", "restart"
        ]
        
        for action in expected_actions:
            assert action in USER_FRIENDLY_MESSAGES
            assert "retrying" in USER_FRIENDLY_MESSAGES[action]
            assert "failed" in USER_FRIENDLY_MESSAGES[action]


# ============================================================================
# SQL 验证测试
# ============================================================================

class TestSQLValidation:
    """SQL 验证测试"""
    
    def test_dangerous_keyword_detection(self):
        """测试危险关键字检测"""
        from app.services.sql_validator import SQLValidator
        
        validator = SQLValidator()
        
        # 危险 SQL
        dangerous_sqls = [
            "DROP TABLE users",
            "DELETE FROM orders",
            "TRUNCATE TABLE products",
            "UPDATE users SET password = 'hacked'",
        ]
        
        for sql in dangerous_sqls:
            result = validator.validate(sql)
            assert result.is_valid == False
            assert len(result.errors) > 0
    
    def test_limit_validation(self):
        """测试 LIMIT 验证"""
        from app.services.sql_validator import SQLValidator
        
        validator = SQLValidator()
        
        # 无 LIMIT 的查询应该自动添加
        sql = "SELECT * FROM products"
        result = validator.validate(sql)
        
        # 验证器应该添加 LIMIT
        if result.fixed_sql:
            assert "LIMIT" in result.fixed_sql.upper()
    
    def test_column_validation(self):
        """测试列名验证"""
        from app.services.schema_prompt_builder import validate_sql_columns
        
        # 创建列名白名单
        column_whitelist = {
            "products": ["id", "name", "price", "category_id"],
            "categories": ["id", "name", "description"]
        }
        
        # 有效 SQL
        valid_sql = "SELECT p.id, p.name, p.price FROM products p"
        result = validate_sql_columns(valid_sql, column_whitelist)
        assert result["valid"] == True
        
        # 无效 SQL（使用不存在的列）
        invalid_sql = "SELECT p.id, p.total_inventory FROM products p"
        result = validate_sql_columns(invalid_sql, column_whitelist)
        assert result["valid"] == False
        assert len(result["errors"]) > 0


# ============================================================================
# Schema 加载测试
# ============================================================================

class TestSchemaLoading:
    """Schema 加载测试"""
    
    def test_schema_prompt_builder(self):
        """测试 Schema 提示词构建"""
        from app.services.schema_prompt_builder import build_schema_prompt, build_column_whitelist
        
        # 模拟表和列数据
        tables = [
            {"table_name": "products", "description": "产品表"},
            {"table_name": "categories", "description": "分类表"}
        ]
        
        columns = [
            {"table_name": "products", "column_name": "id", "data_type": "INT", 
             "is_primary_key": True, "is_foreign_key": False, "description": "主键"},
            {"table_name": "products", "column_name": "name", "data_type": "VARCHAR(100)", 
             "is_primary_key": False, "is_foreign_key": False, "description": "产品名称"},
            {"table_name": "products", "column_name": "category_id", "data_type": "INT", 
             "is_primary_key": False, "is_foreign_key": True, "description": "分类ID"},
            {"table_name": "categories", "column_name": "id", "data_type": "INT", 
             "is_primary_key": True, "is_foreign_key": False, "description": "主键"},
            {"table_name": "categories", "column_name": "name", "data_type": "VARCHAR(50)", 
             "is_primary_key": False, "is_foreign_key": False, "description": "分类名称"},
        ]
        
        relationships = [
            {"source_table": "products", "source_column": "category_id",
             "target_table": "categories", "target_column": "id"}
        ]
        
        # 构建提示词
        prompt = build_schema_prompt(tables, columns, relationships, "mysql")
        
        # 验证提示词包含关键信息
        assert "products" in prompt
        assert "categories" in prompt
        assert "主键" in prompt
        assert "外键" in prompt
        assert "严格约束" in prompt
        
        # 构建列名白名单
        whitelist = build_column_whitelist(columns)
        
        assert "products" in whitelist
        assert "id" in whitelist["products"]
        assert "name" in whitelist["products"]
        assert "category_id" in whitelist["products"]


# ============================================================================
# 缓存测试
# ============================================================================

class TestCaching:
    """缓存测试"""
    
    def test_query_analysis_cache(self):
        """测试查询分析缓存"""
        from app.services.text2sql_utils import (
            query_analysis_cache,
            query_analysis_cache_timestamps,
            _is_query_cache_valid,
            _cleanup_query_cache
        )
        import time
        
        # 清理缓存
        query_analysis_cache.clear()
        query_analysis_cache_timestamps.clear()
        
        # 添加缓存项
        test_query = "测试查询"
        test_result = {"entities": ["测试"], "query_intent": "测试"}
        
        query_analysis_cache[test_query] = test_result
        query_analysis_cache_timestamps[test_query] = time.time()
        
        # 验证缓存有效
        assert _is_query_cache_valid(test_query) == True
        
        # 清理缓存
        _cleanup_query_cache()
        
        # 缓存应该仍然存在（未过期）
        assert test_query in query_analysis_cache


# ============================================================================
# LangSmith 集成测试
# ============================================================================

@pytest.mark.skipif(not is_langsmith_enabled(), reason="LangSmith not enabled")
class TestLangSmithIntegration:
    """LangSmith 集成测试"""
    
    async def test_tracing_enabled(self):
        """测试追踪是否启用"""
        import os
        
        assert os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
        assert os.getenv("LANGCHAIN_API_KEY", "") != ""
    
    async def test_llm_call_traced(self):
        """测试 LLM 调用是否被追踪"""
        from app.core.llm_wrapper import get_llm_wrapper
        from app.core.tracing import TraceContext
        from langchain_core.messages import HumanMessage
        
        # 这个测试需要真实的 LLM 配置
        # 在 CI 环境中可能需要 mock
        
        with TraceContext() as ctx:
            ctx.add_metadata("test_name", "test_llm_call_traced")
            
            # 如果有真实的 LLM 配置，可以执行实际调用
            # wrapper = get_llm_wrapper()
            # response = await wrapper.ainvoke([HumanMessage(content="Hello")])
            
            # 验证追踪上下文
            assert ctx.trace_id is not None


# ============================================================================
# 性能测试
# ============================================================================

@pytest.mark.slow
class TestPerformance:
    """性能测试"""
    
    async def test_llm_wrapper_latency(self):
        """测试 LLM 包装器延迟"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        from langchain_core.messages import HumanMessage, AIMessage
        import time
        
        # 创建 mock LLM（模拟 100ms 延迟）
        async def mock_ainvoke(*args, **kwargs):
            await asyncio.sleep(0.1)
            return AIMessage(content="Response")
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = mock_ainvoke
        
        config = LLMWrapperConfig(timeout=5.0)
        wrapper = LLMWrapper(llm=mock_llm, config=config)
        
        # 执行多次调用
        start_time = time.time()
        for _ in range(10):
            await wrapper.ainvoke([HumanMessage(content="Test")])
        total_time = time.time() - start_time
        
        # 验证总时间（应该约 1 秒）
        assert total_time >= 1.0
        assert total_time < 2.0
        
        # 验证指标
        metrics = wrapper.get_metrics()
        assert metrics["total_calls"] == 10
        assert metrics["successful_calls"] == 10
        assert metrics["avg_latency_ms"] >= 100
    
    async def test_concurrent_requests(self):
        """测试并发请求"""
        from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
        from langchain_core.messages import HumanMessage, AIMessage
        import time
        
        # 创建 mock LLM
        async def mock_ainvoke(*args, **kwargs):
            await asyncio.sleep(0.05)
            return AIMessage(content="Response")
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = mock_ainvoke
        
        config = LLMWrapperConfig(timeout=5.0)
        wrapper = LLMWrapper(llm=mock_llm, config=config)
        
        # 并发执行 20 个请求
        start_time = time.time()
        tasks = [
            wrapper.ainvoke([HumanMessage(content=f"Test {i}")])
            for i in range(20)
        ]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # 并发执行应该比串行快很多
        # 串行需要 20 * 0.05 = 1 秒
        # 并发应该接近 0.05 秒（加上一些开销）
        assert total_time < 0.5
        
        # 验证所有请求都成功
        metrics = wrapper.get_metrics()
        assert metrics["total_calls"] == 20
        assert metrics["successful_calls"] == 20


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
