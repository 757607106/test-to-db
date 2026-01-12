# Chat-To-DB-Rwx 项目详细设计文档

## 一、项目概述

### 1.1 项目名称
**Chat-To-DB-Rwx** - 智能数据库查询系统

### 1.2 项目目标
将自然语言问题转换为SQL查询，通过AI代理系统自动执行查询并返回结果，支持数据可视化。

### 1.3 核心功能
- 自然语言转SQL (Text2SQL)
- 多代理协作工作流
- 混合检索系统 (向量+图+结构)
- 数据库连接管理
- 数据可视化
- 知识图谱管理

### 1.4 技术栈
**后端**: Python, FastAPI, LangGraph, LangChain, SQLAlchemy
**前端**: Next.js (Chat UI), React (Admin UI)
**数据库**: MySQL, Neo4j, Milvus
**LLM**: DeepSeek API, Ollama
**向量化**: Ollama Embeddings

---

## 二、系统架构设计

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────────┐
│                     前端层 (Frontend)                        │
├──────────────────────┬──────────────────────────────────────┤
│  Chat UI (Next.js)   │    Admin UI (React)                  │
│  - 对话界面          │    - 连接管理                        │
│  - 流式输出          │    - Schema管理                      │
│  - 结果展示          │    - 知识图谱                        │
└──────────────────────┴──────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   API网关层 (FastAPI)                        │
├──────────────────────────────────────────────────────────────┤
│  - admin_server.py (8000)  - 管理API                        │
│  - chat_server.py (2025)   - LangGraph API                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   业务逻辑层 (Services)                      │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │  多代理协作系统 (LangGraph Supervisor)              │   │
│  │  ┌──────────────┬──────────────┬──────────────┐    │   │
│  │  │ Schema Agent │ SQL Generator│ SQL Validator│    │   │
│  │  ├──────────────┼──────────────┼──────────────┤    │   │
│  │  │Sample Retriev│ SQL Executor │Error Recovery│    │   │
│  │  └──────────────┴──────────────┴──────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  混合检索引擎 (Hybrid Retrieval)                    │   │
│  │  - 向量检索 (Milvus)                               │   │
│  │  - 结构检索 (Neo4j)                                │   │
│  │  - 模式检索 (Neo4j)                                │   │
│  │  - 融合排序 (Fusion Ranker)                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  其他服务                                           │   │
│  │  - DB Service (数据库操作)                         │   │
│  │  - Schema Service (Schema管理)                     │   │
│  │  - Text2SQL Service (转换服务)                     │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   数据访问层 (CRUD)                          │
├──────────────────────────────────────────────────────────────┤
│  - DB Connection CRUD                                       │
│  - Schema Table/Column CRUD                                 │
│  - Value Mapping CRUD                                       │
│  - Relationship CRUD                                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   数据存储层 (Databases)                     │
├──────────────────────────────────────────────────────────────┤
│  MySQL (业务数据) │ Neo4j (知识图谱) │ Milvus (向量库)      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块说明

#### 2.2.1 多代理系统 (Agent System)
**位置**: `backend/app/agents/`

**组成代理**:
1. **Schema Agent** - 分析查询，提取相关表结构
2. **Sample Retrieval Agent** - 检索相似的历史查询样本
3. **SQL Generator Agent** - 基于Schema和样本生成SQL
4. **SQL Validator Agent** - 验证SQL语法和安全性
5. **SQL Executor Agent** - 执行SQL并获取结果
6. **Error Recovery Agent** - 处理错误并重试
7. **Chart Generator Agent** - 生成数据可视化

**工作流程**:
```
用户查询 → Supervisor → Schema Agent → Sample Retrieval Agent
    ↓
SQL Generator Agent → SQL Validator Agent → SQL Executor Agent
    ↓
Error Recovery (if needed) → Chart Generator → 返回结果
```

#### 2.2.2 混合检索系统 (Hybrid Retrieval)
**位置**: `backend/app/services/hybrid_retrieval_service.py`

**三层检索**:
1. **语义检索** (Semantic Search)
   - 使用Ollama Embeddings向量化查询
   - 在Milvus中进行向量相似度搜索
   - 返回语义相似的历史查询

2. **结构检索** (Structural Search)
   - 基于Neo4j图数据库
   - 匹配使用相同表的历史查询
   - 计算表重叠度

3. **模式检索** (Pattern Search)
   - 识别查询类型 (SELECT, JOIN, GROUP_BY等)
   - 估算查询难度
   - 匹配相似的查询模式

