# Phase 2 设置指南

## 📋 概述

本指南帮助您完成 Phase 2 的设置，启用多轮对话和状态持久化功能。

---

## 🔧 前置条件

在开始之前，请确保已完成 Phase 1 的设置：

- ✅ PostgreSQL Checkpointer 已通过 Docker 部署
- ✅ 环境变量已配置（`.env` 文件）
- ✅ Phase 1 测试通过

如果还未完成 Phase 1，请先阅读：
- `backend/CHECKPOINTER_SETUP.md`
- `backend/GETTING_STARTED_CHECKPOINTER.md`

---

## 📦 步骤1: 安装依赖

Phase 2 需要以下额外的 Python 包：

```bash
# 进入backend目录
cd backend

# 安装所有依赖（包括Phase 2所需的）
pip install -r requirements.txt
```

**关键依赖**:
- `langgraph-checkpoint-postgres~=2.0.14` - PostgreSQL Checkpointer
- `psycopg2-binary~=2.9.10` - PostgreSQL 驱动

### 验证安装

```bash
python3 verify_phase2_setup.py
```

**预期输出**:
```
============================================================
Phase 2 设置验证
============================================================

=== 检查Python依赖 ===
✓ LangGraph核心库: langgraph
✓ PostgreSQL Checkpointer: langgraph.checkpoint.postgres
✓ PostgreSQL驱动: psycopg2
✓ LangChain核心库: langchain_core

✓ 所有依赖已安装

=== 检查环境变量 ===
✓ .env文件存在
✓ CHECKPOINT_MODE: postgres
✓ CHECKPOINT_POSTGRES_URI: postgresql:****@localhost:5433/...

✓ 所有环境变量已配置

=== 检查Checkpointer ===
✓ Checkpointer类型: PostgresSaver
✓ Checkpointer健康检查通过

=== 检查Graph ===
✓ Graph创建成功: IntelligentSQLGraph
✓ Supervisor: SupervisorAgent
✓ Worker Agents数量: 5

============================================================
验证结果总结
============================================================
依赖检查: ✓ 通过
环境变量: ✓ 通过
Checkpointer: ✓ 通过
Graph: ✓ 通过
============================================================

✓ 所有检查通过！Phase 2 已准备就绪。
```

---

## 🚀 步骤2: 启动 PostgreSQL Checkpointer

如果还未启动 PostgreSQL 服务：

```bash
# 启动PostgreSQL Checkpointer
docker-compose -f docker-compose.checkpointer.yml up -d

# 查看日志
docker-compose -f docker-compose.checkpointer.yml logs -f

# 验证服务状态
docker-compose -f docker-compose.checkpointer.yml ps
```

**预期输出**:
```
NAME                          STATUS    PORTS
langgraph-checkpointer-db-1   Up        0.0.0.0:5433->5432/tcp
```

---

## ✅ 步骤3: 运行测试

运行 Phase 2 的集成测试：

```bash
python3 test_phase2_api_integration.py
```

**预期输出**:
```
============================================================
Phase 2 API集成测试
============================================================

=== 测试Checkpointer健康状态 ===
Checkpointer类型: PostgresSaver
健康状态: True
✓ 健康检查通过

=== 测试单轮对话 ===
成功: True
Thread ID: xxx-xxx-xxx-xxx
最终阶段: completed
✓ 单轮对话测试通过

=== 测试多轮对话 ===
第一轮: 查询2024年的销售数据
Thread ID: xxx-xxx-xxx-xxx
成功: True

第二轮: 按月份分组（使用相同thread_id）
Thread ID: xxx-xxx-xxx-xxx
成功: True
✓ 多轮对话测试通过

=== 测试thread_id持久化 ===
使用自定义thread_id: test-xxx-xxx-xxx
查询结果: True
返回的thread_id: test-xxx-xxx-xxx
✓ thread_id持久化测试通过

=== 测试会话隔离 ===
会话1 Thread ID: xxx-xxx-xxx-xxx
会话2 Thread ID: yyy-yyy-yyy-yyy
✓ 会话隔离测试通过

=== 测试错误处理 ===
成功: False
Thread ID: xxx-xxx-xxx-xxx
错误: ...
✓ 错误处理测试通过

============================================================
✓ 所有测试通过！
============================================================
```

---

## 🔍 步骤4: 验证API功能

