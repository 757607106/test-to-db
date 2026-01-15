import api from './api';

export interface AgentProfile {
  id: number;
  name: string;
  role_description?: string;
  system_prompt?: string;
  tools?: string[];
  llm_config_id?: number;
  is_active: boolean;
}

export interface AgentProfileCreate {
  name: string;
  role_description?: string;
  system_prompt?: string;
  tools?: string[];
  llm_config_id?: number;
  is_active?: boolean;
  is_system?: boolean;
}

export interface AgentProfileUpdate {
  name?: string;
  role_description?: string;
  system_prompt?: string;
  tools?: string[];
  llm_config_id?: number;
  is_active?: boolean;
}

// 获取所有智能体配置
export const getAgentProfiles = (params?: { is_system?: boolean }) => api.get<AgentProfile[]>('/agent-profiles/', { params });

// 创建智能体配置
export const createAgentProfile = (data: AgentProfileCreate) => api.post<AgentProfile>('/agent-profiles/', data);

// 智能优化 Prompt
export const optimizeAgentPrompt = (description: string) => api.post<string>('/agent-profiles/optimize-prompt', { description });

// 更新智能体配置
export const updateAgentProfile = (id: number, data: AgentProfileUpdate) => api.put<AgentProfile>(`/agent-profiles/${id}`, data);

// 删除智能体配置
export const deleteAgentProfile = (id: number) => api.delete<AgentProfile>(`/agent-profiles/${id}`);
