/** @type {import('next').NextConfig} */

// 后端 API 地址 - 支持通过环境变量配置
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

const nextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
    // 性能优化：启用增量静态生成
    incrementalCacheHandlerPath: undefined,
    // 启用 Turbopack（Next.js 15+ 实验性功能，显著提升开发速度）
    // turbo: {},
  },
  // 开发环境性能优化
  ...(process.env.NODE_ENV === 'development' && {
    // 开发环境启用更快的刷新
    reactStrictMode: false, // 减少双重渲染
  }),
  // 生产环境禁用页面缓存，开发环境允许缓存以提升性能
  generateEtags: process.env.NODE_ENV === 'production' ? false : true,
  // 仅在生产环境添加自定义响应头禁用缓存
  async headers() {
    if (process.env.NODE_ENV === 'production') {
      return [
        {
          source: '/:path*',
          headers: [
            {
              key: 'Cache-Control',
              value: 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
            },
            {
              key: 'Pragma',
              value: 'no-cache',
            },
            {
              key: 'Expires',
              value: '0',
            },
          ],
        },
      ];
    }
    return [];
  },
  async rewrites() {
    // 将特定的 API 路径代理到 FastAPI 后端，避免与 LangGraph 路由冲突
    // 注意: 需要同时代理根路径和子路径
    // 后端地址通过环境变量配置，支持局域网访问
    return [
      // hybrid-qa
      {
        source: '/api/hybrid-qa',
        destination: `${BACKEND_URL}/api/hybrid-qa`,
      },
      {
        source: '/api/hybrid-qa/:path*',
        destination: `${BACKEND_URL}/api/hybrid-qa/:path*`,
      },
      // connections
      {
        source: '/api/connections',
        destination: `${BACKEND_URL}/api/connections/`,
      },
      {
        source: '/api/connections/:path*',
        destination: `${BACKEND_URL}/api/connections/:path*`,
      },
      // schema
      {
        source: '/api/schema/:path*',
        destination: `${BACKEND_URL}/api/schema/:path*`,
      },
      // query
      {
        source: '/api/query',
        destination: `${BACKEND_URL}/api/query/`,
      },
      {
        source: '/api/query/:path*',
        destination: `${BACKEND_URL}/api/query/:path*`,
      },
      // value-mappings
      {
        source: '/api/value-mappings/:path*',
        destination: `${BACKEND_URL}/api/value-mappings/:path*`,
      },
      // dashboards
      {
        source: '/api/dashboards/:path*',
        destination: `${BACKEND_URL}/api/dashboards/:path*`,
      },
      // llm-configs
      {
        source: '/api/llm-configs/:path*',
        destination: `${BACKEND_URL}/api/llm-configs/:path*`,
      },
      // agent-profiles
      {
        source: '/api/agent-profiles',
        destination: `${BACKEND_URL}/api/agent-profiles/`,
      },
      {
        source: '/api/agent-profiles/:path*',
        destination: `${BACKEND_URL}/api/agent-profiles/:path*`,
      },
      // system-config
      {
        source: '/api/system-config/:path*',
        destination: `${BACKEND_URL}/api/system-config/:path*`,
      },
    ];
  },
};

export default nextConfig;
