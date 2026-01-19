# 系统记忆与上下文管理机制

## 📋 文档概述

本文档详细说明了Chat-to-DB系统中用户问答数据的存储机制和上下文处理策略。

**最后更新**: 2026-01-18  
**维护者**: AI Assistant

---

## 📊 1. 用户问答数据存储

### 1.1 存储概述

系统通过 `QueryHistory` 表完整记录用户的查询历史，支持：
- ✅ 查询文本存储
- ✅ 向量嵌入存储（用于相似查询检索）
- ✅ 执行结果元信息
- ✅ 时间戳和数据库连接关联

### 1.2 数据库表结构

**表名**: `query_history`

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BIGINT | 查询历史ID | 主键，自增 |
| query_text | TEXT | 用户查询文本 | 非空 |
| embedding | JSON | 查询向量嵌入 | 可空，JSON格式 |
| connection_id | BIGINT | 数据库连接ID | 可空，外键 |
| created_at | TIMESTAMP | 创建时间 | 非空，自动生成 |
| meta_info | JSON | 元信息 | 可空（执行结果、耗时等） |

**索引**:
- `idx_queryhistory_created` (created_at)
- `idx_queryhistory_connection` (connection_id)

### 1.3 数据模型代码

```python
# backend/app/models/query_history.py
from sqlalchemy import Column, BigInteger, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # Store as JSON list of floats
    connection_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta_info = Column(JSON, nullable=True)  # 执行成功、结果摘要等
```

### 1.4 查询历史服务

**位置**: `backend/app/services/query_history_service.py`

#### 保存查询

```python
def save_query(self, query_text: str, connection_id: int, meta_info: Dict[str, Any] = None):
    """保存用户查询及其向量嵌入"""
    embedding = []
    if self.embedding_model:
        try:
            embedding = self.embedding_model.embed_query(query_text)
        except Exception as e:
            print(f"Error generating embedding: {e}")
    
    history = QueryHistory(
        query_text=query_text,
        embedding=embedding,
        connection_id=connection_id,
        meta_info=meta_info
    )
    self.db.add(history)
    self.db.commit()
    self.db.refresh(history)
    return history
```

#### 相似查询检索

系统使用**余弦相似度**算法检索历史上相似的查询：

```python
def find_similar_queries(self, query_text: str, limit: int = 5, threshold: float = 0.7):
    """使用余弦相似度查找相似查询"""
    if not self.embedding_model:
        return []

    # 1. 生成目标查询的向量嵌入
    target_embedding = self.embedding_model.embed_query(query_text)
    
    # 2. 获取所有历史查询
    history_items = self.db.query(QueryHistory)\
        .filter(QueryHistory.embedding.isnot(None))\
        .all()
    
    # 3. 计算相似度
    results = []
    for item in history_items:
        similarity = self._cosine_similarity(target_embedding, item.embedding)
        if similarity >= threshold:
            results.append((similarity, item))
    
    # 4. 按相似度排序并返回Top-K
    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:limit]]
```

**相似度计算公式**:
```python
def _cosine_similarity(self, v1, v2):
    """余弦相似度 = (A·B) / (||A|| * ||B||)"""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2)
```

### 1.5 使用场景

1. **Few-shot学习**: 检索相似查询作为样本，提高SQL生成质量
2. **查询建议**: 为用户推荐历史上的相似查询
3. **性能分析**: 分析用户查询模式和频率
4. **智能缓存**: 缓存常见查询的结果

---

## 🧠 2. 系统记忆与上下文处理

系统采用**两层记忆和上下文机制**：

### 2.1 第一层：上下文工程（Prompt Engineering）

系统广泛使用多种上下文工程技术来增强LLM的理解和生成能力。

#### 2.1.1 技术总览

