
import axios from 'axios';

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

// API基础URL配置
const API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
