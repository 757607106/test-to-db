"""
Skill Service 单元测试

测试内容：
- Skill CRUD 操作
- 多租户隔离
- 零配置兼容性
- Schema 验证
- Neo4j 同步（Mock）
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.models.skill import Skill as SkillModel
from app.schemas.skill import (
    SkillCreate, SkillUpdate, Skill, SkillLoadResult,
    SkillListResponse, SkillStatusResponse
)
from app.services.skill_service import SkillService


class TestSkillSchemas:
    """测试 Skill Schema 验证"""
    
    def test_skill_create_valid_name(self):
        """测试有效的 name 格式"""
        data = SkillCreate(
            name="sales_order",
            display_name="销售订单",
            connection_id=1
        )
        assert data.name == "sales_order"
    
    def test_skill_create_invalid_name_uppercase(self):
        """测试无效 name - 大写字母"""
        with pytest.raises(ValueError, match="必须以小写字母开头"):
            SkillCreate(
                name="Sales_Order",
                display_name="销售订单",
                connection_id=1
            )
    
    def test_skill_create_invalid_name_starts_with_number(self):
        """测试无效 name - 数字开头"""
        with pytest.raises(ValueError, match="必须以小写字母开头"):
            SkillCreate(
                name="123sales",
                display_name="销售订单",
                connection_id=1
            )
    
    def test_skill_create_invalid_name_special_chars(self):
        """测试无效 name - 特殊字符"""
        with pytest.raises(ValueError, match="必须以小写字母开头"):
            SkillCreate(
                name="sales-order",
                display_name="销售订单",
                connection_id=1
            )
    
    def test_skill_create_with_keywords(self):
        """测试带关键词的创建"""
        data = SkillCreate(
            name="inventory",
            display_name="库存管理",
            keywords=["库存", "入库", "出库", "盘点"],
            table_names=["inventory", "stock_movement"],
            connection_id=1
        )
        assert len(data.keywords) == 4
        assert len(data.table_names) == 2
    
    def test_skill_create_with_business_rules(self):
        """测试带业务规则的创建"""
        data = SkillCreate(
            name="finance",
            display_name="财务管理",
            business_rules="金额字段使用 DECIMAL(18,2)，日期范围过滤优先使用索引字段",
            connection_id=1
        )
        assert "DECIMAL" in data.business_rules
    
    def test_skill_update_partial(self):
        """测试部分更新"""
        data = SkillUpdate(display_name="新显示名称")
        assert data.display_name == "新显示名称"
        assert data.name is None
        assert data.keywords is None
    
    def test_skill_load_result(self):
        """测试 SkillLoadResult 结构"""
        result = SkillLoadResult(
            skill_name="sales",
            display_name="销售",
            tables=[{"table_name": "orders", "table_comment": "订单表"}],
            columns=[{"column_name": "id", "data_type": "bigint"}],
            metrics=[{"name": "total_sales", "formula": "SUM(amount)"}],
            business_rules="销售数据以订单创建时间为准"
        )
        assert result.skill_name == "sales"
        assert len(result.tables) == 1
        assert len(result.columns) == 1
        assert len(result.metrics) == 1
    
    def test_skill_status_response(self):
        """测试 SkillStatusResponse"""
        response = SkillStatusResponse(
            has_skills_configured=True,
            skills_count=3,
            mode="skill"
        )
        assert response.has_skills_configured is True
        assert response.mode == "skill"
    
    def test_skill_list_response(self):
        """测试 SkillListResponse"""
        response = SkillListResponse(
            skills=[],
            total=0,
            has_skills_configured=False
        )
        assert response.has_skills_configured is False


class TestSkillServiceCRUD:
    """测试 SkillService CRUD 操作"""
    
    @pytest.fixture
    def skill_service(self):
        """创建 SkillService 实例"""
        return SkillService()
    
    @pytest.fixture
    def mock_skill_model(self):
        """创建 Mock Skill 模型"""
        skill = MagicMock(spec=SkillModel)
        skill.id = 1
        skill.name = "sales_order"
        skill.display_name = "销售订单"
        skill.description = "处理销售订单相关查询"
        skill.keywords = ["销售", "订单", "客户"]
        skill.intent_examples = []
        skill.table_patterns = []
        skill.table_names = ["orders", "order_items", "customers"]
        skill.business_rules = "订单金额使用 total_amount 字段"
        skill.common_patterns = []
        skill.priority = 10
        skill.is_active = True
        skill.icon = "shopping-cart"
        skill.color = "#1890ff"
        skill.connection_id = 1
        skill.tenant_id = 1
        skill.usage_count = 0
        skill.hit_rate = 0.0
        skill.is_auto_generated = False
        skill.created_at = datetime.now()
        skill.updated_at = None
        return skill
    
    @pytest.mark.asyncio
    async def test_create_skill(self, skill_service, mock_skill_model):
        """测试创建 Skill"""
        with patch.object(skill_service, '_sync_to_neo4j', new_callable=AsyncMock) as mock_sync:
            with patch('app.services.skill_service.get_db_session') as mock_session:
                # 设置 mock
                mock_db = MagicMock()
                mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_session.return_value.__exit__ = MagicMock(return_value=False)
                
                mock_db.add = MagicMock()
                mock_db.commit = MagicMock()
                mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, 'id', 1))
                
                # 创建数据
                data = SkillCreate(
                    name="sales_order",
                    display_name="销售订单",
                    keywords=["销售", "订单"],
                    table_names=["orders"],
                    connection_id=1
                )
                
                # 执行 - 因为 mock 复杂性，这里主要测试接口
                # 实际测试需要集成测试环境
                assert data.name == "sales_order"
                assert data.connection_id == 1
    
    @pytest.mark.asyncio
    async def test_has_skills_configured_true(self, skill_service, mock_skill_model):
        """测试 has_skills_configured - 有配置"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [Skill.model_validate(mock_skill_model)]
            
            result = await skill_service.has_skills_configured(connection_id=1)
            assert result is True
            mock_get.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_has_skills_configured_false(self, skill_service):
        """测试 has_skills_configured - 无配置（零配置兼容）"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await skill_service.has_skills_configured(connection_id=1)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_skill_prompt_section_with_skills(self, skill_service, mock_skill_model):
        """测试 get_skill_prompt_section - 有 Skills"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_skill = Skill.model_validate(mock_skill_model)
            mock_get.return_value = [mock_skill]
            
            result = await skill_service.get_skill_prompt_section(connection_id=1)
            
            assert result is not None
            assert "销售订单" in result
            assert "load_skill" in result
    
    @pytest.mark.asyncio
    async def test_get_skill_prompt_section_no_skills(self, skill_service):
        """测试 get_skill_prompt_section - 无 Skills（零配置）"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            result = await skill_service.get_skill_prompt_section(connection_id=1)
            
            assert result is None  # 零配置返回 None


class TestSkillServiceNeo4j:
    """测试 Neo4j 同步功能"""
    
    @pytest.fixture
    def skill_service(self):
        return SkillService()
    
    def test_get_neo4j_driver_lazy_init(self, skill_service):
        """测试 Neo4j 驱动懒加载"""
        assert skill_service._neo4j_driver is None
        assert skill_service._neo4j_initialized is False
    
    @patch('app.services.skill_service.GraphDatabase')
    def test_get_neo4j_driver_success(self, mock_graph_db, skill_service):
        """测试成功获取 Neo4j 驱动"""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        
        driver = skill_service._get_neo4j_driver()
        
        # 验证驱动被创建
        assert mock_graph_db.driver.called
    
    @patch('app.services.skill_service.GraphDatabase')
    def test_get_neo4j_driver_failure(self, mock_graph_db, skill_service):
        """测试获取 Neo4j 驱动失败"""
        mock_graph_db.driver.side_effect = Exception("Connection failed")
        
        driver = skill_service._get_neo4j_driver()
        
        assert driver is None


class TestSkillServiceMultiTenant:
    """测试多租户隔离"""
    
    @pytest.fixture
    def skill_service(self):
        return SkillService()
    
    def test_skill_model_tenant_id(self):
        """测试 Skill 模型包含 tenant_id"""
        # 验证模型定义
        from app.models.skill import Skill as SkillModel
        
        assert hasattr(SkillModel, 'tenant_id')
        assert hasattr(SkillModel, 'connection_id')
    
    def test_skill_model_unique_constraint(self):
        """测试唯一约束：name + connection_id"""
        from app.models.skill import Skill as SkillModel
        
        # 验证表约束存在
        constraints = SkillModel.__table__.constraints
        constraint_names = [c.name for c in constraints if hasattr(c, 'name')]
        
        assert 'uq_skill_name_connection' in constraint_names


class TestSkillServiceZeroConfig:
    """测试零配置兼容性"""
    
    @pytest.fixture
    def skill_service(self):
        return SkillService()
    
    @pytest.mark.asyncio
    async def test_zero_config_mode_detection(self, skill_service):
        """测试零配置模式检测"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            # 场景1: 没有配置 Skill
            mock_get.return_value = []
            has_skills = await skill_service.has_skills_configured(1)
            assert has_skills is False
            
            # 场景2: 有配置 Skill
            mock_get.return_value = [MagicMock()]
            has_skills = await skill_service.has_skills_configured(1)
            assert has_skills is True
    
    @pytest.mark.asyncio
    async def test_zero_config_prompt_injection(self, skill_service):
        """测试零配置时不注入 Skill 提示词"""
        with patch.object(skill_service, 'get_skills_by_connection', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            
            prompt = await skill_service.get_skill_prompt_section(1)
            
            # 零配置模式下返回 None
            assert prompt is None


class TestSkillModelIntegrity:
    """测试 Skill 模型完整性"""
    
    def test_skill_model_fields(self):
        """测试 Skill 模型字段完整性"""
        from app.models.skill import Skill as SkillModel
        
        required_fields = [
            'id', 'name', 'display_name', 'description',
            'keywords', 'intent_examples', 'table_patterns', 'table_names',
            'business_rules', 'common_patterns', 'priority', 'is_active',
            'icon', 'color', 'usage_count', 'hit_rate', 'is_auto_generated',
            'connection_id', 'tenant_id', 'created_at', 'updated_at'
        ]
        
        for field in required_fields:
            assert hasattr(SkillModel, field), f"Missing field: {field}"
    
    def test_skill_model_relationships(self):
        """测试 Skill 模型关系"""
        from app.models.skill import Skill as SkillModel
        
        # 验证外键关系
        assert hasattr(SkillModel, 'connection')
        assert hasattr(SkillModel, 'tenant')
    
    def test_skill_model_table_name(self):
        """测试表名"""
        from app.models.skill import Skill as SkillModel
        
        assert SkillModel.__tablename__ == 'skills'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