| 技术 | 使用情况 | 位置 | 效果 |
|------|---------|------|------|
| **System Prompts** | ✅ 广泛使用 | 所有Agents | 定义角色和行为 |
| **Dynamic Context** | ✅ 动态注入 | Schema/SQL生成 | 提供实时信息 |
| **Few-shot Learning** | ✅ 样本增强 | SQL生成 | 提高生成质量 |
| **Chain-of-Thought** | ✅ 步骤指导 | Supervisor | 引导推理过程 |
| **Constraint Prompting** | ✅ 约束条件 | SQL执行 | 防止错误行为 |
| **Role Prompting** | ✅ 角色定位 | 所有Agents | 明确职责 |

#### 2.1.2 上下文层次结构

系统在生成SQL时，会按照以下层次构建上下文：

```
上下文层次（从基础到高级）:
├─ 1. 系统角色：定义Agent的专业身份和职责
├─ 2. 数据库Schema：表结构、字段类型、约束、关系
├─ 3. 值映射：自然语言术语 → 数据库实际值的映射
├─ 4. 数据库语法：MySQL/PostgreSQL特定语法指导
├─ 5. 历史样本：相似查询的成功案例（Few-shot）
└─ 6. 约束条件：安全性规则、性能要求、业务规则
```

#### 2.1.3 示例：Schema Agent的系统提示词

**位置**: `backend/app/agents/agents/schema_agent.py`

```python
def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig):
    connection_id = extract_connection_id(state)
    system_msg = f"""你是一个专业的数据库模式分析专家。
    **重要：当前数据库connection_id是 {connection_id}**
    
你的任务是：
1. 分析用户的自然语言查询，理解其意图和涉及的实体
2. 获取与查询相关的数据库表结构信息
3. 验证获取的模式信息是否足够完整

工作流程：
- 使用 search_schema 工具查找相关表
- 使用 fetch_table_details 获取详细结构
- 确保获取了所有必需的表和字段信息
"""
    return system_msg
```

**特点**:
- 动态注入 `connection_id` 上下文
- 明确角色定位和任务
- 结构化的工作流程说明

#### 2.1.4 示例：SQL Generator的动态上下文

**位置**: `backend/app/services/text2sql_service.py`

```python
def construct_prompt(schema_context, query, value_mappings, db_type):
    """为LLM构建增强上下文和指令的提示"""
    
    # 1. 格式化表结构信息
    schema_str = format_schema_for_prompt(schema_context)
    
    # 2. 添加值映射上下文
    mappings_str = ""
    if value_mappings:
        mappings_str = "-- 值映射:\n"
        for column, mappings in value_mappings.items():
            mappings_str += f"-- 对于 {column}:\n"
            for nl_term, db_value in mappings.items():
                mappings_str += f"--   '{nl_term}' → '{db_value}'\n"
    
    # 3. 根据数据库类型添加特定语法说明
    db_syntax_guide = ""
    if db_type.lower() == "mysql":
        db_syntax_guide = """### MySQL 语法要求：
- 日期截断：DATE_FORMAT(date_column, '%Y-%m-01')
- 月份提取：DATE_FORMAT(date_column, '%Y-%m')
- 当前日期：NOW() 或 CURRENT_DATE
"""
    
    # 4. 整合上下文
    prompt = f"""
{schema_str}
{mappings_str}
{db_syntax_guide}

用户查询: {query}
"""
    return prompt
```

#### 2.1.5 示例：Few-shot学习

**位置**: `backend/app/agents/agents/sql_generator_agent.py`

```python
@tool
def generate_sql_with_samples(user_query, schema_info, sample_qa_pairs, value_mappings):
    """基于样本生成高质量SQL查询"""
    
    # 构建样本分析
    sample_analysis = "最相关的样本分析:\n"
    for i, sample in enumerate(best_samples, 1):
        sample_analysis += f"""
样本{i} (相关性: {sample['final_score']:.3f}):
- 问题: {sample['question']}
- SQL: {sample['sql']}
- 查询类型: {sample['query_type']}
- 成功率: {sample['success_rate']:.2f}
"""
    
    # 构建增强的生成提示
    prompt = f"""
作为SQL专家，请基于以下信息生成高质量的SQL查询：

用户查询: {user_query}
数据库模式: {schema_info}
{sample_analysis}
值映射信息: {value_mappings}

请参考样本的写法，生成准确的SQL。
"""
    return prompt
```

