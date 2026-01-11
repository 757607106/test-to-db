#!/bin/bash

# 服务器部署脚本
# 在服务器上运行此脚本

APP_NAME="chat-app"
APP_DIR="/var/www/chat-app"
PORT=3000

echo "🚀 开始部署 Next.js 应用..."

# 检查 Node.js 是否安装
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js"
    exit 1
fi

echo "✅ Node.js 版本: $(node --version)"

# 创建应用目录
echo "📁 创建应用目录: $APP_DIR"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# 进入应用目录
cd $APP_DIR

# 检查必需文件是否存在
if [ ! -f "package.json" ]; then
    echo "❌ package.json 文件不存在，请确保已上传所有必需文件"
    echo "📋 需要上传的文件："
    echo "   - package.json"
    echo "   - next.config.mjs"
    echo "   - .next/ 文件夹"
    echo "   - public/ 文件夹（如果有）"
    echo "   - .env 文件（如果有）"
    exit 1
fi

if [ ! -d ".next" ]; then
    echo "❌ .next 文件夹不存在，请确保已运行 'npm run build' 并上传构建文件"
    exit 1
fi

echo "✅ 必需文件检查通过"

# 安装生产依赖
echo "📦 安装生产依赖..."
npm ci --only=production

if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    exit 1
fi

echo "✅ 依赖安装完成"

# 检查是否安装了 PM2
if command -v pm2 &> /dev/null; then
    echo "✅ 检测到 PM2，使用 PM2 管理进程"
    
    # 停止现有进程（如果存在）
    pm2 stop $APP_NAME 2>/dev/null || true
    pm2 delete $APP_NAME 2>/dev/null || true
    
    # 启动应用
    pm2 start npm --name $APP_NAME -- start
    pm2 save
    
    echo "🎉 应用已通过 PM2 启动！"
    echo "📊 查看状态: pm2 status"
    echo "📝 查看日志: pm2 logs $APP_NAME"
    
else
    echo "⚠️  PM2 未安装，使用 systemd 管理进程"
    
    # 创建 systemd 服务文件
    sudo tee /etc/systemd/system/$APP_NAME.service > /dev/null << EOF
[Unit]
Description=Next.js Chat Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=PORT=$PORT

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd 并启动服务
    sudo systemctl daemon-reload
    sudo systemctl enable $APP_NAME
    sudo systemctl start $APP_NAME
    
    echo "🎉 应用已通过 systemd 启动！"
    echo "📊 查看状态: sudo systemctl status $APP_NAME"
    echo "📝 查看日志: sudo journalctl -u $APP_NAME -f"
fi

# 检查应用是否正常运行
echo "🔍 检查应用状态..."
sleep 5

if curl -f http://localhost:$PORT > /dev/null 2>&1; then
    echo "✅ 应用运行正常！"
    echo "🌐 访问地址: http://$(hostname -I | awk '{print $1}'):$PORT"
else
    echo "⚠️  应用可能未正常启动，请检查日志"
fi

echo ""
echo "📋 部署完成！"
echo "🔧 管理命令："
if command -v pm2 &> /dev/null; then
    echo "   pm2 status           - 查看状态"
    echo "   pm2 logs $APP_NAME   - 查看日志"
    echo "   pm2 restart $APP_NAME - 重启应用"
    echo "   pm2 stop $APP_NAME   - 停止应用"
else
    echo "   sudo systemctl status $APP_NAME  - 查看状态"
    echo "   sudo journalctl -u $APP_NAME -f - 查看日志"
    echo "   sudo systemctl restart $APP_NAME - 重启应用"
    echo "   sudo systemctl stop $APP_NAME    - 停止应用"
fi

echo ""
echo "⚠️  注意事项："
echo "   - 确保端口 $PORT 在防火墙中开放"
echo "   - 如需域名访问，请配置域名解析"
echo "   - 生产环境建议配置 HTTPS"
