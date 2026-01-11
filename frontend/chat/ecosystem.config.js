
module.exports = {
  apps: [
    {
      name: 'chat-app',
      script: 'npm',
      args: 'start',
      cwd: '/var/www/chat-app', // 修改为你的实际部署路径
      instances: 1, // 可以设置为 'max' 使用所有 CPU 核心
      exec_mode: 'fork', // 或 'cluster' 用于集群模式
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
        // 添加其他环境变量
        // LANGGRAPH_API_URL: 'your_api_url',
        // LANGSMITH_API_KEY: 'your_api_key'
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      // 日志配置
      log_file: '/var/log/chat-app/combined.log',
      out_file: '/var/log/chat-app/out.log',
      error_file: '/var/log/chat-app/error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // 自动重启配置
      watch: false, // 生产环境建议关闭文件监听
      ignore_watch: ['node_modules', 'logs'],
      max_memory_restart: '1G',
      
      // 其他配置
      restart_delay: 4000,
      max_restarts: 10,
      min_uptime: '10s'
    }
  ]
};
