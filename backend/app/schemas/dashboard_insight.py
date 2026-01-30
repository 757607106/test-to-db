"""Dashboard洞察分析相关Schema定义"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ===== 数据溯源Schema (P0) =====

class ExecutionMetadata(BaseModel):
    """执行元数据"""
    execution_time_ms: int = Field(0, description="执行耗时(毫秒)")
    from_cache: bool = Field(False, description="是否来自缓存")
    row_count: int = Field(0, description="返回行数")
    db_type: Optional[str] = Field(None, description="数据库类型")
    connection_id: Optional[int] = Field(None, description="连接ID")


class SqlGenerationTrace(BaseModel):
    """SQL生成过程追踪"""
    user_intent: Optional[str] = Field(None, description="用户意图")
    enriched_query: Optional[str] = Field(None, description="增强后的查询")
    schema_tables_used: List[str] = Field(default_factory=list, description="使用的Schema表")
    few_shot_samples_count: int = Field(0, description="Few-shot样本数量")
    generation_method: str = Field("standard", description="生成方法: standard/template/cache")


class InsightLineage(BaseModel):
    """数据血缘追踪"""
    source_tables: List[str] = Field(default_factory=list, description="数据来源表")
    generated_sql: Optional[str] = Field(None, description="生成的SQL语句")
    sql_generation_trace: SqlGenerationTrace = Field(
        default_factory=SqlGenerationTrace,
        description="SQL生成过程追踪"
    )
    execution_metadata: ExecutionMetadata = Field(
        default_factory=ExecutionMetadata,
        description="执行元数据"
    )
    data_transformations: List[str] = Field(
        default_factory=list,
        description="数据转换步骤"
    )
    schema_context: Optional[Dict[str, Any]] = Field(
        None,
        description="使用的Schema上下文"
    )


class EnhancedInsightResponse(BaseModel):
    """增强的洞察响应（含溯源）"""
    widget_id: int = Field(..., description="洞察Widget ID")
    insights: "InsightResult" = Field(..., description="洞察结果")
    lineage: InsightLineage = Field(..., description="数据血缘")
    confidence_score: float = Field(0.8, ge=0, le=1, description="置信度评分")
    analysis_method: str = Field("auto", description="分析方法说明")
    analyzed_widget_count: int = Field(0, description="分析的Widget数量")
    relationship_count: int = Field(0, description="发现的表关系数量")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")


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
    force_requery: bool = Field(False, description="是否重新查询数据源")
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
    metric: Optional[str] = Field(None, description="异常指标/列名")
    column: Optional[str] = Field(None, description="异常列（兼容旧字段）")
    description: str = Field(..., description="异常描述")
    severity: Optional[str] = Field(None, description="严重程度: high/medium/low")


class InsightCorrelation(BaseModel):
    """关联分析"""
    type: str = Field(..., description="关联类型: cross_widget/cross_table")
    tables: Optional[List[str]] = Field(None, description="涉及的表")
    entities: Optional[List[str]] = Field(None, description="涉及的实体（兼容字段）")
    relationship: Optional[str] = Field(None, description="关系描述")
    description: Optional[str] = Field(None, description="关联描述")
    insight: Optional[str] = Field(None, description="关联洞察描述")
    strength: Optional[Any] = Field(None, description="关联强度: strong/medium/weak 或 0-1 数值")


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
    # P0-FIX: 添加 status 字段
    status: str = Field("completed", description="分析状态: processing/completed/failed")


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


# ===== 智能挖掘相关 Schema =====

class MiningDimension(str, Enum):
    """挖掘维度"""
    BUSINESS = "business"      # 业务数据维度
    METRIC = "metric"          # 指标维度
    SEMANTIC = "semantic"      # 语义维度
    TREND = "trend"            # 趋势维度
    ANOMALY = "anomaly"        # 异常维度


class MiningSuggestion(BaseModel):
    """智能挖掘推荐项（增强版）"""
    title: str = Field(..., description="图表标题")
    description: str = Field(..., description="简要描述")
    sql: str = Field(..., description="SQL查询语句")
    chart_type: str = Field(..., description="推荐图表类型")
    analysis_intent: str = Field(..., description="对应的分析意图")
    
    # 增强字段：可解释性
    reasoning: str = Field("", description="推荐理由（AI为什么推荐这个分析）")
    mining_dimension: str = Field("business", description="挖掘维度: business/metric/semantic/trend/anomaly")
    confidence: float = Field(0.8, ge=0, le=1, description="置信度评分")
    
    # 数据来源
    source_tables: List[str] = Field(default_factory=list, description="涉及的数据表")
    key_fields: List[str] = Field(default_factory=list, description="关键字段")
    
    # 业务价值
    business_value: str = Field("", description="业务价值说明")
    suggested_actions: List[str] = Field(default_factory=list, description="建议的后续动作")

class MiningRequest(BaseModel):
    """智能挖掘请求"""
    connection_id: int = Field(..., description="数据库连接ID")
    intent: Optional[str] = Field(None, description="用户意图/关注点，为空则全自动推荐")
    limit: int = Field(10, ge=3, le=20, description="推荐数量，默认10，范围3-20")
    dimensions: List[str] = Field(
        default_factory=lambda: ["business", "metric", "trend"],
        description="挖掘维度: business/metric/semantic/trend/anomaly"
    )

class MiningResponse(BaseModel):
    """智能挖掘响应"""
    suggestions: List[MiningSuggestion] = Field(default_factory=list)

class ApplyMiningRequest(BaseModel):
    """应用推荐请求"""
    connection_id: int = Field(..., description="数据库连接ID")
    suggestions: List[MiningSuggestion] = Field(..., description="用户选中的推荐项")
