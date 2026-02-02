/**
 * 预测服务
 * P2功能：数据预测相关的API调用
 */
import axios from 'axios';
import type {
  PredictionRequest,
  PredictionResult,
  PredictionColumnsResponse,
  CategoricalAnalysisRequest,
  CategoricalAnalysisResult,
} from '../types/prediction';

const API_URL = process.env.REACT_APP_API_URL || 'http://192.168.13.163:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
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
        rSquared: data.accuracy_metrics?.r_squared,
      },
      trendAnalysis: {
        direction: data.trend_analysis?.direction || 'stable',
        growthRate: data.trend_analysis?.growth_rate || 0,
        averageValue: data.trend_analysis?.average_value || 0,
        minValue: data.trend_analysis?.min_value || 0,
        maxValue: data.trend_analysis?.max_value || 0,
        volatility: data.trend_analysis?.volatility || 0,
        hasSeasonality: data.trend_analysis?.has_seasonality,
        seasonalityPeriod: data.trend_analysis?.seasonality_period,
      },
      generatedAt: data.generated_at,
      // 新增可解释性字段
      dataQuality: data.data_quality ? {
        totalPoints: data.data_quality.total_points,
        validPoints: data.data_quality.valid_points,
        missingCount: data.data_quality.missing_count || 0,
        missingFilledMethod: data.data_quality.missing_filled_method,
        outlierCount: data.data_quality.outlier_count || 0,
        outlierIndices: data.data_quality.outlier_indices || [],
        dateInterval: data.data_quality.date_interval,
      } : undefined,
      methodSelectionReason: data.method_selection ? {
        selectedMethod: data.method_selection.selected_method,
        reason: data.method_selection.reason,
        dataCharacteristics: data.method_selection.data_characteristics || {},
        methodScores: data.method_selection.method_scores || {},
      } : undefined,
      explanation: data.explanation ? {
        methodExplanation: data.explanation.method_explanation,
        formulaUsed: data.explanation.formula_used,
        keyParameters: data.explanation.key_parameters || {},
        calculationSteps: data.explanation.calculation_steps || [],
        confidenceExplanation: data.explanation.confidence_explanation,
        reliabilityAssessment: data.explanation.reliability_assessment,
      } : undefined,
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
      categoryColumns: data.category_columns || [],
      sampleData: data.sample_data,
      suggestedAnalysis: data.suggested_analysis || 'none',
    };
  },

  /**
   * 分类数据统计分析
   */
  async analyzeCategorical(
    widgetId: number,
    request: CategoricalAnalysisRequest
  ): Promise<CategoricalAnalysisResult> {
    const response = await api.post(`/widgets/${widgetId}/categorical-analysis`, {
      widget_id: request.widgetId,
      category_column: request.categoryColumn,
      value_column: request.valueColumn,
      include_outliers: request.includeOutliers ?? true,
    });
    return response.data;
  },
};

export default predictionService;
