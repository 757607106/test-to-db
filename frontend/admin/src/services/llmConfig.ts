import api from './api';

export interface LLMConfig {
  id: number;
  provider: string;
  base_url?: string;
  model_name: string;
  model_type: string;
  is_active: boolean;
  api_key?: string; // 读取时通常会被掩码或不返回
}

export interface LLMConfigCreate {
  provider: string;
  base_url?: string;
  model_name: string;
  model_type?: string;
  is_active?: boolean;
  api_key?: string;
}

export interface LLMConfigUpdate {
  provider?: string;
  base_url?: string;
  model_name?: string;
  model_type?: string;
  is_active?: boolean;
  api_key?: string;
}

// 获取所有配置
export const getLLMConfigs = () => api.get<LLMConfig[]>('/llm-configs/');

// 创建配置
export const createLLMConfig = (data: LLMConfigCreate) => api.post<LLMConfig>('/llm-configs/', data);

// 更新配置
export const updateLLMConfig = (id: number, data: LLMConfigUpdate) => api.put<LLMConfig>(`/llm-configs/${id}`, data);

// 删除配置
export const deleteLLMConfig = (id: number) => api.delete<LLMConfig>(`/llm-configs/${id}`);

// 测试连接
export const testLLMConfig = (data: LLMConfigCreate) => api.post<{success: boolean, message: string}>('/llm-configs/test', data);

// --- Agent Profile 辅助 (暂时放在这里，或移至专门的 agentProfile.ts) ---

export interface AgentProfile {
  id: number;
  name: string;
  role_description?: string;
  system_prompt?: string;
  tools?: any;
  llm_config_id?: number;
  is_active: boolean;
}

export const getAgentProfileByName = (name: string) => 
  api.get<AgentProfile[]>(`/agent-profiles/?skip=0&limit=100`)
  .then(res => {
    // 客户端过滤，因为后端暂时不支持 ?name=xxx 查询
    if (Array.isArray(res.data)) {
        return res.data.find((p: AgentProfile) => p.name === name);
    }
    return undefined;
  });

export const createAgentProfile = (data: any) => api.post<AgentProfile>('/agent-profiles/', data);

export const updateAgentProfile = (id: number, data: any) => api.put<AgentProfile>(`/agent-profiles/${id}`, data);