---

### 2.2 第二层：LangGraph记忆体（Checkpointer）

系统**已完整实现**LangGraph Checkpointer，支持**多轮对话和状态持久化**。

#### 2.2.1 Checkpointer配置

**位置**: `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    # LangGraph Checkpointer 配置
    CHECKPOINT_MODE: str = os.getenv("CHECKPOINT_MODE", "postgres")
    # 选项: postgres | none
    
    CHECKPOINT_POSTGRES_URI: Optional[str] = os.getenv(
        "CHECKPOINT_POSTGRES_URI",
        "postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints"
    )
```

#### 2.2.2 Checkpointer实现

**位置**: `backend/app/core/checkpointer.py`

```python
def create_checkpointer() -> Optional[PostgresSaver]:
    """
    创建 PostgreSQL Checkpointer 实例
    
    功能：
    - 使用 Docker 部署的 PostgreSQL 作为持久化存储
    - 连接信息从环境变量读取
    - 支持通过 CHECKPOINT_MODE 配置启用/禁用
    """
    mode = settings.CHECKPOINT_MODE.lower()
    
    # 检查是否禁用
    if mode == "none" or mode == "":
        logger.info("Checkpointer 已禁用 (mode=none)")
        return None
    
    # 检查是否为 postgres 模式
    if mode != "postgres":
        logger.warning(f"不支持的 Checkpointer 模式: {mode}")
        return None
    
    # 检查配置
    if not settings.CHECKPOINT_POSTGRES_URI:
        raise ValueError("PostgreSQL URI 是必需的")
    
    try:
        logger.info(f"正在创建 PostgreSQL Checkpointer...")
        checkpointer = PostgresSaver.from_conn_string(
            settings.CHECKPOINT_POSTGRES_URI
        )
        logger.info("PostgreSQL Checkpointer 创建成功")
        return checkpointer
        
    except Exception as e:
        logger.error(f"创建 PostgreSQL Checkpointer 失败: {str(e)}")
        raise
```

#### 2.2.3 单例模式访问

```python
# 全局 Checkpointer 实例（单例模式）
_global_checkpointer: Optional[PostgresSaver] = None

def get_checkpointer() -> Optional[PostgresSaver]:
    """获取全局 Checkpointer 实例（单例模式）"""
    global _global_checkpointer
    
    if _global_checkpointer is None:
        _global_checkpointer = create_checkpointer()
        
    return _global_checkpointer
```

#### 2.2.4 图编译集成

**位置**: `backend/app/agents/chat_graph.py`

```python
def _create_graph_with_agent_loader(self):
    """创建带有Checkpointer的LangGraph状态图"""
    from langgraph.graph import StateGraph, END
    from app.core.checkpointer import get_checkpointer
    
    graph = StateGraph(SQLMessageState)
    
    # 添加节点
    graph.add_node("load_custom_agent", self._load_custom_agent_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("supervisor", self._supervisor_node)
    
    # 设置边
    graph.set_entry_point("load_custom_agent")
    graph.add_edge("load_custom_agent", "clarification")
    graph.add_conditional_edges("clarification", after_clarification, {...})
    graph.add_edge("supervisor", END)
    
    # ✅ 获取Checkpointer并编译图
    checkpointer = get_checkpointer()
    
    if checkpointer:
        logger.info("✓ 使用 Checkpointer 编译图（支持多轮对话）")
        return graph.compile(checkpointer=checkpointer)
    else:
        logger.warning("⚠ 未配置 Checkpointer，多轮对话功能受限")
        return graph.compile()
```

