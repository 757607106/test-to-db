# Agent 核心逻辑流程图

## 一、主图流程 (IntelligentSQLGraph)

### 1.1 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            用户发送查询                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     🎯 intent_router 节点                                   │
│  - 检测用户意图：数据查询 vs 闲聊                                           │
│  - 数据查询关键词：查询、统计、显示、SQL关键词等                              │
│  - 闲聊关键词：你好、谢谢、帮助等                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            数据查询 ▼                          闲聊 ▼
    ┌───────────────────────┐       ┌───────────────────────┐
    │  数据查询流程          │       │  general_chat 节点     │
    │        ↓              │       │  - 直接 LLM 回复       │
    └───────────────────────┘       │  - 返回 END            │
                │                   └───────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     1️⃣ load_custom_agent 节点                               │
│  - 从消息中提取 agent_id 和 connection_id                                   │
│  - 如果有 agent_id，从数据库加载自定义分析专家（废弃）                        │
│  - connection_id 动态传入，支持多数据库连接                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     2️⃣ fast_mode_detect 节点                                │
│  - 检测查询复杂度，决定是否启用快速模式                                       │
│  - 简单查询 → skip_sample_retrieval=True, skip_chart_generation=True       │
│  - 复杂查询 → 使用完整模式（样本检索 + 图表生成）                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     3️⃣ thread_history_check 节点 (三级缓存-L0)              │
│  - 检查当前对话线程内是否有相同问题                                          │
│  - 命中 → 直接返回历史答案，END                                             │
│  - 未命中 → 继续到全局缓存检查                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     4️⃣ cache_check 节点 (三级缓存-L1/L2)                    │
│  - L1: 精确匹配缓存 (相同查询+连接ID)                                       │
│       存储: 内存 OrderedDict, 容量: 1000条, TTL: 1小时                      │
│  - L2: 语义匹配缓存 (相似度 >= 95%)                                         │
│       存储: Milvus 向量数据库, 返回相似SQL模板                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            缓存命中 ▼                       缓存未命中 ▼
    ┌───────────────────────┐       ┌───────────────────────┐
    │ 精确命中：直接返回     │       │  继续到 clarification │
    │ 语义命中：基于模板生成  │       └───────────────────────┘
    │        ↓              │                    │
    │      END              │                    ▼
    └───────────────────────┘  ┌─────────────────────────────────────────────┐
                               │             5️⃣ clarification 节点            │
                               │  - 检测用户查询是否模糊/歧义                 │
                               │  - 使用 interrupt() 暂停，等待用户澄清回复   │
                               │  - 用户回复后，生成增强查询继续执行           │
                               └─────────────────────────────────────────────┘
                                               │
                                               ▼
                               ┌─────────────────────────────────────────────┐
                               │             6️⃣ supervisor 节点               │
                               │    (协调 Worker Agents 完成任务)             │
                               │    - 使用原生 Supervisor 实现                │
                               │    - 双模式路由：状态机 + LLM智能决策         │
                               └─────────────────────────────────────────────┘
                                               │
                                               ▼
                               ┌─────────────────────────────────────────────┐
                               │     7️⃣ question_recommendation 节点          │
                               │  - 根据查询结果推荐相关问题                   │
                               │  - 帮助用户深入探索数据                       │
                               └─────────────────────────────────────────────┘
                                               │
                                               ▼
                               ┌─────────────────────────────────────────────┐
                               │       存储结果到缓存 → END                   │
                               └─────────────────────────────────────────────┘
