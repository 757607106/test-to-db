"""Dashboard洞察分析相关Schema定义"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


# 查询条件Schema
class TimeRangeCondition(BaseModel):
    """时间范围条件"""
    start: Optional[str] = Field(None, description="开始时间")
    end: Optional[str] = Field(None, description="结束时间")


class InsightConditions(BaseModel):
    """洞察分析条件"""
    time_range: Optional[TimeRangeCondition] = None
    dimension_filters: Optional[Dict[str, Any]] = Field(None, description="维度筛选")
    aggregation_level: Optional[str] = Field(None, description="聚合粒度: day/week/month/quarter")


# 洞察生成请求Schema
class DashboardInsightRequest(BaseModel):
    """生成看板洞察的请求Schema"""
    analysis_dimensions: Optional[List[str]] = Field(
        None,
        description="分析维度: summary/trends/anomalies/correlations/recommendations"
    )
    included_widget_ids: Optional[List[int]] = Field(None, description="包含的Widget ID列表")
    force_refresh: bool = Field(False, description="强制重新分析")
    conditions: Optional[InsightConditions] = Field(None, description="查询条件")
    use_graph_relationships: bool = Field(True, description="是否启用图谱关系分析")


# 洞察结果详情Schema
class InsightSummary(BaseModel):
    """数据摘要"""
    total_rows: Optional[int] = None
    key_metrics: Optional[Dict[str, Any]] = None
    time_range: Optional[str] = None


class InsightTrend(BaseModel):
    """趋势分析"""
    trend_direction: Optional[str] = Field(None, description="趋势方向: 上升/下降/平稳")
    total_growth_rate: Optional[float] = Field(None, description="总体增长率")
    description: Optional[str] = Field(None, description="趋势描述")


class InsightAnomaly(BaseModel):
    """异常检测"""
    type: str = Field(..., description="异常类型")
    column: Optional[str] = Field(None, description="异常列")
    description: str = Field(..., description="异常描述")
    severity: Optional[str] = Field(None, description="严重程度: high/medium/low")


class InsightCorrelation(BaseModel):
    """关联分析"""
    type: str = Field(..., description="关联类型: cross_widget/cross_table")
    tables: Optional[List[str]] = Field(None, description="涉及的表")
    relationship: Optional[str] = Field(None, description="关系描述")
    insight: str = Field(..., description="关联洞察描述")
    strength: Optional[str] = Field(None, description="关联强度: strong/medium/weak")


class InsightRecommendation(BaseModel):
    """业务建议"""
    type: str = Field(..., description="建议类型: optimization/warning/opportunity")
    content: str = Field(..., description="建议内容")
    priority: Optional[str] = Field(None, description="优先级: high/medium/low")
    basis: Optional[str] = Field(None, description="建议依据")


class InsightResult(BaseModel):
    """洞察分析结果"""
    summary: Optional[InsightSummary] = None
    trends: Optional[InsightTrend] = None
    anomalies: Optional[List[InsightAnomaly]] = Field(default_factory=list)
    correlations: Optional[List[InsightCorrelation]] = Field(default_factory=list)
    recommendations: Optional[List[InsightRecommendation]] = Field(default_factory=list)


# 洞察生成响应Schema
class DashboardInsightResponse(BaseModel):
    """生成看板洞察的响应Schema"""
    widget_id: int = Field(..., description="创建的洞察Widget ID")
    insights: InsightResult = Field(..., description="洞察结果详情")
    analyzed_widget_count: int = Field(..., description="分析的Widget数量")
    analysis_timestamp: datetime = Field(..., description="分析时间")
    applied_conditions: Optional[InsightConditions] = Field(None, description="应用的条件")
    relationship_count: int = Field(0, description="发现的表关系数量")


# 洞察刷新请求Schema
class InsightRefreshRequest(BaseModel):
    """刷新洞察的请求Schema"""
    updated_conditions: Optional[InsightConditions] = Field(None, description="更新的查询条件")
    force_requery: bool = Field(False, description="是否重新查询数据源")


# 可调整条件配置Schema (存储在query_config中)
class AdjustableTimeRange(BaseModel):
    """可调整的时间范围配置"""
    column: str = Field(..., description="时间列名")
    type: str = Field(..., description="时间列类型: date/datetime/timestamp")
    presets: List[str] = Field(default_factory=lambda: ["最近7天", "最近30天", "本月", "自定义"])


class AdjustableDimensionFilter(BaseModel):
    """可调整的维度筛选配置"""
    column: str = Field(..., description="维度列名")
    values: List[Any] = Field(..., description="可选值列表")


class AdjustableAggregationLevel(BaseModel):
    """可调整的聚合粒度配置"""
    options: List[str] = Field(default_factory=lambda: ["day", "week", "month", "quarter"])


class AdjustableConditionsConfig(BaseModel):
    """可调整条件的完整配置"""
    time_range: Optional[AdjustableTimeRange] = None
    dimension_filters: Optional[List[AdjustableDimensionFilter]] = Field(default_factory=list)
    aggregation_level: Optional[AdjustableAggregationLevel] = None
