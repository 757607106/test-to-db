# Chat-to-DB 项目结构

## 📁 目录结构

```
chat-to-db/
├── README.md                           # 项目主页
├── .gitignore                          # Git 忽略配置
├── PROJECT_STRUCTURE.md                # 本文档 - 项目结构说明
├── PROJECT_CLEANUP_PLAN.md             # 清理计划
├── PROJECT_CLEANUP_COMPLETE.md         # 清理完成报告
│
├── docs/                               # 📚 统一文档目录
│   ├── README.md                       # 文档索引
│   ├── START_HERE.md                   # 英文快速开始
│   ├── 启动指南.md                     # 中文快速开始
│   ├── 最终优化报告.md                 # 优化报告
│   │
│   ├── architecture/                   # 架构文档
│   │   ├── TEXT2SQL_ANALYSIS.md       # Text-to-SQL 架构分析
│   │   └── CONTEXT_ENGINEERING.md     # 上下文工程分析
│   │
│   ├── langgraph/                      # LangGraph 记忆体文档
│   │   ├── IMPLEMENTATION_SUMMARY.md  # 完整实施总结
│   │   ├── CHECKPOINTER_SETUP.md      # Checkpointer 设置指南
│   │   ├── GETTING_STARTED.md         # 快速开始指南
│   │   └── API_SETUP_GUIDE.md         # API 设置指南
│   │
│   ├── features/                       # 功能文档
│   │   └── (待整理)
│   │
│   ├── deployment/                     # 部署文档
│   │   └── ALIYUN_VECTOR_SETUP.md     # 阿里云向量服务设置
│   │
│   └── (其他文档...)                   # 项目报告、分析等
│
├── backend/                            # 🔧 后端代码
│   │
│   ├── app/                            # 应用代码
│   │   ├── __init__.py
│   │   │
│   │   ├── agents/                     # LangGraph Agents
│   │   │   ├── agents/                # Agent 实现
│   │   │   │   ├── schema_agent.py
│   │   │   │   ├── sql_generator_agent.py
│   │   │   │   ├── sql_executor_agent.py
│   │   │   │   ├── error_recovery_agent.py
│   │   │   │   ├── chart_generator_agent.py
│   │   │   │   └── supervisor_agent.py
│   │   │   ├── nodes/                 # Graph 节点
│   │   │   ├── templates/             # Prompt 模板
│   │   │   ├── chat_graph.py          # 主 Graph 定义
│   │   │   ├── dashboard_insight_graph.py
│   │   │   └── agent_factory.py       # Agent 工厂
│   │   │
│   │   ├── api/                        # FastAPI 端点
│   │   │   ├── api_v1/
│   │   │   │   ├── api.py             # API 路由汇总
│   │   │   │   └── endpoints/         # 端点实现
│   │   │   │       ├── query.py       # 查询端点
│   │   │   │       ├── dashboard.py   # Dashboard 端点
│   │   │   │       ├── db_connection.py
│   │   │   │       ├── schema.py
│   │   │   │       ├── llm_config.py
│   │   │   │       └── agent_profile.py
│   │   │   └── deps.py                # 依赖注入
│   │   │
│   │   ├── core/                       # 核心模块
│   │   │   ├── config.py              # 配置管理
│   │   │   ├── llms.py                # LLM 管理
│   │   │   ├── state.py               # State 定义
│   │   │   ├── checkpointer.py        # Checkpointer 工厂
│   │   │   ├── message_history.py     # 消息历史管理
│   │   │   ├── message_utils.py       # 消息工具
│   │   │   ├── agent_config.py        # Agent 配置
│   │   │   ├── security.py            # 安全相关
│   │   │   ├── exceptions.py          # 异常定义
│   │   │   └── utils.py               # 工具函数
│   │   │
│   │   ├── crud/                       # 数据库 CRUD 操作
│   │   │   ├── base.py                # 基础 CRUD
│   │   │   ├── crud_db_connection.py
│   │   │   ├── crud_schema_table.py
│   │   │   ├── crud_schema_column.py
│   │   │   ├── crud_schema_relationship.py
│   │   │   ├── crud_value_mapping.py
│   │   │   ├── crud_dashboard.py
│   │   │   ├── crud_dashboard_widget.py
│   │   │   ├── crud_dashboard_permission.py
│   │   │   ├── crud_llm_config.py
│   │   │   └── crud_agent_profile.py
│   │   │
│   │   ├── db/                         # 数据库配置
│   │   │   ├── base.py                # 模型基类
│   │   │   ├── base_class.py
│   │   │   ├── session.py             # 数据库会话
│   │   │   ├── init_db.py             # 数据库初始化
│   │   │   ├── init_system_agents.py  # 系统 Agent 初始化
│   │   │   ├── db_manager.py          # 数据库管理器
│   │   │   └── dbaccess.py            # 数据库访问
│   │   │
│   │   ├── models/                     # SQLAlchemy 模型
│   │   │   ├── user.py
│   │   │   ├── db_connection.py
│   │   │   ├── schema_table.py
│   │   │   ├── schema_column.py
│   │   │   ├── schema_relationship.py
│   │   │   ├── value_mapping.py
│   │   │   ├── query_history.py
│   │   │   ├── dashboard.py
│   │   │   ├── dashboard_widget.py
│   │   │   ├── dashboard_permission.py
│   │   │   ├── llm_config.py
│   │   │   └── agent_profile.py
│   │   │
│   │   ├── schemas/                    # Pydantic Schemas
│   │   │   ├── __init__.py            # Schema 导出
│   │   │   ├── query.py               # 查询相关 Schema
│   │   │   ├── db_connection.py
│   │   │   ├── schema_table.py
│   │   │   ├── schema_column.py
│   │   │   ├── schema_relationship.py
│   │   │   ├── value_mapping.py
│   │   │   ├── dashboard.py
│   │   │   ├── dashboard_widget.py
│   │   │   ├── dashboard_insight.py
│   │   │   ├── llm_config.py
│   │   │   └── agent_profile.py
│   │   │
│   │   └── services/                   # 业务逻辑服务
│   │       ├── text2sql_service.py    # Text-to-SQL 服务
│   │       ├── text2sql_utils.py      # Text-to-SQL 工具
│   │       ├── db_service.py          # 数据库服务
│   │       ├── schema_service.py      # Schema 服务
│   │       ├── schema_utils.py        # Schema 工具
│   │       ├── hybrid_retrieval_service.py  # 混合检索
│   │       ├── query_history_service.py
│   │       ├── dashboard_service.py
│   │       ├── dashboard_widget_service.py
│   │       ├── dashboard_insight_service.py
│   │       ├── analyst_utils.py
│   │       └── graph_relationship_service.py
│   │
│   ├── tests/                          # 测试文件
│   │   ├── integration/                # 集成测试
│   │   │   └── test_api_multi_turn.py # API 多轮对话测试
│   │   ├── test_checkpointer.py       # Checkpointer 测试
│   │   ├── test_message_history.py    # 消息历史管理测试
│   │   └── verify_setup.py            # 设置验证脚本
│   │
│   ├── alembic/                        # 数据库迁移
│   │   ├── versions/                   # 迁移版本
│   │   └── env.py                      # Alembic 环境
│   │
│   ├── backups/                        # 代码备份
│   │   ├── agents_backup_20260116_175357/
│   │   └── removed_validators/
│   │
│   ├── admin_server.py                 # 管理服务入口
│   ├── chat_server.py                  # 聊天服务入口
│   │
│   ├── .env                            # 环境变量（不提交）
│   ├── .env.example                    # 环境变量示例
│   ├── requirements.txt                # Python 依赖
│   │
│   ├── alembic.ini                     # Alembic 配置
│   ├── langgraph.json                  # LangGraph 配置
│   │
│   ├── docker-compose.checkpointer.yml # Checkpointer Docker 配置
│   ├── init-checkpointer-db.sql        # Checkpointer 数据库初始化
│   ├── start-checkpointer.sh           # Checkpointer 启动脚本
│   │
│   └── Chinook.db                      # 示例数据库
│
└── frontend/                           # 🎨 前端代码
    │
    ├── admin/                          # 管理后台 (React + Ant Design)
    │   ├── public/                     # 静态资源
    │   ├── src/
    │   │   ├── components/            # React 组件
    │   │   ├── pages/                 # 页面
    │   │   ├── services/              # API 服务
    │   │   ├── types/                 # TypeScript 类型
    │   │   ├── utils/                 # 工具函数
    │   │   ├── App.tsx                # 应用入口
    │   │   └── index.tsx              # 渲染入口
    │   ├── package.json               # 依赖配置
    │   ├── tsconfig.json              # TypeScript 配置
    │   └── craco.config.js            # Craco 配置
    │
    └── chat/                           # 聊天界面 (Next.js + Tailwind)
        ├── public/                     # 静态资源
        ├── src/
        │   ├── app/                   # Next.js App Router
        │   ├── components/            # React 组件
        │   ├── hooks/                 # React Hooks
        │   ├── lib/                   # 库和工具
        │   ├── providers/             # Context Providers
        │   └── types/                 # TypeScript 类型
        ├── package.json               # 依赖配置
        ├── tsconfig.json              # TypeScript 配置
        ├── next.config.mjs            # Next.js 配置
        └── tailwind.config.js         # Tailwind 配置
```

