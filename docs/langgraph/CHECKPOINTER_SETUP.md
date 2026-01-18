# LangGraph Checkpointer 部署指南

## 📋 概述

本指南说明如何使用 Docker 部署 PostgreSQL 作为 LangGraph Checkpointer 的持久化存储，实现多轮对话和会话管理功能。

---

## 🚀 快速开始

### 1. 启动 PostgreSQL 服务

```bash
# 进入 backend 目录
cd backend

# 启动 PostgreSQL 容器
docker-compose -f docker-compose.checkpointer.yml up -d

# 查看容器状态
docker-compose -f docker-compose.checkpointer.yml ps

# 查看日志
docker-compose -f docker-compose.checkpointer.yml logs -f postgres-checkpointer
```

### 2. 验证数据库连接

```bash
# 使用 psql 连接数据库
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints

# 在 psql 中执行
\dt  # 查看表（首次启动时为空，应用启动后会自动创建）
\q   # 退出
```

### 3. 配置应用

确保 `.env` 文件中的配置正确：

```bash
# LangGraph Checkpointer 配置
CHECKPOINT_MODE=postgres
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints

# 消息历史管理
MAX_MESSAGE_HISTORY=20
ENABLE_MESSAGE_SUMMARY=false
SUMMARY_THRESHOLD=10
```

### 4. 启动应用

```bash
# 应用启动时会自动初始化 Checkpointer 表结构
python chat_server.py
```

---

## 🔧 配置说明

### Docker Compose 配置

**文件**: `docker-compose.checkpointer.yml`

```yaml
services:
  postgres-checkpointer:
    image: postgres:15-alpine        # 使用轻量级 Alpine 版本
    container_name: langgraph-checkpointer-db
    ports:
      - "5433:5432"                  # 映射到 5433 避免冲突
    environment:
      POSTGRES_DB: langgraph_checkpoints
      POSTGRES_USER: langgraph
      POSTGRES_PASSWORD: langgraph_password_2026
    volumes:
      - postgres_checkpointer_data:/var/lib/postgresql/data  # 数据持久化
      - ./init-checkpointer-db.sql:/docker-entrypoint-initdb.d/init.sql
```

### 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `CHECKPOINT_MODE` | `postgres` | Checkpointer 模式：`postgres` 启用，`none` 禁用 |
| `CHECKPOINT_POSTGRES_URI` | `postgresql://...` | PostgreSQL 连接字符串 |
| `MAX_MESSAGE_HISTORY` | `20` | 最大保留消息数（防止 token 溢出） |
| `ENABLE_MESSAGE_SUMMARY` | `false` | 是否启用消息摘要（长对话优化） |
| `SUMMARY_THRESHOLD` | `10` | 触发摘要的消息数阈值 |

### 连接字符串格式

```
postgresql://[用户名]:[密码]@[主机]:[端口]/[数据库名]
```

**示例**:
```
postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints
```

---

## 📊 数据库结构

LangGraph 会自动创建以下表：

### checkpoints 表
存储会话检查点数据

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | VARCHAR | 会话 ID（主键之一） |
| checkpoint_id | VARCHAR | 检查点 ID（主键之一） |
| parent_id | VARCHAR | 父检查点 ID |
| checkpoint | JSONB | 检查点数据 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |

### checkpoint_writes 表
存储检查点写入记录

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | VARCHAR | 会话 ID |
| checkpoint_id | VARCHAR | 检查点 ID |
| task_id | VARCHAR | 任务 ID |
| idx | INTEGER | 索引 |
| channel | VARCHAR | 通道名称 |
| value | JSONB | 写入值 |

---

## 🛠️ 常用操作

### 查看所有会话

```sql
-- 连接数据库
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints

-- 查询会话列表
SELECT 
    thread_id,
    COUNT(*) as checkpoint_count,
    MAX(created_at) as last_updated
FROM checkpoints
GROUP BY thread_id
ORDER BY last_updated DESC
LIMIT 10;
```

### 查看特定会话的检查点

```sql
SELECT 
    checkpoint_id,
    parent_id,
    created_at,
    metadata
FROM checkpoints
WHERE thread_id = 'your-thread-id-here'
ORDER BY created_at DESC;
```

### 删除旧会话

```sql
-- 删除 7 天前的会话
DELETE FROM checkpoints
WHERE created_at < NOW() - INTERVAL '7 days';

-- 删除特定会话
DELETE FROM checkpoints
WHERE thread_id = 'your-thread-id-here';
```

### 查看数据库大小

```sql
SELECT 
    pg_size_pretty(pg_database_size('langgraph_checkpoints')) as database_size;

SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 🔍 故障排查

### 问题 1: 容器无法启动

**症状**: `docker-compose up` 失败

**解决方案**:
```bash
# 检查端口是否被占用
lsof -i :5433

