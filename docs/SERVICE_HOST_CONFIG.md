# 服务地址配置指南

本文档说明如何通过环境变量统一配置系统中所有服务的访问地址。

## 概述

系统支持通过修改环境变量来切换服务地址，例如从 `localhost` 切换到局域网 IP `192.168.13.163`。

## 需要修改的文件

| 序号 | 文件路径 | 说明 |
|------|----------|------|
| 1 | `backend/.env` | 后端服务配置 |
| 2 | `frontend/chat/.env` | Chat 前端配置 |
| 3 | `frontend/chat/.env.local` | Chat 前端本地配置（优先级更高） |
| 4 | `frontend/admin/.env` | Admin 前端配置 |
| 5 | `frontend/admin/.env.local` | Admin 前端本地配置（优先级更高） |

> **注意**: `.env.local` 优先级高于 `.env`，建议两个文件保持一致以避免混淆。

```bash
# ===== 服务主机配置 =====
SERVICE_HOST=192.168.13.163

# LangGraph API URL
LANGGRAPH_API_URL=http://192.168.13.163:2024

# PostgreSQL Checkpointer URI
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@192.168.13.163:5433/langgraph_checkpoints

# Neo4j配置
NEO4J_URI=bolt://192.168.13.163:7687

# MySQL配置
MYSQL_SERVER=192.168.13.163

# Milvus配置
MILVUS_HOST=192.168.13.163
```

### 2. Chat 前端配置

**文件**: `frontend/chat/.env.local`

```bash
# 服务主机地址
NEXT_PUBLIC_SERVICE_HOST=192.168.13.163

# LangGraph API
NEXT_PUBLIC_API_URL=http://192.168.13.163:2024

# 后端 API
NEXT_PUBLIC_BACKEND_URL=http://192.168.13.163:8000
NEXT_PUBLIC_BACKEND_API_URL=http://192.168.13.163:8000/api
```

### 3. Admin 前端配置

**文件**: `frontend/admin/.env.local`

```bash
# 服务主机地址
REACT_APP_SERVICE_HOST=192.168.13.163

# 后端 API
REACT_APP_API_URL=http://192.168.13.163:8000/api

# Chat 前端地址
REACT_APP_CHAT_URL=http://192.168.13.163:3000
```

## 快速切换

### 切换到 192.168.13.163

**文件 1**: `backend/.env`
```bash
SERVICE_HOST=192.168.13.163
LANGGRAPH_API_URL=http://192.168.13.163:2024
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@192.168.13.163:5433/langgraph_checkpoints
NEO4J_URI=bolt://192.168.13.163:7687
MYSQL_SERVER=192.168.13.163
MILVUS_HOST=192.168.13.163
```

**文件 2**: `frontend/chat/.env.local`
```bash
NEXT_PUBLIC_SERVICE_HOST=192.168.13.163
NEXT_PUBLIC_API_URL=http://192.168.13.163:2024
NEXT_PUBLIC_BACKEND_URL=http://192.168.13.163:8000
NEXT_PUBLIC_BACKEND_API_URL=http://192.168.13.163:8000/api
```

**文件 3**: `frontend/admin/.env.local`
```bash
REACT_APP_SERVICE_HOST=192.168.13.163
REACT_APP_API_URL=http://192.168.13.163:8000/api
REACT_APP_CHAT_URL=http://192.168.13.163:3000
```

### 切换到 localhost

**文件 1**: `backend/.env`
```bash
SERVICE_HOST=localhost
LANGGRAPH_API_URL=http://localhost:2024
CHECKPOINT_POSTGRES_URI=postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints
NEO4J_URI=bolt://localhost:7687
MYSQL_SERVER=localhost
MILVUS_HOST=localhost
```

**文件 2**: `frontend/chat/.env.local`
```bash
NEXT_PUBLIC_SERVICE_HOST=localhost
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000/api
```

**文件 3**: `frontend/admin/.env.local`
```bash
REACT_APP_SERVICE_HOST=localhost
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_CHAT_URL=http://localhost:3000
```

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Chat 前端 | 3000 | Next.js 应用 |
| Admin 前端 | 3001 | React 应用 |
| LangGraph API | 2024 | LangGraph 服务 |
| 后端 API | 8000 | FastAPI 服务 |
| MySQL | 3306 | 数据库 |
| PostgreSQL | 5433 | Checkpointer 数据库 |
| Neo4j | 7687 | 图数据库 |
| Milvus | 19530 | 向量数据库 |

## 注意事项

1. **重启服务**：修改环境变量后，需要重启对应的服务才能生效
   - 后端：重启 Python 服务
   - 前端：重启开发服务器或重新构建

2. **数据库连接**：确保目标 IP 的数据库服务已启动且允许远程连接

3. **防火墙**：确保目标 IP 的相关端口已开放

4. **CORS**：后端服务已配置允许跨域访问

## 环境变量优先级

前端配置的优先级（从高到低）：
1. 完整 URL 环境变量（如 `NEXT_PUBLIC_API_URL`）
2. `SERVICE_HOST` 环境变量 + 默认端口
3. 默认值 `localhost`
