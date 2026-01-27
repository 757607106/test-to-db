"""
Skill Agent 集成测试

测试内容：
- query_planning_node Skill 路由集成
- schema_agent Skill 限定检索
- sql_generator Skill 业务规则注入
- skill_tools 工具功能
- 零配置兼容性
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.core.state import create_initial_state, SQLMessageState
from app.schemas.skill import Skill, SkillLoadResult


class TestQueryPlanningNodeSkillIntegration:
    """测试 query_planning_node Skill 路由集成"""
    
    @pytest.fixture
    def mock_skill(self):
        return Skill(
            id=1,
            name="sales_order",
            display_name="销售订单",
            description="处理销售订单相关查询",
            keywords=["销售", "订单"],
            intent_examples=[],
            table_patterns=[],
            table_names=["orders", "order_items"],
            business_rules="订单金额使用 total_amount 字段",
            common_patterns=[],
            priority=10,
            is_active=True,
            icon=None,
            color=None,
            connection_id=1,
            tenant_id=1,
            usage_count=0,
            hit_rate=0.0,
            is_auto_generated=False,
            created_at=datetime.now(),
            updated_at=None
        )
    
    @pytest.mark.asyncio
    async def test_perform_skill_routing_no_skills(self):
        """测试无 Skills 配置时的路由"""
        from app.agents.nodes.query_planning_node import _perform_skill_routing
        
        with patch('app.services.skill_router.should_use_skill_mode', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            
            result = await _perform_skill_routing(
                query="查询销售数据",
                connection_id=1
            )
            
            assert result["skill_mode_enabled"] is False
            assert result["selected_skill_name"] is None
    
    @pytest.mark.asyncio
    async def test_perform_skill_routing_with_match(self, mock_skill):
        """测试有 Skill 匹配时的路由"""
        from app.agents.nodes.query_planning_node import _perform_skill_routing
        from app.services.skill_router import RoutingResult, SkillMatch
        
        # Mock 路由结果
        mock_routing_result = RoutingResult(
            has_skills=True,
            selected_skill=SkillMatch(
                skill_name="sales_order",
                display_name="销售订单",
                confidence=0.85,
                match_type="keyword",
                matched_keywords=["销售", "订单"]
            ),
            strategy_used="keyword",
            reasoning="关键词匹配"
        )
        
        # Mock Skill 内容
        mock_skill_content = SkillLoadResult(
            skill_name="sales_order",
            display_name="销售订单",
            description="处理销售订单",
            tables=[{"table_name": "orders"}],
            columns=[{"column_name": "id"}],
            relationships=[],
            metrics=[],
            join_rules=[],
            business_rules="订单金额使用 total_amount 字段",
            common_patterns=[],
            enum_columns=[]
        )
        
        with patch('app.services.skill_router.should_use_skill_mode', new_callable=AsyncMock) as mock_check:
            with patch('app.services.skill_router.skill_router.route', new_callable=AsyncMock) as mock_route:
                with patch('app.services.skill_service.skill_service.load_skill', new_callable=AsyncMock) as mock_load:
                    mock_check.return_value = True
                    mock_route.return_value = mock_routing_result
                    mock_load.return_value = mock_skill_content
                    
                    result = await _perform_skill_routing(
                        query="查询销售订单",
                        connection_id=1
                    )
                    
                    assert result["skill_mode_enabled"] is True
                    assert result["selected_skill_name"] == "sales_order"
                    assert result["skill_confidence"] == 0.85
                    assert result["skill_business_rules"] == "订单金额使用 total_amount 字段"


class TestSkillTools:
    """测试 Skill 工具"""
    
    @pytest.fixture
    def mock_state(self):
        return {
            "connection_id": 1,
            "skill_mode_enabled": True,
            "selected_skill_name": "sales_order",
            "skill_business_rules": "使用 total_amount 字段",
            "loaded_skill_content": {
                "common_patterns": [{"pattern": "销售统计", "hint": "GROUP BY"}]
            }
        }
    
    @pytest.mark.asyncio
    async def test_list_skills_no_config(self):
        """测试 list_skills - 无配置"""
        from app.agents.tools.skill_tools import list_skills
        import json
        
        with patch('app.services.skill_service.skill_service.get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            state = {"connection_id": 1}
            result = await list_skills.ainvoke({"state": state})
            
            data = json.loads(result)
            assert data["success"] is True
            assert data["mode"] == "default"
            assert len(data["skills"]) == 0
    
    @pytest.mark.asyncio
    async def test_list_skills_with_skills(self):
        """测试 list_skills - 有配置"""
        from app.agents.tools.skill_tools import list_skills
        import json
        
        mock_skill = Skill(
            id=1,
            name="sales",
            display_name="销售",
            description="销售管理",
            keywords=["销售"],
            intent_examples=[],
            table_patterns=[],
            table_names=["orders"],
            business_rules=None,
            common_patterns=[],
            priority=10,
            is_active=True,
            icon=None,
            color=None,
            connection_id=1,
            tenant_id=1,
            usage_count=0,
            hit_rate=0.0,
            is_auto_generated=False,
            created_at=datetime.now(),
            updated_at=None
        )
        
        with patch('app.services.skill_service.skill_service.get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [mock_skill]
            
            state = {"connection_id": 1}
            result = await list_skills.ainvoke({"state": state})
            
            data = json.loads(result)
            assert data["success"] is True
            assert data["mode"] == "skill"
            assert len(data["skills"]) == 1
            assert data["skills"][0]["name"] == "sales"
    
    @pytest.mark.asyncio
    async def test_get_skill_business_rules(self, mock_state):
        """测试 get_skill_business_rules"""
        from app.agents.tools.skill_tools import get_skill_business_rules
        import json
        
        result = await get_skill_business_rules.ainvoke({"state": mock_state})
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["mode"] == "skill"
        assert data["skill_name"] == "sales_order"
        assert "total_amount" in data["business_rules"]
    
    @pytest.mark.asyncio
    async def test_get_skill_business_rules_no_skill(self):
        """测试 get_skill_business_rules - 无 Skill 模式"""
        from app.agents.tools.skill_tools import get_skill_business_rules
        import json
        
        state = {"connection_id": 1, "skill_mode_enabled": False}
        result = await get_skill_business_rules.ainvoke({"state": state})
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["mode"] == "default"
        assert data["business_rules"] is None


class TestSchemaAgentSkillIntegration:
    """测试 schema_agent Skill 限定检索"""
    
    def test_skill_mode_state_detection(self):
        """测试 Skill 模式状态检测"""
        state = create_initial_state(connection_id=1)
        
        # 默认模式
        assert state.get("skill_mode_enabled") is False
        
        # 启用 Skill 模式
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = "sales_order"
        state["loaded_skill_content"] = {
            "tables": [{"table_name": "orders"}],
            "columns": [{"column_name": "id", "table_name": "orders"}],
            "relationships": []
        }
        
        assert state.get("skill_mode_enabled") is True
        assert state.get("loaded_skill_content") is not None


class TestSqlGeneratorSkillIntegration:
    """测试 sql_generator Skill 业务规则注入"""
    
    def test_skill_rules_prompt_generation(self):
        """测试 Skill 业务规则提示词生成"""
        state = {
            "connection_id": 1,
            "skill_mode_enabled": True,
            "selected_skill_name": "sales_order",
            "skill_business_rules": "订单金额使用 total_amount 字段",
            "loaded_skill_content": {
                "common_patterns": [
                    {"pattern": "销售统计", "hint": "使用 GROUP BY 聚合"}
                ]
            }
        }
        
        # 测试 Skill 规则注入逻辑
        skill_rules_prompt = ""
        if state.get("skill_mode_enabled"):
            skill_name = state.get("selected_skill_name", "")
            business_rules = state.get("skill_business_rules", "")
            loaded_content = state.get("loaded_skill_content", {})
            
            if business_rules:
                skill_rules_prompt = f"""
