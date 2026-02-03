
import axios from 'axios';
import { getBackendApiUrl } from '@/utils/apiConfig';

// 数据库连接类型定义
export interface DBConnection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number;
  username: string;
  database_name: string;
  created_at: string;
  updated_at: string;
}

// API基础URL配置 - 动态获取，支持 localhost 和局域网 IP
const getApiUrl = () => {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000/api';
  }
  return getBackendApiUrl();
};

const api = axios.create({
  baseURL: getApiUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// 动态更新 baseURL（客户端初始化后）
if (typeof window !== 'undefined') {
  api.defaults.baseURL = getBackendApiUrl();
}

// 请求拦截器 - 添加认证 token
api.interceptors.request.use(
  (config) => {
    // 尝试从 localStorage 获取 token (与 admin 前端共享)
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 数据库连接相关API
// 注意: 统一使用尾部斜杠以匹配 FastAPI 默认行为
export const getConnections = () => api.get<DBConnection[]>('/connections/');

// 智能体配置类型定义
export interface AgentProfile {
  id: number;
  name: string;
  role_description: string;
  system_prompt?: string;
  is_active: boolean;
  llm_config_id?: number;
  is_system?: boolean;
}

// 智能体相关API
export const getAgentProfiles = (params?: { is_system?: boolean }) => api.get<AgentProfile[]>('/agent-profiles/', { params });

export default api;
