# 数据库初始化指南

## 📋 概览

本指南介绍如何初始化Chat-to-DB项目所需的所有数据库，包括：
- 主应用数据库（chatdb）
- 测试数据库（进销存系统）
- Checkpointer数据库（LangGraph）

---

## 🎯 前提条件

### 1. MySQL 8.0+
确保MySQL服务正在运行：
```bash
# 检查MySQL状态
mysql --version
mysql -u root -p -e "SELECT VERSION();"
```

### 2. Python 3.8+
确保Python环境已配置：
```bash
python3 --version
pip3 install pymysql python-dotenv
```

### 3. 环境变量
配置 `.env` 文件（根目录或backend目录）：
```bash
MYSQL_SERVER=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=chatdb
```

---

## 🚀 快速开始

### 一键初始化（推荐）

```bash
cd backend/scripts

# 1. 初始化主数据库结构
mysql -u root -p < init_database_complete.sql

# 2. 初始化基础数据（用户、连接等）
python3 init_mock_data.py

# 3. 初始化测试数据库（可选）
python3 init_inventory_simple.py
```

---

## 📝 详细步骤

### Step 1: 初始化主数据库

#### 方法1: 使用SQL脚本（推荐）

```bash
cd backend/scripts
mysql -u root -p < init_database_complete.sql
```

这将创建：
- ✅ chatdb 数据库
- ✅ 12张核心表
- ✅ 所有索引和外键关系

**验证**:
```bash
mysql -u root -p -e "USE chatdb; SHOW TABLES;"
```

应该看到12张表：
- users
- dbconnection
- schematable
- schemacolumn
- schemarelationship
- valuemapping
- dashboards
- dashboard_widgets
- dashboard_permissions
- llm_configuration
- agent_profile
- query_history

#### 方法2: 使用Alembic迁移

```bash
cd backend

# 初始化Alembic（如果首次使用）
alembic init alembic

# 执行迁移
alembic upgrade head
```

---

### Step 2: 初始化基础Mock数据

运行 `init_mock_data.py` 脚本：

```bash
cd backend/scripts
python3 init_mock_data.py
```

这将创建：
- ✅ 管理员用户 (admin/admin123)
- ✅ 测试用户 (test_user/test123)
- ✅ 示例数据库连接（Chinook示例数据库）
- ✅ Chinook数据库的Schema元数据
- ✅ 值映射示例

**验证**:
```bash
mysql -u root -p chatdb -e "
SELECT '用户数:' as info, COUNT(*) as count FROM users
UNION ALL
SELECT '连接数:', COUNT(*) FROM dbconnection
UNION ALL
SELECT 'Schema表数:', COUNT(*) FROM schematable;
"
```

---

### Step 3: 初始化测试数据库

#### 选项A: 简化版进销存系统（推荐用于测试）

创建 `inventory_demo` 数据库（16张表，~1700条数据）：

```bash
cd backend/scripts
python3 init_inventory_simple.py
```

**特点**:
- ✅ 16张核心表
- ✅ 约1700条测试数据
- ✅ 包含完整的进销存业务流程
- ✅ 适合快速测试Text2SQL功能

**数据库连接信息**:
```
数据库名: inventory_demo
主机: localhost
端口: 3306
用户名: root
密码: (你的MySQL密码)
```

#### 选项B: 完整版进销存ERP系统

创建 `erp_inventory` 数据库（34张表，~5000条数据）：

```bash
cd backend/scripts
python3 init_erp_mock_data.py
```

**特点**:
- ✅ 34张表（完整ERP结构）
- ✅ 约5000条测试数据
- ✅ 支持批次管理、库位管理
- ✅ 适合复杂业务场景测试

**数据库连接信息**:
```
数据库名: erp_inventory
主机: localhost
端口: 3306
用户名: root
密码: (你的MySQL密码)
```

**验证测试数据库**:
```bash
cd backend/scripts
python3 verify_inventory_db.py
```

---

### Step 4: 初始化LangGraph Checkpointer数据库

如果使用Docker部署，需要初始化PostgreSQL checkpointer数据库：

```bash
cd backend/scripts

# 方法1: Docker容器内执行
docker exec -i chat_to_db_rwx-postgres-checkpointer psql -U langgraph -d langgraph_checkpoints < init-checkpointer-db.sql

# 方法2: 本地PostgreSQL
psql -U langgraph -d langgraph_checkpoints < init-checkpointer-db.sql
```

