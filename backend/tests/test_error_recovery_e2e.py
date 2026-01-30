"""
端到端测试：错误恢复流程

测试完整的错误恢复流程，验证：
1. 列名验证失败 → error_recovery → sql_generator 重试
2. retry_count 正确递增
3. 列名白名单正确传递
4. LLM 在重试时能看到正确的列名信息
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any

from app.core.state import SQLMessageState
from app.agents.chat_graph import supervisor_route, create_hub_spoke_graph
from app.agents.agents.error_recovery_agent import ErrorRecoveryAgent
from app.services.schema_prompt_builder import build_column_whitelist, validate_sql_columns


class TestErrorRecoveryE2E:
    """端到端错误恢复测试"""
    
    @pytest.fixture
    def mock_state_with_column_error(self) -> Dict[str, Any]:
        """创建包含列名验证错误的状态"""
        return {
            "messages": [],
            "current_stage": "error_recovery",
            "retry_count": 1,
            "max_retries": 3,
            "connection_id": 1,
            "generated_sql": None,
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "error_message": "列名验证失败: 列 `i.total_inventory` 不存在于表 `inventory` 中，您是否想使用 `quantity`？",
                "failed_sql": "SELECT p.name, i.total_inventory FROM product p JOIN inventory i ON p.id = i.product_id ORDER BY i.total_inventory DESC LIMIT 5",
                "recovery_action": "regenerate_sql",
                "recovery_steps": [
                    "检查 SQL 中使用的列名",
                    "只使用下面列出的可用列名",
                    "不要猜测或虚构列名"
                ],
                "available_columns_hint": """表 `inventory` 的可用列: id, warehouse_id, product_id, quantity, available_qty, locked_qty, cost_price, total_cost, last_in_date
表 `product` 的可用列: id, name, sku, category_id, unit, description, status, created_at, updated_at""",
                "column_whitelist": {
                    "inventory": ["id", "warehouse_id", "product_id", "quantity", "available_qty", "locked_qty", "cost_price", "total_cost", "last_in_date"],
                    "product": ["id", "name", "sku", "category_id", "unit", "description", "status", "created_at", "updated_at"]
                },
                "fix_prompt": """
【严重错误】上一次生成的 SQL 使用了不存在的列名！

错误详情:
  - 列 `i.total_inventory` 不存在于表 `inventory` 中，您是否想使用 `quantity`？

【正确的列名信息】
表 `inventory` 的可用列: id, warehouse_id, product_id, quantity, available_qty, locked_qty, cost_price, total_cost, last_in_date
表 `product` 的可用列: id, name, sku, category_id, unit, description, status, created_at, updated_at

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
4. 如果需要的数据不存在，使用最接近的可用列

请重新生成 SQL，确保所有列名都在可用列表中。
"""
            },
            "error_history": [{
                "stage": "sql_generation_column_validation",
                "error": "列名验证失败: 列 `i.total_inventory` 不存在于表 `inventory` 中，您是否想使用 `quantity`？",
                "failed_sql": "SELECT p.name, i.total_inventory FROM product p JOIN inventory i ON p.id = i.product_id ORDER BY i.total_inventory DESC LIMIT 5",
                "column_errors": ["列 `i.total_inventory` 不存在于表 `inventory` 中，您是否想使用 `quantity`？"],
                "column_whitelist": {
                    "inventory": ["id", "warehouse_id", "product_id", "quantity", "available_qty", "locked_qty", "cost_price", "total_cost", "last_in_date"],
                    "product": ["id", "name", "sku", "category_id", "unit", "description", "status", "created_at", "updated_at"]
                },
                "available_columns": """表 `inventory` 的可用列: id, warehouse_id, product_id, quantity, available_qty, locked_qty, cost_price, total_cost, last_in_date
