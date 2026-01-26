"""
预测分析Schema定义
P2功能：数据预测相关的请求和响应Schema
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PredictionMethod(str, Enum):
    """预测方法枚举"""
    AUTO = "auto"
    LINEAR = "linear"
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"


class PredictionRequest(BaseModel):
    """预测请求"""
    widget_id: int = Field(..., description="数据来源Widget ID")
    date_column: str = Field(..., description="时间列名")
    value_column: str = Field(..., description="预测目标列名")
    periods: int = Field(7, ge=1, le=365, description="预测周期数")
    method: PredictionMethod = Field(
        PredictionMethod.AUTO,
        description="预测方法: auto/linear/moving_average/exponential_smoothing"
    )
    confidence_level: float = Field(0.95, ge=0.5, le=0.99, description="置信水平")


class PredictionDataPoint(BaseModel):
    """预测数据点"""
    date: str = Field(..., description="日期")
    value: float = Field(..., description="值")
    lower_bound: Optional[float] = Field(None, description="置信区间下界")
    upper_bound: Optional[float] = Field(None, description="置信区间上界")
    is_prediction: bool = Field(False, description="是否为预测值")


class AccuracyMetrics(BaseModel):
    """准确性指标"""
    mape: float = Field(..., description="平均绝对百分比误差 (%)")
    rmse: float = Field(..., description="均方根误差")
    mae: float = Field(..., description="平均绝对误差")


class TrendAnalysis(BaseModel):
    """趋势分析"""
    direction: str = Field(..., description="趋势方向: up/down/stable")
    growth_rate: float = Field(..., description="增长率 (%)")
    average_value: float = Field(..., description="平均值")
    min_value: float = Field(..., description="最小值")
    max_value: float = Field(..., description="最大值")
    volatility: float = Field(0, description="波动率 (%)")


class PredictionResult(BaseModel):
    """预测结果"""
    historical_data: List[PredictionDataPoint] = Field(..., description="历史数据")
    predictions: List[PredictionDataPoint] = Field(..., description="预测数据")
    method_used: PredictionMethod = Field(..., description="实际使用的预测方法")
    accuracy_metrics: AccuracyMetrics = Field(..., description="准确性指标")
    trend_analysis: TrendAnalysis = Field(..., description="趋势分析")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")


class PredictionColumnsResponse(BaseModel):
    """可用于预测的列信息"""
    date_columns: List[str] = Field(default_factory=list, description="时间类型列")
    value_columns: List[str] = Field(default_factory=list, description="数值类型列")
    sample_data: Optional[List[Dict[str, Any]]] = Field(None, description="样本数据(前5行)")
