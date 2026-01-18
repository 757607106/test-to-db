# 🚀 Checkpointer 快速开始指南

## 3 步启动多轮对话功能

### 步骤 1: 安装依赖 📦

```bash
cd backend
pip install -r requirements.txt
```

这将安装：
- `langgraph-checkpoint-postgres` - PostgreSQL Checkpointer
- `psycopg2-binary` - PostgreSQL 驱动

### 步骤 2: 启动 PostgreSQL 🐘

```bash
./start-checkpointer.sh
```

或手动启动：
```bash
docker-compose -f docker-compose.checkpointer.yml up -d
```

### 步骤 3: 验证安装 ✅

```bash
python3 test_checkpointer.py
```

预期输出：
```
============================================================
  🎉 所有测试通过！Checkpointer 已就绪
============================================================
```

---

## 🎯 使用示例

### 基础用法

```python
from app.agents.chat_graph import IntelligentSQLGraph

# 创建 Graph 实例
graph = IntelligentSQLGraph()

# 处理查询
result = await graph.process_query(
    query="查询2024年的销售数据",
    connection_id=15
)

print(f"Thread ID: {result['thread_id']}")
print(f"Success: {result['success']}")
```

### 多轮对话

```python
# 第一轮对话
result1 = await graph.process_query(
    query="查询2024年的销售数据",
    connection_id=15
)
thread_id = result1["thread_id"]

# 第二轮对话（使用相同 thread_id）
result2 = await graph.process_query(
    query="按月份分组",
    connection_id=15,
    thread_id=thread_id  # 继续之前的对话
)

# 第三轮对话
result3 = await graph.process_query(
    query="只看前3个月",
    connection_id=15,
    thread_id=thread_id  # 继续同一对话
)
```

---

## ⚙️ 配置

### 启用/禁用 Checkpointer

编辑 `.env` 文件：

```bash
# 启用（默认）
CHECKPOINT_MODE=postgres

# 禁用
CHECKPOINT_MODE=none
```

### 自定义连接

```bash
# 修改连接字符串
CHECKPOINT_POSTGRES_URI=postgresql://user:password@host:port/database
```

### 消息历史管理

```bash
# 最大保留消息数
MAX_MESSAGE_HISTORY=20

# 启用消息摘要
ENABLE_MESSAGE_SUMMARY=true

# 摘要触发阈值
SUMMARY_THRESHOLD=10
```

---

## 🔧 常用命令

### Docker 管理

```bash
# 启动
docker-compose -f docker-compose.checkpointer.yml up -d

# 停止
docker-compose -f docker-compose.checkpointer.yml down

# 重启
docker-compose -f docker-compose.checkpointer.yml restart

# 查看日志
docker-compose -f docker-compose.checkpointer.yml logs -f

# 查看状态
docker-compose -f docker-compose.checkpointer.yml ps
```

### 数据库操作

```bash
# 连接数据库
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints

# 查看表
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints -c "\dt"

# 查看会话数量
docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints -c "SELECT COUNT(DISTINCT thread_id) FROM checkpoints;"
```

### 测试

```bash
# 基础测试
python3 test_checkpointer.py

# 单元测试
pytest tests/test_checkpointer_unit.py -v

# 集成测试
python3 test_graph_checkpointer_integration.py
```

---

## 📚 更多文档

- [完整部署指南](./CHECKPOINTER_SETUP.md) - 详细的部署和运维文档
- [依赖安装指南](./INSTALL_CHECKPOINTER_DEPS.md) - 依赖安装说明
- [快速参考](./CHECKPOINTER_README.md) - 常用命令和配置
- [完成总结](./PHASE1_FINAL_SUMMARY.md) - 功能特性和技术细节

---

## ❓ 常见问题

### Q: 如何禁用 Checkpointer？
A: 在 `.env` 中设置 `CHECKPOINT_MODE=none`

### Q: 如何查看会话历史？
A: 使用 SQL 查询：
```sql
SELECT * FROM checkpoints WHERE thread_id = 'your-thread-id';
```

### Q: 如何清理旧会话？
A: 使用 SQL 删除：
```sql
DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL '7 days';
```

### Q: 容器无法启动？
A: 检查端口是否被占用：
```bash
lsof -i :5433
```

---

## 🆘 获取帮助

如果遇到问题：

1. 查看 [故障排查指南](./CHECKPOINTER_SETUP.md#故障排查)
2. 检查容器日志
3. 运行测试脚本诊断问题

---

**快速开始指南** | 创建日期: 2026-01-18