```

### 1.2 三级缓存策略

系统采用三级缓存机制，逐层检查以提升性能：

1. **L0 - Thread 历史缓存** (`thread_history_check`)
   - 范围：当前对话线程内
   - 存储：对话状态中
   - 优势：最快，无需跨线程查询
   
2. **L1 - 精确匹配缓存** (`cache_check`)
   - 范围：全局，所有用户
   - 存储：内存 OrderedDict
   - 匹配：MD5(normalize(query):connection_id)
   
3. **L2 - 语义匹配缓存** (`cache_check`)
   - 范围：全局，所有用户
   - 存储：Milvus 向量数据库
   - 匹配：相似度 >= 0.95，返回 SQL 模板

---

## 二、Supervisor 内部流程 (Worker Agents 协调)

### 2.1 Supervisor 架构设计

**核心特点**：
- **原生 LangGraph 实现**：不依赖第三方 supervisor 库
- **双模式路由**：状态机路由（快速）+ LLM智能路由（复杂场景）
- **死循环检测**：防止同一阶段重复失败
- **智能错误恢复**：专门的错误恢复上下文传递

### 2.2 Worker Agents 流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Supervisor Agent (原生实现)                          │
│  - 基于 current_stage 的状态机路由（正常流程，无LLM调用）                     │
│  - 基于 LLM 的智能路由（错误恢复、复杂场景）                                  │
│  - 死循环检测：同一阶段连续出错2次以上自动终止                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🔍 schema_agent (ReAct Agent)                          │
│  - 职责：分析用户查询意图，检索相关数据库表结构                               │
│  - 工具：analyze_user_query, retrieve_database_schema                       │
│  - 优化：异步并行获取表和列（性能提升 20s → 8-12s）                          │
│  - 输出：schema_info (tables, columns, relationships, value_mappings)       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ⚙️ sql_generator_agent (ReAct Agent)                    │
│  - 职责：根据 schema 信息生成高质量 SQL 语句                                 │
│  - 工具：generate_sql_query, generate_sql_with_samples                      │
│  - 优化：内置样本检索（快速模式可跳过，避免独立 Agent 调度延迟）               │
│  - 特性：支持基于缓存SQL模板生成、错误恢复上下文传递                          │
│  - 输出：generated_sql, sample_retrieval_result                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🚀 sql_executor_agent (直接工具调用)                    │
│  - 职责：安全执行 SQL 查询并返回结果                                         │
│  - 实现：ToolNode 包装（不使用 ReAct，避免重复调用）                         │
│  - 优化：工具级缓存（防止重复执行）+ 并发锁                                  │
│  - 输出：execution_result (success, data, error, execution_time)            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
               执行成功 ▼                      执行失败 ▼
    ┌───────────────────────────┐    ┌───────────────────────────┐
    │  进入数据分析阶段          │    │  🔧 error_recovery_agent   │
    │  (总是执行，快速模式不影响)│    │  - 错误模式识别            │
    │        ↓                  │    │  - 恢复策略生成            │
    │  📊 data_analyst_agent    │    │  - 用户友好消息            │
    │  - 分析查询结果            │    │  - 传递错误上下文重试       │
    │  - 生成数据洞察            │    └───────────────────────────┘
    │  - 提供业务建议            │                  │
    └───────────────────────────┘                  │
                │                                  │
                ▼                                  │
    ┌───────────────────────────┐                  │
    │  检查是否需要图表可视化    │                  │
    │  (快速模式可跳过)          │                  │
    └───────────────────────────┘                  │
                │                                  │
        ┌───────┴───────┐                         │
        │               │                         │
   需要图表 ▼      跳过图表 ▼                      │
┌─────────────┐  ┌─────────────┐                 │
│ 📊 chart_   │  │    完成     │                 │
│ generator_  │  │             │                 │
│ agent       │  │             │                 │
│ - 规则推断  │  │             │                 │
│   图表类型  │  │             │                 │
│ - 生成配置  │  │             │                 │
└─────────────┘  └─────────────┘                 │
        │               │                         │
        └───────┬───────┘◀────────────────────────┘
                ▼                      (重试或终止)
┌─────────────────────────────────────────────────────────────────────────────┐
│                             返回最终结果                                     │
│  - 标准流程: schema → sql_gen → sql_exec → analysis → chart → completed      │
│  - 快速流程: schema → sql_gen → sql_exec → analysis → completed (跳过chart)  │
│  - 错误流程: 任意阶段 → error_recovery → [重试 | 终止]                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 路由模式详解

#### 模式1：状态机路由 (route_by_stage)
**使用场景**：正常流程的阶段转换  
**特点**：快速，无 LLM 调用

```
current_stage 状态转换:
  schema_analysis      → schema_agent
  sql_generation       → sql_generator_agent
  sql_execution        → sql_executor_agent
  analysis             → data_analyst_agent (或自定义分析专家)
  chart_generation     → chart_generator_agent
  error_recovery       → error_recovery_agent
  completed            → FINISH
