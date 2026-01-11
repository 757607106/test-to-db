#!/bin/bash

# Next.js 应用部署脚本
# 使用方法: ./deploy.sh [部署目录]

DEPLOY_DIR=${1:-"/var/www/chat-app"}
APP_NAME="chat-app"
PORT=${2:-3000}

echo "🚀 开始部署 Next.js 应用到 $DEPLOY_DIR"

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
cp -r node_modules $DEPLOY_DIR/ 2>/dev/null || echo "⚠️  node_modules 未复制，需要在服务器上安装依赖"

# 3. 复制环境变量文件（如果存在）
cp .env* $DEPLOY_DIR/ 2>/dev/null || echo "ℹ️  未找到环境变量文件"

# 4. 创建启动脚本
cat > $DEPLOY_DIR/start.sh << EOF
#!/bin/bash
cd $DEPLOY_DIR
export NODE_ENV=production
export PORT=$PORT

# 如果 node_modules 不存在，安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装生产依赖..."
    npm ci --only=production
fi

echo "🚀 启动应用在端口 $PORT..."
npm start
EOF

chmod +x $DEPLOY_DIR/start.sh

# 5. 创建 systemd 服务文件
sudo tee /etc/systemd/system/$APP_NAME.service > /dev/null << EOF
[Unit]
Description=Next.js Chat Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
ExecStart=$DEPLOY_DIR/start.sh
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=PORT=$PORT

[Install]
WantedBy=multi-user.target
EOF

echo "✅ 部署完成！"
echo ""
echo "📋 接下来的步骤："
echo "1. 启用并启动服务: sudo systemctl enable $APP_NAME && sudo systemctl start $APP_NAME"
echo "2. 检查服务状态: sudo systemctl status $APP_NAME"
echo "3. 查看日志: sudo journalctl -u $APP_NAME -f"
echo "4. 配置 nginx 反向代理（见 nginx.conf 文件）"
