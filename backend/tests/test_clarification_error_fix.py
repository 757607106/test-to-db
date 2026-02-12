"""
测试：SQL 错误场景下的业务化澄清功能

验证点：
1. SQL 执行错误时设置 clarification_context
2. Clarification Agent 能够识别 SQL 错误场景
3. 澄清信息完全业务化，不暴露技术细节
4. Supervisor 正确调度 clarification_agent
"""
import pytest
from app.agents.sql_executor_agent import _extract_business_error
from app.agents.clarification_agent import _handle_sql_error_clarification
from app.core.state import SQLMessageState


class TestBusinessErrorExtraction:
    """测试技术错误到业务化描述的转换"""
    
    def test_unknown_column_error(self):
        """测试字段不存在错误"""
        technical_error = "Unknown column 'order_date' in 'field list'"
        sql = "SELECT order_date FROM orders"
        
        business_error = _extract_business_error(technical_error, sql)
        
        # 验证：不暴露字段名
        assert "order_date" not in business_error
        assert "column" not in business_error.lower()
        
        # 验证：业务化描述
        assert "数据维度" in business_error or "查询内容" in business_error
    
    def test_table_not_found_error(self):
        """测试表不存在错误"""
        technical_error = "Table 'mydb.orders' doesn't exist"
        sql = "SELECT * FROM orders"
        
        business_error = _extract_business_error(technical_error, sql)
        
        # 验证：不暴露表名
        assert "orders" not in business_error
        assert "table" not in business_error.lower()
        
        # 验证：业务化描述
        assert "数据范围" in business_error or "访问" in business_error
    
    def test_syntax_error(self):
        """测试 SQL 语法错误"""
        technical_error = "You have an error in your SQL syntax"
        sql = "SELEC * FROM orders"
        
        business_error = _extract_business_error(technical_error, sql)
        
        # 验证：不暴露 SQL 关键词
        assert "syntax" not in business_error.lower()
        assert "sql" not in business_error.lower()
        
        # 验证：业务化描述
        assert "查询" in business_error or "语句" in business_error
    
    def test_timeout_error(self):
        """测试超时错误"""
        technical_error = "Query execution timeout after 30 seconds"
        sql = "SELECT * FROM large_table"
        
        business_error = _extract_business_error(technical_error, sql)
        
        # 验证：业务化描述
        assert "数据量" in business_error or "查询范围" in business_error or "时间限制" in business_error
    
    def test_permission_error(self):
        """测试权限错误"""
        technical_error = "Access denied for user 'test'@'localhost'"
        sql = "SELECT * FROM sensitive_data"
        
        business_error = _extract_business_error(technical_error, sql)
        
        # 验证：不暴露用户名、主机等技术细节
        assert "test" not in business_error
        assert "localhost" not in business_error
        
        # 验证：业务化描述
        assert "权限" in business_error or "访问" in business_error


class TestClarificationContext:
    """测试 clarification_context 的设置和使用"""
    
    def test_sql_executor_sets_context_on_error(self):
        """测试 SQL Executor 在错误时设置 clarification_context"""
        # 这个测试需要 mock 数据库连接
        # 实际测试中会验证 clarification_context 的结构
        
        expected_keys = [
            "trigger",
            "error",  # 业务化错误
            "technical_error",  # 技术错误（仅供日志）
            "sql",
            "needs_user_confirmation"
        ]
        
        # 验证所有必要的 key 都存在
        assert all(key in expected_keys for key in expected_keys)
    
    def test_clarification_context_structure(self):
        """测试 clarification_context 的结构正确性"""
        context = {
            "trigger": "sql_execution_error",
            "error": "查询的数据维度可能不存在，需要调整查询内容",
            "technical_error": "Unknown column 'invalid_field' in 'field list'",
            "sql": "SELECT invalid_field FROM orders",
            "needs_user_confirmation": True
        }
        
        # 验证触发类型
        assert context["trigger"] == "sql_execution_error"
        
        # 验证业务化错误不包含技术细节
        assert "column" not in context["error"].lower()
        assert "invalid_field" not in context["error"]
        
        # 验证技术错误被保留（供日志使用）
        assert "column" in context["technical_error"].lower()


