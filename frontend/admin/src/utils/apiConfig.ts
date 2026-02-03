/**
 * 动态 API 配置工具
 * 根据当前访问域名自动切换 API 地址
 * 支持本地 localhost 和局域网 IP 访问
 */

/**
 * 获取当前环境的 API 基础地址
 * - 通过 localhost 访问时，使用 localhost:8000
 * - 通过 IP 地址访问时，使用相同 IP:8000
 */
export const getApiBaseUrl = (): string => {
  // 服务端渲染时使用默认值
  if (typeof window === 'undefined') {
    return process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
  }

  const hostname = window.location.hostname;
  
  // localhost 或 127.0.0.1 使用本地地址
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000/api';
  }
  
  // 其他情况（局域网 IP 或外网域名）使用当前 hostname
  return `http://${hostname}:8000/api`;
};

/**
 * 获取 Chat 前端地址
 * 与 API 地址逻辑一致
 */
export const getChatUrl = (): string => {
  if (typeof window === 'undefined') {
    return process.env.REACT_APP_CHAT_URL || 'http://localhost:3000';
  }

  const hostname = window.location.hostname;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:3000';
  }
  
  return `http://${hostname}:3000`;
};

/**
 * 获取 LangGraph API 地址（用于 Chat 功能）
 */
export const getLangGraphUrl = (): string => {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:2024';
  }

  const hostname = window.location.hostname;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:2024';
  }
  
  return `http://${hostname}:2024`;
};

// 导出常量供静态初始化使用
export const API_BASE_URL = getApiBaseUrl();