---

## 🔧 高级配置

### 自定义数据库名称

编辑脚本中的数据库名称：

```python
# 例如：修改 init_inventory_simple.py
DATABASE_NAME = 'my_custom_db'  # 改为你想要的名称
```

### 修改Mock数据

编辑脚本中的数据常量数组：

```python
# 例如：添加更多供应商
SUPPLIERS = [
    ('S001', '深圳华强电子', '张经理', '0755-88881001', ...),
    ('S002', '你的供应商', '李经理', '0755-88881002', ...),
    # ... 添加更多
]
```

### 批量导入数据

如果有现有的SQL dump文件：

```bash
mysql -u root -p chatdb < your_data_dump.sql
```

---

## 🧹 清理和重置

### 重置主数据库

```bash
# ⚠️ 警告：这将删除所有数据
mysql -u root -p -e "DROP DATABASE IF EXISTS chatdb;"
mysql -u root -p < backend/scripts/init_database_complete.sql
```

### 重置测试数据库

```bash
# 重置简化版
python3 backend/scripts/init_inventory_simple.py

# 重置完整版
python3 backend/scripts/init_erp_mock_data.py
```

### 清理硬编码的示例连接

如果之前存在硬编码的"Sample Database"连接：

```bash
cd backend/scripts

# 方法1: 使用SQL
mysql -u root -p chatdb < cleanup_sample_db.sql

# 方法2: 使用Python脚本
python3 cleanup_sample_db.py
```

---

## ✅ 验证检查清单

运行以下命令验证初始化是否成功：

```bash
# 1. 检查chatdb数据库
mysql -u root -p -e "
SELECT table_schema, COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema IN ('chatdb', 'inventory_demo', 'erp_inventory')
GROUP BY table_schema;
"

# 2. 检查用户数据
mysql -u root -p chatdb -e "
SELECT username, email, role, is_active 
FROM users;
"

# 3. 检查数据库连接
mysql -u root -p chatdb -e "
SELECT id, name, db_type, host, port, database_name 
FROM dbconnection;
"

# 4. 检查测试数据库（如果已创建）
mysql -u root -p -e "SHOW DATABASES LIKE '%inventory%';"
```

---

## 🐛 常见问题

### 问题1: 连接被拒绝
```
ERROR 2002 (HY000): Can't connect to local MySQL server
```

**解决方案**:
```bash
# 检查MySQL是否运行
sudo systemctl status mysql  # Linux
brew services list            # macOS

# 启动MySQL
sudo systemctl start mysql    # Linux
brew services start mysql     # macOS
```

### 问题2: 权限不足
```
ERROR 1044 (42000): Access denied for user 'xxx'@'localhost'
```

**解决方案**:
```bash
# 以root用户登录
mysql -u root -p

# 授予权限
GRANT ALL PRIVILEGES ON chatdb.* TO 'your_user'@'localhost';
GRANT ALL PRIVILEGES ON inventory_demo.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;
```

### 问题3: 表已存在
```
ERROR 1050 (42S01): Table 'xxx' already exists
```

**解决方案**:
```bash
# 删除并重建（⚠️ 会丢失数据）
mysql -u root -p -e "DROP DATABASE chatdb;"
mysql -u root -p < backend/scripts/init_database_complete.sql
```

### 问题4: 字符集问题
```
Incorrect string value: '\xE4\xB8\xAD\xE6\x96\x87'
```

**解决方案**:
```bash
# 确保使用utf8mb4字符集
mysql -u root -p -e "
ALTER DATABASE chatdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"
```

### 问题5: Python依赖缺失
```
ModuleNotFoundError: No module named 'pymysql'
```

**解决方案**:
```bash
pip3 install pymysql python-dotenv
```

---

## 📚 相关文档

- [数据库表结构说明](DATABASE_SCHEMA.md)
- [测试数据库说明](TEST_DATABASES.md)
- [数据库连接配置](DATABASE_CONNECTION_INFO.md)

---

## 🔗 下一步

初始化完成后，你可以：

1. **启动后端服务**: `cd backend && python3 admin_server.py`
2. **访问Admin后台**: http://localhost:8000
3. **添加数据库连接**: 在Admin中配置测试数据库
4. **测试Text2SQL**: 开始使用自然语言查询数据库

---

**最后更新**: 2026-01-18