```

#### 模式2：LLM智能路由 (route_with_llm)
**使用场景**：错误恢复、复杂决策  
**触发条件**：
- 存在 `error_recovery_context`（说明是错误恢复后的重试）
- 迭代次数 > 7（可能陷入循环）

**上下文信息**：
- 用户原始查询
- 当前阶段和状态
- 错误历史（最近3条）
- 执行进度（schema、SQL、结果）
- 错误恢复上下文（失败SQL、错误类型、修复建议）

**决策原则**：
1. **SQL 语法/结构错误** → 重新生成 SQL (retry < 3)
2. **Schema 相关错误** → 重新获取 schema
3. **连接/权限错误** → 通常无法自动恢复，告知用户
4. **达到重试上限** → 终止流程

#### 死循环检测
**检测逻辑**：
- 同一阶段连续出错 2 次以上
- 错误消息完全相同或错误类型相同
- 触发后直接终止，避免无限重试

**注意**：`sample_retrieval_agent` 已临时禁用并集成到 `sql_generator_agent` 内部（避免 ReAct agent 调度延迟）

---

## 三、状态流转 (current_stage)

### 3.1 标准流程状态转换

```
intent_router (意图路由)
  ↓
clarification (澄清检测，可能 interrupt)
  ↓
thread_history_check → [命中 → completed] | [未命中 ↓]
  ↓
cache_check → [命中 → completed] | [未命中 ↓]
  ↓
schema_analysis (获取数据库模式)
  ↓
sql_generation (生成SQL，内置样本检索)
  ↓
sql_execution (执行SQL)
  ├─ 成功 → analysis (数据分析，总是执行)
  │          ↓
  │      chart_generation (图表生成，快速模式可跳过)
  │          ↓
  │      completed
  └─ 失败 → error_recovery
              ├─ 可自动修复 → [重试对应阶段]
              └─ 无法修复 → completed (返回错误消息)
```

### 3.2 快速模式流程

**简单查询的优化路径**：

```
clarification → cache_check → schema_analysis → sql_generation (跳过样本检索) 
→ sql_execution → analysis → completed (跳过图表生成)
```

**触发条件**：
- 查询长度 < 50 字符
- 不包含可视化关键词（图表、趋势、分布等）
- 简单查询模式（查询数量、列出信息等）

**性能提升**：响应时间减少 30-50%

### 3.3 完整模式流程

**复杂查询的完整路径**：

```
clarification → cache_check → schema_analysis → sql_generation (含样本检索) 
→ sql_execution → analysis (数据洞察) → chart_generation (可视化) → completed
```

**触发条件**：
- 包含分析关键词（趋势、对比、分布）
- 包含可视化关键词（图表、图形）
- 复杂聚合查询

### 3.4 错误恢复流程

**错误发生时的处理**：

```
[任意阶段出错]
  ↓
current_stage = "error_recovery"
  ↓
error_recovery_agent 分析错误
  ├─ SQL语法错误 → current_stage = "sql_generation" (重新生成)
  ├─ Schema错误 → current_stage = "schema_analysis" (重新获取)
  ├─ 连接错误 → current_stage = "completed" (告知用户)
  └─ 达到重试上限 → current_stage = "completed" (终止)
