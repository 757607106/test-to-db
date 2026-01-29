"""
库存分析 Schema 定义
商业级库存分析引擎：ABC-XYZ分类、周转率分析、安全库存计算、供应商评估
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 枚举定义 ====================

class ABCClass(str, Enum):
    """ABC 分类"""
    A = "A"  # 高价值（累计贡献70%）
    B = "B"  # 中价值（累计贡献70%-90%）
    C = "C"  # 低价值（累计贡献90%-100%）


class XYZClass(str, Enum):
    """XYZ 分类（需求稳定性）"""
    X = "X"  # 稳定（CV < 0.5）
    Y = "Y"  # 波动（0.5 <= CV < 1.0）
    Z = "Z"  # 不稳定（CV >= 1.0）


# ==================== ABC-XYZ 分析 ====================

class ABCXYZRequest(BaseModel):
    """ABC-XYZ 分析请求"""
    widget_id: Optional[int] = Field(None, description="数据来源 Widget ID")
    connection_id: Optional[int] = Field(None, description="数据库连接 ID")
    sql: Optional[str] = Field(None, description="自定义 SQL 查询")
    
    # 列映射
    product_column: str = Field(..., description="产品/SKU 标识列")
    value_column: str = Field(..., description="价值列（如销售额、成本）")
    quantity_column: str = Field(..., description="数量列（用于计算变异系数）")
    
    # 可选配置
    abc_thresholds: List[float] = Field(
        default=[0.7, 0.9],
        description="ABC 分类阈值，默认 [0.7, 0.9] 对应 70%/90%"
    )
    xyz_thresholds: List[float] = Field(
        default=[0.5, 1.0],
        description="XYZ 分类阈值（变异系数），默认 [0.5, 1.0]"
    )


class ABCClassSummary(BaseModel):
    """单个 ABC 分类的汇总"""
    count: int = Field(..., description="产品数量")
    value: float = Field(..., description="总价值")
    pct: float = Field(..., description="价值占比")
    product_pct: float = Field(..., description="产品数量占比")


class ABCXYZSummary(BaseModel):
    """ABC-XYZ 分析汇总"""
    total_products: int = Field(..., description="总产品数")
    total_value: float = Field(..., description="总价值")
    a_class: ABCClassSummary = Field(..., description="A 类汇总")
    b_class: ABCClassSummary = Field(..., description="B 类汇总")
    c_class: ABCClassSummary = Field(..., description="C 类汇总")


class ABCXYZMatrix(BaseModel):
    """9宫格矩阵数据"""
    rows: List[str] = Field(default=["A", "B", "C"], description="行标签")
    cols: List[str] = Field(default=["X", "Y", "Z"], description="列标签")
    data: List[List[int]] = Field(..., description="3x3 矩阵，每个格子的产品数量")
    percentages: List[List[float]] = Field(..., description="3x3 矩阵，每个格子的占比")
    values: List[List[float]] = Field(..., description="3x3 矩阵，每个格子的价值总和")


class ParetoData(BaseModel):
    """帕累托图数据"""
    labels: List[str] = Field(..., description="产品标签")
    values: List[float] = Field(..., description="价值")
    cumulative_pct: List[float] = Field(..., description="累计占比（0-1）")
    abc_class: List[str] = Field(..., description="ABC 分类")


class ABCXYZDetail(BaseModel):
    """单个产品的 ABC-XYZ 分类详情"""
    product_id: str = Field(..., description="产品标识")
    value: float = Field(..., description="价值")
    quantity: float = Field(..., description="数量")
    cumulative_pct: float = Field(..., description="累计价值占比")
    cv: float = Field(..., description="变异系数")
    abc_class: str = Field(..., description="ABC 分类")
    xyz_class: str = Field(..., description="XYZ 分类")
    combined_class: str = Field(..., description="组合分类（如 AX, BY）")


class ABCXYZResult(BaseModel):
    """ABC-XYZ 分析结果"""
    summary: ABCXYZSummary = Field(..., description="汇总统计")
    matrix: ABCXYZMatrix = Field(..., description="9宫格矩阵")
    pareto: ParetoData = Field(..., description="帕累托图数据")
    details: List[ABCXYZDetail] = Field(..., description="详细分类列表")
    
    # 统计依据
    statistical_basis: Dict[str, Any] = Field(
        default_factory=dict,
        description="统计方法说明"
    )


# ==================== 库存周转率分析 ====================

class TurnoverRequest(BaseModel):
    """周转率分析请求"""
    widget_id: Optional[int] = Field(None, description="数据来源 Widget ID")
    connection_id: Optional[int] = Field(None, description="数据库连接 ID")
    sql: Optional[str] = Field(None, description="自定义 SQL 查询")
    
    # 列映射
    product_column: str = Field(..., description="产品标识列")
    cogs_column: str = Field(..., description="销售成本列")
    inventory_column: str = Field(..., description="库存价值列")
    period_column: Optional[str] = Field(None, description="时间周期列")


class TurnoverDetail(BaseModel):
    """单个产品的周转率详情"""
    product_id: str = Field(..., description="产品标识")
    cogs: float = Field(..., description="销售成本")
    avg_inventory: float = Field(..., description="平均库存")
    turnover_rate: float = Field(..., description="周转率")
    days_in_inventory: float = Field(..., description="库存天数")
    health: str = Field(..., description="健康度：good/warning/critical")


class TurnoverSummary(BaseModel):
    """周转率汇总"""
    total_products: int = Field(..., description="产品数量")
    avg_turnover_rate: float = Field(..., description="平均周转率")
    avg_days_in_inventory: float = Field(..., description="平均库存天数")
    good_count: int = Field(..., description="健康产品数")
    warning_count: int = Field(..., description="警告产品数")
    critical_count: int = Field(..., description="严重产品数")


class TurnoverResult(BaseModel):
    """周转率分析结果"""
    summary: TurnoverSummary = Field(..., description="汇总统计")
    details: List[TurnoverDetail] = Field(..., description="详细列表")
    thresholds: Dict[str, float] = Field(
        default={"good": 30, "warning": 90},
        description="库存天数阈值"
    )


# ==================== 安全库存计算 ====================

class SafetyStockRequest(BaseModel):
    """安全库存计算请求"""
    widget_id: Optional[int] = Field(None, description="数据来源 Widget ID")
    connection_id: Optional[int] = Field(None, description="数据库连接 ID")
    sql: Optional[str] = Field(None, description="自定义 SQL 查询")
    
    # 列映射
    product_column: str = Field(..., description="产品标识列")
    demand_column: str = Field(..., description="需求量列")
    period_column: str = Field(..., description="时间周期列")
    
    # 参数
    lead_time: float = Field(..., ge=0, description="前置时间（天）")
    service_level: float = Field(0.95, ge=0.5, le=0.99, description="服务水平")


class SafetyStockDetail(BaseModel):
    """单个产品的安全库存详情"""
    product_id: str = Field(..., description="产品标识")
    avg_demand: float = Field(..., description="平均需求")
    demand_std: float = Field(..., description="需求标准差")
    safety_stock: float = Field(..., description="安全库存")
    reorder_point: float = Field(..., description="再订货点")


class SafetyStockSummary(BaseModel):
    """安全库存汇总"""
    total_products: int = Field(..., description="产品数量")
    total_safety_stock: float = Field(..., description="安全库存总量")
    total_reorder_point: float = Field(..., description="再订货点总量")
    service_level: str = Field(..., description="服务水平")


class SafetyStockResult(BaseModel):
    """安全库存计算结果"""
    summary: SafetyStockSummary = Field(..., description="汇总统计")
    details: List[SafetyStockDetail] = Field(..., description="详细列表")
    statistical_basis: Dict[str, Any] = Field(
        default_factory=dict,
        description="统计依据（Z值、公式等）"
    )


# ==================== 供应商评估 ====================

class SupplierEvaluationRequest(BaseModel):
    """供应商评估请求"""
    widget_id: Optional[int] = Field(None, description="数据来源 Widget ID")
    connection_id: Optional[int] = Field(None, description="数据库连接 ID")
    sql: Optional[str] = Field(None, description="自定义 SQL 查询")
    
    # 列映射
    supplier_column: str = Field(..., description="供应商标识列")
    metrics_columns: List[str] = Field(..., description="评估指标列")
    weights: Optional[List[float]] = Field(None, description="指标权重（默认等权）")


class SupplierDetail(BaseModel):
    """单个供应商的评估详情"""
    supplier_id: str = Field(..., description="供应商标识")
    metrics: Dict[str, float] = Field(..., description="各指标值")
    normalized_metrics: Dict[str, float] = Field(..., description="标准化后的指标值")
    weighted_score: float = Field(..., description="加权得分")
    rank: int = Field(..., description="排名")
    cluster: Optional[int] = Field(None, description="聚类分组")


class SupplierSummary(BaseModel):
    """供应商评估汇总"""
    total_suppliers: int = Field(..., description="供应商数量")
    avg_score: float = Field(..., description="平均得分")
    top_supplier: str = Field(..., description="最佳供应商")
    cluster_count: Optional[int] = Field(None, description="聚类数量")


class SupplierResult(BaseModel):
    """供应商评估结果"""
    summary: SupplierSummary = Field(..., description="汇总统计")
    details: List[SupplierDetail] = Field(..., description="详细列表")
    weights_used: Dict[str, float] = Field(..., description="使用的权重")


# ==================== 通用响应 ====================

class InventoryAnalysisResponse(BaseModel):
    """库存分析通用响应"""
    success: bool = Field(True, description="是否成功")
    analysis_type: str = Field(..., description="分析类型")
    result: Any = Field(..., description="分析结果")
    execution_time_ms: int = Field(..., description="执行时间（毫秒）")
    data_rows: int = Field(..., description="分析数据行数")
