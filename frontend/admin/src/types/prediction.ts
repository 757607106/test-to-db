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
}

export interface TrendAnalysis {
  direction: 'up' | 'down' | 'stable';
  growthRate: number;
  averageValue: number;
  minValue: number;
  maxValue: number;
  volatility: number;
}

export interface PredictionResult {
  historicalData: PredictionDataPoint[];
  predictions: PredictionDataPoint[];
  methodUsed: PredictionMethod;
  accuracyMetrics: AccuracyMetrics;
  trendAnalysis: TrendAnalysis;
  generatedAt: string;
}

export interface PredictionColumnsResponse {
  dateColumns: string[];
  valueColumns: string[];
  sampleData?: Record<string, any>[];
}
