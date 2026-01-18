# Chat-to-DB: 智能 Text-to-SQL 系统

一个基于 LangGraph 的智能 Text-to-SQL 系统，支持多轮对话、数据分析和可视化。

## 🌟 核心特性

- **智能 SQL 生成**: 自然语言转 SQL，支持复杂查询
- **多轮对话**: 基于 LangGraph Checkpointer 的状态持久化
- **数据分析**: 自动生成数据洞察和趋势分析
- **图表可视化**: 智能推荐和生成数据可视化图表
- **Dashboard 管理**: 创建和管理数据仪表板
- **混合检索**: 结合语义和结构化检索优化 SQL 生成

## 📚 文档

### 快速开始
- [启动指南](docs/启动指南.md) - 中文快速开始指南
- [START_HERE](docs/START_HERE.md) - English quick start guide

### 架构文档
- [架构和技术栈](docs/ARCHITECTURE_AND_TECH_STACK.md)
- [Text-to-SQL 架构分析](docs/architecture/TEXT2SQL_ANALYSIS.md)
- [上下文工程分析](docs/architecture/CONTEXT_ENGINEERING.md)
- [项目设计文档](docs/PROJECT_DESIGN_DOCUMENT.md)

### LangGraph 记忆体
- [实施总结](docs/langgraph/IMPLEMENTATION_SUMMARY.md)
- [Checkpointer 设置](docs/langgraph/CHECKPOINTER_SETUP.md)
- [快速开始](docs/langgraph/GETTING_STARTED.md)
- [API 设置指南](docs/langgraph/API_SETUP_GUIDE.md)

### 功能文档
- [多轮对话功能](docs/MULTI_ROUND_AND_ANALYST_FEATURES.md)
- [禁用的功能](docs/DISABLED_FEATURES.md)

### 部署文档
- [Docker 部署指南](docs/deployment/DOCKER_DEPLOYMENT.md)
- [阿里云向量服务设置](docs/deployment/ALIYUN_VECTOR_SETUP.md)

## 🚀 快速开始

> 💡 **快速启动**: 查看 [Docker 快速启动指南](DOCKER_QUICK_START.md) 一键启动所有服务  
> 📋 **设置完成**: 查看 [Docker 设置完成报告](DOCKER_SETUP_COMPLETE.md) 了解配置详情

### 1. 环境要求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (推荐)

或者手动安装：
- PostgreSQL 15+ (用于 Checkpointer)
- MySQL 8+ (用于应用数据)

### 2. 使用 Docker 启动服务（推荐）

```bash
# 方式 1: 使用启动脚本（推荐）
./start-services.sh start        # 启动核心服务（MySQL + PostgreSQL）
./start-services.sh start-full   # 启动所有服务（包括 Neo4j, Milvus, Redis）

# 方式 2: 直接使用 docker-compose
docker-compose up -d                    # 启动核心服务
docker-compose --profile full up -d     # 启动所有服务

# 查看服务状态
./start-services.sh status
# 或
docker-compose ps

# 查看日志
./start-services.sh logs
# 或
docker-compose logs -f
```

**服务端口**:
- MySQL: `localhost:3306`
- PostgreSQL Checkpointer: `localhost:5433`
- Neo4j: `http://localhost:7474` (可选)
- Milvus: `localhost:19530` (可选)
- Redis: `localhost:6379` (可选)

> 📖 详细的 Docker 部署说明请参考 [Docker 部署指南](docs/deployment/DOCKER_DEPLOYMENT.md)

### 3. 后端设置

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接和 API 密钥

# 运行数据库迁移
alembic upgrade head

# 启动服务
python admin_server.py  # 管理后台 (端口 8000)
python chat_server.py   # 聊天服务 (端口 8001)
```

### 4. 前端设置

#### 管理后台

```bash
cd frontend/admin
npm install
npm start  # 开发模式，端口 3000
```

#### 聊天界面

```bash
cd frontend/chat
npm install
npm run dev  # 开发模式，端口 3001
```

### 4. 验证安装

```bash
cd backend
python tests/verify_setup.py
```

## 📁 项目结构

```
chat-to-db/
├── docs/                    # 📚 文档
│   ├── architecture/        # 架构文档
│   ├── langgraph/          # LangGraph 记忆体文档
│   ├── features/           # 功能文档
│   └── deployment/         # 部署文档
│
├── backend/                # 🔧 后端
│   ├── app/               # 应用代码
│   │   ├── agents/        # LangGraph Agents
│   │   ├── api/           # FastAPI 端点
│   │   ├── core/          # 核心模块
│   │   ├── crud/          # 数据库操作
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # 业务逻辑
│   ├── tests/             # 测试
│   ├── alembic/           # 数据库迁移
│   └── backups/           # 代码备份
│
└── frontend/              # 🎨 前端
    ├── admin/            # 管理后台 (React)
    └── chat/             # 聊天界面 (Next.js)
```

## 🧪 测试

```bash
cd backend

# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_checkpointer.py
pytest tests/test_message_history.py
pytest tests/integration/test_api_multi_turn.py

# 验证设置
python tests/verify_setup.py
```

## 🔧 核心技术栈

### 后端
- **框架**: FastAPI
- **AI/LLM**: LangChain, LangGraph
- **数据库**: MySQL (应用数据), PostgreSQL (Checkpointer)
- **向量数据库**: Milvus
- **图数据库**: Neo4j (可选)

### 前端
- **管理后台**: React, Ant Design
- **聊天界面**: Next.js, Tailwind CSS
- **图表**: ECharts, Recharts

## 📊 主要功能

### 1. Text-to-SQL
- 自然语言转 SQL
- 支持复杂查询和多表关联
- 自动 Schema 分析和推荐

### 2. 多轮对话
- 基于 LangGraph Checkpointer 的状态持久化
- 支持上下文理解和引用
- 自动消息历史管理

### 3. 数据分析
- 自动生成数据洞察
- 趋势分析和异常检测
- 智能推荐

### 4. 可视化
- 智能图表推荐
- 多种图表类型支持
- 交互式数据探索

### 5. Dashboard
- 创建和管理仪表板
- Widget 组件化
- 权限管理

## 🤝 贡献

欢迎贡献！请查看 [贡献指南](docs/CONTRIBUTING.md)（待创建）。

## 📄 许可证

[MIT License](LICENSE)

## 📞 联系方式

- 问题反馈: [GitHub Issues](https://github.com/your-repo/chat-to-db/issues)
- 文档: [docs/](docs/)

---

**最后更新**: 2026-01-18
