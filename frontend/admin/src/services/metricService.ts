/**
 * 指标库服务
 * 提供指标CRUD操作的API调用
 */
import axios from 'axios';

// 动态获取 API 地址
const getApiUrl = (): string => {
  if (process.env.REACT_APP_API_URL) return process.env.REACT_APP_API_URL;
  const hostname = window.location.hostname;
  return (hostname === 'localhost' || hostname === '127.0.0.1') 
    ? 'http://localhost:8000/api' 
    : 'http://192.168.13.163:8000/api';
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 指标类型
export interface Metric {
  id: string;
  name: string;
  business_name?: string;
  description?: string;
  formula: string;
  aggregation: string;
  source_table: string;
  source_column: string;
  dimension_columns: string[];
  time_column?: string;
  category?: string;
  tags: string[];
  unit?: string;
  decimal_places: number;
  connection_id: number;
  created_at: string;
  updated_at?: string;
}

export interface MetricCreate {
  name: string;
  business_name?: string;
  description?: string;
  formula: string;
  aggregation?: string;
  source_table: string;
  source_column: string;
  dimension_columns?: string[];
  time_column?: string;
  category?: string;
  tags?: string[];
  unit?: string;
  decimal_places?: number;
  connection_id: number;
}

// 告警规则类型
export interface MetricAlert {
  id: string;
  metric_id: string;
  name: string;
  alert_type: 'threshold' | 'yoy' | 'mom';
  condition: 'gt' | 'lt' | 'gte' | 'lte' | 'eq';
  threshold_value?: number;
  change_percent?: number;
  enabled: boolean;
  notify_channels: string[];
  created_at: string;
  last_triggered_at?: string;
  trigger_count: number;
}

export interface MetricAlertCreate {
  metric_id: string;
  name: string;
  alert_type: 'threshold' | 'yoy' | 'mom';
  condition: 'gt' | 'lt' | 'gte' | 'lte' | 'eq';
  threshold_value?: number;
  change_percent?: number;
  enabled?: boolean;
  notify_channels?: string[];
}

export const metricService = {
  // 获取指标列表
  async listMetrics(connectionId: number, category?: string): Promise<Metric[]> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    if (category) params.append('category', category);
    
    const response = await api.get(`/semantic-layer/metrics?${params}`);
    return response.data;
  },

  // 获取单个指标
  async getMetric(id: string): Promise<Metric> {
    const response = await api.get(`/semantic-layer/metrics/${id}`);
    return response.data;
  },

  // 创建指标
  async createMetric(data: MetricCreate): Promise<Metric> {
    const response = await api.post('/semantic-layer/metrics', data);
    return response.data;
  },

  // 更新指标
  async updateMetric(id: string, data: Partial<MetricCreate>): Promise<Metric> {
    const response = await api.put(`/semantic-layer/metrics/${id}`, data);
    return response.data;
  },

  // 删除指标
  async deleteMetric(id: string): Promise<void> {
    await api.delete(`/semantic-layer/metrics/${id}`);
  },

  // 搜索指标
  async searchMetrics(connectionId: number, query: string): Promise<Metric[]> {
    const response = await api.get(`/semantic-layer/metrics/search`, {
      params: { connection_id: connectionId, q: query },
    });
    return response.data;
  },

  // ===== 告警相关 =====
  
  // 获取指标的告警规则
  async listAlerts(metricId: string): Promise<MetricAlert[]> {
    const response = await api.get(`/semantic-layer/metrics/${metricId}/alerts`);
    return response.data;
  },

  // 创建告警规则
  async createAlert(data: MetricAlertCreate): Promise<MetricAlert> {
    const response = await api.post('/semantic-layer/alerts', data);
    return response.data;
  },

  // 更新告警规则
  async updateAlert(id: string, data: Partial<MetricAlertCreate>): Promise<MetricAlert> {
    const response = await api.put(`/semantic-layer/alerts/${id}`, data);
    return response.data;
  },

  // 删除告警规则
  async deleteAlert(id: string): Promise<void> {
    await api.delete(`/semantic-layer/alerts/${id}`);
  },

  // 切换告警启用状态
  async toggleAlert(id: string, enabled: boolean): Promise<MetricAlert> {
    const response = await api.patch(`/semantic-layer/alerts/${id}/toggle?enabled=${enabled}`);
    return response.data;
  },
};

export default metricService;
