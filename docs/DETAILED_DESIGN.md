# Chat-To-DB-Rwx 项目详细设计说明书

## 一、模块详细设计

### 1.1 多代理系统详细设计

#### 1.1.1 Schema Agent
**文件**: `backend/app/agents/agents/schema_agent.py`

**职责**:
- 分析用户查询意图
- 从数据库获取相关表结构
- 提取表之间的关系
- 获取列的详细信息

**输入**:
```python
{
    "messages": [{"role": "user", "content": "查询..."}],
    "connection_id": 15
}
```

**输出**:
```python
{
    "schema_info": {
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "INT", "nullable": False},
                    {"name": "name", "type": "VARCHAR", "nullable": False}
                ]
            }
        ],
        "relationships": [
            {
                "source": "users",
                "target": "orders",
                "type": "one_to_many"
            }
        ]
    }
}
```

**实现细节**:
1. 使用LLM分析查询
2. 调用`schema_service.retrieve_relevant_schema()`
3. 获取表、列、关系信息
4. 返回结构化Schema

#### 1.1.2 Sample Retrieval Agent
**文件**: `backend/app/agents/agents/sample_retrieval_agent.py`

**职责**:
- 执行混合检索
- 返回相似的历史查询
- 提供SQL生成参考

**输入**:
```python
{
    "schema_info": {...},
    "messages": [{"role": "user", "content": "查询..."}],
    "connection_id": 15
}
```

**输出**:
```python
{
    "sample_retrieval_result": {
        "samples": [
            {
                "question": "类似的问题",
                "sql": "SELECT ...",
                "similarity_score": 0.85
            }
        ]
    }
}
```

**实现细节**:
1. 调用`HybridRetrievalEngine.hybrid_retrieve()`
2. 执行三层检索 (语义、结构、模式)
3. 融合排序返回Top-K结果
4. 格式化为代理输出

#### 1.1.3 SQL Generator Agent
**文件**: `backend/app/agents/agents/sql_generator_agent.py`

**职责**:
- 基于Schema和样本生成SQL
- 应用值映射
- 优化查询

**输入**:
```python
{
    "schema_info": {...},
    "sample_retrieval_result": {...},
    "messages": [{"role": "user", "content": "查询..."}]
}
```

**输出**:
```python
{
    "generated_sql": "SELECT * FROM users WHERE id = 1"
}
```

**实现细节**:
1. 构建LLM提示词
2. 包含Schema信息
3. 包含样本SQL
4. 包含值映射
5. 调用LLM生成SQL
6. 提取SQL语句

#### 1.1.4 SQL Validator Agent
**文件**: `backend/app/agents/agents/sql_validator_agent.py`

**职责**:
- 验证SQL语法
- 检查安全性
- 评估性能

**输入**:
```python
{
    "generated_sql": "SELECT ...",
    "schema_info": {...}
}
```

**输出**:
```python
{
    "validation_result": {
        "is_valid": True,
        "errors": [],
        "warnings": ["可能的性能问题"],
        "suggestions": ["添加索引"]
    }
}
```

**实现细节**:
1. 语法验证 (sqlparse)
2. 安全检查 (SQL注入防护)
3. 性能评估 (复杂度分析)
4. 返回验证结果

#### 1.1.5 SQL Executor Agent
**文件**: `backend/app/agents/agents/sql_executor_agent.py`

**职责**:
- 执行SQL查询
- 获取结果
- 处理异常

**输入**:
```python
{
    "generated_sql": "SELECT ...",
    "connection_id": 15
}
```

**输出**:
```python
{
    "execution_result": {
        "success": True,
        "data": [...],
        "rows_affected": 100,
        "execution_time": 0.5
    }
}
```

**实现细节**:
1. 获取数据库连接
2. 执行SQL
3. 获取结果集
4. 计算执行时间
5. 处理异常

#### 1.1.6 Error Recovery Agent
**文件**: `backend/app/agents/agents/error_recovery_agent.py`