---

### 2.3 会话状态管理

#### 2.3.1 SQLMessageState 数据结构

**位置**: `backend/app/core/state.py`

系统维护了一个丰富的状态结构，包含查询处理的所有阶段信息：

```python
class SQLMessageState(AgentState):
    # === 基础信息 ===
    connection_id: int = 15                      # 数据库连接ID
    agent_id: Optional[int] = None               # 自定义智能体ID
    thread_id: Optional[str] = None              # 会话线程ID（用于多轮对话）
    user_id: Optional[str] = None                # 用户ID
    conversation_id: Optional[str] = None        # 对话ID
    
    # === 查询相关 ===
    original_query: Optional[str] = None         # 原始查询
    enriched_query: Optional[str] = None         # 增强后的查询
    query_analysis: Optional[Dict] = None        # 查询分析结果
    similar_queries: Optional[List[Dict]] = None # 相似历史查询
    
    # === Schema信息 ===
    schema_info: Optional[SchemaInfo] = None     # 数据库模式信息
    
    # === SQL处理 ===
    generated_sql: Optional[str] = None          # 生成的SQL
    validation_result: Optional[...] = None      # 验证结果
    execution_result: Optional[...] = None       # 执行结果
    sample_retrieval_result: Optional[Dict] = None # 样本检索结果
    
    # === 流程控制 ===
    current_stage: Literal[...] = "schema_analysis"  # 当前阶段
    retry_count: int = 0                         # 重试次数
    max_retries: int = 3                         # 最大重试次数
    
    # === 澄清机制 ===
    needs_clarification: bool = False            # 是否需要澄清
    pending_clarification: bool = False          # 是否等待澄清回复
    clarification_questions: List[Dict] = []     # 澄清问题列表
    clarification_responses: Optional[List] = None # 澄清回复
    clarification_history: List[Dict] = []       # 澄清历史
    clarification_round: int = 0                 # 澄清轮次
    max_clarification_rounds: int = 2            # 最大澄清轮次
    
    # === 分析与图表 ===
    analyst_insights: Optional[Dict] = None      # 分析洞察
    needs_analysis: bool = False                 # 是否需要分析
    chart_config: Optional[Dict] = None          # 图表配置
    analysis_result: Optional[Dict] = None       # 分析结果
    
    # === 通信与历史 ===
    agent_messages: Dict[str, Any] = {}          # Agent间通信消息
    error_history: List[Dict] = []               # 错误历史
    
    # === 路由 ===
    route_decision: Literal[...] = "data_query"  # 路由决策
```

#### 2.3.2 状态字段分类

| 类别 | 字段数量 | 主要用途 |
|------|---------|---------|
| **基础信息** | 5 | 标识用户、会话、数据库连接 |
| **查询处理** | 5 | 存储查询文本和分析结果 |
| **Schema** | 1 | 数据库结构信息 |
| **SQL处理** | 4 | SQL生成、验证、执行 |
| **流程控制** | 3 | 阶段管理、重试控制 |
| **澄清机制** | 7 | 处理模糊查询的澄清流程 |
| **分析图表** | 4 | 数据分析和可视化 |
| **通信历史** | 2 | Agent协作和错误追踪 |
| **路由决策** | 1 | 查询类型路由 |

---

### 2.4 多轮对话实现

#### 2.4.1 API层集成

**位置**: `backend/app/api/api_v1/endpoints/query.py`

