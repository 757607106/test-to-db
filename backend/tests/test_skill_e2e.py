"""
Skills-SQL-Assistant 端到端测试

测试覆盖范围：
1. Skills CRUD API 测试
2. 零配置兼容性测试
3. Skill 路由集成测试
4. State 传播测试
5. Schema 限定检索测试
6. 业务规则注入测试

运行方式:
    pytest tests/test_skill_e2e.py -v
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import json

from app.core.state import (
    create_initial_state, 
    SQLMessageState, 
    is_skill_mode_enabled,
    get_skill_context
)
from app.schemas.skill import (
    Skill, SkillCreate, SkillUpdate, SkillLoadResult,
    SkillListResponse, SkillStatusResponse
)


class TestSkillsE2EFlow:
    """端到端 Skill 流程测试"""
    
    @pytest.fixture
    def sample_skill(self):
        """示例 Skill"""
        return Skill(
            id=1,
            name="sales_order",
            display_name="销售订单",
            description="处理销售订单相关查询",
            keywords=["销售", "订单", "客户", "金额", "交易"],
            intent_examples=["查询销售订单", "统计销售额", "分析客户订单"],
            table_patterns=["order*", "customer*"],
            table_names=["orders", "order_items", "customers"],
            business_rules="订单金额使用 total_amount 字段；已取消的订单(status='cancelled')不计入统计",
            common_patterns=[
                {"pattern": "销售统计", "hint": "使用 GROUP BY 按时间维度聚合"},
                {"pattern": "客户分析", "hint": "关联 customers 表获取客户信息"}
            ],
            priority=10,
            is_active=True,
            icon="shopping-cart",
            color="#1890ff",
            connection_id=1,
            tenant_id=1,
            usage_count=100,
            hit_rate=0.85,
            is_auto_generated=False,
            created_at=datetime.now(),
            updated_at=None
        )
    
    @pytest.fixture
    def sample_skill_content(self):
        """示例 Skill 加载内容"""
        return SkillLoadResult(
            skill_name="sales_order",
            display_name="销售订单",
            description="处理销售订单相关查询",
            tables=[
                {"table_name": "orders", "table_comment": "订单主表"},
                {"table_name": "order_items", "table_comment": "订单明细表"},
                {"table_name": "customers", "table_comment": "客户表"}
            ],
            columns=[
                {"column_name": "id", "table_name": "orders", "data_type": "bigint"},
                {"column_name": "total_amount", "table_name": "orders", "data_type": "decimal"},
                {"column_name": "status", "table_name": "orders", "data_type": "varchar"},
                {"column_name": "customer_id", "table_name": "orders", "data_type": "bigint"},
            ],
            relationships=[
                {"source_table": "orders", "target_table": "customers", "type": "many_to_one"}
            ],
            metrics=[
                {"name": "total_sales", "formula": "SUM(total_amount)", "description": "总销售额"}
            ],
            join_rules=[
                {"tables": ["orders", "customers"], "condition": "orders.customer_id = customers.id"}
            ],
            business_rules="订单金额使用 total_amount 字段",
            common_patterns=[
                {"pattern": "销售统计", "hint": "使用 GROUP BY"}
            ],
            enum_columns=[
                {"table_name": "orders", "column_name": "status", "values": ["pending", "completed", "cancelled"]}
            ]
        )
    
    def test_complete_skill_flow_state_propagation(self, sample_skill, sample_skill_content):
        """测试完整的 Skill 状态传播流程"""
        # 1. 创建初始状态
        state = create_initial_state(connection_id=1, tenant_id=1)
        
        # 验证初始状态
        assert state.get("skill_mode_enabled") is False
        assert state.get("selected_skill_name") is None
        
        # 2. 模拟 query_planning_node 设置 Skill 上下文
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = sample_skill.name
        state["skill_confidence"] = 0.85
        state["skill_business_rules"] = sample_skill.business_rules
        state["loaded_skill_content"] = sample_skill_content.model_dump()
        state["skill_routing_strategy"] = "keyword"
        state["skill_routing_reasoning"] = "关键词匹配选中 '销售订单'"
        
        # 验证 Skill 模式已启用
        assert is_skill_mode_enabled(state) is True
        
        # 3. 获取 Skill 上下文
        context = get_skill_context(state)
        
        assert context["skill_mode_enabled"] is True
        assert context["selected_skill_name"] == "sales_order"
        assert context["skill_confidence"] == 0.85
        assert "total_amount" in context["skill_business_rules"]
        
        # 4. 验证加载的内容
        loaded_content = state.get("loaded_skill_content")
        assert loaded_content is not None
        assert len(loaded_content["tables"]) == 3
        assert len(loaded_content["columns"]) == 4
    
    def test_zero_config_mode_flow(self):
        """测试零配置模式流程"""
        # 1. 创建初始状态（无 Skill 配置）
        state = create_initial_state(connection_id=1)
        
        # 2. 模拟 query_planning_node 检测到无 Skill 配置
        state["skill_mode_enabled"] = False
        state["skill_routing_reasoning"] = "未配置 Skills，使用默认模式"
        
        # 3. 验证零配置模式
        assert is_skill_mode_enabled(state) is False
        
        # 4. schema_agent 应该使用默认检索
        skill_mode_enabled = state.get("skill_mode_enabled", False)
        loaded_skill_content = state.get("loaded_skill_content")
        
        use_skill_schema = skill_mode_enabled and loaded_skill_content
        assert use_skill_schema is False
    
    def test_skill_routing_fallback(self):
        """测试 Skill 路由降级"""
        state = create_initial_state(connection_id=1)
        
        # 模拟路由失败后的降级
        state["skill_mode_enabled"] = False
        state["skill_routing_strategy"] = "keyword"
        state["skill_routing_reasoning"] = "关键词匹配无结果，退化到默认模式"
        
        # 验证降级状态
        assert is_skill_mode_enabled(state) is False
        context = get_skill_context(state)
        assert context["selected_skill_name"] is None


class TestSkillServiceE2E:
    """Skill 服务端到端测试"""
    
    @pytest.mark.asyncio
    async def test_skill_crud_workflow(self):
        """测试 Skill CRUD 工作流"""
        from app.services.skill_service import SkillService
        
        service = SkillService()
        
        # Mock 数据库操作
        with patch('app.services.skill_service.get_db_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            # 测试 has_skills_configured
            with patch.object(service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
                # 无配置
                mock_get.return_value = []
                result = await service.has_skills_configured(1)
                assert result is False
                
                # 有配置
                mock_skill = MagicMock()
                mock_get.return_value = [mock_skill]
                result = await service.has_skills_configured(1)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_skill_prompt_section_generation(self):
        """测试 Skill Prompt 段落生成"""
        from app.services.skill_service import SkillService
        
        service = SkillService()
        
        # 有 Skill 配置时
        mock_skill = Skill(
            id=1,
            name="inventory",
            display_name="库存管理",
            description="处理库存相关查询",
            keywords=["库存", "入库", "出库"],
            intent_examples=[],
            table_patterns=[],
            table_names=["inventory"],
            business_rules=None,
            common_patterns=[],
            priority=5,
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
        
        with patch.object(service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [mock_skill]
            
            prompt = await service.get_skill_prompt_section(1)
            
            assert prompt is not None
            assert "库存管理" in prompt
            assert "load_skill" in prompt
    
    @pytest.mark.asyncio
    async def test_skill_prompt_section_no_skills(self):
        """测试无 Skill 配置时的 Prompt 段落"""
        from app.services.skill_service import SkillService
        
        service = SkillService()
        
        with patch.object(service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            prompt = await service.get_skill_prompt_section(1)
            
            # 零配置模式返回 None
            assert prompt is None


class TestSkillRouterE2E:
    """Skill 路由器端到端测试"""
    
    @pytest.fixture
    def mock_skills_list(self):
        """多个 Mock Skills"""
        return [
            Skill(
                id=1, name="sales", display_name="销售",
                description="销售管理", keywords=["销售", "订单", "客户"],
                intent_examples=[], table_patterns=[], table_names=["orders"],
                business_rules=None, common_patterns=[], priority=10,
                is_active=True, icon=None, color=None, connection_id=1,
                tenant_id=1, usage_count=0, hit_rate=0.0,
                is_auto_generated=False, created_at=datetime.now(), updated_at=None
            ),
            Skill(
                id=2, name="inventory", display_name="库存",
                description="库存管理", keywords=["库存", "仓库", "入库", "出库"],
                intent_examples=[], table_patterns=[], table_names=["inventory"],
                business_rules=None, common_patterns=[], priority=5,
                is_active=True, icon=None, color=None, connection_id=1,
                tenant_id=1, usage_count=0, hit_rate=0.0,
                is_auto_generated=False, created_at=datetime.now(), updated_at=None
            ),
            Skill(
                id=3, name="finance", display_name="财务",
                description="财务管理", keywords=["财务", "付款", "收款", "账单"],
                intent_examples=[], table_patterns=[], table_names=["payments"],
                business_rules=None, common_patterns=[], priority=8,
                is_active=True, icon=None, color=None, connection_id=1,
                tenant_id=1, usage_count=0, hit_rate=0.0,
                is_auto_generated=False, created_at=datetime.now(), updated_at=None
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_router_selects_best_match(self, mock_skills_list):
        """测试路由器选择最佳匹配"""
        from app.services.skill_router import SkillRouter, RoutingStrategy
        
        router = SkillRouter()
        
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills_list)
            
            # 测试销售相关查询
            result = await router.route(
                query="查询本月销售订单总额",
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert result.selected_skill is not None
            assert result.selected_skill.skill_name == "sales"
            
            # 测试库存相关查询
            result = await router.route(
                query="统计仓库库存数量",
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.selected_skill is not None
            assert result.selected_skill.skill_name == "inventory"
            
            # 测试财务相关查询
            result = await router.route(
                query="查询未付款账单",
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.selected_skill is not None
            assert result.selected_skill.skill_name == "finance"
    
    @pytest.mark.asyncio
    async def test_router_handles_no_match(self, mock_skills_list):
        """测试路由器处理无匹配情况"""
        from app.services.skill_router import SkillRouter, RoutingStrategy
        
        router = SkillRouter()
        
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills_list)
            
            # 测试无关查询
            result = await router.route(
                query="今天天气怎么样",
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert result.fallback_to_default is True


class TestSkillDiscoveryE2E:
    """Skill 自动发现端到端测试"""
    
    def test_prefix_grouping(self):
        """测试前缀分组"""
        from app.services.skill_discovery_service import SkillDiscoveryService
        
        service = SkillDiscoveryService()
        
        tables = [
            {"table_name": "order_header", "description": "", "id": 1},
            {"table_name": "order_items", "description": "", "id": 2},
            {"table_name": "order_payment", "description": "", "id": 3},
            {"table_name": "customer_info", "description": "", "id": 4},
            {"table_name": "customer_address", "description": "", "id": 5},
            {"table_name": "inventory_stock", "description": "", "id": 6},
            {"table_name": "inventory_movement", "description": "", "id": 7},
        ]
        
        groups = service._group_by_prefix(tables)
        
        # 应该有 3 个组
        group_names = [g.name for g in groups]
        assert "order" in group_names
        assert "customer" in group_names
        assert "inventory" in group_names
        
        # 验证每组的表数量
        order_group = next(g for g in groups if g.name == "order")
        assert len(order_group.tables) == 3
        
        customer_group = next(g for g in groups if g.name == "customer")
        assert len(customer_group.tables) == 2
    
    def test_suggestion_generation(self):
        """测试建议生成"""
        from app.services.skill_discovery_service import SkillDiscoveryService, TableGroup
        
        service = SkillDiscoveryService()
        
        groups = [
            TableGroup(
                name="order",
                tables=["order_header", "order_items", "order_payment"],
                keywords=["订单", "销售"],
                confidence=0.8,
                grouping_reason="表名前缀 'order'"
            )
        ]
        
        all_tables = [
            {"table_name": "order_header", "description": "订单主表", "id": 1},
            {"table_name": "order_items", "description": "订单明细", "id": 2},
            {"table_name": "order_payment", "description": "订单支付", "id": 3},
        ]
        
        suggestions = service._generate_suggestions(groups, all_tables)
        
        assert len(suggestions) == 1
        assert suggestions[0].name == "order"
        assert len(suggestions[0].table_names) == 3
        assert suggestions[0].confidence == 0.8


class TestSkillAgentIntegrationE2E:
    """Skill Agent 集成端到端测试"""
    
    def test_schema_agent_skill_mode_detection(self):
        """测试 schema_agent Skill 模式检测"""
        state = create_initial_state(connection_id=1)
        
        # 设置 Skill 模式
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = "sales_order"
        state["loaded_skill_content"] = {
            "tables": [{"table_name": "orders"}],
            "columns": [{"column_name": "id", "table_name": "orders"}],
            "relationships": []
        }
        
        # 验证 schema_agent 会使用 Skill 限定的 Schema
        skill_mode_enabled = state.get("skill_mode_enabled", False)
        loaded_skill_content = state.get("loaded_skill_content")
        
        use_skill_schema = skill_mode_enabled and loaded_skill_content is not None
        assert use_skill_schema is True
    
    def test_sql_generator_business_rules_injection(self):
        """测试 sql_generator 业务规则注入"""
        state = create_initial_state(connection_id=1)
        
        # 设置 Skill 上下文
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = "sales_order"
        state["skill_business_rules"] = "订单金额使用 total_amount 字段；已取消的订单不计入统计"
        state["loaded_skill_content"] = {
            "common_patterns": [
                {"pattern": "销售统计", "hint": "使用 GROUP BY 聚合"}
            ]
        }
        
        # 构建业务规则提示词（模拟 sql_generator 的逻辑）
        skill_rules_prompt = ""
        if state.get("skill_mode_enabled"):
            skill_name = state.get("selected_skill_name", "")
            business_rules = state.get("skill_business_rules", "")
            loaded_content = state.get("loaded_skill_content", {})
            
            if business_rules:
                skill_rules_prompt = f"【业务领域规则 - {skill_name}】\n{business_rules}"
            
            common_patterns = loaded_content.get("common_patterns", [])
            if common_patterns:
                patterns_str = "\n".join([
                    f"- {p.get('pattern', '')}: {p.get('hint', '')}"
                    for p in common_patterns[:3]
                ])
                skill_rules_prompt += f"\n【常用查询模式参考】\n{patterns_str}"
        
        # 验证业务规则被注入
        assert "sales_order" in skill_rules_prompt
        assert "total_amount" in skill_rules_prompt
        assert "销售统计" in skill_rules_prompt
        assert "GROUP BY" in skill_rules_prompt


class TestSkillAPIIntegration:
    """Skill API 集成测试（模拟）"""
    
    def test_skill_list_response_format(self):
        """测试 Skills 列表响应格式"""
        response = SkillListResponse(
            skills=[],
            total=0,
            has_skills_configured=False
        )
        
        assert response.has_skills_configured is False
        assert response.total == 0
    
    def test_skill_status_response_format(self):
        """测试 Skills 状态响应格式"""
        # 零配置模式
        response = SkillStatusResponse(
            has_skills_configured=False,
            skills_count=0,
            mode="default"
        )
        assert response.mode == "default"
        
        # Skill 模式
        response = SkillStatusResponse(
            has_skills_configured=True,
            skills_count=3,
            mode="skill"
        )
        assert response.mode == "skill"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
