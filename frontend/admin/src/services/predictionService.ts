/**
 * 预测服务
 * P2功能：数据预测相关的API调用
 */
import axios from 'axios';
import type {
  PredictionRequest,
  PredictionResult,
  PredictionColumnsResponse,
} from '../types/prediction';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const predictionService = {
  /**
   * 创建预测分析
   */
  async createPrediction(
    dashboardId: number,
    request: PredictionRequest
  ): Promise<PredictionResult> {
    const response = await api.post(`/dashboards/${dashboardId}/predict`, {
      widget_id: request.widgetId,
      date_column: request.dateColumn,
      value_column: request.valueColumn,
      periods: request.periods,
      method: request.method,
      confidence_level: request.confidenceLevel,
    });

    const data = response.data;

    return {
      historicalData: (data.historical_data || []).map((p: any) => ({
        date: p.date,
        value: p.value,
        lowerBound: p.lower_bound,
        upperBound: p.upper_bound,
        isPrediction: p.is_prediction || false,
      })),
      predictions: (data.predictions || []).map((p: any) => ({
        date: p.date,
        value: p.value,
        lowerBound: p.lower_bound,
        upperBound: p.upper_bound,
        isPrediction: p.is_prediction || true,
      })),
      methodUsed: data.method_used,
      accuracyMetrics: {
        mape: data.accuracy_metrics?.mape || 0,
        rmse: data.accuracy_metrics?.rmse || 0,
        mae: data.accuracy_metrics?.mae || 0,
      },
      trendAnalysis: {
        direction: data.trend_analysis?.direction || 'stable',
        growthRate: data.trend_analysis?.growth_rate || 0,
        averageValue: data.trend_analysis?.average_value || 0,
        minValue: data.trend_analysis?.min_value || 0,
        maxValue: data.trend_analysis?.max_value || 0,
        volatility: data.trend_analysis?.volatility || 0,
      },
      generatedAt: data.generated_at,
    };
  },

  /**
   * 获取可用于预测的列
   */
  async getPredictionColumns(widgetId: number): Promise<PredictionColumnsResponse> {
    const response = await api.get(`/widgets/${widgetId}/prediction-columns`);
    const data = response.data;

    return {
      dateColumns: data.date_columns || [],
      valueColumns: data.value_columns || [],
      sampleData: data.sample_data,
    };
  },
};

export default predictionService;
