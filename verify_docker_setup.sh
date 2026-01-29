#!/bin/bash

# Docker 设置验证脚本
# 用于验证 Docker 服务配置是否正确

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

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 检查计数器
CHECKS_PASSED=0
CHECKS_FAILED=0

# 检查函数
check_file() {
    local file=$1
    local description=$2
    
    if [ -f "$file" ]; then
        print_success "$description: $file"
        ((CHECKS_PASSED++))
        return 0
    else
        print_error "$description 不存在: $file"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_executable() {
    local file=$1
    local description=$2
    
    if [ -x "$file" ]; then
        print_success "$description 可执行: $file"
        ((CHECKS_PASSED++))
        return 0
    else
        print_error "$description 不可执行: $file"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# 主验证流程
main() {
    print_header "Docker 设置验证"
    
    # 1. 检查核心配置文件
    print_info "检查核心配置文件..."
    check_file "docker-compose.yml" "Docker Compose 配置"
    check_file "backend/.env" "环境变量配置"
    check_file "backend/scripts/init-mysql.sql" "MySQL 初始化脚本"
    check_file "backend/scripts/init-checkpointer-db.sql" "PostgreSQL 初始化脚本"
    
    # 2. 检查启动脚本
    echo ""
    print_info "检查启动脚本..."
    check_file "start-services.sh" "启动脚本"
    check_executable "start-services.sh" "启动脚本"
    
    # 3. 检查文档
    echo ""
    print_info "检查文档..."
    check_file "README.md" "项目 README"
    check_file "DOCKER_QUICK_START.md" "Docker 快速启动指南"
    check_file "docs/deployment/DOCKER_DEPLOYMENT.md" "Docker 部署指南"
    check_file "docs/deployment/DOCKER_INTEGRATION_COMPLETE.md" "Docker 集成完成报告"
    
    # 4. 验证 Docker Compose 配置
    echo ""
    print_info "验证 Docker Compose 配置..."
    if docker-compose config --quiet 2>/dev/null; then
        print_success "Docker Compose 配置语法正确"
        ((CHECKS_PASSED++))
    else
        print_error "Docker Compose 配置语法错误"
        ((CHECKS_FAILED++))
    fi
    
    # 5. 检查服务定义
    echo ""
    print_info "检查服务定义..."
    
    local services=("mysql" "postgres-checkpointer")
    for service in "${services[@]}"; do
        if docker-compose config --services 2>/dev/null | grep -q "^${service}$"; then
            print_success "服务已定义: $service"
            ((CHECKS_PASSED++))
        else
            print_error "服务未定义: $service"
            ((CHECKS_FAILED++))
        fi
    done
    
    # 6. 检查可选服务（profile: full）
    echo ""
    print_info "检查可选服务..."
    
    local optional_services=("neo4j" "milvus" "redis")
    for service in "${optional_services[@]}"; do
        if docker-compose config --services 2>/dev/null | grep -q "^${service}$"; then
            print_success "可选服务已定义: $service"
            ((CHECKS_PASSED++))
        else
            print_warning "可选服务未定义: $service"
        fi
    done
    
    # 7. 检查环境变量配置
    echo ""
    print_info "检查环境变量配置..."
    
    if grep -q "CHECKPOINT_MODE=postgres" backend/.env; then
        print_success "Checkpointer 模式已配置"
        ((CHECKS_PASSED++))
    else
        print_error "Checkpointer 模式未配置"
        ((CHECKS_FAILED++))
    fi
    
    if grep -q "CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints" backend/.env; then
        print_success "PostgreSQL 连接字符串已配置"
        ((CHECKS_PASSED++))
    else
        print_error "PostgreSQL 连接字符串未配置或不正确"
        ((CHECKS_FAILED++))
    fi
    
    # 8. 检查旧文件是否已删除
    echo ""
    print_info "检查旧文件是否已删除..."
    
    if [ ! -f "backend/docker-compose.checkpointer.yml" ]; then
        print_success "旧的 Checkpointer Docker Compose 文件已删除"
        ((CHECKS_PASSED++))
    else
        print_warning "旧的 Checkpointer Docker Compose 文件仍然存在"
    fi
    
    if [ ! -f "backend/start-checkpointer.sh" ]; then
        print_success "旧的 Checkpointer 启动脚本已删除"
        ((CHECKS_PASSED++))
    else
        print_warning "旧的 Checkpointer 启动脚本仍然存在"
    fi
    
    # 9. 检查 Docker 环境
    echo ""
    print_info "检查 Docker 环境..."
    
    if command -v docker &> /dev/null; then
        print_success "Docker 已安装"
        ((CHECKS_PASSED++))
    else
        print_error "Docker 未安装"
        ((CHECKS_FAILED++))
    fi
    
    if command -v docker-compose &> /dev/null; then
        print_success "Docker Compose 已安装"
        ((CHECKS_PASSED++))
    else
        print_error "Docker Compose 未安装"
        ((CHECKS_FAILED++))
    fi
    
    # 10. 显示总结
    print_header "验证总结"
    
    echo -e "${GREEN}通过检查: $CHECKS_PASSED${NC}"
    echo -e "${RED}失败检查: $CHECKS_FAILED${NC}"
    echo ""
    
    if [ $CHECKS_FAILED -eq 0 ]; then
        print_success "所有检查通过！Docker 设置已正确配置。"
        echo ""
        print_info "下一步："
        echo "  1. 启动服务: ./start-services.sh start"
        echo "  2. 查看状态: ./start-services.sh status"
        echo "  3. 查看日志: ./start-services.sh logs"
        echo ""
        return 0
    else
        print_error "部分检查失败，请修复上述问题。"
        echo ""
        return 1
    fi
}

# 运行主函数
main

