#!/bin/bash

# 简单的 Node.js 部署脚本（无需 nginx）
# 使用方法: ./deploy-simple.sh [部署目录] [端口]

DEPLOY_DIR=${1:-"/var/www/chat-app"}
APP_NAME="chat-app"
PORT=${2:-3000}

echo "🚀 开始部署 Next.js 应用到 $DEPLOY_DIR (端口: $PORT)"

# 1. 创建部署目录
sudo mkdir -p $DEPLOY_DIR
sudo chown $USER:$USER $DEPLOY_DIR

# 2. 复制构建文件
echo "📦 复制应用文件..."
cp -r .next $DEPLOY_DIR/
cp -r public $DEPLOY_DIR/
cp package.json $DEPLOY_DIR/
cp package-lock.json $DEPLOY_DIR/ 2>/dev/null || cp pnpm-lock.yaml $DEPLOY_DIR/ 2>/dev/null || true
cp next.config.mjs $DEPLOY_DIR/

# 3. 复制环境变量文件（如果存在）
cp .env* $DEPLOY_DIR/ 2>/dev/null || echo "ℹ️  未找到环境变量文件"

# 4. 安装生产依赖
echo "📦 安装生产依赖..."
cd $DEPLOY_DIR
npm ci --only=production

# 5. 创建启动脚本
cat > $DEPLOY_DIR/start.sh << EOF
#!/bin/bash
cd $DEPLOY_DIR
export NODE_ENV=production
export PORT=$PORT

echo "🚀 启动应用在端口 $PORT..."
echo "🌐 访问地址: http://localhost:$PORT"
npm start
EOF

chmod +x $DEPLOY_DIR/start.sh

# 6. 创建 systemd 服务文件
sudo tee /etc/systemd/system/$APP_NAME.service > /dev/null << EOF
[Unit]
Description=Next.js Chat Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=PORT=$PORT

[Install]
WantedBy=multi-user.target
EOF

# 7. 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable $APP_NAME
sudo systemctl start $APP_NAME

echo "✅ 部署完成！"
echo ""
echo "📋 服务信息："
echo "- 应用名称: $APP_NAME"
echo "- 部署目录: $DEPLOY_DIR"
echo "- 运行端口: $PORT"
echo "- 访问地址: http://localhost:$PORT"
echo ""
echo "🔧 管理命令："
echo "- 查看状态: sudo systemctl status $APP_NAME"
echo "- 查看日志: sudo journalctl -u $APP_NAME -f"
echo "- 重启服务: sudo systemctl restart $APP_NAME"
echo "- 停止服务: sudo systemctl stop $APP_NAME"
echo ""
echo "⚠️  注意事项："
echo "- 确保端口 $PORT 在防火墙中开放"
echo "- 如果需要域名访问，建议配置 nginx 反向代理"
echo "- 生产环境建议使用 HTTPS"
