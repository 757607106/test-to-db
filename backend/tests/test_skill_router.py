"""
Skill Router 单元测试

测试内容：
- 关键词路由匹配
- 零配置兼容性
- 路由策略选择
- State 集成
- 发现服务基础功能
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.services.skill_router import (
    SkillRouter, RoutingStrategy, SkillMatch, RoutingResult,
    get_skill_routing_context, should_use_skill_mode
)
from app.services.skill_discovery_service import (
    SkillDiscoveryService, TableGroup, DiscoveryResult
)
from app.schemas.skill import Skill, SkillSuggestion
from app.core.state import (
    create_initial_state, is_skill_mode_enabled, get_skill_context
)


class TestSkillRouter:
    """测试 SkillRouter"""
    
    @pytest.fixture
    def router(self):
        return SkillRouter()
    
    @pytest.fixture
    def mock_skills(self):
        """创建 Mock Skills 列表"""
        return [
            Skill(
                id=1,
                name="sales_order",
                display_name="销售订单",
                description="处理销售订单相关查询",
                keywords=["销售", "订单", "客户", "金额"],
                intent_examples=["查询销售订单", "统计销售额"],
                table_patterns=[],
                table_names=["orders", "order_items", "customers"],
                business_rules="订单金额使用 total_amount 字段",
                common_patterns=[],
                priority=10,
                is_active=True,
                icon="shopping-cart",
                color="#1890ff",
                connection_id=1,
                tenant_id=1,
                usage_count=0,
                hit_rate=0.0,
                is_auto_generated=False,
                created_at=datetime.now(),
                updated_at=None
            ),
            Skill(
                id=2,
                name="inventory",
                display_name="库存管理",
                description="处理库存相关查询",
                keywords=["库存", "入库", "出库", "盘点", "仓库"],
                intent_examples=["查询库存", "库存盘点"],
                table_patterns=[],
                table_names=["inventory", "stock_movement", "warehouses"],
                business_rules=None,
                common_patterns=[],
                priority=5,
                is_active=True,
                icon="database",
                color="#52c41a",
                connection_id=1,
                tenant_id=1,
                usage_count=0,
                hit_rate=0.0,
                is_auto_generated=False,
                created_at=datetime.now(),
                updated_at=None
            )
        ]
    
    @pytest.mark.asyncio
    async def test_route_no_skills_configured(self, router):
        """测试无 Skill 配置时的路由（零配置兼容）"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=False)
            
            result = await router.route("查询销售订单", connection_id=1)
            
            assert result.has_skills is False
            assert result.fallback_to_default is True
            assert "未配置" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_route_keyword_match_single(self, router, mock_skills):
        """测试关键词匹配 - 单个 Skill"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills)
            
            result = await router.route(
                "查询销售订单总金额", 
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert result.selected_skill is not None
            assert result.selected_skill.skill_name == "sales_order"
            assert "销售" in result.selected_skill.matched_keywords or "订单" in result.selected_skill.matched_keywords
    
    @pytest.mark.asyncio
    async def test_route_keyword_match_inventory(self, router, mock_skills):
        """测试关键词匹配 - 库存领域"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills)
            
            result = await router.route(
                "查询仓库库存盘点情况", 
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert result.selected_skill is not None
            assert result.selected_skill.skill_name == "inventory"
    
    @pytest.mark.asyncio
    async def test_route_keyword_no_match(self, router, mock_skills):
        """测试关键词匹配 - 无匹配"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills)
            
            result = await router.route(
                "天气怎么样", 
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert result.fallback_to_default is True
            assert "无结果" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_route_multiple_matches(self, router, mock_skills):
        """测试多个 Skill 匹配时选择置信度最高的"""
        # 添加一个同时包含两个领域关键词的 Skill
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            mock_service.get_skills_by_connection = AsyncMock(return_value=mock_skills)
            
            # 使用同时包含两个领域关键词的查询
            result = await router.route(
                "销售订单的库存变动", 
                connection_id=1,
                strategy=RoutingStrategy.KEYWORD
            )
            
            assert result.has_skills is True
            assert len(result.all_matches) >= 1
            # 应该返回匹配度最高的
            assert result.selected_skill is not None
    
    def test_simplify_table_name(self, router):
        """测试表名简化"""
        assert router._simplify_table_name("t_order") == "order"
        assert router._simplify_table_name("tb_customer") == "customer"
        assert router._simplify_table_name("sys_config") == "config"
        assert router._simplify_table_name("inventory_item") == "inventoryitem"
    
    def test_simple_similarity(self, router):
        """测试简单相似度计算"""
        sim1 = router._simple_similarity("查询 销售 订单", "销售 订单 统计")
        assert sim1 > 0.3
        
        sim2 = router._simple_similarity("abc def", "xyz uvw")
        assert sim2 == 0.0


class TestRoutingResult:
    """测试 RoutingResult 数据结构"""
    
    def test_routing_result_no_skills(self):
        """测试无 Skill 的结果"""
        result = RoutingResult(
            has_skills=False,
            fallback_to_default=True,
            reasoning="未配置 Skills"
        )
        assert result.selected_skill is None
        assert len(result.all_matches) == 0
    
    def test_routing_result_with_match(self):
        """测试有匹配的结果"""
        match = SkillMatch(
            skill_name="sales",
            display_name="销售",
            confidence=0.8,
            match_type="keyword",
            matched_keywords=["销售", "订单"]
        )
        
        result = RoutingResult(
            has_skills=True,
            selected_skill=match,
            all_matches=[match],
            strategy_used="keyword"
        )
        
        assert result.selected_skill.confidence == 0.8
        assert "销售" in result.selected_skill.matched_keywords


class TestSkillDiscoveryService:
    """测试 SkillDiscoveryService"""
    
    @pytest.fixture
    def discovery_service(self):
        return SkillDiscoveryService()
    
    def test_extract_prefix(self, discovery_service):
        """测试前缀提取"""
        assert discovery_service._extract_prefix("order_items") == "order"
        assert discovery_service._extract_prefix("t_sales_order") == "sales"
        assert discovery_service._extract_prefix("inventory_movement") == "inventory"
        assert discovery_service._extract_prefix("user") is None  # 没有下划线
    
    def test_generate_skill_name(self, discovery_service):
        """测试 Skill 名称生成"""
        assert discovery_service._generate_skill_name("order") == "order"
        assert discovery_service._generate_skill_name("Sales-Order") == "sales_order"
        assert discovery_service._generate_skill_name("123test") == "skill_123test"
    
    def test_generate_display_name(self, discovery_service):
        """测试显示名称生成"""
        name = discovery_service._generate_display_name("order", ["订单", "销售"])
        assert "订单" in name
        
        name2 = discovery_service._generate_display_name("inventory", [])
        assert "Inventory" in name2 or "业务" in name2
    
    def test_group_by_prefix(self, discovery_service):
        """测试基于前缀的分组"""
        tables = [
            {"table_name": "order_header", "description": "", "id": 1},
            {"table_name": "order_items", "description": "", "id": 2},
            {"table_name": "order_payment", "description": "", "id": 3},
            {"table_name": "inventory_stock", "description": "", "id": 4},
            {"table_name": "inventory_movement", "description": "", "id": 5},
            {"table_name": "single_table", "description": "", "id": 6},
        ]
        
        groups = discovery_service._group_by_prefix(tables)
        
        # 应该有 order 和 inventory 两个组
        group_names = [g.name for g in groups]
        assert "order" in group_names
        assert "inventory" in group_names
        
        # order 组应该有 3 个表
        order_group = next(g for g in groups if g.name == "order")
        assert len(order_group.tables) == 3
    
    def test_generate_description(self, discovery_service):
        """测试描述生成"""
        group = TableGroup(
            name="order",
            tables=["order_header", "order_items", "order_payment"],
            keywords=["订单", "销售"]
        )
        
        desc = discovery_service._generate_description(group)
        assert "订单" in desc or "order" in desc


class TestStateIntegration:
    """测试 State 集成"""
    
    def test_initial_state_skill_fields(self):
        """测试初始状态包含 Skill 字段"""
        state = create_initial_state(connection_id=1)
        
        assert state.get("skill_mode_enabled") is False
        assert state.get("selected_skill_name") is None
        assert state.get("skill_confidence") == 0.0
        assert state.get("loaded_skill_content") is None
    
    def test_is_skill_mode_enabled(self):
        """测试 Skill 模式检查"""
        state = create_initial_state()
        assert is_skill_mode_enabled(state) is False
        
        state["skill_mode_enabled"] = True
        assert is_skill_mode_enabled(state) is True
    
    def test_get_skill_context(self):
        """测试获取 Skill 上下文"""
        state = create_initial_state()
        state["skill_mode_enabled"] = True
        state["selected_skill_name"] = "sales_order"
        state["skill_confidence"] = 0.85
        state["skill_business_rules"] = "使用 total_amount 字段"
        
        context = get_skill_context(state)
        
        assert context["skill_mode_enabled"] is True
        assert context["selected_skill_name"] == "sales_order"
        assert context["skill_confidence"] == 0.85
        assert "total_amount" in context["skill_business_rules"]


class TestZeroConfigCompatibility:
    """测试零配置兼容性"""
    
    @pytest.mark.asyncio
    async def test_should_use_skill_mode_false(self):
        """测试未配置 Skill 时不启用 Skill 模式"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=False)
            
            result = await should_use_skill_mode(connection_id=1)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_should_use_skill_mode_true(self):
        """测试已配置 Skill 时启用 Skill 模式"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=True)
            
            result = await should_use_skill_mode(connection_id=1)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_skill_routing_context_no_skills(self):
        """测试无 Skill 配置时的路由上下文"""
        with patch('app.services.skill_router.skill_service') as mock_service:
            mock_service.has_skills_configured = AsyncMock(return_value=False)
            
            context = await get_skill_routing_context(
                query="查询销售数据",
                connection_id=1
            )
            
            assert context["skill_mode_enabled"] is False
            assert context["selected_skill_name"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
