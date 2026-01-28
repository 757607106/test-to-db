import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

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

// ============================================================================
// SQL 增强配置相关类型
// ============================================================================

export interface SQLEnhancementConfig {
  // QA 样本检索配置
  qa_sample_enabled: boolean;
  qa_sample_min_similarity: number;
  qa_sample_top_k: number;
  qa_sample_verified_only: boolean;
  
  // 指标库配置
  metrics_enabled: boolean;
  metrics_max_count: number;
  
  // 枚举值提示配置
  enum_hints_enabled: boolean;
  enum_max_values: number;
  
  // 简化流程配置
  simplified_flow_enabled: boolean;
  skip_clarification_for_clear_queries: boolean;
  
  // 缓存配置
  cache_mode: 'simple' | 'full';
}

// 默认配置
export const DEFAULT_SQL_ENHANCEMENT_CONFIG: SQLEnhancementConfig = {
  qa_sample_enabled: false,
  qa_sample_min_similarity: 0.85,
  qa_sample_top_k: 3,
  qa_sample_verified_only: true,
  metrics_enabled: false,
  metrics_max_count: 3,
  enum_hints_enabled: true,
  enum_max_values: 20,
  simplified_flow_enabled: true,
  skip_clarification_for_clear_queries: true,
  cache_mode: 'simple'
};

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

// ============================================================================
// SQL 增强配置 API
// ============================================================================

/**
 * 获取 SQL 增强功能配置
 */
export const getSQLEnhancementConfig = async () => {
  return axios.get<SQLEnhancementConfig>(`${API_BASE_URL}/system-config/sql-enhancement/config`);
};

/**
 * 更新 SQL 增强功能配置
 */
export const updateSQLEnhancementConfig = async (config: SQLEnhancementConfig) => {
  return axios.put<SQLEnhancementConfig>(`${API_BASE_URL}/system-config/sql-enhancement/config`, config);
};

/**
 * 重置 SQL 增强功能配置为默认值
 */
export const resetSQLEnhancementConfig = async () => {
  return axios.post<{ message: string; config: SQLEnhancementConfig }>(`${API_BASE_URL}/system-config/sql-enhancement/reset`);
};
