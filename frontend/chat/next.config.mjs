/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
  // 禁用页面缓存，确保刷新后获取最新代码
  generateEtags: false,
  // 添加自定义响应头禁用缓存
  async headers() {
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
  },
  async rewrites() {
    // 将特定的 API 路径代理到 FastAPI 后端，避免与 LangGraph 路由冲突
    return [
      {
        source: '/api/hybrid-qa/:path*',
        destination: 'http://localhost:8000/api/hybrid-qa/:path*',
      },
      {
        source: '/api/connections/:path*',
        destination: 'http://localhost:8000/api/connections/:path*',
      },
      {
        source: '/api/schema/:path*',
        destination: 'http://localhost:8000/api/schema/:path*',
      },
      {
        source: '/api/query/:path*',
        destination: 'http://localhost:8000/api/query/:path*',
      },
      {
        source: '/api/value-mappings/:path*',
        destination: 'http://localhost:8000/api/value-mappings/:path*',
      },
      {
        source: '/api/dashboards/:path*',
        destination: 'http://localhost:8000/api/dashboards/:path*',
      },
      {
        source: '/api/llm-configs/:path*',
        destination: 'http://localhost:8000/api/llm-configs/:path*',
      },
      {
        source: '/api/agent-profiles/:path*',
        destination: 'http://localhost:8000/api/agent-profiles/:path*',
      },
      {
        source: '/api/system-config/:path*',
        destination: 'http://localhost:8000/api/system-config/:path*',
      },
    ];
  },
};

export default nextConfig;
