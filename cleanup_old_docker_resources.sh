#!/bin/bash

# 清理旧的 Docker 资源脚本
# 用于删除旧的 chatdb_ 和 langgraph- 前缀的资源

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

print_header "清理旧的 Docker 资源"

# 1. 查找旧容器
print_info "查找旧容器..."
OLD_CONTAINERS=$(docker ps -a --format "{{.Names}}" | grep -E "(^chatdb_|^chatdb-|^langgraph-)" || true)

if [ -n "$OLD_CONTAINERS" ]; then
    echo "$OLD_CONTAINERS"
    echo ""
    read -p "是否删除这些容器？(yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "$OLD_CONTAINERS" | xargs docker rm -f 2>/dev/null || true
        print_success "旧容器已删除"
    else
        print_info "跳过删除容器"
    fi
else
    print_success "没有找到旧容器"
fi

echo ""

# 2. 查找旧数据卷
print_info "查找旧数据卷..."
OLD_VOLUMES=$(docker volume ls --format "{{.Name}}" | grep -E "(^chatdb_|^langgraph-)" || true)

if [ -n "$OLD_VOLUMES" ]; then
    echo "$OLD_VOLUMES"
    echo ""
    print_warning "⚠️  警告：删除数据卷将永久删除数据！"
    read -p "是否删除这些数据卷？(yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "$OLD_VOLUMES" | xargs docker volume rm 2>/dev/null || true
        print_success "旧数据卷已删除"
    else
        print_info "跳过删除数据卷"
    fi
else
    print_success "没有找到旧数据卷"
fi

echo ""

# 3. 查找旧网络
print_info "查找旧网络..."
OLD_NETWORKS=$(docker network ls --format "{{.Name}}" | grep -E "(^chatdb-|^langgraph-)" || true)

if [ -n "$OLD_NETWORKS" ]; then
    echo "$OLD_NETWORKS"
    echo ""
    read -p "是否删除这些网络？(yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo "$OLD_NETWORKS" | xargs docker network rm 2>/dev/null || true
        print_success "旧网络已删除"
    else
        print_info "跳过删除网络"
    fi
else
    print_success "没有找到旧网络"
fi

echo ""
print_header "清理完成"

print_info "当前 chat_to_db_rwx 项目资源："
echo ""
echo "容器："
docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep chat_to_db_rwx || echo "  无"
echo ""
echo "数据卷："
docker volume ls | grep chat_to_db_rwx || echo "  无"
echo ""
echo "网络："
docker network ls | grep chat_to_db_rwx || echo "  无"
echo ""