```python
@router.post("/chat", response_model=schemas.ChatQueryResponse)
async def chat_query(
    *,
    db: Session = Depends(deps.get_db),
    chat_request: schemas.ChatQueryRequest,
):
    """
    支持多轮对话的智能查询接口
    ✅ 支持thread_id实现真正的多轮对话和状态持久化
    """
    
    # ✅ 使用conversation_id作为thread_id
    # 如果客户端提供了conversation_id，使用它作为thread_id
    # 否则生成新的UUID
    thread_id = chat_request.conversation_id or str(uuid4())
    
    logger.info(f"Processing chat query with thread_id: {thread_id}")
    
    # 构建初始状态
    initial_state = SQLMessageState(
        messages=[HumanMessage(content=query_text)],
        connection_id=chat_request.connection_id,
        thread_id=thread_id,  # ✅ 设置thread_id
        conversation_id=thread_id,
        original_query=chat_request.natural_language_query,
        current_stage="clarification",
    )
    
    # ✅ 执行图，传递thread_id配置
    result = await graph_instance.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": thread_id  # ✅ 启用记忆体
            }
        }
    )
    
    return result
```

#### 2.4.2 工作原理

```
┌─────────────────────────────────────────────────────────────────┐
│                      多轮对话流程                                 │
└─────────────────────────────────────────────────────────────────┘

第一轮查询:
用户: "查询2024年的销售数据"
  │
  ├─> thread_id: "conv-123" (新生成)
  ├─> 执行查询流程
  ├─> 状态保存到 PostgreSQL (通过Checkpointer)
  └─> 返回结果

第二轮查询（使用相同thread_id）:
用户: "按月份分组"
  │
  ├─> thread_id: "conv-123" (客户端传入)
  ├─> Checkpointer 恢复之前的状态
  ├─> 系统理解"按月份分组"指的是销售数据
  ├─> 在之前SQL基础上添加 GROUP BY
  └─> 返回结果

第三轮查询:
用户: "只看前3个月"
  │
  ├─> thread_id: "conv-123" (继续使用)
  ├─> 继续在同一上下文中处理
  ├─> 添加 WHERE 条件限制月份
  └─> 返回结果
```

#### 2.4.3 状态持久化

Checkpointer将状态持久化到PostgreSQL：

```sql
-- langgraph_checkpoints 数据库表结构
CREATE TABLE checkpoints (
    thread_id TEXT,          -- 会话线程ID
    checkpoint_id TEXT,      -- Checkpoint ID
    parent_checkpoint_id TEXT,
    checkpoint JSONB,        -- 序列化的状态数据
    metadata JSONB,
    created_at TIMESTAMP
);

-- 索引
CREATE INDEX idx_thread_id ON checkpoints(thread_id);
CREATE INDEX idx_checkpoint_id ON checkpoints(checkpoint_id);
```

---

## 🔄 3. 完整的查询处理流程

### 3.1 单次查询流程

```
用户输入查询
    ↓
API接收请求（生成/使用thread_id）
    ↓
加载自定义Agent（如有）
    ↓
澄清节点：检测查询模糊性
    ├─ 需要澄清 → 生成澄清问题 → 等待用户回复 → END
    └─ 不需要澄清 → 继续
    ↓
Supervisor协调Worker Agents:
    ├─ Schema Agent: 分析Schema
    ├─ SQL Generator: 生成SQL（使用Few-shot）
    ├─ SQL Executor: 执行SQL
    └─ Chart Generator/Analyst: 分析和可视化
    ↓
保存查询历史（带向量嵌入）
    ↓
Checkpointer保存状态
    ↓
返回结果给用户
```

### 3.2 多轮对话流程

```
第1轮: "查询销售数据"
    → 完整执行 → 保存状态(thread_id="conv-123")

第2轮: "按月份分组" (thread_id="conv-123")
    → 恢复状态 → 理解上下文 → 修改SQL → 保存新状态

第3轮: "导出为图表" (thread_id="conv-123")
    → 恢复状态 → 使用之前的SQL结果 → 生成图表 → 保存状态
```

---

## 📈 4. 性能与优化

### 4.1 查询历史优化