**职责**:
- 分析错误
- 修复SQL
- 重试执行

**输入**:
```python
{
    "generated_sql": "SELECT ...",
    "error": "错误信息",
    "error_history": [...]
}
```

**输出**:
```python
{
    "generated_sql": "修复后的SQL",
    "retry_count": 1
}
```

**实现细节**:
1. 分析错误类型
2. 使用LLM修复SQL
3. 更新重试计数
4. 返回修复后的SQL

#### 1.1.7 Chart Generator Agent
**文件**: `backend/app/agents/agents/chart_generator_agent.py`

**职责**:
- 分析查询结果
- 生成可视化图表
- 优化展示方式

**输入**:
```python
{
    "execution_result": {
        "data": [...]
    }
}
```

**输出**:
```python
{
    "chart": {
        "type": "bar",
        "data": {...},
        "options": {...}
    }
}
```

**实现细节**:
1. 分析结果数据
2. 选择合适的图表类型
3. 生成图表配置
4. 返回可视化数据

### 1.2 混合检索系统详细设计

#### 1.2.1 向量化服务 (VectorService)
**文件**: `backend/app/services/hybrid_retrieval_service.py`

**类**: `VectorService`

**主要方法**:
```python
async def initialize()
    # 初始化向量模型

async def embed_question(question: str) -> List[float]
    # 向量化单个问题

async def batch_embed(questions: List[str]) -> List[List[float]]
    # 批量向量化

async def health_check() -> Dict
    # 健康检查
```

**特点**:
- 支持Ollama和SentenceTransformer
- 缓存机制 (TTL: 3600秒)
- 批处理优化
- 重试机制 (指数退避)

#### 1.2.2 Milvus服务 (MilvusService)
**类**: `MilvusService`

**主要方法**:
```python
async def initialize(dimension: int)
    # 初始化Milvus连接和集合

async def insert_qa_pair(qa_pair: QAPairWithContext) -> str
    # 插入问答对

async def search_similar(query_vector: List[float], 
                        top_k: int = 5) -> List[Dict]
    # 搜索相似问答对
```

**集合结构**:
```
集合名: {database_name}_qa_pairs
字段:
- id (VARCHAR, 主键)
- question (VARCHAR)
- sql (VARCHAR)
- connection_id (INT64)
- difficulty_level (INT64)
- query_type (VARCHAR)
- success_rate (FLOAT)
- verified (BOOL)
- vector (FLOAT_VECTOR, 维度1024)

索引: IVF_FLAT, COSINE相似度
```

#### 1.2.3 Neo4j服务 (EnhancedNeo4jService)
**类**: `EnhancedNeo4jService`

**主要方法**:
```python
async def store_qa_pair_with_context(qa_pair, schema_context)
    # 存储问答对及上下文

async def structural_search(schema_context, connection_id) -> List
    # 结构检索

async def pattern_search(query_type, difficulty_level) -> List
    # 模式检索
```

**图结构**:
```
节点类型:
- QAPair (问答对)
- Table (表)
- Column (列)
- QueryPattern (查询模式)
- Entity (实体)

关系类型:
- USES_TABLES (使用表)
- FOLLOWS_PATTERN (遵循模式)
- MENTIONS_ENTITY (提及实体)
- HAS_COLUMNS (拥有列)
```

#### 1.2.4 融合排序器 (FusionRanker)
**类**: `FusionRanker`

**主要方法**:
```python
def fuse_and_rank(semantic_results, structural_results, 
                 pattern_results) -> List[RetrievalResult]
    # 融合多个检索结果并排序

def _calculate_quality_score(qa_pair) -> float
    # 计算质量分数

def _calculate_dynamic_final_score(...) -> float
    # 动态权重计算最终分数
```

