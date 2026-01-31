"""
测试预测API的问题修复
1. 400 Bad Request 问题
2. 日期解析失败问题（数值型日期）
"""
import pytest
from app.services.prediction_service import PredictionService


class TestPredictionAPIFix:
    """测试预测API修复"""
    
    @pytest.mark.asyncio
    async def test_numeric_date_column(self):
        """测试数值型日期列（如分组序号）的处理"""
        service = PredictionService()
        
        # 模拟数据：日期列是数值型（如分组序号 0, 1, 2...）
        data = [
            {"date": 0.0, "value": 100},
            {"date": 1.0, "value": 110},
            {"date": 2.0, "value": 105},
            {"date": 3.0, "value": 115},
            {"date": 4.0, "value": 120},
        ]
        
        # 应该能正常处理
        result = await service.predict(
            data=data,
            date_column="date",
            value_column="value",
            periods=2,
            method="linear"
        )
        
        # 验证预测成功
        assert result is not None
        assert len(result.predictions) == 2
        assert result.explanation is not None
    
    @pytest.mark.asyncio
    async def test_various_date_formats(self):
        """测试各种日期格式"""
        service = PredictionService()
        
        # 测试案例
        test_cases = [
            # 1. 标准日期字符串
            {"data": [{"date": "2024-01-01", "value": 100}, {"date": "2024-01-02", "value": 110}, {"date": "2024-01-03", "value": 105}], "desc": "标准日期"},
            # 2. 数值序号
            {"data": [{"date": 0, "value": 100}, {"date": 1, "value": 110}, {"date": 2, "value": 105}], "desc": "数值序号"},
            # 3. 时间戳
            {"data": [{"date": 1704067200, "value": 100}, {"date": 1704153600, "value": 110}, {"date": 1704240000, "value": 105}], "desc": "Unix时间戳"},
        ]
        
        for case in test_cases:
            result = await service.predict(
                data=case["data"],
                date_column="date",
                value_column="value",
                periods=2,
                method="linear"
            )
            assert result is not None, f"Failed for: {case['desc']}"
            print(f"✅ {case['desc']}: OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
