# Docker 部署指南

## 📋 概述

本项目使用 Docker Compose 管理所有依赖服务，包括数据库、向量数据库等。

---

## 🏗️ 服务架构

### 核心服务（默认启动）

| 服务 | 端口 | 说明 | 必需 |
|------|------|------|------|
| **MySQL** | 3306 | 应用数据库 | ✅ 是 |
| **PostgreSQL** | 5433 | LangGraph Checkpointer | ✅ 是 |

### 扩展服务（可选启动）

| 服务 | 端口 | 说明 | 启动方式 |
|------|------|------|----------|
| **Neo4j** | 7474, 7687 | 图数据库 | `--profile full` |
| **Milvus** | 19530, 9091 | 向量数据库 | `--profile full` |
| **Redis** | 6379 | 缓存 | `--profile full` |

### Milvus 依赖服务

| 服务 | 端口 | 说明 |
|------|------|------|
| **etcd** | 2379 | Milvus 元数据存储 |
| **MinIO** | 9000, 9001 | Milvus 对象存储 |

---

## 🚀 快速开始

### 1. 启动核心服务

只启动 MySQL 和 PostgreSQL（最小化部署）：

```bash
# 启动核心服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 2. 启动所有服务

启动包括 Neo4j、Milvus、Redis 在内的所有服务：

```bash
# 启动所有服务
docker-compose --profile full up -d

# 查看服务状态
docker-compose --profile full ps

# 查看日志
docker-compose --profile full logs -f
```

### 3. 验证服务

```bash
# 检查 MySQL
docker exec -it chat_to_db_rwx-mysql mysql -uroot -pmysql -e "SELECT 1;"

# 检查 PostgreSQL
docker exec -it chat_to_db_rwx-postgres-checkpointer psql -U langgraph -d langgraph_checkpoints -c "SELECT 1;"

# 检查 Neo4j（如果启动）
docker exec -it chat_to_db_rwx-neo4j cypher-shell -u neo4j -p 65132090 "RETURN 1;"

# 检查 Redis（如果启动）
docker exec -it chat_to_db_rwx-redis redis-cli -a redis_password ping
```

---

## 📝 配置说明

### 环境变量

服务配置在 `docker-compose.yml` 中定义，对应的环境变量在 `backend/.env` 中配置。

#### MySQL 配置

```yaml
MYSQL_ROOT_PASSWORD: mysql
MYSQL_DATABASE: chatdb
MYSQL_USER: chatdb_user
MYSQL_PASSWORD: chatdb_password
```

对应 `.env`:
```bash
MYSQL_SERVER=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_DB=chatdb
MYSQL_PASSWORD=mysql
```

#### PostgreSQL Checkpointer 配置

```yaml
POSTGRES_DB: langgraph_checkpoints
POSTGRES_USER: langgraph
POSTGRES_PASSWORD: langgraph_password_2026
```

对应 `.env`:
```bash
CHECKPOINT_MODE=postgres
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints
```

#### Neo4j 配置

```yaml
NEO4J_AUTH: neo4j/65132090
```

对应 `.env`:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=65132090
```

#### Milvus 配置

对应 `.env`:
```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

---

## 🔧 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d                    # 核心服务
docker-compose --profile full up -d     # 所有服务

# 停止服务
docker-compose down                     # 核心服务
docker-compose --profile full down      # 所有服务

# 重启服务
docker-compose restart                  # 核心服务
docker-compose --profile full restart   # 所有服务

# 停止并删除数据卷（⚠️ 会删除所有数据）
docker-compose down -v
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f mysql
docker-compose logs -f postgres-checkpointer
docker-compose logs -f neo4j
docker-compose logs -f milvus

# 查看最近100行日志
docker-compose logs --tail=100 mysql
```

### 服务状态

```bash
# 查看服务状态
docker-compose ps

# 查看服务详细信息
docker-compose ps -a

# 查看资源使用
docker stats
```

### 数据管理

```bash
# 备份 MySQL 数据
docker exec chat_to_db_rwx-mysql mysqldump -uroot -pmysql chatdb > backup.sql

# 恢复 MySQL 数据
docker exec -i chat_to_db_rwx-mysql mysql -uroot -pmysql chatdb < backup.sql

# 备份 PostgreSQL 数据
docker exec chat_to_db_rwx-postgres-checkpointer pg_dump -U langgraph langgraph_checkpoints > checkpointer_backup.sql

# 恢复 PostgreSQL 数据
docker exec -i chat_to_db_rwx-postgres-checkpointer psql -U langgraph langgraph_checkpoints < checkpointer_backup.sql
```

---

## 🔍 故障排查

### 问题 1: 端口冲突

**症状**: 服务启动失败，提示端口已被占用

**解决方案**:

1. 检查端口占用：
```bash
# macOS/Linux
lsof -i :3306
lsof -i :5433

# Windows
netstat -ano | findstr :3306
netstat -ano | findstr :5433
```

