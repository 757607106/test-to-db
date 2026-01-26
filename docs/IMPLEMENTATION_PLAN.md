# BI仪表盘三大核心功能实施计划

> 版本: 1.0 | 创建日期: 2026-01-26 | 状态: 已确认

## 概述

本文档定义了 Chat-to-Insight BI系统三大核心功能的详细实施计划：
- **P0**: 数据洞察溯源功能
- **P1**: 动态数据刷新机制
- **P2**: 数据预测功能

技术栈：LangGraph + LangChain v0.3+ + FastAPI + React

---

## 实施时间线

```
P0 数据洞察 (5天)
├── 后端API开发 (2天)
├── 前端组件开发 (2天)
└── 集成测试 (1天)

P1 动态刷新 (5天)
├── 后端API开发 (2天)
├── 前端组件开发 (2天)
└── 集成测试 (1天)

P2 数据预测 (7天)
├── 后端服务开发 (3天)
├── 前端可视化 (3天)
└── 集成测试 (1天)
```

---

## P0: 数据洞察溯源功能

### 目标
实现准确且全面的数据洞察，能够追溯数据来源，明确展示数据生成的逻辑和原因。

### 后端实现

#### 1. Schema 定义 (`backend/app/schemas/dashboard_insight.py`)

```python
class InsightLineage(BaseModel):
    """数据血缘追踪"""
    source_tables: List[str] = Field(..., description="数据来源表")
    generated_sql: str = Field(..., description="生成的SQL语句")
    sql_generation_trace: Dict[str, Any] = Field(
        default_factory=dict, 
        description="SQL生成过程追踪"
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行元数据(耗时、缓存命中等)"
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
    widget_id: int
    insights: InsightResult
    lineage: InsightLineage
    confidence_score: float = Field(ge=0, le=1, description="置信度评分")
    analysis_method: str = Field(..., description="分析方法说明")
    generated_at: datetime
```

#### 2. API 端点 (`backend/app/api/api_v1/endpoints/dashboard_insights.py`)

```python
@router.get("/dashboards/{dashboard_id}/insights/detail")
async def get_insight_detail(
    dashboard_id: int,
    widget_id: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_user_id: int = Depends(deps.get_current_user_id)
) -> EnhancedInsightResponse:
    """获取洞察详情（含数据溯源）"""
    pass
```

#### 3. 服务层修改 (`backend/app/services/dashboard_insight_service.py`)

在 `insight_analyzer_node` 中收集溯源数据：
- 记录 source_tables
- 保存 generated_sql
- 追踪 SQL 生成过程
- 记录执行元数据

### 前端实现

#### 1. 类型定义 (`frontend/admin/src/types/dashboard.ts`)

```typescript
export interface InsightLineage {
  sourceTables: string[];
  generatedSql: string;
  sqlGenerationTrace: Record<string, any>;
  executionMetadata: {
    executionTimeMs: number;
    fromCache: boolean;
    rowCount: number;
  };
  dataTransformations: string[];
}

export interface EnhancedInsightResponse {
  widgetId: number;
  insights: InsightResult;
  lineage: InsightLineage;
  confidenceScore: number;
  analysisMethod: string;
  generatedAt: string;
}
```

#### 2. 组件 (`frontend/admin/src/components/InsightLineagePanel.tsx`)

```typescript
interface InsightLineagePanelProps {
  lineage: InsightLineage;
  onViewSql: () => void;
  onViewTables: (tables: string[]) => void;
}
```

### 实施步骤

| 步骤 | 任务 | 负责文件 | 预估工时 |
|-----|------|---------|---------|
| P0.1 | 扩展 InsightLineage Schema | `schemas/dashboard_insight.py` | 2h |
| P0.2 | 修改 insight_analyzer_node 收集溯源 | `agents/dashboard_insight_graph.py` | 4h |
| P0.3 | 新增 /insights/detail API | `api/endpoints/dashboard_insights.py` | 2h |
| P0.4 | 前端类型定义 | `types/dashboard.ts` | 1h |
| P0.5 | InsightLineagePanel 组件 | `components/InsightLineagePanel.tsx` | 4h |
| P0.6 | 集成到 Dashboard 页面 | `pages/DashboardDetail.tsx` | 2h |
| P0.7 | 单元测试 + 集成测试 | `tests/` | 3h |

---

## P1: 动态数据刷新机制

### 目标
实现页面自定义时间间隔刷新功能，以及全局报表的一键刷新功能。

### 后端实现

#### 1. Schema 定义 (`backend/app/schemas/dashboard.py`)

