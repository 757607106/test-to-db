"""
测试预测解释功能的增强（数据溯源和推理链）
"""
import pytest
from app.schemas.prediction import (
    PredictionExplanation,
    DataSourceInfo,
    KeyMetricValue,
    ReasoningStep
)
from app.services.prediction_service import PredictionService


class TestPredictionExplanationEnhancement:
    """测试预测解释的增强功能"""
    
    def test_schema_backward_compatibility(self):
        """测试向后兼容性：不传新字段也能正常工作"""
        # 原有的创建方式（不包含新字段）
        explanation = PredictionExplanation(
            method_explanation="线性回归说明",
            formula_used="y = ax + b",
            key_parameters={"slope": 0.5, "intercept": 10},
            calculation_steps=["步骤1", "步骤2"],
            confidence_explanation="95%置信区间",
            reliability_assessment="高可靠性"
        )
        
        # 应该能成功创建，新字段为空
        assert explanation.method_explanation == "线性回归说明"
        assert explanation.data_source is None
        assert explanation.key_metrics == []
        assert explanation.reasoning_chain == []
    
    def test_schema_with_new_fields(self):
        """测试包含新字段的创建"""
        data_source = DataSourceInfo(
            tables=["orders"],
            columns=["date", "amount"],
            row_count=100,
            time_range="2024-01-01 至 2024-12-31"
        )
        
        key_metrics = [
            KeyMetricValue(
                name="均值",
                value=1234.56,
                description="平均值",
                used_in_steps=[1, 3]
            )
        ]
        
        reasoning_chain = [
            ReasoningStep(
                step=1,
                description="统计基本信息",
                input_description="100个数据点",
                output_description="均值=1234.56"
            )
        ]
        
        explanation = PredictionExplanation(
            method_explanation="线性回归说明",
            formula_used="y = ax + b",
            key_parameters={},
            calculation_steps=[],
            confidence_explanation="",
            reliability_assessment="",
            data_source=data_source,
            key_metrics=key_metrics,
            reasoning_chain=reasoning_chain
        )
        
        # 验证新字段
        assert explanation.data_source is not None
        assert explanation.data_source.row_count == 100
        assert len(explanation.key_metrics) == 1
        assert explanation.key_metrics[0].name == "均值"
        assert len(explanation.reasoning_chain) == 1
        assert explanation.reasoning_chain[0].step == 1
    
    @pytest.mark.asyncio
    async def test_prediction_service_generates_explanation(self):
        """测试预测服务能生成完整的解释"""
        service = PredictionService()
        
        # 模拟数据
        data = [
            {"date": "2024-01-01", "value": 100},
            {"date": "2024-01-02", "value": 110},
            {"date": "2024-01-03", "value": 105},
            {"date": "2024-01-04", "value": 115},
            {"date": "2024-01-05", "value": 120},
        ]
        
        result = await service.predict(
            data=data,
            date_column="date",
            value_column="value",
            periods=2,
            method="linear"
        )
        
        # 验证解释包含新字段
        assert result.explanation is not None
        assert result.explanation.data_source is not None
        assert result.explanation.data_source.row_count == 5
        assert result.explanation.data_source.columns == ["date", "value"]
        
        # 验证关键指标
        assert len(result.explanation.key_metrics) > 0
        metric_names = [m.name for m in result.explanation.key_metrics]
        assert "均值" in metric_names
        assert "标准差" in metric_names
        
        # 验证推理步骤
        assert len(result.explanation.reasoning_chain) > 0
        assert result.explanation.reasoning_chain[0].step == 1
        
        # 验证原有字段仍然存在（向后兼容）
        assert result.explanation.method_explanation != ""
        assert result.explanation.formula_used != ""
        assert len(result.explanation.calculation_steps) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