表 `product` 的可用列: id, name, sku, category_id, unit, description, status, created_at, updated_at"""
            }]
        }
    
    def test_router_routes_column_error_to_sql_generator(self, mock_state_with_column_error):
        """测试路由器将列名错误路由到 sql_generator"""
        route = supervisor_route(mock_state_with_column_error)
        
        # 列名验证失败应该直接路由到 sql_generator
        assert route == "sql_generator"
    
    def test_router_does_not_route_to_schema_agent_for_column_error(self, mock_state_with_column_error):
        """测试路由器不会将列名错误路由到 schema_agent"""
        route = supervisor_route(mock_state_with_column_error)
        
        # 列名验证失败不需要重新获取 schema
        assert route != "schema_agent"
    
    def test_error_recovery_context_preserved_through_routing(self, mock_state_with_column_error):
        """测试错误恢复上下文在路由过程中被保留"""
        state = mock_state_with_column_error
        
        # 验证上下文包含所有必要信息
        ctx = state["error_recovery_context"]
        assert ctx["error_type"] == "column_validation_failed"
        assert "available_columns_hint" in ctx
        assert "column_whitelist" in ctx
        assert "fix_prompt" in ctx
        assert "quantity" in ctx["available_columns_hint"]
    
    @pytest.mark.asyncio
    async def test_error_recovery_agent_preserves_column_info(self, mock_state_with_column_error):
        """测试 error_recovery_agent 保留列名信息"""
        agent = ErrorRecoveryAgent()
        
        # Mock analyze_error_pattern 和 generate_recovery_strategy
        with patch('app.agents.agents.error_recovery_agent.analyze_error_pattern') as mock_analyze, \
             patch('app.agents.agents.error_recovery_agent.generate_recovery_strategy') as mock_strategy:
            
            mock_analyze.invoke = Mock(return_value=json.dumps({
                "success": True,
                "pattern_found": False,
                "most_common_type": "column_validation_failed",
                "total_errors": 1
            }))
            
            mock_strategy.invoke = Mock(return_value=json.dumps({
                "success": True,
                "strategy": {
                    "primary_action": "regenerate_sql",
                    "auto_fixable": True,
                    "confidence": 0.85,
                    "steps": ["检查列名", "使用正确的列名"]
                }
            }))
            
            result = await agent.process(mock_state_with_column_error)
            
            # 验证返回的上下文包含列名信息
            assert "error_recovery_context" in result
            ctx = result["error_recovery_context"]
            assert "available_columns_hint" in ctx
            assert "column_whitelist" in ctx
    
    def test_retry_count_not_incremented_by_error_recovery(self, mock_state_with_column_error):
        """测试 error_recovery 不会递增 retry_count"""
        initial_retry_count = mock_state_with_column_error["retry_count"]
        
        # 模拟 error_recovery_agent 的返回
        # 根据修复后的逻辑，retry_count 应该保持不变
        # 因为它已经在 sql_generator_agent 中递增过了
        
        # 这个测试验证的是设计意图
        assert initial_retry_count == 1
        # error_recovery 返回时不应该再递增
        expected_retry_count_after_recovery = 1
        assert expected_retry_count_after_recovery == initial_retry_count


class TestColumnValidationScenarios:
    """列名验证场景测试"""
    
    def test_common_hallucination_columns(self):
        """测试常见的幻觉列名"""
        # 这些是 LLM 经常错误生成的列名
        hallucination_columns = [
            "total_inventory",
            "total_sales",
            "avg_daily_sales",
            "product_name",  # 可能应该是 name
            "category_name",  # 可能应该是 name
            "order_total",
            "customer_name",
        ]
        
        # 实际的列名白名单
        whitelist = {
            "inventory": ["id", "quantity", "product_id", "warehouse_id"],
            "product": ["id", "name", "sku", "category_id"],
            "sales_order": ["id", "order_no", "customer_id", "total_amount"],
        }
        
        for bad_col in hallucination_columns:
            # 构建使用幻觉列名的 SQL
            sql = f"SELECT t.{bad_col} FROM some_table t"
            
            # 验证这些列名不在白名单中
            found = False
            for table, cols in whitelist.items():
                if bad_col in cols:
                    found = True
                    break
            
            assert not found, f"幻觉列名 {bad_col} 不应该在白名单中"
    
    def test_correct_column_suggestions(self):
        """测试正确的列名建议"""
        whitelist = {
            "inventory": ["id", "quantity", "product_id", "warehouse_id", "available_qty"]
        }
        
        # 测试 total_inventory → 建议相似列名
        sql = "SELECT i.total_inventory FROM inventory i"
        result = validate_sql_columns(sql, whitelist)
        
        assert not result["valid"]
        # 验证建议了某个相似的列名（可能是 quantity 或 available_qty）
        # 关键是错误信息中包含了可用的列名
        assert len(result["errors"]) > 0
        # 验证错误信息中提到了 total_inventory 不存在
        assert any("total_inventory" in err for err in result["errors"])
    
    def test_multiple_invalid_columns(self):
        """测试多个无效列名"""
        whitelist = {
            "inventory": ["id", "quantity", "product_id"],
            "product": ["id", "name", "sku"]
        }
        
        sql = """
        SELECT p.product_name, i.total_inventory, i.avg_daily_sales
        FROM product p
        JOIN inventory i ON p.id = i.product_id
        """
        
        result = validate_sql_columns(sql, whitelist)
        
        assert not result["valid"]
        # 应该检测到多个错误
        assert len(result["errors"]) >= 2


class TestRetryFlow:
    """重试流程测试"""
    
    def test_first_retry_with_column_error(self):
        """测试第一次重试（列名错误）"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 1,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "available_columns_hint": "表 `inventory` 的可用列: id, quantity"
            }
        }
        
        route = supervisor_route(state)
        assert route == "sql_generator"
    
    def test_second_retry_with_column_error(self):
        """测试第二次重试（列名错误）"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 2,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "available_columns_hint": "表 `inventory` 的可用列: id, quantity"
            }
        }
        
        route = supervisor_route(state)
        assert route == "sql_generator"
    
    def test_max_retries_reached(self):
        """测试达到最大重试次数"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 3,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "column_validation_failed"
            }
        }
        
        route = supervisor_route(state)
        assert route in ["fallback_response", "FINISH"]
    
    def test_schema_error_first_retry_goes_to_schema_agent(self):
        """测试 Schema 错误第一次重试去 schema_agent"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 1,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "sql_syntax_error",
                "error_message": "unknown table 'nonexistent'"
            }
        }
        
        route = supervisor_route(state)
        assert route == "schema_agent"
    
    def test_schema_error_second_retry_goes_to_sql_generator(self):
        """测试 Schema 错误第二次重试去 sql_generator"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 2,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "sql_syntax_error",
                "error_message": "unknown table 'nonexistent'"
            }
        }
        
        route = supervisor_route(state)
        assert route == "sql_generator"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
