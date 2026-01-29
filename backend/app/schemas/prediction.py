"""
预测分析Schema定义
优化版：增加可解释性、数据质量信息
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
    r_squared: float = Field(0, description="决定系数 R²，拟合优度")


class TrendAnalysis(BaseModel):
    """趋势分析"""
    direction: str = Field(..., description="趋势方向: up/down/stable")
    growth_rate: float = Field(..., description="增长率 (%)")
    average_value: float = Field(..., description="平均值")
    min_value: float = Field(..., description="最小值")
    max_value: float = Field(..., description="最大值")
    volatility: float = Field(0, description="波动率 (%)")
    has_seasonality: bool = Field(False, description="是否检测到季节性")
    seasonality_period: Optional[int] = Field(None, description="季节性周期（如果检测到）")


class DataQualityInfo(BaseModel):
    """数据质量信息"""
    total_points: int = Field(..., description="原始数据点数")
    valid_points: int = Field(..., description="有效数据点数")
    missing_count: int = Field(0, description="缺失值数量")
    missing_filled_method: Optional[str] = Field(None, description="缺失值填充方法")
    outlier_count: int = Field(0, description="异常值数量")
    outlier_indices: List[int] = Field(default_factory=list, description="异常值位置索引")
    date_interval: Optional[str] = Field(None, description="检测到的日期间隔（如'daily','weekly'...)")


class MethodSelectionReason(BaseModel):
    """方法选择理由"""
    selected_method: str = Field(..., description="选择的预测方法")
    reason: str = Field(..., description="选择该方法的理由")
    data_characteristics: Dict[str, Any] = Field(default_factory=dict, description="数据特征分析")
    method_scores: Dict[str, float] = Field(default_factory=dict, description="各方法评分")


class PredictionExplanation(BaseModel):
    """预测解释 - 让用户理解预测结果是怎么来的"""
    method_explanation: str = Field(..., description="算法原理说明")
    formula_used: str = Field(..., description="使用的计算公式")
    key_parameters: Dict[str, Any] = Field(default_factory=dict, description="关键参数及其值")
    calculation_steps: List[str] = Field(default_factory=list, description="计算步骤说明")
    confidence_explanation: str = Field("", description="置信区间说明")
    reliability_assessment: str = Field("", description="可靠性评估")


class PredictionResult(BaseModel):
    """预测结果 - 增强版，包含可解释性"""
    historical_data: List[PredictionDataPoint] = Field(..., description="历史数据")
    predictions: List[PredictionDataPoint] = Field(..., description="预测数据")
    method_used: PredictionMethod = Field(..., description="实际使用的预测方法")
    accuracy_metrics: AccuracyMetrics = Field(..., description="准确性指标")
    trend_analysis: TrendAnalysis = Field(..., description="趋势分析")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")
    # 新增可解释性字段
    data_quality: Optional[DataQualityInfo] = Field(None, description="数据质量信息")
    method_selection: Optional[MethodSelectionReason] = Field(None, description="方法选择理由")
    explanation: Optional[PredictionExplanation] = Field(None, description="预测解释")


class PredictionColumnsResponse(BaseModel):
    """可用于预测的列信息"""
    date_columns: List[str] = Field(default_factory=list, description="时间类型列")
    value_columns: List[str] = Field(default_factory=list, description="数值类型列")
    sample_data: Optional[List[Dict[str, Any]]] = Field(None, description="样本数据(前5行)")
