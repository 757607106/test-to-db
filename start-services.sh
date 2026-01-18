#!/bin/bash

# Chat-to-DB 服务启动脚本
# 用于快速启动所有必需的服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
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

# 检查 Docker 是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    print_success "Docker 和 Docker Compose 已安装"
}

# 显示帮助信息
show_help() {
    echo "Chat-to-DB 服务启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  start           启动核心服务（MySQL + PostgreSQL）"
    echo "  start-full      启动所有服务（包括 Neo4j, Milvus, Redis）"
    echo "  stop            停止核心服务"
    echo "  stop-full       停止所有服务"
    echo "  restart         重启核心服务"
    echo "  restart-full    重启所有服务"
    echo "  status          查看服务状态"
    echo "  logs            查看服务日志"
    echo "  clean           停止服务并删除数据卷（⚠️ 会删除所有数据）"
    echo "  help            显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start        # 启动核心服务"
    echo "  $0 start-full   # 启动所有服务"
    echo "  $0 logs         # 查看日志"
}

# 启动核心服务
start_core() {
    print_info "启动核心服务（MySQL + PostgreSQL）..."
    docker-compose up -d
    
    print_info "等待服务启动..."
    sleep 5
    
    print_info "检查服务状态..."
    docker-compose ps
    
    print_success "核心服务已启动"
    print_info "MySQL: localhost:3306"
    print_info "PostgreSQL Checkpointer: localhost:5433"
}

# 启动所有服务
start_full() {
    print_info "启动所有服务（MySQL + PostgreSQL + Neo4j + Milvus + Redis）..."
    docker-compose --profile full up -d
    
    print_info "等待服务启动..."
    sleep 10
    
    print_info "检查服务状态..."
    docker-compose --profile full ps
    
    print_success "所有服务已启动"
    print_info "MySQL: localhost:3306"
    print_info "PostgreSQL Checkpointer: localhost:5433"
    print_info "Neo4j: http://localhost:7474 (bolt://localhost:7687)"
    print_info "Milvus: localhost:19530"
    print_info "MinIO Console: http://localhost:9001"
    print_info "Redis: localhost:6379"
}

# 停止核心服务
stop_core() {
    print_info "停止核心服务..."
    docker-compose down
    print_success "核心服务已停止"
}

# 停止所有服务
stop_full() {
    print_info "停止所有服务..."
    docker-compose --profile full down
    print_success "所有服务已停止"
}

# 重启核心服务
restart_core() {
    print_info "重启核心服务..."
    docker-compose restart
    print_success "核心服务已重启"
}

# 重启所有服务
restart_full() {
    print_info "重启所有服务..."
    docker-compose --profile full restart
    print_success "所有服务已重启"
}

# 查看服务状态
show_status() {
    print_info "服务状态:"
    docker-compose ps
    
    echo ""
    print_info "数据卷:"
    docker volume ls | grep chatdb || echo "没有找到数据卷"
    
    echo ""
    print_info "网络:"
    docker network ls | grep chatdb || echo "没有找到网络"
}

# 查看日志
show_logs() {
    print_info "查看服务日志（按 Ctrl+C 退出）..."
    docker-compose logs -f
}

# 清理所有数据
clean_all() {
    print_warning "⚠️  警告：此操作将删除所有服务和数据卷！"
    read -p "确定要继续吗？(yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        print_info "停止并删除所有服务和数据卷..."
        docker-compose --profile full down -v
        print_success "清理完成"
    else
        print_info "操作已取消"
    fi
}

# 主函数
main() {
    # 检查 Docker
    check_docker
    
    # 解析命令
    case "${1:-help}" in
        start)
            start_core
            ;;
        start-full)
            start_full
            ;;
        stop)
            stop_core
            ;;
        stop-full)
            stop_full
            ;;
        restart)
            restart_core
            ;;
        restart-full)
            restart_full
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        clean)
            clean_all
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
