/**
 * 库存分析类型定义
 * 商业级库存分析引擎：ABC-XYZ分类、周转率分析、安全库存计算、供应商评估
 */

// ==================== ABC-XYZ 分析 ====================

/** ABC-XYZ 分析请求 */
export interface ABCXYZRequest {
  widget_id?: number;
  connection_id?: number;
  sql?: string;
  product_column: string;
  value_column: string;
  quantity_column: string;
  abc_thresholds?: [number, number]; // 默认 [0.7, 0.9]
  xyz_thresholds?: [number, number]; // 默认 [0.5, 1.0]
}

/** 单个 ABC 分类的汇总 */
export interface ABCClassSummary {
  count: number;
  value: number;
  pct: number;
  product_pct: number;
}

/** ABC-XYZ 分析汇总 */
export interface ABCXYZSummary {
  total_products: number;
  total_value: number;
  a_class: ABCClassSummary;
  b_class: ABCClassSummary;
  c_class: ABCClassSummary;
}

/** 9宫格矩阵数据 */
export interface ABCXYZMatrix {
  rows: ['A', 'B', 'C'];
  cols: ['X', 'Y', 'Z'];
  data: number[][];        // 3x3 矩阵，每个格子的产品数量
  percentages: number[][]; // 3x3 矩阵，每个格子的占比
  values: number[][];      // 3x3 矩阵，每个格子的价值总和
}

/** 帕累托图数据 */
export interface ParetoData {
  labels: string[];         // 产品标签
  values: number[];         // 价值
  cumulative_pct: number[]; // 累计占比（0-1）
  abc_class: string[];      // ABC 分类
}

/** 单个产品的 ABC-XYZ 分类详情 */
export interface ABCXYZDetail {
  product_id: string;
  value: number;
  quantity: number;
  cumulative_pct: number;
  cv: number;
  abc_class: 'A' | 'B' | 'C';
  xyz_class: 'X' | 'Y' | 'Z';
  combined_class: string;
}

/** ABC-XYZ 分析结果 */
export interface ABCXYZResult {
  summary: ABCXYZSummary;
  matrix: ABCXYZMatrix;
  pareto: ParetoData;
  details: ABCXYZDetail[];
  statistical_basis: Record<string, unknown>;
}

// ==================== 库存周转率分析 ====================

/** 周转率分析请求 */
export interface TurnoverRequest {
  widget_id?: number;
  connection_id?: number;
  sql?: string;
  product_column: string;
  cogs_column: string;
  inventory_column: string;
  period_column?: string;
}

/** 单个产品的周转率详情 */
export interface TurnoverDetail {
  product_id: string;
  cogs: number;
  avg_inventory: number;
  turnover_rate: number;
  days_in_inventory: number;
  health: 'good' | 'warning' | 'critical';
}

/** 周转率汇总 */
export interface TurnoverSummary {
  total_products: number;
  avg_turnover_rate: number;
  avg_days_in_inventory: number;
  good_count: number;
  warning_count: number;
  critical_count: number;
}

/** 周转率分析结果 */
export interface TurnoverResult {
  summary: TurnoverSummary;
  details: TurnoverDetail[];
  thresholds: { good: number; warning: number };
}

// ==================== 安全库存计算 ====================

/** 安全库存计算请求 */
export interface SafetyStockRequest {
  widget_id?: number;
  connection_id?: number;
  sql?: string;
  product_column: string;
  demand_column: string;
  period_column: string;
  lead_time: number;
  service_level?: number; // 默认 0.95
}

/** 单个产品的安全库存详情 */
export interface SafetyStockDetail {
  product_id: string;
  avg_demand: number;
  demand_std: number;
  safety_stock: number;
  reorder_point: number;
}

/** 安全库存汇总 */
export interface SafetyStockSummary {
  total_products: number;
  total_safety_stock: number;
  total_reorder_point: number;
  service_level: string;
}

/** 安全库存计算结果 */
export interface SafetyStockResult {
  summary: SafetyStockSummary;
  details: SafetyStockDetail[];
  statistical_basis: {
    formula: string;
    z_score: number;
    lead_time: number;
    service_level: number;
    distribution: string;
  };
}

// ==================== 供应商评估 ====================

/** 供应商评估请求 */
export interface SupplierEvaluationRequest {
  widget_id?: number;
  connection_id?: number;
  sql?: string;
  supplier_column: string;
  metrics_columns: string[];
  weights?: number[];
}

/** 单个供应商的评估详情 */
export interface SupplierDetail {
  supplier_id: string;
  metrics: Record<string, number>;
  normalized_metrics: Record<string, number>;
  weighted_score: number;
  rank: number;
  cluster?: number;
}

/** 供应商评估汇总 */
export interface SupplierSummary {
  total_suppliers: number;
  avg_score: number;
  top_supplier: string;
  cluster_count?: number;
}

/** 供应商评估结果 */
export interface SupplierResult {
  summary: SupplierSummary;
  details: SupplierDetail[];
  weights_used: Record<string, number>;
}

// ==================== 通用响应 ====================

/** 库存分析响应 */
export interface InventoryAnalysisResponse<T = unknown> {
  success: boolean;
  analysis_type: 'abc_xyz' | 'turnover' | 'safety_stock' | 'supplier_evaluation';
  result: T;
  execution_time_ms: number;
  data_rows: number;
}

// ==================== Widget 配置 ====================

/** 库存分析 Widget 配置 */
export interface InventoryAnalysisConfig {
  analysis_type: 'abc_xyz' | 'turnover' | 'safety_stock' | 'supplier_eval';
  data_source: {
    widget_id?: number;
    connection_id?: number;
    sql?: string;
  };
  column_mapping: {
    product_column?: string;
    value_column?: string;
    quantity_column?: string;
    cogs_column?: string;
    inventory_column?: string;
    demand_column?: string;
    period_column?: string;
    supplier_column?: string;
    metrics_columns?: string[];
  };
  parameters?: {
    abc_thresholds?: [number, number];
    xyz_thresholds?: [number, number];
    lead_time?: number;
    service_level?: number;
    weights?: number[];
  };
}