**融合排序** (Fusion Ranker):
- 动态权重调整
- 语义高度匹配时权重0.8
- 语义低匹配时权重0.4
- 综合质量分数、验证状态、成功率

#### 2.2.3 数据库管理 (Database Management)
**位置**: `backend/app/db/`, `backend/app/models/`

**支持的数据库类型**:
- MySQL
- PostgreSQL (配置支持)
- SQLite

**核心模型**:
- `DBConnection` - 数据库连接信息
- `SchemaTable` - 表结构
- `SchemaColumn` - 列信息
- `SchemaRelationship` - 表关系
- `ValueMapping` - 值映射 (自然语言↔数据库值)

---

## 三、功能设计

### 3.1 核心功能流程

#### 3.1.1 自然语言查询流程
```
1. 用户输入自然语言问题
2. 系统提取连接ID
3. Schema Agent获取相关表结构
4. Sample Retrieval Agent检索相似查询
5. SQL Generator Agent生成SQL
6. SQL Validator Agent验证SQL
7. SQL Executor Agent执行SQL
8. Chart Generator Agent生成图表
9. 返回结果给用户
```

#### 3.1.2 混合检索流程
```
1. 向量化用户查询
2. 并行执行三种检索:
   - 语义检索 (Milvus)
   - 结构检索 (Neo4j)
   - 模式检索 (Neo4j)
3. 融合排序
4. 返回Top-K结果
```

### 3.2 API端点设计

#### 3.2.1 管理API (admin_server.py:8000)
```
POST   /api/connections/          - 创建数据库连接
GET    /api/connections/          - 获取连接列表
GET    /api/connections/{id}      - 获取连接详情
PUT    /api/connections/{id}      - 更新连接
DELETE /api/connections/{id}      - 删除连接

GET    /api/schema/               - 获取Schema
POST   /api/schema/refresh        - 刷新Schema

POST   /api/query/                - 执行查询
GET    /api/query/history         - 查询历史

POST   /api/value-mappings/       - 创建值映射
GET    /api/value-mappings/       - 获取值映射

GET    /api/graph-visualization/  - 获取图谱可视化
GET    /api/relationship-tips/    - 获取关系提示

POST   /api/hybrid-qa/            - 混合检索查询
```

#### 3.2.2 LangGraph API (chat_server.py:2025)
```
POST   /runs/                     - 创建运行
GET    /runs/{run_id}             - 获取运行状态
GET    /runs/{run_id}/stream      - 流式获取结果
POST   /threads/                  - 创建线程
GET    /threads/{thread_id}       - 获取线程
```

### 3.3 数据模型

#### 3.3.1 SQLMessageState (状态管理)
```python
class SQLMessageState:
    messages: List[Message]           # 消息历史
    connection_id: int                # 数据库连接ID
    query_analysis: Dict              # 查询分析结果
    schema_info: SchemaInfo           # Schema信息
    generated_sql: str                # 生成的SQL
    validation_result: ValidationResult  # 验证结果
    execution_result: ExecutionResult    # 执行结果
    sample_retrieval_result: Dict     # 样本检索结果
    retry_count: int                  # 重试次数
    current_stage: str                # 当前阶段
    error_history: List               # 错误历史
```

#### 3.3.2 QAPairWithContext (问答对)
```python
class QAPairWithContext:
    id: str                           # 唯一ID
    question: str                     # 自然语言问题
    sql: str                          # SQL查询
    connection_id: int                # 连接ID
    difficulty_level: int             # 难度等级
    query_type: str                   # 查询类型
    success_rate: float               # 成功率
    verified: bool                    # 是否验证
    used_tables: List[str]            # 使用的表
    used_columns: List[str]           # 使用的列
    query_pattern: str                # 查询模式
    mentioned_entities: List[str]     # 提及的实体
    embedding_vector: List[float]     # 向量表示
```

---

## 四、技术实现细节

### 4.1 LLM集成
- **主模型**: DeepSeek Chat (通过OpenAI兼容API)
- **API端点**: https://api.deepseek.com/v1
- **备选**: Ollama本地模型

### 4.2 向量化服务
- **模型**: Ollama qwen3-embedding:0.6b
- **维度**: 1024
- **缓存**: 支持TTL缓存 (默认3600秒)
- **批处理**: 支持批量向量化

