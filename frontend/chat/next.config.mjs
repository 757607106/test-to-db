/** @type {import('next').NextConfig} */

// 后端 API 地址 - 支持通过环境变量配置
// 优先级：NEXT_PUBLIC_BACKEND_URL > SERVICE_HOST + 端口
const SERVICE_HOST = process.env.NEXT_PUBLIC_SERVICE_HOST || 'localhost';
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || `http://${SERVICE_HOST}:8000`;

const nextConfig = {
  // 允许局域网 IP 访问开发服务器
  allowedDevOrigins: [
    'http://192.168.13.163:3000',
    'http://localhost:3000',
  ],
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
  // 开发环境性能优化
  ...(process.env.NODE_ENV === 'development' && {
    reactStrictMode: false,
  }),
  generateEtags: process.env.NODE_ENV === 'production' ? false : true,
  async headers() {
    if (process.env.NODE_ENV === 'production') {
      return [
        {
          source: '/:path*',
          headers: [
            { key: 'Cache-Control', value: 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0' },
            { key: 'Pragma', value: 'no-cache' },
            { key: 'Expires', value: '0' },
          ],
        },
      ];
    }
    return [];
  },
  async rewrites() {
    return [
      { source: '/api/hybrid-qa', destination: `${BACKEND_URL}/api/hybrid-qa` },
      { source: '/api/hybrid-qa/:path*', destination: `${BACKEND_URL}/api/hybrid-qa/:path*` },
      { source: '/api/connections', destination: `${BACKEND_URL}/api/connections/` },
      { source: '/api/connections/:path*', destination: `${BACKEND_URL}/api/connections/:path*` },
      { source: '/api/schema/:path*', destination: `${BACKEND_URL}/api/schema/:path*` },
      { source: '/api/query', destination: `${BACKEND_URL}/api/query/` },
      { source: '/api/query/:path*', destination: `${BACKEND_URL}/api/query/:path*` },
      { source: '/api/value-mappings/:path*', destination: `${BACKEND_URL}/api/value-mappings/:path*` },
      { source: '/api/dashboards/:path*', destination: `${BACKEND_URL}/api/dashboards/:path*` },
      { source: '/api/llm-configs/:path*', destination: `${BACKEND_URL}/api/llm-configs/:path*` },
      { source: '/api/agent-profiles', destination: `${BACKEND_URL}/api/agent-profiles/` },
      { source: '/api/agent-profiles/:path*', destination: `${BACKEND_URL}/api/agent-profiles/:path*` },
      { source: '/api/system-config/:path*', destination: `${BACKEND_URL}/api/system-config/:path*` },
    ];
  },
};

export default nextConfig;