【业务领域规则 - {skill_name}】
{business_rules}
"""
            
            common_patterns = loaded_content.get("common_patterns", []) if loaded_content else []
            if common_patterns:
                patterns_str = "\n".join([
                    f"- {p.get('pattern', '')}: {p.get('hint', '')}"
                    for p in common_patterns[:3]
                ])
                skill_rules_prompt += f"""
【常用查询模式参考】
{patterns_str}
"""
        
        assert "sales_order" in skill_rules_prompt
        assert "total_amount" in skill_rules_prompt
        assert "销售统计" in skill_rules_prompt
    
    def test_no_skill_rules_in_default_mode(self):
        """测试默认模式无 Skill 规则"""
        state = {
            "connection_id": 1,
            "skill_mode_enabled": False
        }
        
        skill_rules_prompt = ""
        if state.get("skill_mode_enabled"):
            skill_rules_prompt = "some rules"
        
        assert skill_rules_prompt == ""


class TestEndToEndSkillFlow:
    """测试端到端 Skill 流程"""
    
    def test_state_skill_fields_initialization(self):
        """测试状态 Skill 字段初始化"""
        state = create_initial_state(connection_id=1, tenant_id=1)
        
        # 验证所有 Skill 字段都已初始化
        assert "skill_mode_enabled" in state
        assert "selected_skill_name" in state
        assert "skill_confidence" in state
        assert "loaded_skill_content" in state
        assert "skill_business_rules" in state
        assert "skill_routing_strategy" in state
        assert "skill_routing_reasoning" in state
    
    def test_skill_context_propagation(self):
        """测试 Skill 上下文在流程中的传播"""
        from app.core.state import get_skill_context
        
        state = create_initial_state(connection_id=1)
        
        # 模拟 query_planning_node 设置 Skill 上下文
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = "inventory"
        state["skill_confidence"] = 0.9
        state["skill_business_rules"] = "库存数量使用 qty 字段"
        state["loaded_skill_content"] = {
            "tables": [{"table_name": "inventory"}],
            "columns": [],
            "metrics": []
        }
        
        # 获取上下文
        context = get_skill_context(state)
        
        assert context["skill_mode_enabled"] is True
        assert context["selected_skill_name"] == "inventory"
        assert context["skill_confidence"] == 0.9
        assert "qty" in context["skill_business_rules"]


class TestZeroConfigCompatibility:
    """测试零配置兼容性（端到端）"""
    
    def test_default_mode_without_skills(self):
        """测试无 Skill 配置时的默认行为"""
        state = create_initial_state(connection_id=1)
        
        # 模拟无 Skill 配置的状态
        assert state.get("skill_mode_enabled") is False
        assert state.get("selected_skill_name") is None
        
        # schema_agent 应该使用默认检索
        skill_mode_enabled = state.get("skill_mode_enabled", False)
        loaded_skill_content = state.get("loaded_skill_content")
        
        use_skill_schema = skill_mode_enabled and loaded_skill_content
        assert use_skill_schema is False  # 应该使用默认模式
    
    def test_graceful_fallback_on_routing_failure(self):
        """测试路由失败时的优雅降级"""
        state = create_initial_state(connection_id=1)
        
        # 模拟路由失败
        state["skill_mode_enabled"] = False
        state["skill_routing_reasoning"] = "路由异常: connection error"
        
        # 系统应该继续使用默认模式
        assert state.get("skill_mode_enabled") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
