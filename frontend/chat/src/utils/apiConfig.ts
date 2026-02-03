/**
 * 动态 API 配置工具 (Chat 前端)
 * 根据当前访问域名自动切换 API 地址
 * 支持本地 localhost 和局域网 IP 访问
 */

/**
 * 获取后端 API 基础地址
 * - 通过 localhost 访问时，使用 localhost:8000
 * - 通过 IP 地址访问时，使用相同 IP:8000
 */
export const getBackendApiUrl = (): string => {
  // 服务端渲染时使用环境变量
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000/api';
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
 * 获取后端基础 URL（不带 /api）
 */
export const getBackendBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  }

  const hostname = window.location.hostname;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  
  return `http://${hostname}:8000`;
};

/**
 * 获取 LangGraph API 地址
 * - 通过 localhost 访问时，使用 localhost:2024
 * - 通过 IP 地址访问时，使用相同 IP:2024
 */
export const getLangGraphApiUrl = (): string => {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:2024';
  }

  const hostname = window.location.hostname;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:2024';
  }
  
  return `http://${hostname}:2024`;
};

/**
 * 获取 Admin 管理后台地址
 */
export const getAdminUrl = (): string => {
  if (typeof window === 'undefined') {
    return 'http://localhost:3001';
  }

  const hostname = window.location.hostname;
  
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:3001';
  }
  
  return `http://${hostname}:3001`;
};
