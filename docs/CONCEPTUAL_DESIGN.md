# Chat-to-DB 项目概要设计说明书

## 一、设计目标

### 1.1 核心目标
构建一个智能数据库查询系统，使用户能够通过自然语言与数据库交互，系统自动将自然语言转换为SQL查询并执行。

### 1.2 设计原则
1. **模块化**: 各功能模块独立，易于扩展
2. **可靠性**: 多层验证和错误恢复机制
3. **高效性**: 缓存、并行处理、索引优化
4. **可维护性**: 清晰的代码结构和文档
5. **可扩展性**: 支持新数据库、新LLM、新代理

---

## 二、系统分层设计

### 2.1 表现层 (Presentation Layer)
**职责**: 用户交互和结果展示

**组件**:
- Chat UI (Next.js) - 对话界面
- Admin UI (React) - 管理界面
- 数据可视化组件

**特点**:
- 实时流式输出
- 响应式设计
- 多种数据展示方式

### 2.2 应用层 (Application Layer)
**职责**: 业务逻辑处理

**核心模块**:
1. **多代理系统** (LangGraph Supervisor)
   - 协调各专门代理
   - 管理工作流程
   - 处理状态转移

2. **混合检索系统** (Hybrid Retrieval)
   - 向量检索 (Milvus)
   - 结构检索 (Neo4j)
   - 模式检索 (Neo4j)
   - 融合排序

3. **业务服务**
   - Text2SQL服务
   - Schema服务
   - 数据库服务

### 2.3 数据访问层 (Data Access Layer)
**职责**: 数据库操作

**CRUD操作**:
- 数据库连接管理
- Schema管理
- 值映射管理
- 关系管理

### 2.4 数据存储层 (Data Storage Layer)
**职责**: 数据持久化

**存储系统**:
- MySQL - 业务数据
- Neo4j - 知识图谱
- Milvus - 向量库

---

## 三、核心功能模块设计

### 3.1 多代理系统设计

#### 3.1.1 代理架构
```
┌─────────────────────────────────────────┐
│         Supervisor (LangGraph)          │
│  - 协调代理                             │
│  - 管理工作流                           │
│  - 处理状态                             │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│         Worker Agents                   │
├─────────────────────────────────────────┤
│ 1. Schema Agent                         │
│    - 分析查询意图                       │
│    - 提取相关表                         │
│    - 获取表结构                         │
│                                         │
│ 2. Sample Retrieval Agent               │
│    - 检索相似查询                       │
│    - 提供参考样本                       │
│    - 优化生成质量                       │
│                                         │
│ 3. SQL Generator Agent                  │
│    - 生成SQL语句                        │
│    - 应用值映射                         │
│    - 优化查询                           │
│                                         │
│ 4. SQL Validator Agent                  │
│    - 验证SQL语法                        │
│    - 检查安全性                         │
│    - 评估性能                           │
│                                         │
│ 5. SQL Executor Agent                   │
│    - 执行SQL                            │
│    - 获取结果                           │
│    - 处理异常                           │
│                                         │
│ 6. Error Recovery Agent                 │
│    - 分析错误                           │
│    - 修复SQL                            │
│    - 重试执行                           │
│                                         │
│ 7. Chart Generator Agent                │
│    - 分析结果                           │
│    - 生成图表                           │
│    - 优化展示                           │
└─────────────────────────────────────────┘
```

#### 3.1.2 工作流程
```
用户查询
   ↓
[Schema Agent] → 获取表结构、列信息、关系
   ↓
[Sample Retrieval Agent] → 检索相似查询样本
   ↓
[SQL Generator Agent] → 生成SQL语句
   ↓
[SQL Validator Agent] → 验证SQL
   ├─ 通过 → [SQL Executor Agent]
   └─ 失败 → [Error Recovery Agent] → 修复 → [SQL Validator Agent]
   ↓
[SQL Executor Agent] → 执行SQL获取结果
   ├─ 成功 → [Chart Generator Agent]
   └─ 失败 → [Error Recovery Agent]
   ↓
[Chart Generator Agent] → 生成可视化
   ↓
返回结果给用户
```

### 3.2 混合检索系统设计

#### 3.2.1 三层检索架构
```
┌──────────────────────────────────────────┐
│        用户查询 (自然语言)               │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│      向量化 (Ollama Embeddings)          │
└──────────────────────────────────────────┘
         ↓
    ┌────┴────┬────────┬────────┐
    ↓         ↓        ↓        ↓
┌────────┐ ┌──────┐ ┌──────┐ ┌──────┐
│语义检索│ │结构  │ │模式  │ │缓存  │
│(Milvus)│ │检索  │ │检索  │ │查询  │
│        │ │(Neo4j)│ │(Neo4j)│ │      │
└────────┘ └──────┘ └──────┘ └──────┘
    ↓         ↓        ↓        ↓
    └────┬────┴────┬───┴────┬───┘
         ↓         ↓        ↓
    ┌──────────────────────────┐
    │   融合排序 (Fusion)      │
    │ - 动态权重调整           │
    │ - 质量评分               │
    │ - 最终排序               │
    └──────────────────────────┘
         ↓
    ┌──────────────────────────┐
    │   返回Top-K结果          │
    └──────────────────────────┘
```

#### 3.2.2 检索策略
**语义检索**:
- 向量化查询
- Milvus相似度搜索
- 返回语义相似的历史查询

**结构检索**:
- 分析查询涉及的表
- Neo4j图查询
- 匹配使用相同表的历史查询
- 计算表重叠度

**模式检索**:
- 识别查询类型 (SELECT, JOIN, GROUP_BY等)
- 估算难度等级
- 匹配相似模式的历史查询

