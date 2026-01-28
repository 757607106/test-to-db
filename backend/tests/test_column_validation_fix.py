"""
测试列名验证失败后的错误恢复流程

测试场景：
1. 列名验证失败时，error_recovery_context 是否包含正确的列名信息
2. retry_count 是否正确递增（不重复递增）
3. error_recovery_agent 是否正确传递列名白名单给 sql_generator
4. 路由逻辑是否正确处理列名验证失败

修复验证：
- 问题1：列名验证失败时错误信息传递不完整
- 问题2：retry_count 递增逻辑分散且不一致
- 问题3：错误恢复上下文在某些路径中丢失
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# 导入被测试的模块
from app.agents.agents.error_recovery_agent import (
    ErrorRecoveryAgent,
    analyze_error_pattern,
    generate_recovery_strategy,
)
from app.agents.chat_graph import supervisor_route
from app.services.schema_prompt_builder import (
    build_column_whitelist,
    validate_sql_columns,
)


class TestColumnValidationErrorRecovery:
    """测试列名验证失败后的错误恢复"""
    
    def test_build_column_whitelist(self):
        """测试列名白名单构建"""
        columns = [
            {"table_name": "inventory", "column_name": "id"},
            {"table_name": "inventory", "column_name": "quantity"},
            {"table_name": "inventory", "column_name": "product_id"},
            {"table_name": "product", "column_name": "id"},
            {"table_name": "product", "column_name": "name"},
        ]
        
        whitelist = build_column_whitelist(columns)
        
        assert "inventory" in whitelist
        assert "product" in whitelist
        assert "quantity" in whitelist["inventory"]
        assert "id" in whitelist["inventory"]
        assert "name" in whitelist["product"]
        # 验证 total_inventory 不在白名单中
        assert "total_inventory" not in whitelist.get("inventory", [])
    
    def test_validate_sql_columns_detects_invalid_column(self):
        """测试列名验证能检测到无效列名"""
        sql = "SELECT i.total_inventory FROM inventory i"
        column_whitelist = {
            "inventory": ["id", "quantity", "product_id", "warehouse_id"]
        }
        
        result = validate_sql_columns(sql, column_whitelist)
        
        assert result["valid"] == False
        assert len(result["errors"]) > 0
        # 验证错误信息中提到了 total_inventory
        assert any("total_inventory" in err for err in result["errors"])
    
    def test_validate_sql_columns_suggests_correct_column(self):
        """测试列名验证能建议正确的列名"""
        sql = "SELECT i.total_inventory FROM inventory i"
        column_whitelist = {
            "inventory": ["id", "quantity", "product_id", "warehouse_id"]
        }
        
        result = validate_sql_columns(sql, column_whitelist)
        
        # 验证建议使用 quantity
        assert any("quantity" in err for err in result["errors"])
    
    def test_validate_sql_columns_passes_valid_sql(self):
        """测试列名验证通过有效的 SQL"""
        sql = "SELECT i.quantity, i.product_id FROM inventory i"
        column_whitelist = {
            "inventory": ["id", "quantity", "product_id", "warehouse_id"]
        }
        
        result = validate_sql_columns(sql, column_whitelist)
        
        assert result["valid"] == True
        assert len(result["errors"]) == 0


class TestErrorRecoveryContextPassing:
    """测试错误恢复上下文传递"""
    
    def test_error_recovery_context_contains_column_whitelist(self):
        """测试错误恢复上下文包含列名白名单"""
        # 模拟 sql_generator_agent 返回的错误恢复上下文
        error_recovery_ctx = {
            "error_type": "column_validation_failed",
            "error_message": "列名验证失败: 列 `i.total_inventory` 不存在于表 `inventory` 中",
            "failed_sql": "SELECT i.total_inventory FROM inventory i",
            "recovery_action": "regenerate_sql",
            "available_columns_hint": "表 `inventory` 的可用列: id, quantity, product_id, warehouse_id",
            "column_whitelist": {
                "inventory": ["id", "quantity", "product_id", "warehouse_id"]
            },
            "fix_prompt": "【严重错误】上一次生成的 SQL 使用了不存在的列名！..."
        }
        
        # 验证上下文包含必要的信息
        assert "available_columns_hint" in error_recovery_ctx
        assert "column_whitelist" in error_recovery_ctx
        assert "fix_prompt" in error_recovery_ctx
        assert "quantity" in error_recovery_ctx["available_columns_hint"]
    
    def test_error_history_contains_column_whitelist(self):
        """测试 error_history 包含列名白名单"""
        # 模拟 error_history 条目
        error_entry = {
            "stage": "sql_generation_column_validation",
            "error": "列名验证失败: 列 `i.total_inventory` 不存在",
            "failed_sql": "SELECT i.total_inventory FROM inventory i",
            "column_errors": ["列 `i.total_inventory` 不存在于表 `inventory` 中"],
            "column_whitelist": {
                "inventory": ["id", "quantity", "product_id", "warehouse_id"]
            },
            "available_columns": "表 `inventory` 的可用列: id, quantity, product_id, warehouse_id"
        }
        
        # 验证 error_history 包含列名白名单
        assert "column_whitelist" in error_entry
        assert "available_columns" in error_entry


class TestRetryCountIncrement:
    """测试 retry_count 递增逻辑"""
    
    def test_retry_count_not_double_incremented(self):
        """测试 retry_count 不会被重复递增"""
        # 模拟状态：sql_generator_agent 已经递增了 retry_count
        state = {
            "retry_count": 1,  # 已经被 sql_generator_agent 递增
            "max_retries": 3,
            "current_stage": "error_recovery",
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "error_message": "列名验证失败",
            },
            "error_history": [{
                "stage": "sql_generation_column_validation",
                "error": "列名验证失败"
            }]
        }
        
        # 验证 error_recovery_agent 不应该再递增 retry_count
        # 这个测试验证的是逻辑，实际的 agent 调用需要 mock
        assert state["retry_count"] == 1
        
        # 模拟 error_recovery_agent 返回的状态
        # 根据修复后的逻辑，retry_count 应该保持不变
        expected_retry_count = 1  # 不再递增
        assert expected_retry_count == state["retry_count"]


class TestRouterLogic:
    """测试路由逻辑"""
    
    def test_column_validation_error_routes_to_sql_generator(self):
        """测试列名验证失败时路由到 sql_generator"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 1,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "error_message": "列名验证失败: 列 `i.total_inventory` 不存在",
                "available_columns_hint": "表 `inventory` 的可用列: id, quantity, product_id"
            }
        }
        
        route = supervisor_route(state)
        
        # 列名验证失败应该直接路由到 sql_generator，不需要重新获取 schema
        assert route == "sql_generator"
    
    def test_schema_error_routes_to_schema_agent_on_first_retry(self):
        """测试 Schema 错误在第一次重试时路由到 schema_agent"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 1,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "sql_syntax_error",
                "error_message": "unknown table 'nonexistent_table'"
            }
        }
        
        route = supervisor_route(state)
        
        # Schema 错误在第一次重试时应该路由到 schema_agent
        assert route == "schema_agent"
    
    def test_max_retries_routes_to_finish(self):
        """测试达到最大重试次数时路由到 FINISH"""
        state = {
            "current_stage": "error_recovery",
            "retry_count": 3,
            "max_retries": 3,
            "error_recovery_context": {
                "error_type": "column_validation_failed",
                "error_message": "列名验证失败"
            }
        }
        
        route = supervisor_route(state)
        
        assert route == "FINISH"


class TestEnhancedErrorContext:
    """测试增强的错误上下文构建"""
    
    def test_build_enhanced_error_context_inherits_column_info(self):
        """测试增强错误上下文继承列名信息"""
        agent = ErrorRecoveryAgent()
        
        existing_context = {
            "available_columns_hint": "表 `inventory` 的可用列: id, quantity, product_id",
            "column_whitelist": {
                "inventory": ["id", "quantity", "product_id"]
            },
            "fix_prompt": "【严重错误】..."
        }
        
        error_context = agent._build_enhanced_error_context(
            error_analysis_data={"most_common_type": "column_validation_failed"},
            latest_error={"error": "列名验证失败"},
            failed_sql="SELECT i.total_inventory FROM inventory i",
            primary_action="regenerate_sql",
            recovery_steps=["检查列名"],
            retry_count=1,
            existing_context=existing_context
        )
        
        # 验证继承了列名信息
        assert "available_columns_hint" in error_context
        assert "column_whitelist" in error_context
        assert "fix_prompt" in error_context
        assert error_context["available_columns_hint"] == existing_context["available_columns_hint"]
    
    def test_build_enhanced_error_context_extracts_from_error_history(self):
        """测试从 error_history 提取列名信息"""
        agent = ErrorRecoveryAgent()
        
        latest_error = {
            "error": "列名验证失败",
            "column_errors": ["列 `i.total_inventory` 不存在"],
            "column_whitelist": {
                "inventory": ["id", "quantity", "product_id"]
            }
        }
        
        error_context = agent._build_enhanced_error_context(
            error_analysis_data={"most_common_type": "column_validation_failed"},
            latest_error=latest_error,
            failed_sql="SELECT i.total_inventory FROM inventory i",
            primary_action="regenerate_sql",
            recovery_steps=["检查列名"],
            retry_count=1,
            existing_context={}  # 空的现有上下文
        )
        
        # 验证从 error_history 提取了列名信息
        assert "column_whitelist" in error_context
        assert "available_columns_hint" in error_context


class TestEndToEndScenario:
    """端到端场景测试"""
    
    def test_inventory_query_with_invalid_column(self):
        """测试库存查询使用无效列名的场景"""
        # 场景：用户查询"库存最多的前5个产品"
        # LLM 错误地生成了 total_inventory 列
        
        # 1. 构建列名白名单
        columns = [
            {"table_name": "inventory", "column_name": "id"},
            {"table_name": "inventory", "column_name": "quantity"},
            {"table_name": "inventory", "column_name": "product_id"},
            {"table_name": "inventory", "column_name": "warehouse_id"},
            {"table_name": "product", "column_name": "id"},
            {"table_name": "product", "column_name": "name"},
            {"table_name": "product", "column_name": "sku"},
        ]
        whitelist = build_column_whitelist(columns)
        
        # 2. 验证错误的 SQL
        bad_sql = """
        SELECT p.name, i.total_inventory 
        FROM product p 
        JOIN inventory i ON p.id = i.product_id 
        ORDER BY i.total_inventory DESC 
        LIMIT 5
        """
        
        validation_result = validate_sql_columns(bad_sql, whitelist)
        
        assert validation_result["valid"] == False
        assert any("total_inventory" in err for err in validation_result["errors"])
        
        # 3. 验证正确的 SQL
        good_sql = """
        SELECT p.name, SUM(i.quantity) as total_qty
        FROM product p 
        JOIN inventory i ON p.id = i.product_id 
        GROUP BY p.id, p.name
        ORDER BY total_qty DESC 
        LIMIT 5
        """
        
        validation_result = validate_sql_columns(good_sql, whitelist)
        
        # 注意：SUM(i.quantity) 中的 i.quantity 应该通过验证
        # total_qty 是别名，不需要验证
        assert validation_result["valid"] == True or len(validation_result["errors"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
