# Docker 快速启动指南

## 🚀 一键启动

### 启动核心服务（推荐）

```bash
./start-services.sh start
```

这将启动：
- ✅ MySQL (端口 3306)
- ✅ PostgreSQL Checkpointer (端口 5433)

### 启动所有服务

```bash
./start-services.sh start-full
```

这将启动核心服务 + 扩展服务：
- ✅ MySQL (端口 3306)
- ✅ PostgreSQL Checkpointer (端口 5433)
- ✅ Neo4j (端口 7474, 7687)
- ✅ Milvus (端口 19530, 9091)
- ✅ Redis (端口 6379)

---

## 📋 常用命令

```bash
# 查看服务状态
./start-services.sh status

# 查看日志
./start-services.sh logs

# 停止服务
./start-services.sh stop

# 重启服务
./start-services.sh restart

# 查看帮助
./start-services.sh help
```

---

## 🔍 验证服务

### 检查 MySQL

```bash
docker exec -it chat_to_db_rwx-mysql mysql -uroot -pmysql -e "SELECT 1;"
```

### 检查 PostgreSQL

```bash
docker exec -it chat_to_db_rwx-postgres-checkpointer psql -U langgraph -d langgraph_checkpoints -c "SELECT 1;"
```

---

## 📖 详细文档

完整的部署说明请参考：[Docker 部署指南](docs/deployment/DOCKER_DEPLOYMENT.md)

---

## ⚠️ 注意事项

1. **首次启动**: 服务需要几秒钟初始化，请耐心等待
2. **端口冲突**: 如果端口被占用，请修改 `docker-compose.yml` 中的端口映射
3. **数据持久化**: 数据保存在 Docker 数据卷中，停止服务不会丢失数据
4. **清理数据**: 使用 `./start-services.sh clean` 会删除所有数据，请谨慎操作

---

**快速链接**:
- [项目 README](README.md)
- [Docker 部署指南](docs/deployment/DOCKER_DEPLOYMENT.md)
- [启动指南](docs/启动指南.md)
