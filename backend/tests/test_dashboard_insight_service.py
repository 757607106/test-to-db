from types import SimpleNamespace
from unittest.mock import MagicMock

from app import schemas
from app.services.dashboard_insight_service import DashboardInsightService


def test_aggregate_widget_data_includes_by_widget_and_prefixes_metrics():
    service = DashboardInsightService()

    w1 = SimpleNamespace(
        id=1,
        widget_type="table",
        title="订单",
        data_cache={"data": [{"created_at": "2026-01-01", "amount": 10.0, "customer": "a"}]},
        query_config={"table_name": "orders"},
    )
    w2 = SimpleNamespace(
        id=2,
        widget_type="table",
        title="支付",
        data_cache={"data": [{"created_at": "2026-01-01", "amount": 3.0, "fee": 1.0}]},
        query_config={"table_name": "payments"},
    )

    aggregated = service._aggregate_widget_data([w1, w2], None)
    assert "by_widget" in aggregated
    assert len(aggregated["by_widget"]) == 2

    key_metrics = service._extract_key_metrics(aggregated)
    assert any(k.startswith("orders.") for k in key_metrics.keys())
    assert any(k.startswith("payments.") for k in key_metrics.keys())


def test_analyze_trends_sets_trend_metadata_and_r_squared_in_description():
    service = DashboardInsightService()

    w1 = SimpleNamespace(
        id=1,
        widget_type="table",
        title="订单",
        data_cache={
            "data": [
                {"created_at": "2026-01-01", "amount": 10.0},
                {"created_at": "2026-01-02", "amount": 12.0},
                {"created_at": "2026-01-03", "amount": 14.0},
                {"created_at": "2026-01-04", "amount": 16.0},
                {"created_at": "2026-01-05", "amount": 18.0},
            ]
        },
        query_config={"table_name": "orders"},
    )

    aggregated = service._aggregate_widget_data([w1], None)
    trend = service._analyze_trends(aggregated)
    assert trend is not None
    assert aggregated.get("_trend_metadata") is not None
    assert "R²=" in (trend.description or "")
    assert 0.0 <= float(aggregated["_trend_metadata"]["r_squared"]) <= 1.0


def test_update_insight_widget_result_persists_analysis_fields(monkeypatch):
    service = DashboardInsightService()
    widget = SimpleNamespace(query_config={}, data_cache=None, last_refresh_at=None)

    import app.services.dashboard_insight_service as mod

    def fake_get(_db, id):
        assert id == 123
        return widget

    monkeypatch.setattr(mod.crud.crud_dashboard_widget, "get", fake_get)

    db = MagicMock()
    insights = schemas.InsightResult(summary=schemas.InsightSummary(total_rows=1, key_metrics={}, time_range="已分析"))

    service._update_insight_widget_result(
        db,
        123,
        insights,
        2,
        status="completed",
        analysis_method="service_rule_based",
        confidence_score=0.77,
        relationship_count=1,
        source_tables=["orders"],
        extra_metrics={"metric": "orders.amount", "r_squared": 0.9, "values": [1.0, 2.0, 3.0]},
    )

    assert widget.query_config["analysis_method"] == "service_rule_based"
    assert widget.query_config["confidence_score"] == 0.77
    assert widget.query_config["relationship_count"] == 1
    assert widget.query_config["source_tables"] == ["orders"]
    assert widget.query_config["trend_metrics"]["metric"] == "orders.amount"
