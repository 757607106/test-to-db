/**
 * 预测分析类型定义
 * P2功能：数据预测相关的类型
 */

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

export interface AccuracyMetrics {
  mape: number;
  rmse: number;
  mae: number;
  rSquared?: number;
}

export interface TrendAnalysis {
  direction: 'up' | 'down' | 'stable';
  growthRate: number;
  averageValue: number;
  minValue: number;
  maxValue: number;
  volatility: number;
  hasSeasonality?: boolean;
  seasonalityPeriod?: number;
}

/** 数据质量信息 */
export interface DataQualityInfo {
  totalPoints: number;
  validPoints: number;
  missingCount: number;
  missingFilledMethod?: string;
  outlierCount: number;
  outlierIndices: number[];
  dateInterval?: string;
}

/** 方法选择理由 */
export interface MethodSelectionReason {
  selectedMethod: string;
  reason: string;
  dataCharacteristics: Record<string, any>;
  methodScores: Record<string, number>;
}

/** 预测解释 - 让用户知道预测结果怎么来的 */
export interface PredictionExplanation {
  methodExplanation: string;
  formulaUsed: string;
  keyParameters: Record<string, any>;
  calculationSteps: string[];
  confidenceExplanation: string;
  reliabilityAssessment: string;
}

export interface PredictionResult {
  historicalData: PredictionDataPoint[];
  predictions: PredictionDataPoint[];
  methodUsed: PredictionMethod;
  accuracyMetrics: AccuracyMetrics;
  trendAnalysis: TrendAnalysis;
  generatedAt: string;
  // 新增可解释性字段
  dataQuality?: DataQualityInfo;
  methodSelectionReason?: MethodSelectionReason;
  explanation?: PredictionExplanation;
}

export interface PredictionColumnsResponse {
  dateColumns: string[];
  valueColumns: string[];
  sampleData?: Record<string, any>[];
}