```python
class RefreshConfig(BaseModel):
    """刷新配置"""
    enabled: bool = False
    interval_seconds: int = Field(300, ge=30, le=86400, description="刷新间隔(秒)")
    auto_refresh_widget_ids: List[int] = Field(
        default_factory=list,
        description="启用自动刷新的Widget ID列表"
    )
    last_global_refresh: Optional[datetime] = None


class GlobalRefreshRequest(BaseModel):
    """全局刷新请求"""
    force: bool = Field(False, description="强制刷新(忽略缓存)")
    widget_ids: Optional[List[int]] = Field(None, description="指定刷新的Widget")


class WidgetRefreshResult(BaseModel):
    """单个Widget刷新结果"""
    widget_id: int
    success: bool
    duration_ms: int
    error: Optional[str] = None
    from_cache: bool = False


class GlobalRefreshResponse(BaseModel):
    """全局刷新响应"""
    success_count: int
    failed_count: int
    results: Dict[int, WidgetRefreshResult]
    total_duration_ms: int
    refresh_timestamp: datetime
```

#### 2. API 端点 (`backend/app/api/api_v1/endpoints/dashboards.py`)

```python
@router.get("/dashboards/{dashboard_id}/refresh/config")
async def get_refresh_config(dashboard_id: int) -> RefreshConfig:
    """获取刷新配置"""
    pass

@router.put("/dashboards/{dashboard_id}/refresh/config")
async def update_refresh_config(
    dashboard_id: int, 
    config: RefreshConfig
) -> RefreshConfig:
    """更新刷新配置"""
    pass

@router.post("/dashboards/{dashboard_id}/refresh/global")
async def global_refresh(
    dashboard_id: int,
    request: GlobalRefreshRequest
) -> GlobalRefreshResponse:
    """全局刷新所有Widget"""
    pass
```

#### 3. 服务层 (`backend/app/services/dashboard_refresh_service.py`)

```python
class DashboardRefreshService:
    """Dashboard刷新服务"""
    
    async def global_refresh(
        self,
        db: Session,
        dashboard_id: int,
        force: bool = False,
        widget_ids: Optional[List[int]] = None
    ) -> GlobalRefreshResponse:
        """执行全局刷新"""
        pass
    
    async def refresh_widget(
        self,
        db: Session,
        widget_id: int,
        force: bool = False
    ) -> WidgetRefreshResult:
        """刷新单个Widget"""
        pass
```

### 前端实现

#### 1. 类型定义 (`frontend/admin/src/types/dashboard.ts`)

```typescript
export interface RefreshConfig {
  enabled: boolean;
  intervalSeconds: number;
  autoRefreshWidgetIds: number[];
  lastGlobalRefresh?: string;
}

export interface GlobalRefreshResponse {
  successCount: number;
  failedCount: number;
  results: Record<number, WidgetRefreshResult>;
  totalDurationMs: number;
  refreshTimestamp: string;
}
```

#### 2. Hook (`frontend/admin/src/hooks/useAutoRefresh.ts`)

```typescript
export function useAutoRefresh(
  dashboardId: number,
  config: RefreshConfig,
  onRefresh: () => Promise<void>
) {
  // 自动刷新逻辑
}
```

#### 3. 组件 (`frontend/admin/src/components/RefreshControlPanel.tsx`)

```typescript
interface RefreshControlPanelProps {
  dashboardId: number;
  config: RefreshConfig;
  onConfigChange: (config: RefreshConfig) => void;
  onGlobalRefresh: () => void;
  isRefreshing: boolean;
  lastRefreshTime?: string;
}
```

### 实施步骤

| 步骤 | 任务 | 负责文件 | 预估工时 |
|-----|------|---------|---------|
| P1.1 | 新增 RefreshConfig Schema | `schemas/dashboard.py` | 1h |
| P1.2 | Dashboard 模型添加 refresh_config | `models/dashboard.py` | 1h |
| P1.3 | 数据库迁移 | `alembic/versions/` | 1h |
| P1.4 | 实现 DashboardRefreshService | `services/dashboard_refresh_service.py` | 4h |
| P1.5 | 新增刷新 API 端点 | `api/endpoints/dashboards.py` | 2h |
| P1.6 | 前端类型定义 | `types/dashboard.ts` | 1h |
| P1.7 | useAutoRefresh Hook | `hooks/useAutoRefresh.ts` | 2h |
| P1.8 | RefreshControlPanel 组件 | `components/RefreshControlPanel.tsx` | 3h |
| P1.9 | 集成测试 | `tests/` | 2h |