```

**retry_count 管理**：
- 每次进入 error_recovery_agent 时 +1
- 最大值：3 次（可配置）
- 达到上限后不再重试

---

## 四、Worker Agents 详解

| Agent | 职责 | 实现方式 | 关键优化 |
|------|------|---------|---------|
| **schema_agent** | 数据库模式分析 | ReAct Agent + InjectedState | 异步并行获取表和列（20s→8-12s） |
| **sql_generator_agent** | SQL生成 | ReAct Agent + 结构化输出 | 内置样本检索，基于模板生成 |
| **sql_executor_agent** | SQL执行 | ToolNode直接调用 | 工具缓存+并发锁，避免重复执行 |
| **data_analyst_agent** | 数据分析洞察 | 纯LLM分析 | 2026-01-23新增，职责分离 |
| **chart_generator_agent** | 图表配置生成 | 规则引擎 + LLM | 规则推断优先，快速模式可跳过 |
| **error_recovery_agent** | 错误恢复 | ReAct Agent + 工具 | 错误分类+恢复策略+上下文传递 |

### 4.1 Schema Agent
**文件**：`backend/app/agents/agents/schema_agent.py`

**工具列表**：
1. `analyze_user_query`：使用LLM分析查询意图，提取关键实体
2. `retrieve_database_schema`：从数据库检索相关表结构和值映射

**关键优化**：
- 使用 `retrieve_relevant_schema_async` 异步并行获取
- 批量获取列和关系，减少数据库查询次数
- 流式事件：`schema_mapping` 步骤，实时反馈进度

**输出示例**：
```python
schema_info = {
    "tables": {
        "products": {
            "columns": ["id", "name", "category", "price"],
            "relationships": [...]
        }
    },
    "value_mappings": {
        "category": {"手机": "mobile_phone"}
    }
}
```

### 4.2 SQL Generator Agent
**文件**：`backend/app/agents/agents/sql_generator_agent.py`

**工具列表**：
1. `generate_sql_query`：基础SQL生成（内置自动样本检索）
2. `generate_sql_with_samples`：基于历史样本生成（更高质量）

**关键特性**：
- **样本检索集成**：使用 `HybridRetrievalEnginePool.quick_retrieve()` 快速检索
- **基于模板生成**：语义缓存命中时，基于缓存SQL模板生成
- **错误恢复支持**：接收 `error_recovery_context`，提供失败SQL和修复建议
- **动态数据库类型**：自动检测 MySQL/PostgreSQL/SQLite

**QA样本配置**：
```python
QA_SAMPLE_ENABLED = True           # 是否启用
QA_SAMPLE_TOP_K = 3                # 检索数量
QA_SAMPLE_MIN_SIMILARITY = 0.6     # 最低相似度
QA_SAMPLE_TIMEOUT = 10             # 超时时间
```

### 4.3 SQL Executor Agent
**文件**：`backend/app/agents/agents/sql_executor_agent.py`

**实现方式**：
- 使用 `ToolNode` 包装工具（官方推荐）
- 不使用 ReAct Agent，避免 LLM 重复调用工具

**缓存机制**：
```python
cache_key = f"{connection_id}:{hash(sql_query)}"
# 只缓存 SELECT 查询
# 缓存有效期: 5分钟
# 最大缓存数: 100条
```

**并发控制**：
```python
_cache_lock = {}  # 执行锁
# 防止并发重复执行同一SQL
```

**执行成功后**：
- 总是进入 `analysis` 阶段（数据分析）
- 快速模式不影响数据分析，只影响图表生成

### 4.4 Data Analyst Agent
**文件**：`backend/app/agents/agents/data_analyst_agent.py`

**职责分离** (2026-01-23)：
- **Data Analyst**：数据解读和洞察生成（文本输出）
- **Chart Generator**：图表配置和可视化建议（配置输出）

**输出结构**：
```markdown
### 回答
[直接回答用户问题]

### 数据洞察
1. [洞察1]
2. [洞察2]

### 建议
- [建议1]
- [建议2]
```

### 4.5 Chart Generator Agent
**文件**：`backend/app/agents/agents/chart_generator_agent.py`

**图表类型推断**（规则优先）：
- 有日期列 + 数值列 → 折线图
- 分类少于8个 + 数值列 → 柱状图
- 只有1个数值列 + 分类少于6个 → 饼图
- 数据较多（>15行）→ 折线图

**适合可视化判断**：
- 至少2列数据
- 至少2行数据
- 数据行数不超过100行

### 4.6 Error Recovery Agent
**文件**：`backend/app/agents/agents/error_recovery_agent.py`

**错误分类**（改进版）：
1. **sql_syntax_error**：SQL语法/结构错误（Unknown column, subquery等）
2. **not_found_error**：表或字段不存在
3. **connection_error**：数据库连接错误
4. **permission_error**：权限不足
5. **timeout_error**：查询超时
6. **unknown_error**：未知错误

**恢复策略示例**：
```python
"sql_syntax_error": {
    "primary_action": "regenerate_sql",
    "auto_fixable": True,
    "confidence": 0.85,
    "steps": [
        "分析错误原因（列名、表名、子查询结构）",
        "重新检查 schema 中的正确列名和表名",
        "使用更简单的 SQL 结构避免子查询问题",
        "重新生成符合数据库约束的 SQL"
    ]
}
```

**用户友好消息**：
- 每种错误类型映射到用户友好的消息
- 重试时显示"正在重新尝试..."
- 失败时提供具体的建议

---

## 五、架构对比：我们的实现 vs LangGraph 官方模式

### 5.1 核心差异

| 维度 | 我们的实现 | LangGraph 官方推荐 | 评价 |
|------|-----------|------------------|------|
| **Supervisor模式** | 自定义原生实现（类封装） | 使用条件边函数 | ✅ 更灵活，支持复杂路由逻辑 |
| **路由方式** | 双模式：状态机+LLM智能 | 基于消息的条件函数 | ✅ 状态机快速，LLM处理复杂场景 |
| **工具调用** | 混合：ReAct + 直接调用 | 推荐ToolNode直接调用 | ⚠️ 部分Agent可简化为ToolNode |
| **消息管理** | 手动去重 + 自动修剪 | add_messages reducer | ⚠️ 可考虑使用reducer简化 |
| **错误处理** | 专门ErrorRecoveryAgent | 通常在条件边中处理 | ✅ 更完善的错误分析和恢复 |
| **状态持久化** | AsyncPostgresSaver | Checkpointer接口 | ✅ 符合官方标准 |
| **前置处理** | 意图路由+三级缓存+澄清 | 通常较简单 | ✅ 更完善的用户体验 |

### 5.2 LangGraph 官方模式参考

#### 官方 SQL Agent 示例
```python
# 官方推荐的简洁模式
builder = StateGraph(MessagesState)
builder.add_node(list_tables)
builder.add_node(get_schema_node, "get_schema")
builder.add_node(generate_query)
builder.add_node(check_query)
builder.add_node(run_query_node, "run_query")

