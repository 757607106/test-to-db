/**
 * JOIN 规则服务
 * 提供 JOIN 规则 CRUD 操作的 API 调用
 */
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

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

// JOIN 规则类型
export interface JoinRule {
  id: string;
  name: string;
  description?: string;
  left_table: string;
  left_column: string;
  right_table: string;
  right_column: string;
  join_type: 'INNER' | 'LEFT' | 'RIGHT' | 'FULL';
  priority: number;
  extra_conditions?: string;
  tags: string[];
  is_active: boolean;
  connection_id: number;
  created_at: string;
  updated_at?: string;
  usage_count: number;
}

export interface JoinRuleCreate {
  name: string;
  description?: string;
  left_table: string;
  left_column: string;
  right_table: string;
  right_column: string;
  join_type?: 'INNER' | 'LEFT' | 'RIGHT' | 'FULL';
  priority?: number;
  extra_conditions?: string;
  tags?: string[];
  is_active?: boolean;
  connection_id: number;
}

export interface JoinRuleContext {
  rule_id: string;
  join_clause: string;
  priority: number;
  description?: string;
}

export const joinRuleService = {
  // 获取规则列表
  async listRules(connectionId: number, isActive?: boolean): Promise<JoinRule[]> {
    const params = new URLSearchParams();
    params.append('connection_id', String(connectionId));
    if (isActive !== undefined) params.append('is_active', String(isActive));
    
    const response = await api.get(`/semantic-layer/join-rules?${params}`);
    return response.data;
  },

  // 获取单个规则
  async getRule(id: string): Promise<JoinRule> {
    const response = await api.get(`/semantic-layer/join-rules/${id}`);
    return response.data;
  },

  // 创建规则
  async createRule(data: JoinRuleCreate): Promise<JoinRule> {
    const response = await api.post('/semantic-layer/join-rules', data);
    return response.data;
  },

  // 更新规则
  async updateRule(id: string, data: Partial<JoinRuleCreate>): Promise<JoinRule> {
    const response = await api.put(`/semantic-layer/join-rules/${id}`, data);
    return response.data;
  },

  // 删除规则
  async deleteRule(id: string): Promise<void> {
    await api.delete(`/semantic-layer/join-rules/${id}`);
  },

  // 获取表关联的规则上下文（用于LLM）
  async getRulesForTables(connectionId: number, tables: string[]): Promise<JoinRuleContext[]> {
    const response = await api.get('/semantic-layer/join-rules/for-tables', {
      params: { 
        connection_id: connectionId, 
        tables: tables.join(',') 
      },
    });
    return response.data;
  },
};

export default joinRuleService;
