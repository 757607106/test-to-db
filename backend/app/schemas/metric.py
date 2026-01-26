"""
指标库 Schema 定义

用于语义层 (Semantic Layer) 的业务指标定义，存储在 Neo4j 图数据库中。
指标包含业务含义、计算逻辑、关联字段等信息，帮助 LLM 更准确地理解用户查询意图。
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


# 聚合类型
AggregationType = Literal["SUM", "AVG", "COUNT", "MAX", "MIN", "COUNT_DISTINCT", "NONE"]


class MetricBase(BaseModel):
    """指标基础属性"""
    name: str = Field(..., description="指标名称，如：销售额、订单数")
    business_name: Optional[str] = Field(None, description="业务别名，如：GMV、成交额")
    description: Optional[str] = Field(None, description="指标描述")
    
    # 计算逻辑
    formula: str = Field(..., description="计算公式，如：SUM(amount)")
    aggregation: AggregationType = Field("SUM", description="聚合方式")
    
    # 关联字段
    source_table: str = Field(..., description="来源表名")
    source_column: str = Field(..., description="来源字段名")
    
    # 维度和过滤
    dimension_columns: List[str] = Field(default_factory=list, description="可用维度字段")
    time_column: Optional[str] = Field(None, description="时间字段")
    default_filters: Optional[Dict[str, Any]] = Field(None, description="默认过滤条件")
    
    # 业务分类
    category: Optional[str] = Field(None, description="指标分类，如：销售、用户、运营")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    
    # 显示配置
    unit: Optional[str] = Field(None, description="单位，如：元、个、%")
    decimal_places: int = Field(2, description="小数位数")


class MetricCreate(MetricBase):
    """创建指标请求"""
    connection_id: int = Field(..., description="数据库连接ID")


class MetricUpdate(BaseModel):
    """更新指标请求"""
    name: Optional[str] = None
    business_name: Optional[str] = None
    description: Optional[str] = None
    formula: Optional[str] = None
    aggregation: Optional[AggregationType] = None
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    dimension_columns: Optional[List[str]] = None
    time_column: Optional[str] = None
    default_filters: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    unit: Optional[str] = None
    decimal_places: Optional[int] = None


class Metric(MetricBase):
    """指标响应模型"""
    id: str = Field(..., description="指标ID")
    connection_id: int = Field(..., description="数据库连接ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True


class MetricWithContext(Metric):
    """带上下文的指标（包含关联表和字段信息）"""
    table_description: Optional[str] = Field(None, description="来源表描述")
    column_type: Optional[str] = Field(None, description="来源字段类型")
    related_metrics: List[str] = Field(default_factory=list, description="相关指标名称")


# ===== 值域 Profile 相关 =====

class ColumnProfile(BaseModel):
    """字段值域 Profile"""
    column_name: str = Field(..., description="字段名")
    table_name: str = Field(..., description="表名")
    data_type: str = Field(..., description="数据类型")
    
    # 值域信息
    distinct_count: int = Field(0, description="去重值数量")
    null_count: int = Field(0, description="空值数量")
    total_count: int = Field(0, description="总行数")
    
    # 枚举值（用于低基数字段）
    enum_values: List[str] = Field(default_factory=list, description="枚举值列表（前100个）")
    is_enum: bool = Field(False, description="是否为枚举类型字段")
    
    # 数值范围（用于数值字段）
    min_value: Optional[Any] = Field(None, description="最小值")
    max_value: Optional[Any] = Field(None, description="最大值")
    
    # 日期范围（用于日期字段）
    date_min: Optional[str] = Field(None, description="最早日期")
    date_max: Optional[str] = Field(None, description="最晚日期")
    
    # 采样值
    sample_values: List[Any] = Field(default_factory=list, description="采样值（前10个）")
    
    # Profile 时间
    profiled_at: Optional[datetime] = Field(None, description="Profile 时间")


class TableProfile(BaseModel):
    """表 Profile"""
    table_name: str = Field(..., description="表名")
    connection_id: int = Field(..., description="数据库连接ID")
    row_count: int = Field(0, description="行数")
    columns: List[ColumnProfile] = Field(default_factory=list, description="字段 Profile 列表")
    profiled_at: Optional[datetime] = Field(None, description="Profile 时间")


# ===== 语义层查询相关 =====

class SemanticQuery(BaseModel):
    """语义层查询请求"""
    metrics: List[str] = Field(..., description="要查询的指标名称列表")
    dimensions: List[str] = Field(default_factory=list, description="分组维度")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    time_range: Optional[Dict[str, str]] = Field(None, description="时间范围")
    order_by: Optional[List[str]] = Field(None, description="排序字段")
    limit: int = Field(100, description="返回行数限制")


class SemanticQueryResult(BaseModel):
    """语义层查询结果"""
    sql: str = Field(..., description="生成的SQL")
    metrics_used: List[str] = Field(..., description="使用的指标")
    dimensions_used: List[str] = Field(..., description="使用的维度")
    explanation: str = Field("", description="SQL 解释")