### 4.3 知识图谱存储
- **Neo4j**: 存储查询模式、表关系、实体关系
- **节点类型**: QAPair, Table, Column, QueryPattern, Entity
- **关系类型**: USES_TABLES, FOLLOWS_PATTERN, MENTIONS_ENTITY

### 4.4 向量数据库
- **Milvus**: 存储问答对向量
- **集合**: 按数据库名称创建 (e.g., `db_name_qa_pairs`)
- **索引**: IVF_FLAT, COSINE相似度

---

## 五、前端设计

### 5.1 Chat UI (Next.js)
**功能**:
- 实时对话界面
- 流式输出显示
- 数据库连接选择
- 查询结果展示
- 代码高亮

**关键组件**:
- `database-connection-selector.tsx` - 连接选择器
- `thread/` - 对话线程管理
- `ui/` - UI组件库

### 5.2 Admin UI (React)
**功能**:
- 数据库连接管理
- Schema可视化
- 知识图谱展示
- 值映射管理
- 查询历史

**关键页面**:
- `ConnectionsPage.tsx` - 连接管理
- `SchemaManagementPage.tsx` - Schema管理
- `GraphVisualizationPage.tsx` - 图谱可视化
- `IntelligentQueryPage.tsx` - 智能查询

---

## 六、配置管理

### 6.1 环境变量 (.env)
```
# 数据库配置
MYSQL_SERVER=localhost
MYSQL_USER=root
MYSQL_PASSWORD=mysql
MYSQL_DB=chatdb
MYSQL_PORT=3306

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# LLM配置
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 向量化配置
VECTOR_SERVICE_TYPE=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b

# 混合检索权重
SEMANTIC_WEIGHT=0.60
STRUCTURAL_WEIGHT=0.20
PATTERN_WEIGHT=0.10
QUALITY_WEIGHT=0.10
```

---

## 七、部署架构

### 7.1 开发环境
```
localhost:3000   - Chat UI (Next.js)
localhost:3001   - Admin UI (React)
localhost:8000   - Admin API (FastAPI)
localhost:2025   - LangGraph API
localhost:3306   - MySQL
localhost:7687   - Neo4j
localhost:19530  - Milvus
localhost:11434  - Ollama
```

### 7.2 生产环境
- Docker容器化部署
- Nginx反向代理
- PM2进程管理
- 数据库集群

---

## 八、性能优化

### 8.1 缓存策略
- 向量缓存 (TTL: 3600秒)
- 检索缓存 (TTL: 3600秒)
- Schema缓存

### 8.2 并行处理
- 混合检索并行执行
- 批量向量化处理
- 异步API调用

### 8.3 数据库优化
- 索引优化
- 连接池管理
- 查询优化

---

## 九、安全性设计

### 9.1 认证授权
- API密钥认证
- 数据库连接加密
- 用户权限管理

### 9.2 SQL安全
- SQL注入防护
- 查询验证
- 执行权限控制

### 9.3 数据保护
- 密码加密存储
- 敏感数据脱敏
- 审计日志

---

## 十、扩展性设计

### 10.1 支持新数据库类型
1. 在`DBConnection`模型中添加新类型
2. 在`db_manager.py`中实现连接逻辑
3. 在`schema_service.py`中实现Schema提取

### 10.2 支持新LLM模型
1. 在`core/llms.py`中添加模型配置
2. 实现模型调用接口
3. 更新提示词

### 10.3 添加新代理
1. 在`agents/agents/`中创建新代理
2. 在`supervisor_agent.py`中注册
3. 定义代理的输入输出

---

## 十一、监控和日志

### 11.1 日志系统
- 结构化日志
- 日志级别控制
- 日志持久化

### 11.2 监控指标
- API响应时间
- 查询成功率
- 缓存命中率
- 向量化性能

### 11.3 错误追踪
- 异常捕获
- 错误恢复
- 重试机制

---

## 十二、测试策略

### 12.1 单元测试
- 服务层测试
- 工具函数测试
- 模型验证测试

### 12.2 集成测试
- API端点测试
- 代理工作流测试
- 数据库操作测试

### 12.3 端到端测试
- 完整查询流程
- 混合检索流程
- 错误恢复流程

---

## 十三、文档和维护

### 13.1 代码文档
- API文档 (Swagger/OpenAPI)
- 代码注释
- 架构文档

### 13.2 用户文档
- 使用指南
- 配置指南
- 故障排除

### 13.3 维护计划
- 定期更新依赖
- 性能优化
- 功能迭代

---

**文档版本**: 1.0
**最后更新**: 2026-01-10
**维护者**: 开发团队