---

## 📝 目录说明

### 根目录

- **README.md**: 项目主页，包含快速开始和核心信息
- **.gitignore**: Git 忽略配置
- **PROJECT_STRUCTURE.md**: 本文档，详细的项目结构说明
- **PROJECT_CLEANUP_*.md**: 清理相关文档

### docs/ - 文档目录

统一的文档中心，包含所有项目文档：

- **README.md**: 文档索引，快速查找文档
- **architecture/**: 架构设计文档
- **langgraph/**: LangGraph 记忆体相关文档
- **features/**: 功能说明文档
- **deployment/**: 部署相关文档

### backend/ - 后端代码

#### app/ - 应用代码

- **agents/**: LangGraph Agents 实现
  - `agents/`: 各个 Agent 的具体实现
  - `nodes/`: Graph 节点函数
  - `templates/`: Prompt 模板
  - `chat_graph.py`: 主 Graph 定义
  - `agent_factory.py`: Agent 工厂

- **api/**: FastAPI API 端点
  - `api_v1/endpoints/`: 各个端点的实现
  - `deps.py`: 依赖注入

- **core/**: 核心模块
  - `config.py`: 配置管理
  - `llms.py`: LLM 管理
  - `checkpointer.py`: Checkpointer 工厂
  - `message_history.py`: 消息历史管理
  - `state.py`: State 定义

- **crud/**: 数据库 CRUD 操作
- **db/**: 数据库配置和初始化
- **models/**: SQLAlchemy 数据模型
- **schemas/**: Pydantic Schemas
- **services/**: 业务逻辑服务

#### tests/ - 测试文件

- **integration/**: 集成测试
- **test_*.py**: 单元测试
- **verify_setup.py**: 设置验证脚本

#### 其他重要文件

- **admin_server.py**: 管理服务入口（端口 8000）
- **chat_server.py**: 聊天服务入口（端口 8001）
- **requirements.txt**: Python 依赖
- **alembic.ini**: 数据库迁移配置
- **langgraph.json**: LangGraph 配置
- **docker-compose.checkpointer.yml**: Checkpointer Docker 配置

### frontend/ - 前端代码

#### admin/ - 管理后台

基于 React + Ant Design 的管理后台：
- 数据库连接管理
- Schema 管理
- Dashboard 管理
- LLM 配置
- Agent 配置

#### chat/ - 聊天界面

基于 Next.js + Tailwind CSS 的聊天界面：
- 自然语言查询
- 多轮对话
- 结果展示
- 图表可视化

---

## 🔑 关键文件说明

### 后端核心文件

| 文件 | 说明 |
|------|------|
| `app/agents/chat_graph.py` | 主 Graph 定义，协调所有 Agent |
| `app/agents/agents/supervisor_agent.py` | Supervisor Agent，管理工作流 |
| `app/core/checkpointer.py` | Checkpointer 工厂，管理状态持久化 |
| `app/core/message_history.py` | 消息历史管理，优化 token 使用 |
| `app/api/api_v1/endpoints/query.py` | 查询 API，支持多轮对话 |
| `app/services/text2sql_service.py` | Text-to-SQL 核心服务 |

### 配置文件

| 文件 | 说明 |
|------|------|
| `backend/.env` | 环境变量配置（不提交到 Git） |
| `backend/.env.example` | 环境变量示例 |
| `backend/alembic.ini` | 数据库迁移配置 |
| `backend/langgraph.json` | LangGraph 配置 |
| `backend/docker-compose.checkpointer.yml` | Checkpointer Docker 配置 |

### 文档文件

| 文件 | 说明 |
|------|------|
| `docs/README.md` | 文档索引 |
| `docs/langgraph/IMPLEMENTATION_SUMMARY.md` | LangGraph 实施总结 |
| `docs/langgraph/CHECKPOINTER_SETUP.md` | Checkpointer 设置指南 |
| `docs/architecture/TEXT2SQL_ANALYSIS.md` | Text-to-SQL 架构分析 |

---

## 🚀 快速导航

### 开发相关

- **启动后端**: `backend/admin_server.py`, `backend/chat_server.py`
- **运行测试**: `backend/tests/`
- **数据库迁移**: `backend/alembic/`
- **配置管理**: `backend/.env`

### 文档相关

- **快速开始**: `docs/START_HERE.md`, `docs/启动指南.md`
- **架构文档**: `docs/architecture/`
- **LangGraph 文档**: `docs/langgraph/`
- **部署文档**: `docs/deployment/`

### 前端相关

- **管理后台**: `frontend/admin/`
- **聊天界面**: `frontend/chat/`

---

## 📌 注意事项

1. **环境变量**: 复制 `.env.example` 到 `.env` 并配置
2. **数据库**: 需要 MySQL 和 PostgreSQL
3. **依赖安装**: 运行 `pip install -r requirements.txt`
4. **Checkpointer**: 使用 Docker 启动 PostgreSQL
5. **测试**: 运行 `python tests/verify_setup.py` 验证设置

---

**最后更新**: 2026-01-18  
**维护者**: 项目团队
