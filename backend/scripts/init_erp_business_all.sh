#!/bin/bash
# ============================================================
# 进销存业务系统一键初始化脚本
# 功能: 自动执行SQL建表 + Python数据生成
# ============================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5433}"
POSTGRES_USER="${POSTGRES_USER:-langgraph}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-langgraph_password_2026}"
DATABASE_NAME="erp_business"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/init_erp_business.sql"
PYTHON_SCRIPT="${SCRIPT_DIR}/init_erp_business_data.py"

echo ""
echo "============================================================"
echo "  进销存业务系统数据库初始化"
echo "============================================================"
echo ""
echo "配置信息:"
echo "  主机: ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "  用户: ${POSTGRES_USER}"
echo "  数据库: ${DATABASE_NAME}"
echo ""

# ============================================================
# 1. 检查依赖
# ============================================================

echo -e "${BLUE}[步骤 1/5] 检查依赖...${NC}"

# 检查psql命令
if ! command -v psql &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 psql 命令${NC}"
    echo "   请安装 PostgreSQL 客户端工具"
    echo ""
    echo "   macOS: brew install postgresql@15"
    echo "   Ubuntu: sudo apt-get install postgresql-client-15"
    exit 1
fi
echo -e "${GREEN}✓ psql 命令可用${NC}"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 错误: 未找到 python3 命令${NC}"
    exit 1
fi
echo -e "${GREEN}✓ python3 可用${NC}"

# 检查Python依赖
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  警告: psycopg2-binary 未安装${NC}"
    echo "   正在尝试安装..."
    pip3 install psycopg2-binary || {
        echo -e "${RED}❌ 安装失败,请手动执行: pip3 install psycopg2-binary${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ psycopg2-binary 安装成功${NC}"
else
    echo -e "${GREEN}✓ psycopg2-binary 已安装${NC}"
fi

# 检查文件
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}❌ 错误: 未找到SQL文件: ${SQL_FILE}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SQL文件存在${NC}"

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}❌ 错误: 未找到Python脚本: ${PYTHON_SCRIPT}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python脚本存在${NC}"

echo ""

# ============================================================
# 2. 测试数据库连接
# ============================================================

echo -e "${BLUE}[步骤 2/5] 测试数据库连接...${NC}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

if ! psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "SELECT 1;" &> /dev/null; then
    echo -e "${RED}❌ 错误: 无法连接到PostgreSQL数据库${NC}"
    echo "   请确保:"
    echo "   1. PostgreSQL容器正在运行"
    echo "   2. 端口配置正确 (默认5433)"
    echo "   3. 用户名密码正确"
    echo ""
    echo "   检查容器状态: docker ps | grep postgres"
    echo "   启动容器: docker-compose up -d postgres-checkpointer"
    exit 1
fi
echo -e "${GREEN}✓ 数据库连接成功${NC}"
echo ""

# ============================================================
# 3. 创建数据库
# ============================================================

echo -e "${BLUE}[步骤 3/5] 创建数据库 ${DATABASE_NAME}...${NC}"

# 检查数据库是否存在
DB_EXISTS=$(psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DATABASE_NAME}';")

if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${YELLOW}⚠️  数据库已存在,是否删除并重建? (y/N)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "正在删除数据库..."
        psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DATABASE_NAME};" > /dev/null
        echo -e "${GREEN}✓ 数据库已删除${NC}"
    else
        echo -e "${YELLOW}跳过数据库创建${NC}"
        echo ""
    fi
fi

# 创建数据库
if [ "$DB_EXISTS" != "1" ] || [[ "$response" =~ ^[Yy]$ ]]; then
    psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${DATABASE_NAME} WITH ENCODING 'UTF8';" > /dev/null 2>&1 || true
    echo -e "${GREEN}✓ 数据库创建成功${NC}"
fi
echo ""

# ============================================================
# 4. 执行SQL建表脚本
# ============================================================

echo -e "${BLUE}[步骤 4/5] 执行SQL建表脚本...${NC}"
echo "   这可能需要几秒钟..."

# 修改SQL文件,去掉\c命令(因为我们会直接指定数据库)
TEMP_SQL="/tmp/init_erp_business_temp.sql"
grep -v "^\\\\c " "$SQL_FILE" > "$TEMP_SQL" 2>/dev/null || cp "$SQL_FILE" "$TEMP_SQL"

if psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${DATABASE_NAME}" -f "$TEMP_SQL" > /tmp/sql_output.log 2>&1; then
    echo -e "${GREEN}✓ SQL脚本执行成功${NC}"
    
    # 统计创建的表数量
    TABLE_COUNT=$(psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${DATABASE_NAME}" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
    echo -e "${GREEN}✓ 已创建 ${TABLE_COUNT} 张表${NC}"
else
    echo -e "${RED}❌ SQL脚本执行失败${NC}"
    echo "   错误日志:"
    tail -20 /tmp/sql_output.log
    rm -f "$TEMP_SQL"
    exit 1
fi

rm -f "$TEMP_SQL"
echo ""

# ============================================================
# 5. 执行Python数据生成脚本
# ============================================================

echo -e "${BLUE}[步骤 5/5] 执行Python数据生成脚本...${NC}"
echo "   这可能需要5-15分钟,请耐心等待..."
echo ""

# 设置环境变量
export POSTGRES_HOST="${POSTGRES_HOST}"
export POSTGRES_PORT="${POSTGRES_PORT}"
export POSTGRES_USER="${POSTGRES_USER}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"

# 执行Python脚本
if python3 "${PYTHON_SCRIPT}"; then
    echo ""
    echo -e "${GREEN}✓ 数据生成成功${NC}"
else
    echo ""
    echo -e "${RED}❌ 数据生成失败${NC}"
    exit 1
fi

# ============================================================
# 完成
# ============================================================

echo ""
echo "============================================================"
echo -e "${GREEN}✅ 初始化完成!${NC}"
echo "============================================================"
echo ""
echo "数据库连接信息:"
echo "  类型: PostgreSQL 15"
echo "  主机: ${POSTGRES_HOST}"
echo "  端口: ${POSTGRES_PORT}"
echo "  数据库: ${DATABASE_NAME}"
echo "  用户: ${POSTGRES_USER}"
echo "  密码: ${POSTGRES_PASSWORD}"
echo ""
echo "连接字符串:"
echo "  postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${DATABASE_NAME}"
echo ""
echo "下一步:"
echo "  1. 使用DBeaver/pgAdmin连接数据库查看数据"
echo "  2. 运行多维度分析查询: erp_business_queries.sql"
echo "  3. 将数据库配置到你的BI系统"
echo ""

unset PGPASSWORD