**融合排序**:
- 语义权重: 0.60 (基础)
- 结构权重: 0.20 (基础)
- 模式权重: 0.10 (基础)
- 质量权重: 0.10 (基础)
- 动态调整: 根据语义相似度调整权重

### 3.3 数据库管理设计

#### 3.3.1 连接管理
```
DBConnection
├─ id (主键)
├─ name (连接名称)
├─ db_type (数据库类型: MySQL, PostgreSQL等)
├─ host (主机地址)
├─ port (端口)
├─ username (用户名)
├─ password_encrypted (加密密码)
├─ database_name (数据库名)
├─ created_at (创建时间)
└─ updated_at (更新时间)
```

#### 3.3.2 Schema管理
```
SchemaTable
├─ id
├─ connection_id (外键)
├─ name (表名)
├─ description (描述)
└─ columns (关系)

SchemaColumn
├─ id
├─ table_id (外键)
├─ name (列名)
├─ data_type (数据类型)
├─ nullable (是否可空)
└─ description (描述)

SchemaRelationship
├─ id
├─ connection_id
├─ source_table (源表)
├─ target_table (目标表)
├─ relationship_type (关系类型)
└─ description (描述)
```

#### 3.3.3 值映射管理
```
ValueMapping
├─ id
├─ connection_id
├─ column_name (列名)
├─ natural_language (自然语言值)
├─ database_value (数据库值)
└─ description (描述)

示例:
- 自然语言: "中石化"
- 数据库值: "中国石化"
```

---

## 四、关键设计决策

### 4.1 为什么使用多代理系统?
1. **模块化**: 每个代理专注一个任务
2. **可维护性**: 易于修改和扩展
3. **可靠性**: 多层验证和错误恢复
4. **灵活性**: 支持不同的工作流程

### 4.2 为什么使用混合检索?
1. **准确性**: 多维度匹配提高准确率
2. **鲁棒性**: 单一方法失败时有备选
3. **性能**: 缓存和索引优化
4. **可解释性**: 提供多维度的推荐理由

### 4.3 为什么使用Neo4j?
1. **关系表示**: 天然支持复杂关系
2. **图查询**: 高效的关系查询
3. **知识图谱**: 支持知识表示
4. **可视化**: 支持图谱可视化

### 4.4 为什么使用Milvus?
1. **向量搜索**: 专业的向量数据库
2. **性能**: 高效的相似度搜索
3. **可扩展性**: 支持大规模数据
4. **多种索引**: 支持多种索引类型

---

## 五、数据流设计

### 5.1 查询数据流
```
用户输入
   ↓
前端 (Chat UI)
   ↓
API Gateway (FastAPI)
   ↓
LangGraph Supervisor
   ↓
Worker Agents (并行/串行)
   ├─ Schema Agent → MySQL
   ├─ Sample Retrieval Agent → Milvus + Neo4j
   ├─ SQL Generator Agent → LLM
   ├─ SQL Validator Agent → 本地验证
   ├─ SQL Executor Agent → 目标数据库
   ├─ Error Recovery Agent → 错误处理
   └─ Chart Generator Agent → 图表生成
   ↓
结果聚合
   ↓
前端展示
```

### 5.2 学习数据流
```
成功查询
   ↓
提取特征
   ├─ 问题
   ├─ SQL
   ├─ 使用的表
   ├─ 查询类型
   └─ 难度等级
   ↓
向量化
   ↓
存储
   ├─ Neo4j (知识图谱)
   └─ Milvus (向量库)
   ↓
用于后续检索
```

---

## 六、状态管理设计

### 6.1 SQLMessageState
```
SQLMessageState
├─ messages (消息历史)
├─ connection_id (数据库连接)
├─ query_analysis (查询分析)
├─ schema_info (Schema信息)
├─ generated_sql (生成的SQL)
├─ validation_result (验证结果)
├─ execution_result (执行结果)
├─ sample_retrieval_result (样本检索)
├─ retry_count (重试次数)
├─ current_stage (当前阶段)
└─ error_history (错误历史)
```

### 6.2 阶段转移
```
schema_analysis
   ↓
sample_retrieval
   ↓
sql_generation
   ↓
sql_validation
   ├─ 通过 → sql_execution
   └─ 失败 → error_recovery → sql_generation
   ↓
sql_execution
   ├─ 成功 → completed
   └─ 失败 → error_recovery
   ↓
completed
```

---

## 七、扩展性设计

### 7.1 支持新数据库
1. 在`DBConnection`中添加新类型
2. 在`db_manager.py`中实现连接
3. 在`schema_service.py`中实现Schema提取
4. 在`db_service.py`中实现查询执行

### 7.2 支持新LLM
1. 在`core/llms.py`中添加配置
2. 实现模型调用接口
3. 更新提示词
4. 测试集成

### 7.3 添加新代理
1. 创建新代理类
2. 实现`invoke`方法
3. 在`supervisor_agent.py`中注册
4. 定义工作流程

---

## 八、性能考虑

### 8.1 缓存策略
- 向量缓存 (TTL: 3600秒)
- 检索缓存 (TTL: 3600秒)
- Schema缓存

### 8.2 并行处理
- 混合检索并行执行
- 批量向量化
- 异步API调用

### 8.3 数据库优化
- 索引优化
- 连接池
- 查询优化

---

## 九、安全性考虑

### 9.1 认证授权
- API密钥认证
- 用户权限管理

### 9.2 SQL安全
- SQL注入防护
- 查询验证
- 执行权限控制

### 9.3 数据保护
- 密码加密
- 敏感数据脱敏
- 审计日志

---

## 十、部署架构

### 10.1 开发环境
- 本地Docker容器
- 单机部署

### 10.2 生产环境
- 容器化部署
- 负载均衡
- 数据库集群
- 监控告警

---

**文档版本**: 1.0
**最后更新**: 2025-10-16

