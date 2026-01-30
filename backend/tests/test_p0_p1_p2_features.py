"""
P0/P1/P2 功能单元测试
- P0: 数据溯源 (Lineage)
- P1: 动态刷新 (Refresh)
- P2: 数据预测 (Prediction)
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestP2PredictionService:
    """P2: 预测服务测试"""

    def test_linear_prediction(self):
        """测试线性回归预测"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        values = [100, 110, 120, 130, 140, 150]
        
        predictions, lower, upper = service._linear_prediction(values, 3, 0.95)
        
        # 验证预测结果
        assert len(predictions) == 3
        assert predictions[0] > values[-1]  # 上升趋势应该继续增长
        assert all(lower[i] < predictions[i] < upper[i] for i in range(3))

    def test_moving_average_prediction(self):
        """测试移动平均预测"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        values = [100, 105, 95, 110, 100, 108]
        
        predictions, lower, upper = service._moving_average_prediction(values, 3, 0.95)
        
        assert len(predictions) == 3
        # 移动平均应该趋近于最近值的平均
        expected_avg = sum(values[-3:]) / 3
        assert abs(predictions[0] - expected_avg) < 1

    def test_exponential_smoothing_prediction(self):
        """测试指数平滑预测"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        values = [100, 120, 110, 130, 125, 135]
        
        predictions, lower, upper = service._exponential_smoothing_prediction(values, 3, 0.95)
        
        assert len(predictions) == 3
        assert all(lower[i] <= predictions[i] <= upper[i] for i in range(3))

    def test_auto_method_selection(self):
        """测试自动方法选择"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        
        # 线性趋势数据应选择linear
        linear_data = [100, 110, 120, 130, 140, 150, 160, 170]
        method = service._select_best_method(linear_data)
        assert method == "linear"
        
        # 波动数据应选择其他方法
        volatile_data = [100, 150, 80, 200, 50, 180, 90, 160]
        method = service._select_best_method(volatile_data)
        assert method in ["moving_average", "exponential_smoothing"]

    def test_trend_analysis(self):
        """测试趋势分析"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        
        # 上升趋势
        up_values = [100, 110, 120, 130, 140]
        trend = service._analyze_trend(up_values)
        assert trend.direction == "up"
        assert trend.growth_rate > 0
        
        # 下降趋势
        down_values = [140, 130, 120, 110, 100]
        trend = service._analyze_trend(down_values)
        assert trend.direction == "down"
        assert trend.growth_rate < 0

    def test_accuracy_metrics(self):
        """测试准确性指标计算"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        values = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
        
        metrics = service._calculate_accuracy_metrics(values, "linear")
        
        assert metrics.mape >= 0
        assert metrics.rmse >= 0
        assert metrics.mae >= 0

    def test_date_generation(self):
        """测试日期生成"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        
        future_dates = service._generate_future_dates(dates, 3)
        
        assert len(future_dates) == 3
        assert future_dates[0] == "2024-01-04"
        assert future_dates[1] == "2024-01-05"


class TestP1RefreshService:
    """P1: 刷新服务测试"""
    
    def test_refresh_config_schema(self):
        """测试刷新配置Schema"""
        from app.schemas.dashboard import RefreshConfig
        
        config = RefreshConfig(
            enabled=True,
            interval_seconds=300,
            auto_refresh_widget_ids=[1, 2, 3]
        )
        
        assert config.enabled == True
        assert config.interval_seconds == 300
        assert len(config.auto_refresh_widget_ids) == 3

    def test_global_refresh_response_schema(self):
        """测试全局刷新响应Schema"""
        from app.schemas.dashboard import GlobalRefreshResponse, WidgetRefreshResult
        
        result = WidgetRefreshResult(
            widget_id=1,
            success=True,
            duration_ms=150,
            from_cache=False,
            row_count=100
        )
        
        response = GlobalRefreshResponse(
            success_count=1,
            failed_count=0,
            results={1: result},
            total_duration_ms=200
        )
        
        assert response.success_count == 1
        assert response.failed_count == 0

    def test_insight_request_force_requery_schema(self):
        from app.schemas.dashboard_insight import DashboardInsightRequest

        req = DashboardInsightRequest()
        assert req.force_requery == False


class TestInsightForceRequery:
    def test_refresh_data_widgets_calls_refresh_widget(self):
        from app.services.dashboard_insight_service import DashboardInsightService

        svc = DashboardInsightService()
        db = MagicMock()
        widgets = [MagicMock(id=1), MagicMock(id=2)]

        with patch("app.services.dashboard_widget_service.dashboard_widget_service.refresh_widget") as refresh_widget:
            svc._refresh_data_widgets(db, widgets, user_id=123)

        assert refresh_widget.call_count == 2
        refresh_widget.assert_any_call(db, widget_id=1, user_id=123)
        refresh_widget.assert_any_call(db, widget_id=2, user_id=123)


class TestP0LineageSchema:
    """P0: 数据溯源Schema测试"""
    
    def test_execution_metadata_schema(self):
        """测试执行元数据Schema"""
        from app.schemas.dashboard_insight import ExecutionMetadata
        
        metadata = ExecutionMetadata(
            execution_time_ms=150,
            from_cache=False,
            row_count=1000,
            db_type="postgresql"
        )
        
        assert metadata.execution_time_ms == 150
        assert metadata.from_cache == False
        assert metadata.row_count == 1000

    def test_sql_generation_trace_schema(self):
        """测试SQL生成追踪Schema"""
        from app.schemas.dashboard_insight import SqlGenerationTrace
        
        trace = SqlGenerationTrace(
            user_intent="查询销售数据",
            schema_tables_used=["sales", "products"],
            few_shot_samples_count=3,
            generation_method="standard"
        )
        
        assert trace.user_intent == "查询销售数据"
        assert len(trace.schema_tables_used) == 2

    def test_insight_lineage_schema(self):
        """测试洞察溯源Schema"""
        from app.schemas.dashboard_insight import (
            InsightLineage,
            ExecutionMetadata,
            SqlGenerationTrace
        )
        
        lineage = InsightLineage(
            source_tables=["sales", "products"],
            generated_sql="SELECT * FROM sales",
            sql_generation_trace=SqlGenerationTrace(
                schema_tables_used=["sales"],
                few_shot_samples_count=2,
                generation_method="standard"
            ),
            execution_metadata=ExecutionMetadata(
                execution_time_ms=100,
                from_cache=False,
                row_count=500
            ),
            data_transformations=["聚合", "排序"]
        )
        
        assert len(lineage.source_tables) == 2
        assert lineage.generated_sql is not None
        assert len(lineage.data_transformations) == 2


@pytest.mark.asyncio
class TestP2PredictionAsync:
    """P2: 预测服务异步测试"""
    
    async def test_full_prediction_flow(self):
        """测试完整预测流程"""
        from app.services.prediction_service import PredictionService
        
        service = PredictionService()
        
        data = [
            {"date": "2024-01-01", "sales": 100},
            {"date": "2024-01-02", "sales": 110},
            {"date": "2024-01-03", "sales": 120},
            {"date": "2024-01-04", "sales": 115},
            {"date": "2024-01-05", "sales": 130},
            {"date": "2024-01-06", "sales": 125},
            {"date": "2024-01-07", "sales": 140},
        ]
        
        result = await service.predict(
            data=data,
            date_column="date",
            value_column="sales",
            periods=3,
            method="auto",
            confidence_level=0.95
        )
        
        assert len(result.historical_data) == 7
        assert len(result.predictions) == 3
        assert result.method_used is not None
        assert result.trend_analysis is not None
        assert result.accuracy_metrics is not None