builder.add_edge(START, "list_tables")
builder.add_conditional_edges(
    "generate_query",
    should_continue,  # 简单函数
)
```

#### 我们的模式
```python
# 更复杂但功能更全的实现
graph = StateGraph(SQLMessageState)
graph.add_node("intent_router", self._intent_router_node)
graph.add_node("thread_history_check", thread_history_check_node)
graph.add_node("cache_check", cache_check_node)
graph.add_node("clarification", clarification_node)
graph.add_node("supervisor", self._supervisor_node)  # 封装了复杂的路由逻辑

# Supervisor内部使用双模式路由
next_agent = await self._intelligent_route(state)
```

### 5.3 我们的优势

1. **更智能的决策**：
   - LLM智能路由可处理复杂错误场景
   - 错误恢复agent提供专业的错误分析
   - 死循环检测防止无限重试

2. **更完善的用户体验**：
   - 意图路由（闲聊vs数据查询）
   - 三级缓存（Thread→精确→语义）
   - 澄清机制（interrupt实现人机交互）
   - 问题推荐（帮助用户探索数据）

3. **更强的性能优化**：
   - 异步并行（Schema获取）
   - 快速模式（简单查询跳过步骤）
   - 多级缓存（减少重复计算）
   - Agent实例缓存（避免重复创建）

### 5.4 可改进之处

1. **消息管理简化**：
   - 当前：手动去重逻辑
   - 改进：使用 `add_messages` reducer

2. **ToolNode应用**：
   - 当前：某些Agent仍使用ReAct
   - 改进：简单工具调用改用ToolNode

3. **条件边简化**：
   - 当前：某些判断在节点内部
   - 改进：可内联到条件函数

### 5.5 架构选择的考量

**为什么选择更复杂的实现？**

1. **业务需求**：企业级Text-to-SQL系统需要更完善的错误处理和用户体验
2. **性能要求**：需要多级缓存和优化策略来提升响应速度
3. **可维护性**：清晰的职责分离（6个专业Agent）便于维护和扩展
4. **智能程度**：LLM辅助路由可以处理更复杂的场景

**权衡**：
- ✅ 功能完善、用户体验好、错误处理强
- ⚠️ 代码复杂度较高、学习曲线陡

---

## 六、关键设计总结

### 6.1 系统架构层次

| 层级 | 组件 | 职责 | 实现方式 |
|------|------|------|---------|
| **主图层** | `IntelligentSQLGraph` | 流程控制、意图路由、三级缓存、澄清机制 | StateGraph + 条件边 |
| **协调层** | `SupervisorAgent` | 智能路由、Agent调度、错误恢复决策 | 原生实现（双模式路由） |
| **执行层** | Worker Agents × 6 | 专业任务执行 | ReAct/ToolNode混合 |
| **服务层** | Services | 数据库操作、检索、缓存 | 纯Python服务 |

### 6.2 核心特性

1. **两层架构**：主图控制流程 + Supervisor协调Agent
2. **三级缓存**：Thread历史 → 精确匹配 → 语义匹配
3. **澄清机制**：使用 LangGraph interrupt() 实现人机交互
4. **双模式路由**：状态机路由（快速）+ LLM智能路由（复杂）
5. **自愈能力**：错误自动检测、分类和恢复
6. **快速模式**：简单查询自动跳过样本检索和图表生成
7. **职责分离**：6个专业Agent，职责清晰

### 6.3 LangGraph 核心模式应用

| 模式 | 应用场景 | 文件位置 |
|------|---------|---------|
| **StateGraph** | 主图和子图管理 | chat_graph.py, supervisor_subgraph.py |
| **Conditional Edges** | 路由决策 | 所有图节点的连接 |
| **InjectedState** | 工具参数注入 | schema_agent.py, sql_generator_agent.py |
| **interrupt()** | 人机交互暂停 | clarification_node.py |
| **Checkpointer** | 状态持久化 | AsyncPostgresSaver |
| **StreamWriter** | 流式事件输出 | 所有Agent的process方法 |
| **ToolNode** | 直接工具调用 | sql_executor_agent.py |
| **ReAct Agent** | 需要推理的工具调用 | schema_agent.py, sql_generator_agent.py |

### 6.4 性能优化技术

1. **异步并行**：Schema获取并行化（20s→8-12s）
2. **三级缓存**：Thread → 精确 → 语义
3. **快速模式**：简单查询跳过步骤（提升30-50%）
4. **工具缓存**：防止重复执行SQL
5. **消息修剪**：自动控制上下文长度
6. **Agent缓存**：复用默认实例

### 6.5 错误处理机制

1. **专门Agent**：ErrorRecoveryAgent负责错误分析
2. **智能路由**：LLM辅助复杂错误场景决策
3. **上下文传递**：失败SQL和修复建议传递给重试
4. **死循环检测**：防止同一错误无限重试
5. **用户友好消息**：错误消息映射到用户可理解的文本

---

## 七、缓存系统详解

### 7.1 三级缓存架构

```
L0: Thread 历史缓存 (最快)
  ↓ 未命中