2. 修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "3307:3306"  # 改为其他端口
```

3. 同时更新 `.env` 中的配置：
```bash
MYSQL_PORT=3307
```

### 问题 2: 服务无法启动

**症状**: 服务状态显示 `Exited` 或 `Restarting`

**解决方案**:

1. 查看日志：
```bash
docker-compose logs mysql
docker-compose logs postgres-checkpointer
```

2. 检查健康状态：
```bash
docker-compose ps
```

3. 重新创建服务：
```bash
docker-compose down
docker-compose up -d
```

### 问题 3: 数据持久化问题

**症状**: 重启后数据丢失

**解决方案**:

1. 检查数据卷：
```bash
docker volume ls | grep chatdb
```

2. 确保使用了数据卷：
```bash
docker-compose down  # 不要使用 -v 参数
```

3. 备份重要数据：
```bash
# 定期备份数据库
docker exec chatdb-mysql mysqldump -uroot -pmysql --all-databases > full_backup.sql
```

### 问题 4: 连接失败

**症状**: 应用无法连接到数据库

**解决方案**:

1. 检查服务是否运行：
```bash
docker-compose ps
```

2. 检查网络连接：
```bash
docker network inspect chatdb-network
```

3. 测试连接：
```bash
# 从容器内测试
docker exec -it chatdb-mysql mysql -uroot -pmysql -e "SELECT 1;"

# 从主机测试
mysql -h 127.0.0.1 -P 3306 -uroot -pmysql -e "SELECT 1;"
```

4. 检查防火墙设置

---

## 📊 性能优化

### MySQL 优化

编辑 `docker-compose.yml`，添加性能参数：

```yaml
mysql:
  command:
    - --character-set-server=utf8mb4
    - --collation-server=utf8mb4_unicode_ci
    - --default-authentication-plugin=mysql_native_password
    - --max_connections=1000
    - --innodb_buffer_pool_size=2G
    - --innodb_log_file_size=256M
```

### PostgreSQL 优化

```yaml
postgres-checkpointer:
  command:
    - postgres
    - -c
    - max_connections=200
    - -c
    - shared_buffers=256MB
    - -c
    - effective_cache_size=1GB
```

### Milvus 优化

```yaml
milvus:
  environment:
    MILVUS_CACHE_SIZE: 4GB
    MILVUS_INSERT_BUFFER_SIZE: 1GB
```

---

## 🔒 安全建议

### 1. 修改默认密码

⚠️ **生产环境必须修改所有默认密码！**

编辑 `docker-compose.yml`:

```yaml
mysql:
  environment:
    MYSQL_ROOT_PASSWORD: your_secure_password_here

postgres-checkpointer:
  environment:
    POSTGRES_PASSWORD: your_secure_password_here

neo4j:
  environment:
    NEO4J_AUTH: neo4j/your_secure_password_here
```

同时更新 `backend/.env` 中的对应配置。

### 2. 限制网络访问

只暴露必要的端口：

```yaml
mysql:
  ports:
    - "127.0.0.1:3306:3306"  # 只允许本地访问
```

### 3. 使用 Docker Secrets

对于生产环境，使用 Docker Secrets 管理敏感信息：

```yaml
secrets:
  mysql_root_password:
    file: ./secrets/mysql_root_password.txt

services:
  mysql:
    secrets:
      - mysql_root_password
    environment:
      MYSQL_ROOT_PASSWORD_FILE: /run/secrets/mysql_root_password
```

---

## 📦 数据卷管理

### 查看数据卷

```bash
# 列出所有数据卷
docker volume ls

# 查看特定数据卷详情
docker volume inspect chat_to_db_rwx-mysql-data
```

### 备份数据卷

```bash
# 备份 MySQL 数据卷
docker run --rm \
  -v chat_to_db_rwx-mysql-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mysql_backup.tar.gz /data

# 备份 PostgreSQL 数据卷
docker run --rm \
  -v chat_to_db_rwx-postgres-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data
```

### 恢复数据卷

```bash
# 恢复 MySQL 数据卷
docker run --rm \
  -v chat_to_db_rwx-mysql-data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/mysql_backup.tar.gz -C /

# 恢复 PostgreSQL 数据卷
docker run --rm \
  -v chat_to_db_rwx-postgres-data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

### 清理未使用的数据卷

```bash
# 清理所有未使用的数据卷（⚠️ 谨慎使用）
docker volume prune

# 删除特定数据卷
docker volume rm chat_to_db_rwx-mysql-data
```

---

## 🌐 网络配置

### 查看网络

```bash
# 列出所有网络
docker network ls

# 查看网络详情
docker network inspect chat_to_db_rwx-network
```

### 连接外部服务

如果需要连接到其他 Docker 网络中的服务：

```yaml
networks:
  chatdb-network:
    external: true
    name: existing-network-name
```

---

## 📋 部署检查清单

部署前请确认：

- [ ] 已修改所有默认密码
- [ ] 已配置正确的端口映射
- [ ] 已准备好数据备份策略
- [ ] 已配置防火墙规则
- [ ] 已测试服务连接
- [ ] 已配置日志轮转
- [ ] 已设置监控告警
- [ ] 已准备好回滚方案

---

## 🔗 相关文档

- [项目 README](../../README.md)
- [启动指南](../启动指南.md)
- [阿里云向量服务设置](ALIYUN_VECTOR_SETUP.md)

---

**最后更新**: 2026-01-18  
**维护者**: 项目团队
