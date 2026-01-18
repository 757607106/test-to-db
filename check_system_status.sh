#!/bin/bash

# 系统状态检查脚本
# 检查所有服务和配置的状态

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

# 检查 Docker 容器
check_docker_containers() {
    print_header "Docker 容器状态"
    
    containers=("chat_to_db_rwx-mysql" "chat_to_db_rwx-postgres-checkpointer" "chat_to_db_rwx-neo4j" "chat_to_db_rwx-milvus" "chat_to_db_rwx-redis")
    
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            status=$(docker ps --format "{{.Status}}" --filter "name=^${container}$")
            print_success "$container: $status"
        else
            print_error "$container: 未运行"
        fi
    done
}

# 检查端口
check_ports() {
    print_header "端口状态"
    
    ports=("3306:MySQL" "5433:PostgreSQL" "7474:Neo4j HTTP" "7687:Neo4j Bolt" "19530:Milvus" "6380:Redis")
    
    for port_info in "${ports[@]}"; do
        port=$(echo $port_info | cut -d: -f1)
        service=$(echo $port_info | cut -d: -f2)
        
        if lsof -i :$port > /dev/null 2>&1; then
            print_success "$service (端口 $port): 正在监听"
        else
            print_warning "$service (端口 $port): 未监听"
        fi
    done
}

# 检查数据库连接
check_database_connections() {
    print_header "数据库连接测试"
    
    # MySQL
    if docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql -e "SELECT 1;" > /dev/null 2>&1; then
        print_success "MySQL: 连接成功"
        db_count=$(docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql -e "SHOW DATABASES;" 2>/dev/null | wc -l)
        echo "  数据库数量: $((db_count - 1))"
    else
        print_error "MySQL: 连接失败"
    fi
    
    # PostgreSQL
    if docker exec chat_to_db_rwx-postgres-checkpointer psql -U langgraph -d langgraph_checkpoints -c "SELECT 1;" > /dev/null 2>&1; then
        print_success "PostgreSQL: 连接成功"
    else
        print_error "PostgreSQL: 连接失败"
    fi
    
    # Neo4j
    if docker exec chat_to_db_rwx-neo4j cypher-shell -u neo4j -p 65132090 "RETURN 1;" > /dev/null 2>&1; then
        print_success "Neo4j: 连接成功"
    else
        print_warning "Neo4j: 连接失败（可能还在启动中）"
    fi
}

# 检查应用数据
check_application_data() {
    print_header "应用数据统计"
    
    if docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql chatdb -e "SELECT COUNT(*) as count FROM users;" 2>/dev/null | tail -1 > /dev/null 2>&1; then
        user_count=$(docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql chatdb -e "SELECT COUNT(*) as count FROM users;" 2>/dev/null | tail -1)
        conn_count=$(docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql chatdb -e "SELECT COUNT(*) as count FROM dbconnection;" 2>/dev/null | tail -1)
        
        print_info "用户数: $user_count"
        print_info "数据库连接数: $conn_count"
        
        echo ""
        print_info "数据库连接列表:"
        docker exec chat_to_db_rwx-mysql mysql -uroot -pmysql chatdb -e "SELECT id, name, db_type, host FROM dbconnection;" 2>/dev/null | tail -n +2
    else
        print_warning "无法获取应用数据"
    fi
}

# 检查数据卷
check_volumes() {
    print_header "Docker 数据卷"
    
    volumes=$(docker volume ls --format "{{.Name}}" | grep chat_to_db_rwx)
    
    if [ -n "$volumes" ]; then
        echo "$volumes" | while read volume; do
            size=$(docker volume inspect $volume --format '{{.Mountpoint}}' | xargs du -sh 2>/dev/null | cut -f1)
            print_info "$volume: $size"
        done
    else
        print_warning "没有找到数据卷"
    fi
}

# 检查环境配置
check_environment() {
    print_header "环境配置"
    
    if [ -f "backend/.env" ]; then
        print_success ".env 文件存在"
        
        # 检查关键配置
        if grep -q "CHECKPOINT_MODE=postgres" backend/.env; then
            print_success "Checkpointer 模式: postgres"
        fi
        
        if grep -q "NEO4J_URI=bolt://localhost:7687" backend/.env; then
            print_success "Neo4j 配置: bolt://localhost:7687"
        fi
        
        if grep -q "MILVUS_HOST=localhost" backend/.env; then
            print_success "Milvus 配置: localhost:19530"
        fi
    else
        print_error ".env 文件不存在"
    fi
}

# 主函数
main() {
    print_header "Chat-to-DB 系统状态检查"
    
    check_docker_containers
    check_ports
    check_database_connections
    check_application_data
    check_volumes
    check_environment
    
    print_header "检查完成"
    
    print_info "💡 提示:"
    echo "  - 如果服务未运行，执行: ./start-services.sh start-full"
    echo "  - 如果需要重置环境，执行: ./reset_and_init_docker.sh"
    echo "  - 查看服务日志: ./start-services.sh logs"
    echo ""
}

# 运行主函数
main