| 优化点 | 当前实现 | 改进建议 |
|--------|---------|---------|
| **向量存储** | JSON字段 | 迁移到 PGVector 扩展 |
| **相似度计算** | 内存计算 | 使用向量数据库索引 |
| **缓存** | 无 | 添加Redis缓存层 |
| **批量查询** | 单条查询 | 实现批量检索API |

### 4.2 Checkpointer优化

| 优化点 | 当前实现 | 改进建议 |
|--------|---------|---------|
| **存储引擎** | PostgreSQL | ✅ 已优化 |
| **连接池** | 默认配置 | 调整连接池大小 |
| **清理策略** | 无 | 实现过期状态清理 |
| **压缩** | 无 | 压缩大型状态对象 |

### 4.3 上下文优化

| 优化点 | 当前实现 | 改进建议 |
|--------|---------|---------|
| **Token管理** | 无限制 | 实现上下文窗口管理 |
| **摘要生成** | 无 | 长对话自动摘要 |
| **相关性过滤** | 全量加载 | 智能过滤无关上下文 |

---

## 🎯 5. 最佳实践

### 5.1 使用Checkpointer

**正确示例**：

```python
# ✅ 正确：使用thread_id
result = await graph.ainvoke(
    state,
    config={"configurable": {"thread_id": "conv-123"}}
)
```

**错误示例**：

```python
# ❌ 错误：忘记传递thread_id
result = await graph.ainvoke(state)
# 结果：无法恢复历史状态，每次都是新对话
```

### 5.2 管理会话生命周期

```python
# 客户端代码示例
class ChatSession:
    def __init__(self):
        self.thread_id = None  # 会话线程ID
    
    def start_new_conversation(self):
        """开始新对话"""
        self.thread_id = str(uuid4())
    
    def continue_conversation(self):
        """继续现有对话"""
        # 使用相同的thread_id
        pass
    
    def send_message(self, query: str):
        """发送消息"""
        response = requests.post("/api/v1/query/chat", json={
            "natural_language_query": query,
            "connection_id": 15,
            "conversation_id": self.thread_id  # 传递thread_id
        })
        return response.json()
```

### 5.3 查询历史最佳实践

```python
# ✅ 在SQL生成前检索相似查询
similar_queries = query_history_service.find_similar_queries(
    query_text="查询本月销售额",
    limit=3,
    threshold=0.8  # 相似度阈值
)

# 使用相似查询作为Few-shot样本
for sq in similar_queries:
    print(f"历史查询: {sq.query_text}")
    print(f"SQL: {sq.meta_info.get('sql')}")
```

---

## 🔍 6. 监控与调试

### 6.1 检查Checkpointer状态

```python
from app.core.checkpointer import check_checkpointer_health

# 健康检查
if check_checkpointer_health():
    print("✓ Checkpointer 正常")
else:
    print("✗ Checkpointer 异常")
```

### 6.2 查看会话历史

```sql
-- 查询特定thread的所有checkpoints
SELECT 
    thread_id,
    checkpoint_id,
    created_at,
    checkpoint->'current_stage' as stage
FROM checkpoints
WHERE thread_id = 'conv-123'
ORDER BY created_at DESC;
```

### 6.3 日志监控

```python
# 启用详细日志
import logging
logging.getLogger("app.core.checkpointer").setLevel(logging.DEBUG)
logging.getLogger("app.agents.chat_graph").setLevel(logging.DEBUG)
```

---

## 📚 7. 相关文档

- [上下文工程分析](./CONTEXT_ENGINEERING.md)
- [Text-to-SQL分析](./TEXT2SQL_ANALYSIS.md)
- [数据库Schema说明](../backend/DATABASE_SCHEMA.md)
- [LangGraph实现总结](../langgraph/IMPLEMENTATION_SUMMARY.md)

---

## 🔄 8. 更新日志

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-01-18 | v1.0 | 初始版本，完整文档化记忆和上下文管理机制 |

---

**文档版本**: v1.0  
**最后更新**: 2026-01-18  
**维护者**: AI Assistant