L1: 精确匹配缓存 (快)
  ↓ 未命中
L2: 语义匹配缓存 (智能)
  ↓ 未命中
完整执行流程
```

### 7.2 L0 - Thread 历史缓存

**实现位置**：`backend/app/agents/nodes/thread_history_check_node.py`

**特点**：
- 范围：当前对话线程内
- 存储：对话状态中
- 匹配：完全相同的用户查询
- 优势：最快，无需跨线程查询

### 7.3 L1 - 精确匹配缓存

**实现位置**：`backend/app/services/query_cache_service.py`

**存储方式**：
- 数据结构：`OrderedDict[str, CacheEntry]`
- 缓存键：`MD5(normalize(query):connection_id)`
- 最大容量：1000条
- TTL：3600秒（1小时）
- 淘汰策略：LRU

**CacheEntry 结构**：
```python
{
    query: str              # 原始查询
    connection_id: int      # 数据库连接ID
    sql: str                # 生成的SQL
    result: Any             # 执行结果
    created_at: float       # 创建时间戳
    hit_count: int          # 命中次数
}
```

### 7.4 L2 - 语义匹配缓存

**实现位置**：`backend/app/services/hybrid_retrieval_service.py`

**存储方式**：
- 数据来源：历史QA样本（问题-SQL对）
- 存储：Milvus向量数据库
- 检索：向量语义检索
- 相似度阈值：>= 0.95
- 返回：SQL模板（不含执行结果）

**工作流程**：
```
1. 用户查询 → 向量化 (Embedding)
2. Milvus 语义检索 → 返回最相似的历史QA对
3. 判断相似度 >= 0.95 → 命中
4. 返回 SQL 模板 + 生成增强查询
5. 基于模板生成最终SQL并执行
```

### 7.5 缓存优势对比

| 层级 | 速度 | 范围 | 智能程度 | 包含结果 |
|------|------|------|---------|---------|
| **L0 Thread** | 最快 | 当前对话 | 精确匹配 | ✅ |
| **L1 精确** | 快 | 全局 | 精确匹配 | ✅ |
| **L2 语义** | 较慢 | 全局 | 语义理解 | ❌ (仅SQL模板) |

---

## 八、已知问题与解决方案

### 问题1: 缓存无法存储执行结果 ✅ 已解决 (2026-01-19)

**现象**：
- 相同查询第二次执行仍未命中缓存
- 或只命中SQL但没有执行结果

**根本原因**：
- Supervisor 使用 `output_mode="full_history"` 只返回messages
- 无法直接返回 `execution_result` 等状态字段

**解决方案**：
- 从 `ToolMessage` 中提取执行结果
- sql_executor_agent 将结果存入 ToolMessage.content（JSON格式）
- _store_result_to_cache 解析并缓存

### 问题2: 消息重复导致上下文过长 ✅ 已解决 (2026-01-21)

**现象**：
- 消息历史中出现重复的ToolMessage
- 上下文长度快速增长

**根本原因**：
- Supervisor添加handoff消息
- Agent返回的消息与已有消息重复

**解决方案**：
- `add_handoff_back_messages=False`：不添加handoff消息
- `output_mode="last_message"`：只返回最后的总结消息
- 手动消息去重：使用消息ID集合去重

### 问题3: Sample Retrieval Agent 调度延迟 ✅ 已解决 (2026-01-19)

**现象**：
- 独立的 sample_retrieval_agent 导致 2+ 分钟延迟
- ReAct agent 调度开销过大

**解决方案**：
- 临时禁用独立的 sample_retrieval_agent
- 样本检索集成到 sql_generator_agent 内部
- 快速检查是否有样本，没有则跳过

---

## 九、优化历史

### 2026-01-23: 职责分离 - Data Analyst Agent

**背景**：
- 原 chart_generator_agent 职责过重
- 既要分析数据又要生成图表

**改进**：
- 新增 data_analyst_agent 负责数据分析和洞察
- chart_generator_agent 专注于图表配置生成
- 流程变为：sql_execution → analysis → chart_generation

**效果**：
- 职责更清晰
- 数据分析总是执行（快速模式不影响）
- 图表生成可选（快速模式跳过）

### 2026-01-22: Supervisor 原生实现

**背景**：
- 使用第三方 langgraph_supervisor 库
- 定制化需求难以满足

**改进**：
- 实现原生 Supervisor（不依赖第三方库）
- 双模式路由：状态机（快速）+ LLM智能（复杂）
- 添加死循环检测

**效果**：
- 更灵活的路由控制
- 更好的错误处理
- 减少外部依赖

### 2026-01-22: 三级缓存策略

**背景**：
- 原有双层缓存（精确+语义）
- 对话内重复问题未优化

**改进**：
- 新增 L0 - Thread历史缓存
- 检查顺序：Thread → 精确 → 语义

**效果**：
- 对话内重复问题响应最快
- 缓存命中率提升

### 2026-01-22: Schema 获取异步并行优化

**背景**：
- Schema 获取耗时 20+ 秒
- 串行获取表和列

**改进**：
- 使用 `retrieve_relevant_schema_async`
- 并行获取表和列

**效果**：
- 性能提升：20s → 8-12s
- 用户体验显著改善

### 2026-01-21: 快速模式 (Fast Mode)

**背景**：
- 简单查询不需要完整流程
- 借鉴 LangGraph 官方 SQL Agent

**改进**：
- 自动检测查询复杂度
- 简单查询跳过样本检索和图表生成

**效果**：
- 简单查询响应时间减少 30-50%
- 复杂查询保持完整功能

### 2026-01-19: 双层缓存 + SQL模板

**背景**：
- 只有基本的内存缓存
- 相似查询无法复用

**改进**：
- L1：精确匹配缓存（内存）
- L2：语义匹配缓存（Milvus）
- 支持基于SQL模板生成

**效果**：
- 缓存命中率大幅提升
- 支持相似查询快速响应

### 2026-01-16: SQL Validator 移除

**背景**：
- 原流程：Schema → SQL生成 → SQL验证 → SQL执行
- 验证步骤增加延迟

**改进**：
- 移除 SQL Validator Agent
- SQL生成后直接执行
- 在生成阶段就确保质量

**效果**：
- LLM调用减少 1-2 次
- 响应时间提升 30-50%

---

**文档版本**: v3.0  
**最后更新**: 2026-01-23  
**维护者**: AI Assistant  
**对应代码版本**: 基于 2026-01-23 的实现

---

**文档版本**: v3.0  
**最后更新**: 2026-01-23  
**维护者**: AI Assistant  
**对应代码版本**: 基于 2026-01-23 的实现