---

## P2: 数据预测功能

### 目标
在现有数据基础上增加预测分析能力，支持时间序列预测和趋势分析。

### 后端实现

#### 1. Schema 定义 (`backend/app/schemas/prediction.py`)

```python
from enum import Enum

class PredictionMethod(str, Enum):
    AUTO = "auto"
    LINEAR = "linear"
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"


class PredictionRequest(BaseModel):
    """预测请求"""
    widget_id: int = Field(..., description="数据来源Widget")
    date_column: str = Field(..., description="时间列名")
    value_column: str = Field(..., description="预测目标列名")
    periods: int = Field(7, ge=1, le=365, description="预测周期数")
    method: PredictionMethod = Field(
        PredictionMethod.AUTO, 
        description="预测方法"
    )
    confidence_level: float = Field(0.95, ge=0.5, le=0.99)


class PredictionDataPoint(BaseModel):
    """预测数据点"""
    date: str
    value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    is_prediction: bool = False


class AccuracyMetrics(BaseModel):
    """准确性指标"""
    mape: float = Field(..., description="平均绝对百分比误差")
    rmse: float = Field(..., description="均方根误差")
    mae: float = Field(..., description="平均绝对误差")


class TrendAnalysis(BaseModel):
    """趋势分析"""
    direction: str = Field(..., description="趋势方向: up/down/stable")
    growth_rate: float = Field(..., description="增长率")
    seasonality: Optional[Dict[str, Any]] = None
    change_points: List[Dict[str, Any]] = Field(default_factory=list)


class PredictionResult(BaseModel):
    """预测结果"""
    historical_data: List[PredictionDataPoint]
    predictions: List[PredictionDataPoint]
    method_used: PredictionMethod
    accuracy_metrics: AccuracyMetrics
    trend_analysis: TrendAnalysis
    generated_at: datetime
```

#### 2. 服务层 (`backend/app/services/prediction_service.py`)

```python
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

class PredictionService:
    """预测分析服务"""
    
    async def predict(
        self,
        data: List[Dict[str, Any]],
        date_column: str,
        value_column: str,
        periods: int,
        method: str = "auto",
        confidence_level: float = 0.95
    ) -> PredictionResult:
        """执行预测分析"""
        pass
    
    def _select_best_method(self, df: pd.DataFrame) -> str:
        """根据数据特征自动选择最佳预测方法"""
        pass
    
    def _linear_prediction(
        self, 
        df: pd.DataFrame, 
        periods: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """线性回归预测"""
        pass
    
    def _moving_average_prediction(
        self,
        df: pd.DataFrame,
        periods: int,
        window: int = 7
    ) -> Tuple[List[float], List[float], List[float]]:
        """移动平均预测"""
        pass
    
    def _exponential_smoothing_prediction(
        self,
        df: pd.DataFrame,
        periods: int,
        alpha: float = 0.3
    ) -> Tuple[List[float], List[float], List[float]]:
        """指数平滑预测"""
        pass
    
    def _calculate_accuracy_metrics(
        self,
        actual: List[float],
        predicted: List[float]
    ) -> AccuracyMetrics:
        """计算预测准确性指标"""
        pass
    
    def _analyze_trend(
        self,
        df: pd.DataFrame
    ) -> TrendAnalysis:
        """分析数据趋势"""
        pass
```

#### 3. API 端点 (`backend/app/api/api_v1/endpoints/predictions.py`)

```python
router = APIRouter()

@router.post("/dashboards/{dashboard_id}/predict")
async def create_prediction(
    dashboard_id: int,
    request: PredictionRequest,
    db: Session = Depends(deps.get_db)
) -> PredictionResult:
    """创建预测分析"""
    pass

@router.get("/widgets/{widget_id}/prediction-columns")
async def get_prediction_columns(
    widget_id: int,
    db: Session = Depends(deps.get_db)
) -> Dict[str, List[str]]:
    """获取可用于预测的列（时间列和数值列）"""
    pass
```

### 前端实现

#### 1. 类型定义 (`frontend/admin/src/types/prediction.ts`)

```typescript
export type PredictionMethod = 'auto' | 'linear' | 'moving_average' | 'exponential_smoothing';

export interface PredictionRequest {
  widgetId: number;
  dateColumn: string;
  valueColumn: string;
  periods: number;
  method: PredictionMethod;
  confidenceLevel: number;
}

export interface PredictionDataPoint {
  date: string;
  value: number;
  lowerBound?: number;
  upperBound?: number;
  isPrediction: boolean;
}

export interface PredictionResult {
  historicalData: PredictionDataPoint[];
  predictions: PredictionDataPoint[];
  methodUsed: PredictionMethod;
  accuracyMetrics: {
    mape: number;
    rmse: number;
    mae: number;
  };
  trendAnalysis: {
    direction: 'up' | 'down' | 'stable';
    growthRate: number;
    seasonality?: Record<string, any>;
  };
  generatedAt: string;
}
```