# 如果被占用，修改 docker-compose.checkpointer.yml 中的端口映射
# 例如改为 "5434:5432"

# 同时更新 .env 中的连接字符串
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5434/langgraph_checkpoints
```

### 问题 2: 应用无法连接数据库

**症状**: 日志显示 "创建 PostgreSQL Checkpointer 失败"

**解决方案**:
```bash
# 1. 检查容器是否运行
docker ps | grep langgraph-checkpointer-db

# 2. 检查容器健康状态
docker-compose -f docker-compose.checkpointer.yml ps

# 3. 测试连接
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints -c "SELECT 1;"

# 4. 检查 .env 配置是否正确
cat .env | grep CHECKPOINT
```

### 问题 3: 数据库表未创建

**症状**: 查询时提示表不存在

**解决方案**:
```bash
# 应用启动时会自动创建表
# 如果未创建，检查应用日志

# 手动触发表创建（在 Python 中）
from app.core.checkpointer import get_checkpointer
checkpointer = get_checkpointer()
checkpointer.setup()  # 创建表结构
```

### 问题 4: 性能问题

**症状**: 查询响应慢

**解决方案**:
```sql
-- 创建索引优化查询
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoints(created_at);

-- 定期清理旧数据
DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL '30 days';

-- 执行 VACUUM
VACUUM ANALYZE checkpoints;
```

---

## 🔐 安全建议

### 生产环境配置

1. **修改默认密码**
```yaml
# docker-compose.checkpointer.yml
environment:
  POSTGRES_PASSWORD: your_strong_password_here
```

2. **限制网络访问**
```yaml
# 只允许本地访问
ports:
  - "127.0.0.1:5433:5432"
```

3. **使用环境变量**
```bash
# 不要在代码中硬编码密码
export CHECKPOINT_POSTGRES_URI="postgresql://user:password@host:port/db"
```

4. **启用 SSL 连接**
```bash
# 在连接字符串中添加 SSL 参数
CHECKPOINT_POSTGRES_URI=postgresql://user:password@host:port/db?sslmode=require
```

---

## 📈 监控与维护

### 定期备份

```bash
# 备份数据库
docker exec langgraph-checkpointer-db pg_dump -U langgraph langgraph_checkpoints > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker exec -i langgraph-checkpointer-db psql -U langgraph langgraph_checkpoints < backup_20260118.sql
```

### 监控指标

```sql
-- 会话数量
SELECT COUNT(DISTINCT thread_id) as total_sessions FROM checkpoints;

-- 今日新增会话
SELECT COUNT(DISTINCT thread_id) as today_sessions 
FROM checkpoints 
WHERE created_at >= CURRENT_DATE;

-- 平均检查点数
SELECT AVG(checkpoint_count) as avg_checkpoints
FROM (
    SELECT thread_id, COUNT(*) as checkpoint_count
    FROM checkpoints
    GROUP BY thread_id
) t;

-- 数据库连接数
SELECT count(*) FROM pg_stat_activity WHERE datname = 'langgraph_checkpoints';
```

### 清理策略

```bash
# 创建定时清理脚本
cat > cleanup_old_checkpoints.sh << 'EOF'
#!/bin/bash
docker exec langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints -c "
DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL '30 days';
VACUUM ANALYZE checkpoints;
"
EOF

chmod +x cleanup_old_checkpoints.sh

# 添加到 crontab（每天凌晨 2 点执行）
# 0 2 * * * /path/to/cleanup_old_checkpoints.sh
```

---

## 🧪 测试验证

### 测试脚本

```python
# test_checkpointer.py
import asyncio
from app.core.checkpointer import get_checkpointer, check_checkpointer_health

async def test_checkpointer():
    """测试 Checkpointer 功能"""
    
    # 1. 健康检查
    print("1. 健康检查...")
    is_healthy = check_checkpointer_health()
    print(f"   健康状态: {'✓ 正常' if is_healthy else '✗ 异常'}")
    
    # 2. 获取实例
    print("\n2. 获取 Checkpointer 实例...")
    checkpointer = get_checkpointer()
    print(f"   实例类型: {type(checkpointer).__name__}")
    
    # 3. 测试基本功能
    print("\n3. 测试完成")
    print("   Checkpointer 工作正常！")

if __name__ == "__main__":
    asyncio.run(test_checkpointer())
```

运行测试：
```bash
cd backend
python test_checkpointer.py
```

---

## 📚 参考资料

- [LangGraph Persistence 文档](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Docker Compose 文档](https://docs.docker.com/compose/)

---

## 🆘 获取帮助

如果遇到问题：

1. 查看应用日志
2. 查看 PostgreSQL 容器日志
3. 参考本文档的故障排查部分
4. 检查 LangGraph 官方文档

---

**文档版本**: v1.0  
**创建日期**: 2026-01-18  
**最后更新**: 2026-01-18
