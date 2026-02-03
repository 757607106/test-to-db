/**
 * API 配置工具 (Chat 前端)
 * 通过环境变量和 URL 参数统一控制所有服务地址
 * 
 * 配置优先级（从高到低）：
 * 1. URL 参数（如 ?apiHost=192.168.13.163）
 * 2. 完整 URL 环境变量（如 NEXT_PUBLIC_API_URL）
 * 3. SERVICE_HOST 环境变量 + 默认端口
 * 4. 默认值 localhost
 * 
 * 环境变量说明：
 * - NEXT_PUBLIC_SERVICE_HOST: 统一配置所有服务的主机地址（默认 localhost）
 * - NEXT_PUBLIC_API_URL: LangGraph API 完整 URL（优先级高于 SERVICE_HOST）
 * - NEXT_PUBLIC_BACKEND_URL: 后端服务完整 URL（优先级高于 SERVICE_HOST）
 * - NEXT_PUBLIC_BACKEND_API_URL: 后端 API 完整 URL（优先级高于 SERVICE_HOST）
 * 
 * URL 参数说明（用于临时切换环境）：
 * - apiHost: 覆盖所有服务的主机地址
 * - langGraphUrl: 覆盖 LangGraph API 地址
 * - backendUrl: 覆盖后端 API 地址
 */

/**
 * 缓存 URL 参数，避免重复解析
 */
let urlParamsCache: URLSearchParams | null = null;

/**
 * 获取 URL 参数
 */
const getUrlParams = (): URLSearchParams | null => {
  if (typeof window === 'undefined') return null;
  if (urlParamsCache === null) {
    urlParamsCache = new URLSearchParams(window.location.search);
  }
  return urlParamsCache;
};

/**
 * 从 URL 参数获取值
 */
const getUrlParam = (key: string): string | null => {
  const params = getUrlParams();
  return params?.get(key) || null;
};

/**
 * 获取配置的服务主机地址
 * 优先级：URL 参数 > 环境变量 > 默认值
 */
const getServiceHost = (): string => {
  // 1. 优先使用 URL 参数
  const urlHost = getUrlParam('apiHost');
  if (urlHost) {
    return urlHost;
  }
  // 2. 使用环境变量
  return process.env.NEXT_PUBLIC_SERVICE_HOST || 'localhost';
};

/**
 * 获取后端 API 基础地址
 * 优先级：URL 参数 > 完整 URL 环境变量 > SERVICE_HOST + 端口
 */
export const getBackendApiUrl = (): string => {
  // 1. 优先使用 URL 参数
  const urlBackend = getUrlParam('backendUrl');
  if (urlBackend) {
    return urlBackend.endsWith('/api') ? urlBackend : `${urlBackend}/api`;
  }
  // 2. 优先使用完整 URL 环境变量
  if (process.env.NEXT_PUBLIC_BACKEND_API_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_API_URL;
  }
  // 3. 使用 SERVICE_HOST + 默认端口
  return `http://${getServiceHost()}:8000/api`;
};

/**
 * 获取后端基础 URL（不带 /api）
 * 优先级：URL 参数 > 完整 URL 环境变量 > SERVICE_HOST + 端口
 */
export const getBackendBaseUrl = (): string => {
  // 1. 优先使用 URL 参数
  const urlBackend = getUrlParam('backendUrl');
  if (urlBackend) {
    return urlBackend.replace(/\/api\/?$/, '');
  }
  // 2. 优先使用完整 URL 环境变量
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  // 3. 使用 SERVICE_HOST + 默认端口
  return `http://${getServiceHost()}:8000`;
};

/**
 * 获取 LangGraph API 地址
 * 优先级：URL 参数 > 完整 URL 环境变量 > SERVICE_HOST + 端口
 */
export const getLangGraphApiUrl = (): string => {
  // 1. 优先使用 URL 参数
  const urlLangGraph = getUrlParam('langGraphUrl');
  if (urlLangGraph) {
    return urlLangGraph;
  }
  // 2. 优先使用完整 URL 环境变量
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  // 3. 使用 SERVICE_HOST + 默认端口
  return `http://${getServiceHost()}:2024`;
};

/**
 * 获取 Admin 管理后台地址
 * 优先级：URL 参数 > SERVICE_HOST + 端口
 */
export const getAdminUrl = (): string => {
  // 1. 优先使用 URL 参数
  const urlAdmin = getUrlParam('adminUrl');
  if (urlAdmin) {
    return urlAdmin;
  }
  // 2. 使用 SERVICE_HOST + 默认端口
  return `http://${getServiceHost()}:3001`;
};

/**
 * 获取当前配置的服务主机地址（用于调试显示）
 */
export const getCurrentServiceHost = (): string => {
  return getServiceHost();
};

/**
 * 检查是否使用了 URL 参数覆盖配置
 */
export const isUsingUrlOverrides = (): boolean => {
  const params = getUrlParams();
  if (!params) return false;
  return params.has('apiHost') || params.has('langGraphUrl') || params.has('backendUrl');
};

/**
 * 重置 URL 参数缓存（用于测试或页面刷新后）
 */
export const resetUrlParamsCache = (): void => {
  urlParamsCache = null;
};