**权重调整策略**:
```
语义相似度 >= 0.9:
  - 语义: 0.80, 结构: 0.10, 模式: 0.05, 质量: 0.05

语义相似度 >= 0.7:
  - 语义: 0.70, 结构: 0.15, 模式: 0.10, 质量: 0.05

语义相似度 >= 0.5:
  - 语义: 0.60, 结构: 0.20, 模式: 0.10, 质量: 0.10

语义相似度 < 0.5:
  - 语义: 0.40, 结构: 0.35, 模式: 0.20, 质量: 0.05
```

#### 1.2.5 混合检索引擎 (HybridRetrievalEngine)
**类**: `HybridRetrievalEngine`

**主要方法**:
```python
async def hybrid_retrieve(query, schema_context, 
                         connection_id, top_k=5) -> List
    # 混合检索主函数

async def _semantic_search(query, connection_id) -> List
    # 语义检索

async def _structural_search(schema_context, connection_id) -> List
    # 结构检索

async def _pattern_search(query, connection_id) -> List
    # 模式检索

async def store_qa_pair(qa_pair, schema_context)
    # 存储问答对
```

**工作流程**:
```
1. 初始化所有服务
2. 并行执行三种检索
3. 融合排序
4. 返回Top-K结果
```

### 1.3 数据库服务详细设计

#### 1.3.1 DB Service
**文件**: `backend/app/services/db_service.py`

**主要函数**:
```python
def get_connection(connection_id: int) -> DBConnection
    # 获取数据库连接

def execute_query(connection: DBConnection, sql: str) -> List[Dict]
    # 执行查询

def test_connection(connection: DBConnection) -> bool
    # 测试连接

def get_database_info(connection: DBConnection) -> Dict
    # 获取数据库信息
```

#### 1.3.2 Schema Service
**文件**: `backend/app/services/schema_service.py`

**主要函数**:
```python
def retrieve_relevant_schema(db: Session, connection_id: int, 
                            query: str) -> Dict
    # 检索相关Schema

def get_all_tables(db: Session, connection_id: int) -> List
    # 获取所有表

def get_table_columns(db: Session, table_id: int) -> List
    # 获取表的列

def get_relationships(db: Session, connection_id: int) -> List
    # 获取表关系
```

#### 1.3.3 Text2SQL Service
**文件**: `backend/app/services/text2sql_service.py`

**主要函数**:
```python
def construct_prompt(schema_context, query, value_mappings) -> str
    # 构建LLM提示词

def call_llm_api(prompt: str) -> str
    # 调用LLM API

def process_text2sql_query(db: Session, connection: DBConnection, 
                          query: str) -> QueryResponse
    # 处理Text2SQL查询
```

---

## 二、API端点详细设计

### 2.1 连接管理API

#### 2.1.1 创建连接
```
POST /api/connections/

请求体:
{
    "name": "生产数据库",
    "db_type": "mysql",
    "host": "localhost",
    "port": 3306,
    "username": "root",
    "password": "password",
    "database_name": "mydb"
}

响应:
{
    "id": 1,
    "name": "生产数据库",
    "db_type": "mysql",
    "created_at": "2026-01-10T10:00:00Z"
}
```

#### 2.1.2 获取连接列表
```
GET /api/connections/

响应:
{
    "connections": [
        {
            "id": 1,
            "name": "生产数据库",
            "db_type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database_name": "mydb"
        }
    ]
}
```

### 2.2 查询API

#### 2.2.1 执行查询
```
POST /api/query/

请求体:
{
    "connection_id": 1,
    "query": "查询所有用户"
}

响应:
{
    "sql": "SELECT * FROM users",
    "results": [
        {"id": 1, "name": "张三"},
        {"id": 2, "name": "李四"}
    ],
    "execution_time": 0.5,
    "rows_affected": 2
}
```

### 2.3 混合检索API

#### 2.3.1 混合检索查询
```
POST /api/hybrid-qa/

请求体:
{
    "connection_id": 1,
    "query": "查询所有用户",
    "top_k": 5
}

响应:
{
    "results": [
        {
            "question": "类似的问题",
            "sql": "SELECT * FROM users",
            "similarity_score": 0.85,
            "explanation": "语义高度相似(0.85); 使用相同的表结构"
        }
    ]
}
```

