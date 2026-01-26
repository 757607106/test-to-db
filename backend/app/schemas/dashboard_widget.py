"""Dashboard Widget Schema定义"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Widget基础Schema
class WidgetBase(BaseModel):
    """Widget基础Schema"""
    widget_type: str = Field(..., description="组件类型: chart/table/text")
    title: str = Field(..., min_length=1, max_length=255, description="组件标题")
    connection_id: int = Field(..., description="数据库连接ID")
    query_config: Dict[str, Any] = Field(..., description="查询配置")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="图表配置")
    position_config: Dict[str, Any] = Field(..., description="位置配置")
    refresh_interval: int = Field(0, ge=0, description="刷新间隔(秒), 0表示不刷新")


# 创建Widget的请求Schema
class WidgetCreate(WidgetBase):
    """创建Widget的请求Schema"""
    pass


# 更新Widget的请求Schema
class WidgetUpdate(BaseModel):
    """更新Widget的请求Schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    chart_config: Optional[Dict[str, Any]] = None
    refresh_interval: Optional[int] = Field(None, ge=0)
    position_config: Optional[Dict[str, Any]] = None


# Widget的响应Schema
class WidgetResponse(WidgetBase):
    """Widget响应Schema"""
    id: int
    dashboard_id: int
    last_refresh_at: Optional[datetime] = None
    data_cache: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    connection_name: Optional[str] = Field(None, description="连接名称")

    class Config:
        from_attributes = True


# Widget刷新响应Schema
class WidgetRefreshResponse(BaseModel):
    """Widget刷新响应Schema"""
    id: int
    data_cache: Optional[Dict[str, Any]]
    last_refresh_at: datetime
    refresh_duration_ms: int = Field(..., description="刷新耗时(毫秒)")


# Widget重新生成查询请求Schema
class WidgetRegenerateRequest(BaseModel):
    """Widget重新生成查询请求Schema"""
    mode: str = Field(..., description="模式: params(只更新参数) 或 full(完全重新生成)")
    updated_query: Optional[str] = Field(None, description="更新后的自然语言查询")
    parameters: Optional[Dict[str, Any]] = Field(None, description="更新后的参数")


# 简化用户Schema (用于响应中的用户信息)
class UserSimple(BaseModel):
    """简化用户信息Schema"""
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


# AI 图表推荐请求 Schema
class AIChartRecommendRequest(BaseModel):
    """AI图表推荐请求Schema"""
    data_sample: Optional[Dict[str, Any]] = Field(None, description="数据样本")
    intent: Optional[str] = Field(None, description="用户意图")


# AI 图表推荐备选项
class ChartAlternative(BaseModel):
    """图表备选项"""
    type: str
    confidence: float
    description: str


# AI 图表推荐响应 Schema
class AIChartRecommendResponse(BaseModel):
    """AI图表推荐响应Schema"""
    recommended_type: str = Field(..., description="推荐的图表类型")
    confidence: float = Field(..., description="置信度 0-1")
    reasoning: str = Field(..., description="推荐理由")
    chart_config: Dict[str, Any] = Field(..., description="推荐的图表配置")
    alternatives: Optional[list[ChartAlternative]] = Field(None, description="备选方案")
