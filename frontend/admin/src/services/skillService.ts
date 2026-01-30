/**
 * Skills 服务
 * 提供 Skills CRUD 操作的 API 调用
 * 
 * Skills-SQL-Assistant 架构的前端服务层
 */
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

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

// JOIN 规则类型定义
export interface JoinRuleItem {
  name?: string;
  description?: string;
  left_table: string;
  left_column: string;
  right_table: string;
  right_column: string;
  join_type?: 'INNER' | 'LEFT' | 'RIGHT' | 'FULL';
  extra_conditions?: string;
}

// Skill 类型定义
export interface Skill {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  keywords: string[];
  intent_examples: string[];
  table_patterns: string[];
  table_names: string[];
  business_rules?: string;
  common_patterns: Array<{ pattern: string; hint: string }>;
  join_rules: JoinRuleItem[];  // 内嵌的 JOIN 规则
  priority: number;
  is_active: boolean;
  icon?: string;
  color?: string;
  connection_id: number;
  tenant_id?: number;
  usage_count: number;
  hit_rate: number;
  is_auto_generated: boolean;
  created_at: string;
  updated_at?: string;
}

export interface SkillCreate {
  name: string;
  display_name: string;
  description?: string;
  keywords?: string[];
  intent_examples?: string[];
  table_patterns?: string[];
  table_names?: string[];
  business_rules?: string;
  common_patterns?: Array<{ pattern: string; hint: string }>;
  join_rules?: JoinRuleItem[];
  priority?: number;
  is_active?: boolean;
  icon?: string;
  color?: string;
  connection_id: number;
}

export interface SkillUpdate {
  name?: string;
  display_name?: string;
  description?: string;
  keywords?: string[];
  intent_examples?: string[];
  table_patterns?: string[];
  table_names?: string[];
  business_rules?: string;
  common_patterns?: Array<{ pattern: string; hint: string }>;
  join_rules?: JoinRuleItem[];
  priority?: number;
  is_active?: boolean;
  icon?: string;
  color?: string;
}

export interface SkillListResponse {
  skills: Skill[];
  total: number;
  has_skills_configured: boolean;
}

export interface SkillStatusResponse {
  has_skills_configured: boolean;
  skills_count: number;
  mode: 'skill' | 'default';
}

export interface SkillSuggestion {
  name: string;
  display_name: string;
  description: string;
  keywords: string[];
  table_names: string[];
  confidence: number;
  reasoning: string;
}

export interface SkillDiscoverResponse {
  suggestions: SkillSuggestion[];
  total: number;
}

export interface SkillLoadResult {
  skill_name: string;
  display_name: string;
  description?: string;
  tables: any[];
  columns: any[];
  relationships: any[];
  metrics: any[];
  join_rules: any[];
  business_rules?: string;
  common_patterns: Array<{ pattern: string; hint: string }>;
  enum_columns: any[];
}

// 优化建议相关类型
export interface OptimizationSuggestion {
  id: string;
  type: 'add_keyword' | 'add_table' | 'create_skill' | 'merge_skills' | 'add_rule' | 'add_join';
  priority: 'high' | 'medium' | 'low';
  skill_name?: string;
  skill_id?: number;
  title: string;
  description: string;
  reasoning: string;
  action_data: Record<string, any>;
  query_count: number;
  failure_count: number;
  confidence: number;
  example_queries: string[];
  status: string;
  created_at: string;
}

export interface OptimizationSummary {
  total_suggestions: number;
  by_priority: {
    high: number;
    medium: number;
    low: number;
  };
  by_type: Record<string, number>;
  top_suggestions: Array<{
    id: string;
    type: string;
    priority: string;
    title: string;
    query_count: number;
  }>;
}

export interface DiscoverResult {
  suggestions: SkillSuggestion[];
  analyzed_tables: number;
  grouped_tables: number;
  ungrouped_tables: string[];
}

export const skillService = {
  // 获取 Skills 列表
  async listSkills(connectionId: number, includeInactive = false): Promise<SkillListResponse> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    if (includeInactive) params.append('include_inactive', 'true');
    
    const response = await api.get(`/skills?${params}`);
    return response.data;
  },

  // 获取 Skills 状态（零配置检查）
  async getSkillsStatus(connectionId: number): Promise<SkillStatusResponse> {
    const response = await api.get(`/skills/status?connection_id=${connectionId}`);
    return response.data;
  },

  // 获取单个 Skill
  async getSkill(id: number): Promise<Skill> {
    const response = await api.get(`/skills/${id}`);
    return response.data;
  },

  // 创建 Skill
  async createSkill(data: SkillCreate): Promise<Skill> {
    const response = await api.post('/skills', data);
    return response.data;
  },

  // 更新 Skill
  async updateSkill(id: number, data: SkillUpdate): Promise<Skill> {
    const response = await api.put(`/skills/${id}`, data);
    return response.data;
  },

  // 删除 Skill
  async deleteSkill(id: number): Promise<void> {
    await api.delete(`/skills/${id}`);
  },

  // 加载 Skill 内容
  async loadSkillContent(skillName: string, connectionId: number): Promise<SkillLoadResult> {
    const response = await api.get(`/skills/${skillName}/content?connection_id=${connectionId}`);
    return response.data;
  },

  // 获取 Skill Prompt 段落
  async getSkillPromptSection(connectionId: number): Promise<{ has_skills: boolean; prompt_section: string | null }> {
    const response = await api.get(`/skills/prompt-section?connection_id=${connectionId}`);
    return response.data;
  },

  // 切换 Skill 激活状态
  async toggleSkillActive(id: number, isActive: boolean): Promise<Skill> {
    const response = await api.put(`/skills/${id}`, { is_active: isActive });
    return response.data;
  },

  // ===== 智能优化 =====

  // 获取优化摘要
  async getOptimizationSummary(connectionId: number): Promise<OptimizationSummary> {
    const response = await api.get(`/skills/optimization/summary?connection_id=${connectionId}`);
    return response.data;
  },

  // 获取优化建议列表
  async getOptimizationSuggestions(
    connectionId: number, 
    days = 7, 
    forceRefresh = false
  ): Promise<{ suggestions: OptimizationSuggestion[]; total: number }> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    params.append('days', String(days));
    if (forceRefresh) params.append('force_refresh', 'true');
    
    const response = await api.get(`/skills/optimization/suggestions?${params}`);
    return response.data;
  },

  // 应用优化建议
  async applyOptimizationSuggestion(
    suggestionId: string, 
    connectionId: number
  ): Promise<{ success: boolean; message?: string; error?: string; action?: string; prefill_data?: any }> {
    const response = await api.post(
      `/skills/optimization/apply/${suggestionId}?connection_id=${connectionId}`
    );
    return response.data;
  },

  // ===== 自动发现 =====

  // 发现 Skill 建议
  async discoverSkills(connectionId: number, useLlm = false): Promise<DiscoverResult> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    if (useLlm) params.append('use_llm', 'true');
    
    const response = await api.get(`/skills/discover?${params}`);
    return response.data;
  },

  // 应用发现的 Skill
  async applyDiscoveredSkills(
    connectionId: number, 
    skillNames: string[]
  ): Promise<{ success: boolean; results: any[]; created_count: number }> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    skillNames.forEach(name => params.append('skill_names', name));
    
    const response = await api.post(`/skills/discover/apply?${params}`);
    return response.data;
  },
};

export default skillService;