---

## 三、数据模型详细设计

### 3.1 SQLMessageState
```python
@dataclass
class SQLMessageState(MessagesState):
    connection_id: int = 15
    query_analysis: Optional[Dict[str, Any]] = None
    schema_info: Optional[SchemaInfo] = None
    generated_sql: Optional[str] = None
    validation_result: Optional[SQLValidationResult] = None
    execution_result: Optional[SQLExecutionResult] = None
    sample_retrieval_result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    current_stage: Literal[...] = "schema_analysis"
    agent_messages: Dict[str, Any] = field(default_factory=dict)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
```

### 3.2 QAPairWithContext
```python
@dataclass
class QAPairWithContext:
    id: str
    question: str
    sql: str
    connection_id: int
    difficulty_level: int
    query_type: str
    success_rate: float
    verified: bool
    created_at: datetime
    used_tables: List[str]
    used_columns: List[str]
    query_pattern: str
    mentioned_entities: List[str]
    embedding_vector: Optional[List[float]] = None
```

### 3.3 RetrievalResult
```python
@dataclass
class RetrievalResult:
    qa_pair: QAPairWithContext
    semantic_score: float = 0.0
    structural_score: float = 0.0
    pattern_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0
    explanation: str = ""
```

---

## 四、配置管理详细设计

### 4.1 环境变量配置
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
VECTOR_DIMENSION=1024
VECTOR_CACHE_ENABLED=true
VECTOR_CACHE_TTL=3600

# 混合检索权重
SEMANTIC_WEIGHT=0.60
STRUCTURAL_WEIGHT=0.20
PATTERN_WEIGHT=0.10
QUALITY_WEIGHT=0.10

# 性能配置
PARALLEL_RETRIEVAL=true
MAX_EXAMPLES_PER_QUERY=5
RETRIEVAL_CACHE_TTL=3600
```

---

## 五、错误处理设计

### 5.1 错误类型
```
1. 连接错误
   - 数据库连接失败
   - 网络超时

2. SQL错误
   - 语法错误
   - 表/列不存在
   - 权限不足

3. 执行错误
   - 查询超时
   - 内存不足
   - 死锁

4. 服务错误
   - LLM API失败
   - 向量化失败
   - 检索失败
```

### 5.2 错误恢复策略
```
1. 重试机制
   - 最多重试3次
   - 指数退避 (1s, 2s, 4s)

2. 降级策略
   - 检索失败时跳过
   - LLM失败时使用备选模型

3. 回滚机制
   - 恢复到上一个成功状态
   - 清理临时数据
```

---

## 六、性能优化详细设计

### 6.1 缓存策略
```
1. 向量缓存
   - 键: {service_type}:{model_name}:{hash(question)}
   - TTL: 3600秒
   - 大小: 无限制

2. 检索缓存
   - 键: {connection_id}:{query_hash}
   - TTL: 3600秒
   - 大小: 1000条

3. Schema缓存
   - 键: {connection_id}
   - TTL: 86400秒 (1天)
   - 大小: 100条
```

### 6.2 并行处理
```
1. 混合检索并行
   - 语义检索
   - 结构检索
   - 模式检索
   - 并行执行，等待所有完成

2. 批量向量化
   - 批大小: 32
   - 异步处理
   - 错误重试

3. 异步API调用
   - 使用asyncio
   - 并发限制: 10
```

### 6.3 数据库优化
```
1. 索引优化
   - connection_id (DBConnection)
   - table_id (SchemaColumn)
   - query_hash (缓存表)

2. 连接池
   - 最小连接: 5
   - 最大连接: 20
   - 超时: 30秒

3. 查询优化
   - 使用EXPLAIN分析
   - 避免全表扫描
   - 使用JOIN优化
```

---

**文档版本**: 1.0
**最后更新**: 2026-01-10