#### 2. 组件

**PredictionConfigPanel.tsx**
```typescript
interface PredictionConfigPanelProps {
  widgetId: number;
  availableColumns: {
    dateColumns: string[];
    valueColumns: string[];
  };
  onPredict: (config: PredictionRequest) => void;
  isLoading: boolean;
}
```

**PredictionChart.tsx**
```typescript
interface PredictionChartProps {
  result: PredictionResult;
  showConfidenceInterval: boolean;
  onExport: () => void;
}
```

### 实施步骤

| 步骤 | 任务 | 负责文件 | 预估工时 |
|-----|------|---------|---------|
| P2.1 | 新增 prediction Schema | `schemas/prediction.py` | 2h |
| P2.2 | 实现 PredictionService 核心逻辑 | `services/prediction_service.py` | 8h |
| P2.3 | 新增预测 API 端点 | `api/endpoints/predictions.py` | 3h |
| P2.4 | 注册 API 路由 | `api/api_v1/api.py` | 0.5h |
| P2.5 | 前端类型定义 | `types/prediction.ts` | 1h |
| P2.6 | PredictionConfigPanel 组件 | `components/PredictionConfigPanel.tsx` | 3h |
| P2.7 | PredictionChart 组件 (Recharts) | `components/PredictionChart.tsx` | 5h |
| P2.8 | 集成到 Widget 详情页 | `pages/WidgetDetail.tsx` | 2h |
| P2.9 | 单元测试 + 集成测试 | `tests/` | 4h |

---

## API 集成测试清单

### P0 测试用例

| ID | 测试项 | 预期结果 |
|----|-------|---------|
| P0-T1 | GET /insights/detail 返回溯源 | lineage 字段不为空 |
| P0-T2 | source_tables 正确性 | 与 SQL 中的表名一致 |
| P0-T3 | execution_metadata 完整性 | 包含 executionTimeMs |
| P0-T4 | 无权限访问 | 返回 403 |

### P1 测试用例

| ID | 测试项 | 预期结果 |
|----|-------|---------|
| P1-T1 | PUT /refresh/config 持久化 | GET 返回相同配置 |
| P1-T2 | POST /refresh/global 刷新全部 | success_count = widget数量 |
| P1-T3 | 指定 widget_ids 刷新 | 只刷新指定的 Widget |
| P1-T4 | force=true 忽略缓存 | from_cache=false |
| P1-T5 | 并发刷新 | 无竞态条件 |

### P2 测试用例

| ID | 测试项 | 预期结果 |
|----|-------|---------|
| P2-T1 | POST /predict 返回格式 | 包含 predictions 数组 |
| P2-T2 | 预测准确性 | MAPE < 30% |
| P2-T3 | 数据不足 | 返回 400 + 错误信息 |
| P2-T4 | 非时间列 | 返回 400 + 错误信息 |
| P2-T5 | method=auto 自动选择 | method_used 有值 |

---

## 依赖项

### 后端依赖

```txt
# requirements.txt 新增
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0      # 用于统计计算
statsmodels>=0.14.0  # 用于时间序列分析（可选）
```

### 前端依赖

```json
{
  "recharts": "^2.10.0",
  "@tanstack/react-query": "^5.0.0"
}
```

---

## 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|-----|-----|---------|
| 预测算法复杂度 | P2延期 | 优先实现简单算法(线性/移动平均) |
| 大数据量刷新慢 | 用户体验差 | 实现增量刷新 + 缓存策略 |
| 前后端联调问题 | 集成延期 | 先定义好 Schema，Mock 开发 |

---

## 验收标准

### P0 验收
- [ ] 洞察详情页展示数据来源表
- [ ] 可查看生成的 SQL 语句
- [ ] 显示执行耗时和缓存状态

### P1 验收
- [ ] 一键刷新所有 Widget
- [ ] 可配置自动刷新间隔
- [ ] 刷新状态实时显示
- [ ] 刷新失败有明确提示

### P2 验收
- [ ] 支持选择时间列和值列
- [ ] 预测结果图表展示
- [ ] 显示置信区间
- [ ] 显示预测准确性指标
