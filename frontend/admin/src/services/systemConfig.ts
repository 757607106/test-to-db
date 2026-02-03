import axios from 'axios';
import { getApiBaseUrl } from '../utils/apiConfig';

// 使用动态 API 地址，支持 localhost 和局域网 IP 访问
const API_BASE_URL = getApiBaseUrl();

export interface SystemConfigResponse {
  id: number;
  config_key: string;
  config_value: string | null;
  description: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface DefaultEmbeddingResponse {
  source: 'database' | 'environment_variables';
  llm_config_id: number | null;
  provider?: string;
  model_name?: string;
  base_url?: string;
  is_active?: boolean;
  message?: string;
}

/**
 * Get system configuration by key
 */
export const getSystemConfig = async (configKey: string) => {
  return axios.get<SystemConfigResponse>(`${API_BASE_URL}/system-config/${configKey}`);
};

/**
 * Update system configuration
 */
export const updateSystemConfig = async (configKey: string, configValue: string) => {
  return axios.put<SystemConfigResponse>(`${API_BASE_URL}/system-config/${configKey}`, {
    config_value: configValue
  });
};

/**
 * Get current default embedding model
 */
export const getDefaultEmbeddingModel = async () => {
  return axios.get<DefaultEmbeddingResponse>(`${API_BASE_URL}/system-config/default-embedding/current`);
};

/**
 * Set default embedding model
 */
export const setDefaultEmbeddingModel = async (llmConfigId: number) => {
  return axios.post(`${API_BASE_URL}/system-config/default-embedding/${llmConfigId}`);
};

/**
 * Clear default embedding model (fall back to environment variables)
 */
export const clearDefaultEmbeddingModel = async () => {
  return axios.delete(`${API_BASE_URL}/system-config/default-embedding`);
};

// ===== QA 样本检索配置 =====

export interface QASampleConfig {
  enabled: boolean;
  top_k: number;
  min_similarity: number;
  timeout_seconds: number;
}

/**
 * 获取 QA 样本检索配置
 */
export const getQASampleConfig = async () => {
  return axios.get<QASampleConfig>(`${API_BASE_URL}/system-config/qa-sample/config`);
};

/**
 * 更新 QA 样本检索配置
 */
export const updateQASampleConfig = async (config: QASampleConfig) => {
  return axios.put(`${API_BASE_URL}/system-config/qa-sample/config`, config);
};

/**
 * 切换 QA 样本检索启用状态
 */
export const toggleQASampleEnabled = async (enabled: boolean) => {
  return axios.post(`${API_BASE_URL}/system-config/qa-sample/toggle?enabled=${enabled}`);
};
