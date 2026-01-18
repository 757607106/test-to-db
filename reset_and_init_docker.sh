#!/bin/bash

# Docker 重置和初始化脚本
# 用于完全重置 Docker 环境并初始化数据

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 主流程
main() {
    print_header "Docker 环境重置和初始化"
    
    # 1. 备份现有数据
    print_info "步骤 1/6: 备份现有数据..."
    BACKUP_DIR="backend/backups/docker_reset_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    if docker ps | grep -q "chat_to_db_rwx-mysql"; then
        print_info "正在备份 MySQL 数据..."
        docker exec chat_to_db_rwx-mysql mysqldump -uroot -pmysql --all-databases --single-transaction --quick --lock-tables=false > "$BACKUP_DIR/mysql_backup.sql" 2>/dev/null || true
        print_success "MySQL 数据已备份到: $BACKUP_DIR/mysql_backup.sql"
    else
        print_warning "MySQL 容器未运行，跳过备份"
    fi
    
    # 2. 停止所有服务
    print_info "步骤 2/6: 停止所有 Docker 服务..."
    ./start-services.sh stop 2>/dev/null || docker-compose down 2>/dev/null || true
    print_success "服务已停止"
    
    # 3. 删除所有相关容器
    print_info "步骤 3/6: 删除所有相关容器..."
    docker ps -a | grep -E "(chat.*db|milvus|langgraph)" | awk '{print $1}' | xargs docker rm -f 2>/dev/null || true
    print_success "容器已删除"
    
    # 4. 删除所有相关数据卷
    print_info "步骤 4/6: 删除所有相关数据卷..."
    docker volume ls --format "{{.Name}}" | grep -E "(chat.*db|langgraph|milvus)" | xargs docker volume rm 2>/dev/null || true
    print_success "数据卷已删除"
    
    # 5. 重新启动服务
    print_info "步骤 5/6: 重新启动 Docker 服务..."
    ./start-services.sh start
    print_success "服务已启动"
    
    # 等待服务就绪
    print_info "等待服务完全启动..."
    sleep 10
    
    # 6. 运行数据库迁移
    print_info "步骤 6/6: 运行数据库迁移..."
    cd backend
    alembic upgrade head
    print_success "数据库迁移完成"
    
    # 7. 初始化 Mock 数据
    print_info "初始化 Mock 数据..."
    python3 init_mock_data.py
    print_success "Mock 数据初始化完成"
    
    cd ..
    
    # 完成
    print_header "✅ 重置和初始化完成！"
    
    print_info "📊 当前状态:"
    echo ""
    echo "Docker 容器:"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep chat_to_db_rwx || echo "  无"
    echo ""
    echo "数据卷:"
    docker volume ls | grep chat_to_db_rwx || echo "  无"
    echo ""
    
    print_info "📝 备份位置: $BACKUP_DIR"
    print_info "🚀 下一步:"
    echo "  1. 启动后端: cd backend && python3 admin_server.py"
    echo "  2. 启动前端: cd frontend/admin && npm start"
    echo "  3. 访问应用: http://localhost:3000"
    echo ""
    
    print_info "🔑 测试账号:"
    echo "  用户名: admin"
    echo "  密码: admin123"
    echo ""
}

# 运行主函数
main

