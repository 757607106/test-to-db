/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
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