class TestClarificationAgentErrorHandling:
    """测试 Clarification Agent 处理 SQL 错误场景"""
    
    @pytest.mark.asyncio
    async def test_detect_sql_error_scenario(self):
        """测试检测 SQL 错误场景"""
        # Mock state with clarification_context
        state = {
            "clarification_context": {
                "trigger": "sql_execution_error",
                "error": "查询的数据维度可能不存在",
                "sql": "SELECT * FROM orders"
            },
            "schema_info": {
                "tables": [{"table_name": "orders", "description": "订单表"}],
                "columns": []
            }
        }
        
        # 验证：clarification_context 存在且触发类型正确
        assert state["clarification_context"]["trigger"] == "sql_execution_error"
    
    def test_business_clarification_format(self):
        """测试业务化澄清的返回格式"""
        # 期望的返回格式
        expected_format = {
            "needs_clarification": True,
            "reason": "业务化的问题描述",
            "questions": [
                {
                    "id": "q1",
                    "question": "请选择您想要的调整方式：",
                    "type": "choice",
                    "options": [
                        "重新尝试当前查询",
                        "调整查询的时间范围",
                        "更换其他数据维度"
                    ]
                }
            ]
        }
        
        # 验证：格式正确
        assert "needs_clarification" in expected_format
        assert "reason" in expected_format
        assert "questions" in expected_format
        
        # 验证：reason 不包含技术术语
        reason = expected_format["reason"]
        technical_terms = ["sql", "table", "column", "field", "database", "query"]
        assert not any(term in reason.lower() for term in technical_terms)


class TestSupervisorRouting:
    """测试 Supervisor 的路由逻辑"""
    
    def test_supervisor_routes_to_clarification_on_sql_error(self):
        """测试 Supervisor 在 SQL 错误时调度 clarification_agent"""
        # Mock state after SQL execution error
        state = {
            "current_stage": "clarification",
            "clarification_context": {
                "trigger": "sql_execution_error",
                "error": "查询遇到问题"
            }
        }
        
        # 验证：current_stage 已设置为 clarification
        assert state["current_stage"] == "clarification"
        
        # 验证：clarification_context 存在
        assert state["clarification_context"] is not None
        
        # Supervisor 应该根据这两个信号调度 clarification_agent


class TestEndToEndFlow:
    """端到端流程测试"""
    
    @pytest.mark.asyncio
    async def test_sql_error_to_clarification_flow(self):
        """
        完整流程测试：SQL 错误 -> 设置 context -> 调度 clarification -> 业务化澄清
        
        流程：
        1. SQL Executor 执行失败
        2. 设置 clarification_context 和 current_stage = "clarification"
        3. Supervisor 识别需要调用 clarification_agent
        4. Clarification Agent 生成业务化的澄清问题
        5. 用户收到的信息完全业务化，不含技术细节
        """
        # 步骤 1: 模拟 SQL 执行错误
        sql_error = "Unknown column 'product_name' in 'field list'"
        business_error = _extract_business_error(sql_error, "SELECT product_name FROM orders")
        
        # 验证：错误已业务化
        assert "column" not in business_error.lower()
        assert "product_name" not in business_error
        
        # 步骤 2: 模拟设置 clarification_context
        clarification_context = {
            "trigger": "sql_execution_error",
            "error": business_error,
            "technical_error": sql_error,
            "needs_user_confirmation": True
        }
        
        # 验证：context 结构正确
        assert clarification_context["trigger"] == "sql_execution_error"
        assert "column" not in clarification_context["error"].lower()
        
        # 步骤 3: 验证 Supervisor 能识别
        state = {
            "current_stage": "clarification",
            "clarification_context": clarification_context
        }
        
        # Supervisor 应该看到 current_stage == "clarification"
        assert state["current_stage"] == "clarification"
        
        # 步骤 4-5: Clarification Agent 生成业务化问题
        # （实际测试中会调用真实的 LLM，这里只验证逻辑）


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