### 4.1 启动服务

```bash
# 启动后端服务
python3 chat_server.py
```

### 4.2 测试单轮对话（向后兼容）

```bash
curl -X POST http://localhost:8000/api/v1/query/chat \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": 15,
    "natural_language_query": "查询所有客户"
  }'
```

**预期响应**:
```json
{
  "conversation_id": "xxx-xxx-xxx-xxx",
  "stage": "completed",
  "sql": "SELECT * FROM customers",
  "results": [...]
}
```

### 4.3 测试多轮对话

**第一轮**:
```bash
curl -X POST http://localhost:8000/api/v1/query/chat \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": 15,
    "natural_language_query": "查询2024年的销售数据"
  }'
```

保存返回的 `conversation_id`。

**第二轮**（使用相同的 `conversation_id`）:
```bash
curl -X POST http://localhost:8000/api/v1/query/chat \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": 15,
    "natural_language_query": "按月份分组",
    "conversation_id": "xxx-xxx-xxx-xxx"
  }'
```

系统会理解"按月份分组"是指对之前的销售数据进行分组。

---

## 🛠️ 故障排查

### 问题1: 依赖安装失败

**症状**:
```
ModuleNotFoundError: No module named 'langgraph.checkpoint.postgres'
```

**解决方案**:
```bash
# 确保使用正确的Python环境
which python3

# 重新安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 验证安装
python3 -c "import langgraph.checkpoint.postgres; print('OK')"
```

### 问题2: PostgreSQL连接失败

**症状**:
```
Checkpointer健康检查失败
```

**解决方案**:
```bash
# 1. 检查PostgreSQL服务状态
docker-compose -f docker-compose.checkpointer.yml ps

# 2. 如果未运行，启动服务
docker-compose -f docker-compose.checkpointer.yml up -d

# 3. 检查日志
docker-compose -f docker-compose.checkpointer.yml logs

# 4. 测试连接
docker exec -it langgraph-checkpointer-db-1 psql -U langgraph -d langgraph_checkpoints -c "SELECT 1;"
```

### 问题3: 环境变量未配置

**症状**:
```
✗ CHECKPOINT_POSTGRES_URI: 未配置
```

**解决方案**:
```bash
# 1. 检查.env文件是否存在
ls -la backend/.env

# 2. 如果不存在，从示例复制
cp backend/.env.example backend/.env

# 3. 编辑.env文件，确保包含:
# CHECKPOINT_MODE=postgres
# CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints
```

### 问题4: Graph创建失败

**症状**:
```
✗ Graph创建失败
```

**解决方案**:
```bash
# 1. 运行验证脚本查看详细错误
python3 verify_phase2_setup.py

# 2. 检查所有依赖是否已安装
pip list | grep langgraph

# 3. 检查数据库连接
python3 -c "from app.core.checkpointer import get_checkpointer; print(get_checkpointer())"
```

---

## 📚 相关文档

- **Phase 1 完成报告**: `PHASE1_FINAL_SUMMARY.md`
- **Phase 2 完成报告**: `PHASE2_COMPLETE.md`
- **Checkpointer 设置**: `CHECKPOINTER_SETUP.md`
- **快速开始指南**: `GETTING_STARTED_CHECKPOINTER.md`
- **设计文档**: `../.kiro/specs/langgraph-memory-activation/design.md`

---

## 🎯 下一步

Phase 2 设置完成后，您可以：

1. **使用多轮对话功能**
   - 在API调用中传递 `conversation_id`
   - 系统会自动恢复历史上下文

2. **进入 Phase 3**
   - 实现会话管理API的具体逻辑
   - 添加消息历史管理
   - 性能优化

3. **集成到前端**
   - 修改前端代码以支持 `conversation_id`
   - 实现会话列表UI
   - 添加会话管理功能

---

## ✅ 验收清单

在继续之前，请确认：

- [ ] 所有依赖已安装（`verify_phase2_setup.py` 通过）
- [ ] PostgreSQL Checkpointer 已启动并运行
- [ ] 环境变量已正确配置
- [ ] Phase 2 测试全部通过
- [ ] API 单轮对话测试成功
- [ ] API 多轮对话测试成功

---

**文档版本**: v1.0  
**创建日期**: 2026-01-18  
**最后更新**: 2026-01-18
