# Text-to-SQL 系统架构分析文档

## 📋 目录

1. [系统概述](#系统概述)
2. [核心架构](#核心架构)
3. [工作流程](#工作流程)
4. [核心组件详解](#核心组件详解)
5. [状态管理](#状态管理)
6. [Agent详解](#agent详解)
7. [与LangGraph官方模式对比](#与langgraph官方模式对比)
8. [优化历史](#优化历史)
9. [关键技术点](#关键技术点)

---

## 系统概述

### 系统定位
这是一个基于 LangGraph 的智能 Text-to-SQL 系统，能够将用户的自然语言查询转换为 SQL 语句并执行，同时支持数据可视化和智能分析。

### 核心特性
- 🤖 **多Agent协作**: 使用原生 LangGraph Supervisor 模式协调6个专业 Agent
- 🔄 **智能路由**: 双模式路由（状态机+LLM智能决策），自动识别查询类型
- 🛡️ **错误恢复**: 完善的错误处理和自动恢复机制（专门的ErrorRecoveryAgent）
- 📊 **数据可视化**: 自动生成适合的图表展示数据（规则引擎+LLM辅助）
- 🎯 **职责分离**: 6个专业Agent职责清晰（Schema、SQL生成、执行、数据分析、图表、错误恢复）
- 🚀 **三级缓存**: Thread历史 → 精确匹配 → 语义匹配
- 💬 **澄清机制**: 使用 interrupt() 实现人机交互
- ⚡ **快速模式**: 简单查询自动跳过样本检索和图表生成

### 技术栈
- **框架**: LangGraph (状态图编排) - 原生实现，不依赖第三方supervisor库
- **LLM**: 支持多种大语言模型 (通过配置切换)
- **数据库**: 支持 MySQL, PostgreSQL, SQLite 等
- **可视化**: Recharts图表库（规则推断+LLM辅助）
- **向量存储**: Milvus (语义缓存和样本检索)

---

## 核心架构

### 整体架构图

```
┌────────────────────────────── 用户交互层 ──────────────────────────────┐
│  Chat UI  ←→  API Server (FastAPI + LangGraph Server)                │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────── 主图层 ──────────────────────────────────┐
│  IntelligentSQLGraph (chat_graph.py)                                 │
│  - 意图路由 (data_query vs general_chat)                              │
│  - 三级缓存 (Thread → 精确 → 语义)                                     │
│  - 澄清机制 (interrupt 人机交互)                                       │
│  - 快速模式检测                                                        │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────── 协调层 ──────────────────────────────────┐
│  SupervisorAgent (supervisor_agent.py)  - 原生LangGraph实现           │
│  - 双模式路由：状态机路由 (快速) + LLM智能路由 (复杂场景)               │
│  - 死循环检测 (防止同一阶段重复失败)                                    │
│  - 智能错误恢复决策                                                    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────── 执行层 (Worker Agents) ─────────────────┐
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  1. SchemaAgent          - 数据库模式分析 (ReAct + 异步并行)    │ │
│  │  2. SQLGeneratorAgent    - SQL生成 (ReAct + 样本检索)          │ │
│  │  3. SQLExecutorAgent     - SQL执行 (ToolNode + 缓存)           │ │
│  │  4. DataAnalystAgent     - 数据分析洞察 (纯LLM)                │ │
│  │  5. ChartGeneratorAgent  - 图表配置生成 (规则+LLM)             │ │
│  │  6. ErrorRecoveryAgent   - 错误恢复 (ReAct + 策略)             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────── 服务层 ──────────────────────────────────┐
│  - DBService: 数据库连接管理、查询执行                                 │
│  - SchemaService: 表结构检索、值映射管理                               │
│  - HybridRetrievalService: 混合检索 (语义+关键词)                      │
│  - QueryCacheService: 查询缓存 (精确匹配)                             │
│  - MessageHistoryService: 消息历史管理                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 架构层次

#### 1. 主图层 (`chat_graph.py`)
- **IntelligentSQLGraph**: 系统的高级接口类
- **全局图实例管理**: 单例模式管理图实例
- **核心节点**:
  - `intent_router`: 意图路由（闲聊 vs 数据查询）
  - `load_custom_agent`: 提取连接ID和自定义Agent
  - `fast_mode_detect`: 快速模式检测
  - `thread_history_check`: Thread历史缓存（L0）
  - `cache_check`: 双层缓存检查（L1+L2）
  - `clarification`: 澄清机制（使用interrupt）
  - `supervisor`: Supervisor子图
  - `question_recommendation`: 问题推荐

#### 2. 协调层 (`supervisor_agent.py`)
- **SupervisorAgent**: 原生LangGraph实现（不使用第三方库）
- **双模式路由**:
  - `route_by_stage()`: 状态机路由（快速，无LLM调用）
  - `route_with_llm()`: LLM智能路由（复杂场景）
- **死循环检测**: 防止同一阶段重复失败
- **智能错误恢复**: 传递错误上下文给重试阶段

#### 3. 执行层 (各个 Worker Agents)
- **专业化分工**: 6个Agent各司其职
- **工具调用**: 混合模式（ReAct Agent + ToolNode直接调用）
- **状态更新**: 通过返回字典更新共享状态

#### 4. 服务层 (`services/`)
- **数据库服务**: 连接管理、查询执行
- **Schema服务**: 表结构检索、值映射
- **混合检索服务**: 语义+结构化检索（Milvus+关键词）
- **缓存服务**: 查询缓存、消息历史管理

### 架构特点

1. **分层清晰**: 四层架构，职责明确
2. **松耦合**: Agent之间通过共享状态通信，不直接依赖
3. **可扩展**: 易于添加新的Agent或修改现有Agent
4. **高性能**: 三级缓存、异步并行、快速模式
5. **智能化**: LLM辅助路由决策、错误恢复、数据分析
6. **标准化**: 遵循LangGraph官方最佳实践

---

## 工作流程

### 标准查询流程

```
1. 用户输入查询
   ↓
2. [Load Custom Agent] - 检查是否需要加载自定义分析专家 + 提取connection_id
   ↓
3. [Fast Mode Detect] - 检测查询复杂度，决定是否启用快速模式 (2026-01-21 新增)
   │  ├─ 简单查询 → 设置 skip_sample_retrieval=True, skip_chart_generation=True
   │  └─ 复杂查询 → 使用完整模式
   ↓
4. [Clarification] - 检测查询模糊性
   │  ├─ 明确查询 → 继续
   │  └─ 模糊查询 → 使用 interrupt() 暂停，等待用户澄清回复
   ↓
5. [Cache Check] - 双层缓存检查 (2026-01-19 新增)
   │  ├─ L1 精确匹配缓存命中 → 返回SQL+结果，结束
   │  ├─ L2 语义匹配缓存命中 → 直接执行缓存的SQL并返回
   │  └─ 缓存未命中 → 继续到Supervisor
   ↓
6. [Supervisor] - 协调Worker Agents
   ↓
7. [Schema Agent] - 分析查询意图，获取相关表结构
   │  ├─ analyze_user_query: 提取关键实体和意图
   │  └─ retrieve_database_schema: 获取表结构和值映射
   ↓
8. [SQL Generator Agent] - 生成SQL语句 (内置样本检索)
   │  ├─ generate_sql_query: 自动检索样本并生成SQL
   │  └─ generate_sql_with_samples: 基于样本生成(如果有)
   │  注: explain_sql_query 已移除以提升速度
   ↓
9. [SQL Executor Agent] - 执行SQL
   │  └─ execute_sql_query: 直接执行(带缓存)
   ↓
10. [Chart Generator Agent] - 生成图表(可选，快速模式跳过)
    │  ├─ should_generate_chart: 判断是否需要图表
    │  ├─ analyze_data_for_chart: 分析数据特征
    │  └─ 调用MCP Chart工具生成图表
    ↓
11. 存储结果到缓存 → 返回结果
```

### 错误处理流程

```
任何阶段出错
   ↓
[Error Recovery Agent]
   ├─ analyze_error_pattern: 分析错误模式
   ├─ generate_recovery_strategy: 制定恢复策略
   └─ auto_fix_sql_error: 尝试自动修复
   ↓
判断是否可恢复
   ├─ 是 → 返回对应阶段重试
   └─ 否 → 返回错误信息给用户
```

---

## 核心组件详解

### 1. IntelligentSQLGraph (chat_graph.py)

**职责**: 系统的高级接口和入口点

**图结构** (2026-01-21 优化):
```
START → load_custom_agent → fast_mode_detect → clarification → cache_check → [supervisor | END]
```

**核心节点**:
1. `load_custom_agent`: 提取 connection_id/agent_id，加载自定义Agent
2. `fast_mode_detect`: 检测查询复杂度，决定是否启用快速模式
3. `clarification`: 使用 interrupt() 实现人机交互澄清
4. `cache_check`: 双层缓存检查 (L1精确 + L2语义)
5. `supervisor`: 协调 Worker Agents 完成任务

**核心方法**:
```python
# 创建图实例
def __init__(self, active_agent_profiles=None, custom_analyst=None)

# 加载自定义Agent + 提取connection_id
async def _load_custom_agent_node(self, state)

# 快速模式检测 (2026-01-21 新增)
async def _fast_mode_detect_node(self, state)

# Supervisor节点包装
async def _supervisor_node(self, state)

# 存储结果到缓存 (2026-01-19 新增)
async def _store_result_to_cache(self, original_state, result)

# 处理查询的便捷方法
async def process_query(self, query, connection_id, thread_id=None)
```

**关键特性**:
- 支持动态加载自定义分析专家
- 从消息中提取 connection_id 和 agent_id
- 提供全局单例访问
- 支持快速模式自动检测
- 集成 Checkpointer 支持多轮对话

### 2. SupervisorAgent (supervisor_agent.py)

**职责**: 协调所有 Worker Agents，智能路由决策

**核心配置**:
```python
# Worker Agents列表
worker_agents = [
    schema_agent,
    # sample_retrieval_agent,  # 已禁用，功能集成到sql_generator
    sql_generator_agent,
    sql_executor_agent,
    error_recovery_agent,
    chart_generator_agent  # 或自定义分析专家
]

# Supervisor配置 (2026-01-21 更新)
create_supervisor(
    model=llm,
    agents=worker_agents,
    prompt=supervisor_prompt,
    add_handoff_back_messages=False,  # ✅ 修复消息重复
    output_mode="last_message"        # ✅ 只返回最后消息
)
```

**路由策略**:
- 根据 `current_stage` 字段决定下一个Agent
- 标准流程: schema → sql_generation → sql_execution → [chart_generation] → completed
- 快速模式: schema → sql_generation → sql_execution → completed (跳过图表)
- 错误流程: 任何阶段 → error_recovery → 重试或终止

**重要说明**:
- SQL Validator Agent 已被移除(2026-01-16)
- Sample Retrieval Agent 已临时禁用(2026-01-19)，功能集成到 sql_generator_agent
- 原因: 简化流程，避免 ReAct agent 调度延迟（原 2+ 分钟）
- 备份位置: `backend/backups/agents_backup_20260116_175357`

### 3. Agent Factory (agent_factory.py)

**职责**: 动态创建自定义Agent实例

**核心功能**:
```python
def create_custom_analyst_agent(profile, db):
    """
    根据AgentProfile创建自定义分析专家
    - 获取自定义LLM配置
    - 应用自定义提示词
    - 返回ChartGeneratorAgent实例
    """
```

**使用场景**:
- 用户创建自定义分析专家
- 需要特定领域的数据分析能力
- 替换默认的图表生成Agent

---

## 状态管理

### SQLMessageState (state.py)

这是整个系统的核心状态对象，所有Agent共享此状态。

**核心字段分类**:

#### 1. 基础信息
```python
connection_id: Optional[int] = None  # 数据库连接ID (由用户选择动态传入)
agent_id: Optional[int] = None       # 自定义Agent ID
thread_id: Optional[str] = None      # 会话线程ID
user_id: Optional[str] = None        # 用户ID
```

#### 2. 查询处理
```python
query_analysis: Dict              # 查询分析结果
schema_info: SchemaInfo          # 数据库模式信息
generated_sql: str               # 生成的SQL
execution_result: SQLExecutionResult  # 执行结果
```

#### 3. 流程控制
```python
current_stage: Literal[...]      # 当前处理阶段
retry_count: int = 0             # 重试计数
max_retries: int = 3             # 最大重试次数
route_decision: Literal[...]     # 路由决策
```

#### 4. 错误处理
```python
error_history: List[Dict]        # 错误历史
```

#### 5. 可视化
```python
chart_config: Dict               # 图表配置
analysis_result: Dict            # 分析结果
```

#### 6. Agent通信
```python
agent_messages: Dict[str, Any]   # Agent间消息
messages: List[BaseMessage]      # LangChain消息历史
```

#### 7. 缓存相关 (2026-01-19 新增)
```python
cache_hit: bool = False                          # 是否命中缓存
cache_hit_type: Optional[Literal["exact", "semantic", "exact_text"]] = None  # 命中类型
```

#### 8. 快速模式相关 (2026-01-21 新增)
```python
fast_mode: bool = False              # 是否启用快速模式
skip_sample_retrieval: bool = False  # 是否跳过样本检索
skip_chart_generation: bool = False  # 是否跳过图表生成
enable_query_checker: bool = True    # 是否启用SQL检查
sql_check_passed: bool = False       # SQL检查是否通过
```

#### 9. 澄清机制相关
```python
clarification_history: List[Dict]        # 澄清历史
clarification_round: int = 0             # 澄清轮次
needs_clarification: bool = False        # 是否需要澄清
pending_clarification: bool = False      # 是否等待用户澄清回复
original_query: Optional[str] = None     # 原始查询
enriched_query: Optional[str] = None     # 增强后的查询
```

### 状态流转

```
初始状态
  current_stage = "clarification"
  retry_count = 0
  fast_mode = False (待检测)
  ↓
快速模式检测完成
  fast_mode = True/False
  skip_sample_retrieval = True/False
  skip_chart_generation = True/False
  ↓
澄清检查完成 (或 interrupt() 等待用户回复)
  current_stage = "cache_check"
  ↓
缓存检查
  ├─ 命中 → current_stage = "completed", cache_hit = True
  └─ 未命中 → current_stage = "schema_analysis"
  ↓
Schema分析完成
  current_stage = "sql_generation"
  schema_info = {...}
  ↓
SQL生成完成
  current_stage = "sql_execution"
  generated_sql = "SELECT ..."
  ↓
SQL执行完成
  current_stage = "completed" 或 "chart_generation"
  execution_result = {...}
  ↓
(可选，快速模式跳过)图表生成完成
  current_stage = "completed"
  chart_config = {...}
```

---

## Agent详解

### 1. Schema Agent (schema_agent.py)

**职责**: 分析用户查询,获取相关数据库模式信息

**实现方式**: ReAct Agent + InjectedState 工具

**工具列表**:
1. `analyze_user_query`: 使用LLM分析查询意图,提取关键实体
2. `retrieve_database_schema`: 从数据库检索相关表结构和值映射（异步并行优化）

**工作流程**:
```python
1. 接收用户查询
2. 调用 analyze_user_query 分析意图
   - 提取实体(表名、字段名)
   - 识别查询类型(聚合、过滤、排序等)
   - 理解查询上下文和业务含义
3. 调用 retrieve_database_schema 获取模式
   - 使用混合检索(语义+关键词)
   - 异步并行获取表和列信息
   - 获取表结构、关系、值映射
4. 发送流式事件 (schema_mapping)
5. 返回完整的schema_info到状态
```

**关键技术与优化**:

#### 异步并行优化 (性能关键)
```python
# 使用 retrieve_relevant_schema_async 异步并行获取
async def retrieve_relevant_schema_async(
    query_analysis: Dict[str, Any],
    connection_id: int,
    top_k: int = 10
) -> Dict[str, Any]:
    # 并行获取表和列信息
    async with asyncio.TaskGroup() as tg:
        table_task = tg.create_task(fetch_tables(...))
        column_task = tg.create_task(fetch_columns(...))
    
    # 性能提升: 20s → 8-12s
```

#### 混合检索策略
- **语义检索**: 使用向量相似度匹配表名和列名
- **关键词检索**: 补充精确匹配结果
- **值映射**: 自动映射自然语言到数据库实际值

#### 流式事件输出
```python
# 发送 schema_mapping 事件，实时反馈给前端
StreamWriter.write_event({
    "event_type": "schema_mapping",
    "data": {
        "tables": [...],
        "columns": [...]
    }
})
```

**输出示例**:
```python
{
    "schema_info": {
        "tables": ["products", "orders"],
        "columns": {
            "products": ["id", "name", "category", "price"],
            "orders": ["id", "product_id", "quantity"]
        },
        "relationships": [...],
        "value_mappings": {
            "category": {
                "手机": "mobile_phone",
                "电脑": "computer"
            }
        }
    }
}
```

### 2. SQL Generator Agent (sql_generator_agent.py)

**职责**: 根据模式信息生成高质量SQL语句

**实现方式**: ReAct Agent + 结构化输出 (with_structured_output)

**工具列表**:
1. `generate_sql_query`: 基础SQL生成（内置自动样本检索）
2. `generate_sql_with_samples`: 基于历史样本生成(更高质量)
3. ~~`explain_sql_query`~~: 已移除以提升速度 (2026-01-18)

**工作流程**:
```python
1. 接收用户查询和schema信息
2. 自动检索相关样本（除非快速模式跳过）
   - 使用 HybridRetrievalEnginePool.quick_retrieve()
   - 配置项: QA_SAMPLE_ENABLED, QA_SAMPLE_TOP_K, QA_SAMPLE_MIN_SIMILARITY
   - 快速模式: skip_sample_retrieval=True 时跳过
3. 选择生成策略:
   - 有高质量样本 → generate_sql_with_samples
   - 无样本或快速模式 → generate_sql_query
   - 缓存命中时: 基于cached_sql_template生成
4. 生成SQL并清理格式
   - 移除markdown代码块标记
   - 移除多余空白
   - 动态检测数据库类型(MySQL/PostgreSQL/SQLite)
5. 使用 with_structured_output 确保输出一致性
```

**生成策略**:
- **基础生成**: 直接根据schema和查询生成
- **样本增强**: 参考历史成功案例,提高质量和准确度
- **模板生成**: 基于语义缓存命中的SQL模板生成
- **错误恢复**: 接收error_recovery_context,包含失败SQL和修复建议

**约束条件**: 
- 确保语法正确(因为不再有验证步骤)
- 添加LIMIT限制(防止返回过多数据)
- 使用正确的值映射(自然语言→数据库值)
- 避免危险操作(DROP, DELETE, TRUNCATE等)
- 动态适配数据库类型差异

**关键优化**:

#### 内置样本检索 (2026-01-19)
```python
# 避免独立ReAct Agent调度延迟(原2+分钟)
samples = await HybridRetrievalEnginePool.quick_retrieve(
    query=state["enriched_query"],
    connection_id=state["connection_id"],
    collection_name="qa_samples",
    top_k=QA_SAMPLE_TOP_K
)

# 快速降级: 检索失败不影响主流程
if samples:
    use_generate_sql_with_samples()
else:
    use_generate_sql_query()
```

#### 快速模式支持 (2026-01-21)
```python
# 简单查询跳过样本检索,直接生成
if state.get("skip_sample_retrieval", False):
    return generate_sql_query(...)
```

#### 错误上下文传递
```python
# 错误恢复时提供上下文
if state.get("error_recovery_context"):
    context = state["error_recovery_context"]
    # 包含: failed_sql, error_message, fix_suggestions
    # 帮助LLM生成修复后的SQL
```

#### 动态数据库类型检测
```python
# 根据connection_id获取数据库类型
db_type = detect_database_type(connection_id)
# 适配不同数据库的语法差异
```

**QA样本检索配置**:
```python
QA_SAMPLE_ENABLED = True           # 是否启用样本召回
QA_SAMPLE_TOP_K = 3                # 检索数量
QA_SAMPLE_MIN_SIMILARITY = 0.6     # 最低相似度
QA_SAMPLE_TIMEOUT = 10             # 超时时间(秒)
QA_SAMPLE_FAST_FALLBACK = True     # 失败时快速降级
```

**重要变更历史**:
- ✅ 简化流程: SQL生成后直接执行,不再验证 (2026-01-16)
- ✅ 样本检索集成: 集成到此Agent内部,避免调度延迟 (2026-01-19)
- ✅ 移除explain: 移除explain_sql_query工具以提升速度 (2026-01-18)
- ✅ 快速模式: 支持跳过样本检索 (2026-01-21)

**输出示例**:
```python
{
    "generated_sql": "SELECT brand FROM products WHERE category='手机' ORDER BY sales DESC LIMIT 1",
    "explanation": "查询手机类别中销量最高的品牌",
    "samples_used": 2,
    "best_sample_score": 0.85,
    "database_type": "mysql"
}
```

### 3. SQL Executor Agent (sql_executor_agent.py)

**职责**: 安全执行SQL查询并返回结果

**实现方式**: ToolNode 直接调用（不使用ReAct模式）

**工具列表**:
1. `execute_sql_query`: 执行SQL(带缓存机制)

**核心特性**:

#### 直接工具调用（关键优化）
```python
# 不使用ReAct模式,避免LLM重复调用工具
# 原问题: execute_sql_query被重复调用4次
# 解决方案: 直接调用工具,从4次降到1次

# 方式1: 使用ToolNode包装
executor_node = ToolNode([execute_sql_query])

# 方式2: 创建兼容ReAct接口的Agent
# 但内部直接调用工具,不经过LLM推理
```

#### 缓存机制（防止重复执行）
```python
_execution_cache = {}  # 缓存执行结果
_cache_timestamps = {}  # 缓存时间戳
_cache_lock = {}        # 并发执行锁

def execute_sql_query(sql_query, connection_id):
    # 生成缓存键
    cache_key = f"{connection_id}:{hash(sql_query)}"
    
    # 检查缓存
    if cache_key in _execution_cache:
        if time.time() - _cache_timestamps[cache_key] < 300:
            return _execution_cache[cache_key]
    
    # 检查执行锁(防止并发重复)
    if cache_key in _cache_lock:
        # 等待正在执行的查询完成
        return wait_for_completion(cache_key)
    
    # 加锁执行
    _cache_lock[cache_key] = True
    try:
        result = execute_query(...)
        _execution_cache[cache_key] = result
        _cache_timestamps[cache_key] = time.time()
        return result
    finally:
        del _cache_lock[cache_key]

# 缓存策略:
# - 只缓存查询操作(SELECT)
# - 缓存有效期: 5分钟
# - 最大缓存数: 100条
# - 自动清理旧缓存
```

#### 并发控制（防止并发重复执行）
```python
# 使用执行锁防止相同SQL并发执行
_cache_lock = {}

if cache_key in _cache_lock:
    # 等待正在执行的查询完成
    while cache_key in _cache_lock:
        await asyncio.sleep(0.1)
    # 返回已缓存的结果
    return _execution_cache[cache_key]
```

#### 流式事件输出
```python
# 发送 data_query 事件,实时返回数据给前端
StreamWriter.write_event({
    "event_type": "data_query",
    "data": {
        "columns": [...],
        "rows": [...],
        "row_count": 100
    }
})
```

**执行流程**:
```python
1. 检查缓存
   - 命中 → 直接返回(from_cache=True)
   - 未命中 → 继续
2. 检查执行锁
   - 正在执行 → 等待完成,返回结果
   - 未执行 → 加锁继续
3. 获取数据库连接
   - 使用 DBService 获取连接
   - 支持连接池管理
4. 执行SQL查询
   - 超时控制(默认30秒)
   - 错误捕获和分类
5. 格式化结果
   - 列名列表
   - 数据行列表
   - 行数统计
6. 发送流式事件
7. 缓存结果(如果是查询)
8. 释放锁,返回结果
```

**安全特性**:
- SQL注入防护（参数化查询）
- 超时控制（防止长时间查询）
- 错误分类（语法/连接/权限/超时）
- 只读检查（可选，防止修改操作）

**性能优化效果**:
- ✅ 工具调用: 从4次降到1次（减少75%）
- ✅ 缓存命中: 相同查询0ms返回
- ✅ 并发控制: 防止重复执行

**输出示例**:
```python
{
    "success": True,
    "data": {
        "columns": ["brand", "sales"],
        "data": [["Apple", 1000], ["Samsung", 800]],
        "row_count": 2
    },
    "execution_time": 0.05,
    "from_cache": False,
    "connection_id": 1
}
```

### 4. Data Analyst Agent (data_analyst_agent.py)

**职责**: 分析查询结果,生成数据洞察和业务建议

**实现方式**: 纯LLM分析（无工具调用）

**新增时间**: 2026-01-23（职责分离优化）

**核心功能**:
1. **直接回答用户问题**: 基于查询结果给出明确答案
2. **数据洞察生成**: 提取2-3个关键数据洞察
3. **业务建议**: 提供1-2条可行的业务建议

**工作流程**:
```python
1. 接收查询结果和用户问题
2. 使用LLM分析数据
   - 理解用户意图
   - 分析数据模式和趋势
   - 提取关键信息
3. 生成结构化输出
   - direct_answer: 直接回答
   - key_insights: 关键洞察列表
   - business_suggestions: 业务建议列表
4. 返回分析结果到状态
```

**职责分离背景**:
- **分离前**: ChartGeneratorAgent同时负责数据分析和图表生成
- **分离后**: 
  - DataAnalystAgent: 专注数据分析和文本洞察
  - ChartGeneratorAgent: 专注图表配置生成
- **优势**: 职责更清晰,各自优化更容易

**输出示例**:
```python
{
    "analyst_insights": {
        "direct_answer": "2024年手机类别销量最高的品牌是Apple,销量达到1000台",
        "key_insights": [
            "Apple品牌占手机类别总销量的45%,市场占有率领先",
            "相比去年同期,Apple销量增长了20%",
            "前三品牌(Apple/Samsung/Huawei)占据80%市场份额"
        ],
        "business_suggestions": [
            "建议加大Apple产品的库存和营销投入",
            "可考虑与Apple合作推出独家优惠活动"
        ]
    }
}
```

### 5. Chart Generator Agent (chart_generator_agent.py)

**职责**: 根据查询结果生成数据可视化图表配置

**实现方式**: 规则引擎优先 + LLM辅助

**工具来源**:
- **本地工具**: `should_generate_chart`, `analyze_data_for_chart`, `generate_chart_config`
- **MCP工具**: 通过 `@antv/mcp-server-chart` 提供的图表生成工具

**工作流程**:
```python
1. 判断是否需要生成图表
   - 检查用户意图(关键词: 图表/趋势/对比)
   - 检查数据特征(数值列、行数)
   - 数据量检查(2-1000行)
   - 快速模式检查(skip_chart_generation=True时跳过)
2. 分析数据特征
   - 识别数值列、文本列、日期列
   - 分析数据分布和范围
   - 计算基本统计信息
3. 规则引擎推荐图表类型
   - 趋势分析 → 折线图(line)
   - 比较分析 → 柱状图(bar)
   - 占比分析 → 饼图(pie)
   - 相关性分析 → 散点图(scatter)
4. 调用MCP工具生成图表
   - 传递数据和推荐配置
   - LLM生成最终图表配置
5. 返回Recharts兼容配置
```

**图表类型推荐逻辑**:

#### 基于查询关键词
```python
keywords_chart_map = {
    "趋势": "line",
    "时间": "line", 
    "变化": "line",
    "比较": "bar",
    "排名": "bar",
    "对比": "bar",
    "占比": "pie",
    "分布": "pie",
    "百分比": "pie"
}
```

#### 基于数据特征
```python
# 2列(1文本+1数值) + 少量行(≤10) → pie chart
if num_columns == 2 and numeric_columns == 1 and row_count <= 10:
    return "pie"

# 2列(1文本+1数值) + 较多行 → bar chart
if num_columns == 2 and numeric_columns == 1:
    return "bar"

# 多个数值列 → scatter plot
if numeric_columns >= 2:
    return "scatter"

# 包含日期列 → line chart
if has_date_column:
    return "line"
```

**自定义支持**:
```python
def __init__(self, custom_prompt=None, llm=None):
    """
    支持自定义提示词和LLM
    用于创建特定领域的分析专家
    例如: 金融分析专家、销售分析专家等
    """
```

**快速模式支持**:
```python
# 简单查询自动跳过图表生成
if state.get("skip_chart_generation", False):
    return {"chart_config": None}
```

**职责变更** (2026-01-23):
- **之前**: 同时负责数据分析和图表生成
- **现在**: 专注图表配置生成,数据分析由DataAnalystAgent负责

**输出示例**:
```python
{
    "chart_config": {
        "type": "bar",
        "data": [
            {"brand": "Apple", "sales": 1000},
            {"brand": "Samsung", "sales": 800}
        ],
        "xField": "brand",
        "yField": "sales",
        "title": "品牌销量对比",
        "color": "#5B8FF9",
        "label": {
            "position": "top"
        }
    }
}
```

### 6. Error Recovery Agent (error_recovery_agent.py)

**职责**: 错误分析、恢复策略生成、自动修复SQL

**实现方式**: ReAct Agent + 工具

**工具列表**:
1. `analyze_error_pattern`: 分析错误模式和根因
2. `generate_recovery_strategy`: 生成恢复策略
3. `auto_fix_sql_error`: 自动修复SQL错误

**错误分类体系**:
```python
error_types = {
    "syntax_error": {
        "description": "SQL语法错误",
        "auto_fixable": True,
        "confidence": 0.8,
        "examples": ["未闭合引号", "缺少分号", "关键字拼写错误"]
    },
    "subquery_error": {
        "description": "子查询错误", 
        "auto_fixable": True,
        "confidence": 0.7,
        "examples": ["子查询返回多行", "子查询列数不匹配"]
    },
    "connection_error": {
        "description": "数据库连接错误",
        "auto_fixable": False,
        "confidence": 0.6,
        "examples": ["连接超时", "认证失败", "网络不可达"]
    },
    "permission_error": {
        "description": "权限不足",
        "auto_fixable": False,
        "confidence": 0.7,
        "examples": ["SELECT权限不足", "访问被拒绝"]
    },
    "timeout_error": {
        "description": "查询超时",
        "auto_fixable": True,
        "confidence": 0.6,
        "examples": ["执行时间过长", "锁等待超时"]
    },
    "unknown_error": {
        "description": "未知错误",
        "auto_fixable": False,
        "confidence": 0.3
    }
}
```

**恢复策略生成**:
```python
strategies = {
    "syntax_error": {
        "primary_action": "regenerate_sql_with_constraints",
        "fallback_action": "simplify_query",
        "retry_stage": "sql_generation",
        "context_to_pass": {
            "failed_sql": "...",
            "error_message": "...",
            "fix_suggestions": [
                "检查引号是否闭合",
                "确认关键字拼写"
            ]
        }
    },
    "subquery_error": {
        "primary_action": "fix_subquery_logic",
        "fallback_action": "convert_to_join",
        "retry_stage": "sql_generation"
    },
    "timeout_error": {
        "primary_action": "optimize_query_performance",
        "fallback_action": "add_limit_clause",
        "retry_stage": "sql_generation",
        "fix_suggestions": [
            "添加 LIMIT 子句限制结果集",
            "优化 JOIN 顺序",
            "添加索引提示"
        ]
    },
    "connection_error": {
        "primary_action": "check_database_connection",
        "fallback_action": "notify_user",
        "retry_stage": None  # 不可自动恢复
    }
}
```

**自动修复能力**:

#### SQL语法错误修复
```python
# 1. 未闭合引号
"SELECT * FROM users WHERE name='John" 
→ "SELECT * FROM users WHERE name='John'"

# 2. 关键字大小写
"select * form users" 
→ "SELECT * FROM users"

# 3. 缺少分号
"SELECT * FROM users"
→ "SELECT * FROM users;"
```

#### 性能问题修复
```python
# 1. 添加LIMIT子句
"SELECT * FROM large_table"
→ "SELECT * FROM large_table LIMIT 1000"

# 2. 优化JOIN顺序
# 小表在前，大表在后
```

#### 子查询错误修复 (2026-01改进)
```python
# 1. 多行子查询改用IN
"SELECT * FROM users WHERE id = (SELECT id FROM orders)"
→ "SELECT * FROM users WHERE id IN (SELECT id FROM orders)"

# 2. 子查询改JOIN
"SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
→ "SELECT u.* FROM users u INNER JOIN orders o ON u.id = o.user_id"
```

**工作流程**:
```python
1. 接收错误信息
   - 错误类型
   - 错误消息
   - 失败的SQL
   - 当前阶段
2. 分析错误模式
   - 提取关键词匹配错误类型
   - 分析错误历史，识别重复模式
   - 评估错误严重程度
3. 制定恢复策略
   - 选择主要动作和备选动作
   - 评估自动修复成功率
   - 生成修复建议列表
4. 尝试自动修复
   - 应用修复规则
   - 验证修复结果
   - 生成error_recovery_context
5. 决定下一步
   - 修复成功 → 重试对应阶段
   - 修复失败 → 人工干预
   - 达到重试上限 → 终止并返回友好错误
```

**错误上下文传递**:
```python
# 传递给重试阶段的上下文
error_recovery_context = {
    "failed_sql": "SELECT * FROM users WHERE id = (SELECT...)",
    "error_type": "subquery_error",
    "error_message": "Subquery returns more than 1 row",
    "fix_suggestions": [
        "将 = 改为 IN 或 EXISTS",
        "在子查询中添加 LIMIT 1",
        "考虑改用 JOIN"
    ],
    "retry_count": 1,
    "max_retries": 3
}
```

**用户友好消息映射**:
```python
# 将技术错误转换为用户友好消息
error_messages = {
    "syntax_error": "SQL语法有误，正在自动修复...",
    "connection_error": "数据库连接失败，请检查数据库状态",
    "permission_error": "权限不足，请联系管理员授权",
    "timeout_error": "查询超时，正在优化查询...",
    "subquery_error": "子查询逻辑有误，正在修正..."
}
```

**关键改进** (2026-01):
- ✅ 新增子查询错误分类和修复
- ✅ 改进错误模式识别算法
- ✅ 增强上下文传递，包含修复建议
- ✅ 支持多轮重试策略

**输出示例**:
```python
{
    "error_analysis": {
        "error_type": "syntax_error",
        "root_cause": "未闭合的引号",
        "auto_fixable": True,
        "confidence": 0.8
    },
    "recovery_strategy": {
        "primary_action": "regenerate_sql_with_constraints",
        "retry_stage": "sql_generation",
        "max_retries": 3
    },
    "error_recovery_context": {
        "failed_sql": "...",
        "fix_suggestions": ["..."],
        "retry_count": 1
    },
    "user_message": "SQL语法有误，正在自动修复..."
}
```

---

## 与LangGraph官方模式对比

### 核心架构对比

| 维度 | 我们的实现 | LangGraph 官方推荐 | 对比说明 |
|------|-----------|-------------------|---------|
| **Supervisor 模式** | 自定义原生实现，使用类封装 | 通常使用条件边函数 | 我们使用更结构化的类实现，易于维护和扩展 |
| **路由方式** | 双模式：状态机路由 + LLM智能路由 | 主要基于消息的条件函数 | 我们混合使用规则路由和LLM路由，兼顾性能和灵活性 |
| **工具调用** | 混合：ReAct Agent + ToolNode直接调用 | 推荐 ToolNode 直接调用 | 我们根据场景选择，简单任务用ToolNode，复杂任务用ReAct |
| **消息管理** | 手动去重 + 自动修剪 | add_messages reducer | 我们手动控制更精细，官方reducer更简洁 |
| **错误处理** | 专门的 ErrorRecoveryAgent | 通常在条件边中处理 | 我们用独立Agent处理错误，职责更清晰 |
| **状态持久化** | AsyncPostgresSaver (Checkpointer) | MemorySaver / AsyncPostgresSaver | 相同，使用官方Checkpointer |
| **人机交互** | interrupt() 实现澄清机制 | interrupt() / Command 模式 | 相同，使用官方interrupt机制 |
| **流式输出** | StreamWriter 自定义事件 | .stream() / .astream() | 我们扩展了流式事件类型 |

### 我们的优势

#### 1. 更强的智能决策能力
- LLM辅助路由可处理复杂错误场景
- 根据历史和上下文做出决策
- 死循环检测防止无限重试

#### 2. 完善的错误恢复机制
- 专门的ErrorRecoveryAgent负责错误处理
- 自动修复常见错误
- 错误上下文传递给重试阶段
- 多轮智能重试策略

#### 3. 丰富的前置处理
- 意图路由（闲聊 vs 数据查询）
- 三级缓存（Thread → 精确 → 语义）
- 澄清机制（interrupt人机交互）
- 快速模式自动检测

#### 4. 性能优化到位
- 异步并行（Schema获取 20s → 8-12s）
- 三级缓存策略
- 快速模式（简单查询提升30-50%）
- 工具缓存（防止重复执行）
- Agent缓存（复用实例）

#### 5. 职责分离清晰
- 6个专业Agent各司其职
- 数据分析和图表生成分离（2026-01-23）
- 易于维护和扩展

### 可改进之处

#### 1. 消息管理
**当前**: 手动去重和修剪
```python
# 手动控制消息
state["messages"] = validate_and_fix_message_history(state["messages"])
state["messages"] = trim_messages(state["messages"], max_length=50)
```

**可改进**: 使用 `add_messages` reducer
```python
from langgraph.graph import add_messages

class SQLMessageState(AgentState):
    messages: Annotated[List[BaseMessage], add_messages]
    # 自动合并和去重
```

#### 2. ToolNode 应用
**当前**: 部分Agent使用ReAct但可能不需要推理

**可改进**: 更多简单Agent改用ToolNode
- SQLExecutorAgent ✅ 已使用ToolNode
- 部分简单工具可直接调用

#### 3. 条件边简化
**当前**: 复杂的路由类方法

**可改进**: 简单判断可内联到条件函数
```python
# 简单场景可以简化
graph.add_conditional_edges(
    "node",
    lambda state: "next" if state["ready"] else "wait"
)
```

---

## 优化历史

### 1. SQL Validator移除 (2026-01-16)

**背景**:
- 原流程: Schema → SQL生成 → SQL验证 → SQL执行
- 问题: 验证步骤增加延迟，且大多数SQL本身就是正确的

**改进**:
- 移除SQL Validator Agent
- SQL生成后直接执行
- 在生成阶段就确保质量

**效果**:
- LLM调用减少1-2次
- 响应时间提升30-50%
- 简化了流程复杂度

**备份位置**: `backend/backups/agents_backup_20260116_175357`

### 1.5 Sample Retrieval Agent 集成 (2026-01-19)

**背景**:
- 原 sample_retrieval_agent 作为独立 ReAct agent 存在调度延迟问题（2+ 分钟）

**改进**:
- 临时禁用独立的 sample_retrieval_agent
- 将样本检索功能集成到 sql_generator_agent 内部
- 先快速检查是否有样本，没有则跳过检索步骤

**效果**:
- 消除了 2+ 分钟的调度延迟
- 样本检索仍可用，但更高效

### 1.6 快速模式 (Fast Mode) 新增 (2026-01-21)

**背景**:
- 借鉴官方 LangGraph SQL Agent 的简洁性思想
- 简单查询不需要完整的流程

**改进**:
- 添加 fast_mode_detect 节点
- 简单查询自动跳过样本检索和图表生成
- 配置化控制各项功能的开关

**效果**:
- 简单查询响应时间减少 30-50%
- 复杂查询保持完整功能

### 1.7 Supervisor 配置优化 (2026-01-21)

**背景**:
- 消息重复问题导致上下文过长

**改进**:
- `add_handoff_back_messages=False`: 不添加 handoff 消息
- `output_mode="last_message"`: 只返回最后的总结消息

**效果**:
- 消除消息重复
- 减少上下文长度

### 2. SQL Executor优化

**问题**: execute_sql_query工具被重复调用4次

**原因**: ReAct模式下LLM可能多次调用工具

**解决方案**:
```python
# 方案1: 工具级缓存
_execution_cache = {}  # 缓存执行结果

# 方案2: 直接工具调用
# 不使用ReAct agent，直接调用工具
result = execute_sql_query.invoke(...)
```

**效果**:
- 工具调用从4次降到1次
- 执行时间减少75%
- 避免了重复的数据库查询

### 3. 消息历史修复

**问题**: ToolCall和ToolMessage不匹配导致错误

**解决方案**:
```python
# 在supervisor执行前后验证并修复消息历史
state["messages"] = validate_and_fix_message_history(state["messages"])
```

**修复逻辑**:
- 检测孤立的ToolCall
- 自动添加占位ToolMessage
- 确保消息对的完整性

---

## 关键技术点

### 1. LangGraph 核心模式应用

#### StateGraph - 状态图管理
```python
from langgraph.graph import StateGraph, START, END

# 创建状态图
graph = StateGraph(SQLMessageState)

# 添加节点
graph.add_node("schema_agent", schema_agent_func)
graph.add_node("sql_generator", sql_generator_func)

# 添加边
graph.add_edge(START, "schema_agent")
graph.add_edge("schema_agent", "sql_generator")
graph.add_edge("sql_generator", END)

# 编译图
compiled_graph = graph.compile(checkpointer=checkpointer)
```

#### Conditional Edges - 条件路由
```python
# 双模式路由实现
graph.add_conditional_edges(
    "supervisor",
    route_decision_func,  # 返回下一个节点名称
    {
        "schema": "schema_agent",
        "sql_generator": "sql_generator",
        "error_recovery": "error_recovery",
        "completed": END
    }
)

def route_decision_func(state):
    """路由决策函数"""
    if state.get("error_recovery_context"):
        return route_with_llm(state)  # LLM智能路由
    else:
        return route_by_stage(state)  # 状态机路由
```

#### InjectedState - 工具参数注入
```python
from langgraph.prebuilt import InjectedState
from typing import Annotated

@tool
def retrieve_database_schema(
    query_analysis: Dict[str, Any],
    state: Annotated[dict, InjectedState]  # 自动注入当前状态
) -> Dict[str, Any]:
    """从状态中获取connection_id,无需显式传递"""
    connection_id = state.get("connection_id")
    # 执行检索逻辑
    return schema_info
```

#### interrupt() - 人机交互
```python
from langgraph.types import interrupt

async def clarification_node(state):
    """澄清节点"""
    if needs_clarification(state):
        # 暂停执行,等待用户回复
        user_response = interrupt({
            "type": "clarification_needed",
            "question": "您是指哪个部门的销售数据?"
        })
        
        # 用户回复后继续执行
        state["enriched_query"] = enrich_query(
            state["original_query"],
            user_response
        )
    
    return state
```

#### Checkpointer - 状态持久化
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# 创建Checkpointer
checkpointer = AsyncPostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/dbname"
)

# 编译图时指定
graph = graph.compile(checkpointer=checkpointer)

# 支持多轮对话
result = await graph.ainvoke(
    input_data,
    config={"configurable": {"thread_id": thread_id}}
)
```

#### StreamWriter - 流式事件输出
```python
from app.utils.stream_writer import StreamWriter

# 发送自定义事件
StreamWriter.write_event({
    "event_type": "schema_mapping",
    "data": {
        "tables": ["products", "orders"],
        "status": "completed"
    }
})

StreamWriter.write_event({
    "event_type": "data_query",
    "data": {
        "columns": [...],
        "rows": [...]
    }
})
```

### 2. ReAct Agent 模式

**原理**: Reasoning + Acting（推理 + 行动）
- LLM推理决定使用哪个工具
- 执行工具获取结果
- 基于结果继续推理
- 循环直到完成任务

**创建方式**:
```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    llm,
    tools,
    state_schema=SQLMessageState,
    prompt=system_prompt,
    name=agent_name
)
```

**适用场景**:
- ✅ **SchemaAgent**: 需要灵活的工具调用顺序（先分析再检索）
- ✅ **SQLGeneratorAgent**: 需要根据情况选择生成策略（基础生成 vs 样本增强）
- ✅ **ErrorRecoveryAgent**: 需要分析错误并决定修复策略
- ✅ **ChartGeneratorAgent**: 需要多步骤的图表生成（分析 → 推荐 → 生成）

**不适用场景**:
- ❌ **SQLExecutorAgent**: 只需执行一次，直接调用更好（避免LLM重复调用）
- ❌ **DataAnalystAgent**: 纯LLM分析，无工具调用

### 3. ToolNode 直接调用

**原理**: 跳过LLM推理，直接调用工具

**创建方式**:
```python
from langgraph.prebuilt import ToolNode

# 方式1: 使用ToolNode包装
executor_node = ToolNode([execute_sql_query])

# 方式2: 创建兼容接口的Agent
def create_tool_only_agent(tool):
    """创建只调用工具的Agent"""
    async def agent_func(state):
        result = await tool.ainvoke({
            "sql_query": state["generated_sql"],
            "connection_id": state["connection_id"]
        })
        return {"execution_result": result}
    
    return agent_func
```

**适用场景**:
- ✅ **SQLExecutorAgent**: 简单的SQL执行，不需要推理
- ✅ 其他确定性操作，无需LLM决策

**优势**:
- 避免LLM重复调用工具（从4次降到1次）
- 执行速度更快
- 成本更低

### 4. 状态共享机制

**核心思想**: 所有Agent共享同一个状态对象

**优势**:
- Agent间无需显式通信
- 状态变更自动传播
- 支持复杂的工作流
- 易于追踪和调试

**实现**:
```python
from langgraph.graph import AgentState

class SQLMessageState(AgentState):
    """继承自LangGraph的AgentState,自动支持状态更新和传播"""
    
    # 基础信息
    connection_id: Optional[int]
    thread_id: Optional[str]
    
    # 流程数据
    schema_info: SchemaInfo
    generated_sql: str
    execution_result: SQLExecutionResult
    
    # 流程控制
    current_stage: Literal[...]
    retry_count: int
    
    # Agent间通信
    messages: List[BaseMessage]
```

**状态更新**:
```python
# Agent返回部分状态，自动合并
def schema_agent_func(state):
    schema_info = retrieve_schema(...)
    return {
        "schema_info": schema_info,
        "current_stage": "sql_generation"
    }
    # 其他字段保持不变
```

### 5. 三级缓存策略

#### L0: Thread 历史缓存
```python
# 当前对话线程内的历史查询
def thread_history_check(state):
    thread_id = state["thread_id"]
    query = state["enriched_query"]
    
    # 检查当前线程历史
    history = get_thread_history(thread_id)
    for item in history:
        if item["query"] == query:
            return item["result"]  # 直接返回
    
    return None  # 未命中，继续
```

#### L1: 精确匹配缓存
```python
# 内存OrderedDict实现
from collections import OrderedDict

_query_cache = OrderedDict()
MAX_CACHE_SIZE = 1000

def exact_cache_check(query, connection_id):
    cache_key = f"{connection_id}:{query}"
    
    if cache_key in _query_cache:
        # LRU: 移到末尾
        _query_cache.move_to_end(cache_key)
        return _query_cache[cache_key]
    
    return None
```

#### L2: 语义匹配缓存
```python
# Milvus向量数据库实现
async def semantic_cache_check(query, connection_id, threshold=0.9):
    # 向量化查询
    query_vector = await embed_query(query)
    
    # Milvus相似度搜索
    results = await milvus_client.search(
        collection_name="query_cache",
        query_vectors=[query_vector],
        limit=1,
        filter=f"connection_id == {connection_id}"
    )
    
    if results and results[0]["score"] >= threshold:
        return results[0]["cached_sql_template"]
    
    return None
```

### 6. 快速模式自动检测

**检测逻辑**:
```python
def detect_fast_mode(query: str) -> bool:
    """检测是否应启用快速模式"""
    
    # 简单查询模式
    simple_patterns = [
        r"^查询.*前\d+",        # "查询销量前10的商品"
        r"^显示.*信息$",         # "显示用户信息"
        r"^列出.*列表$",         # "列出部门列表"
    ]
    
    for pattern in simple_patterns:
        if re.search(pattern, query):
            return True
    
    # 复杂查询模式（需要完整流程）
    complex_keywords = ["趋势", "对比", "分析", "预测", "图表"]
    if any(keyword in query for keyword in complex_keywords):
        return False
    
    # 默认返回False(使用完整模式)
    return False

# 设置快速模式标志
if detect_fast_mode(state["enriched_query"]):
    state["fast_mode"] = True
    state["skip_sample_retrieval"] = True
    state["skip_chart_generation"] = True
```

### 7. 错误上下文传递

**实现方式**:
```python
# ErrorRecoveryAgent生成上下文
error_recovery_context = {
    "failed_sql": state["generated_sql"],
    "error_type": "syntax_error",
    "error_message": "near 'FROM': syntax error",
    "fix_suggestions": [
        "检查关键字拼写",
        "确认引号闭合",
        "验证表名存在"
    ],
    "retry_count": 1,
    "max_retries": 3
}

# 传递给重试阶段
state["error_recovery_context"] = error_recovery_context
state["current_stage"] = "sql_generation"  # 重试SQL生成

# SQLGeneratorAgent接收并使用
if state.get("error_recovery_context"):
    context = state["error_recovery_context"]
    # 在Prompt中包含失败SQL和修复建议
    prompt = f"""
    之前生成的SQL失败了:
    {context['failed_sql']}
    
    错误原因: {context['error_message']}
    
    修复建议:
    {chr(10).join(context['fix_suggestions'])}
    
    请重新生成修复后的SQL。
    """
```

### 8. 动态Agent加载

**场景**: 用户创建自定义分析专家

**实现流程**:
```python
async def _load_custom_agent_node(self, state):
    """加载自定义Agent节点"""
    
    # 1. 从消息中提取agent_id
    agent_id = extract_agent_id_from_messages(state["messages"])
    
    if not agent_id:
        return state  # 使用默认Agent
    
    # 2. 从数据库加载AgentProfile
    profile = crud_agent_profile.get(db, id=agent_id)
    
    # 3. 创建自定义Agent
    custom_analyst = create_custom_analyst_agent(
        profile=profile,
        db=db
    )
    
    # 4. 重新创建Supervisor（替换默认chart_generator）
    self.supervisor_agent = create_intelligent_sql_supervisor(
        custom_analyst=custom_analyst
    )
    
    # 5. 更新状态
    state["agent_id"] = agent_id
    
    return state
```

### 9. MCP工具集成

**MCP**: Model Context Protocol（模型上下文协议）

**集成方式**:
```python
from app.mcp.mcp_manager import MultiServerMCPClient
from app.mcp.mcp_tool_wrapper import MCPToolWrapper

# 初始化MCP客户端
client = MultiServerMCPClient({
    "mcp-server-chart": {
        "command": "npx",
        "args": ["-y", "@antv/mcp-server-chart"]
    }
})

# 获取工具
await client.start()
chart_tools = await client.get_tools()

# 包装为LangChain工具
wrapped_tools = [
    MCPToolWrapper(tool, tool.name) 
    for tool in chart_tools
]

# 添加到Agent
chart_agent = create_react_agent(
    llm,
    local_tools + wrapped_tools,  # 本地工具 + MCP工具
    prompt=chart_prompt
)
```

**优势**:
- 标准化的工具接口
- 易于扩展新工具
- 支持远程工具调用
- 工具版本管理

---

## 总结

### 系统优势

1. **模块化设计**: 每个Agent职责清晰，易于维护和扩展
2. **智能协调**: Supervisor自动路由，无需硬编码流程
3. **错误恢复**: 完善的错误处理和自动修复机制
4. **性能优化**: 双层缓存、快速模式、直接调用等优化手段
5. **可扩展性**: 支持自定义Agent和工具
6. **人机交互**: 使用 LangGraph interrupt() 模式实现澄清机制

### 最佳实践

1. **状态管理**: 使用共享状态而非消息传递
2. **工具设计**: 单一职责，可组合
3. **错误处理**: 分层处理，自动恢复
4. **性能优化**: 双层缓存、快速模式自动检测
5. **可观测性**: 详细的日志记录
6. **消息历史管理**: 自动修剪和验证消息历史

### 近期改进 (2026-01)

1. **快速模式** (2026-01-21): 简单查询自动跳过样本检索和图表生成
2. **缓存直接执行** (2026-01-21): 缓存命中时直接执行SQL，无需走完整流程
3. **消息重复修复** (2026-01-21): 优化 Supervisor 配置，消除消息重复
4. **样本检索集成** (2026-01-19): 将样本检索集成到 sql_generator_agent
5. **双层缓存** (2026-01-19): L1精确匹配 + L2语义匹配

### 未来改进方向

1. **流式输出**: 支持实时返回中间结果
2. **并行执行**: 某些Agent可以并行运行
3. **更智能的路由**: 基于历史数据优化路由决策
4. **更多数据源**: 支持更多类型的数据库和API
5. **增强的可视化**: 更丰富的图表类型和交互

---

## 附录

### 相关文件清单

**核心文件**:
- `backend/app/agents/chat_graph.py` - 主入口
- `backend/app/agents/agent_factory.py` - Agent工厂
- `backend/app/agents/agents/supervisor_agent.py` - 协调器
- `backend/app/core/state.py` - 状态定义

**节点文件** (2026-01-19 新增):
- `backend/app/agents/nodes/cache_check_node.py` - 缓存检查节点
- `backend/app/agents/nodes/clarification_node.py` - 澄清节点

**Worker Agents**:
- `backend/app/agents/agents/schema_agent.py`
- `backend/app/agents/agents/sql_generator_agent.py` (含样本检索)
- `backend/app/agents/agents/sql_executor_agent.py`
- `backend/app/agents/agents/chart_generator_agent.py`
- `backend/app/agents/agents/error_recovery_agent.py`
- `backend/app/agents/agents/clarification_agent.py`
- ~~`backend/app/agents/agents/sample_retrieval_agent.py`~~ (已禁用)

**服务层**:
- `backend/app/services/text2sql_service.py`
- `backend/app/services/text2sql_utils.py`
- `backend/app/services/db_service.py`
- `backend/app/services/schema_service.py`
- `backend/app/services/query_cache_service.py` - 缓存服务
- `backend/app/services/hybrid_retrieval_service.py` - 混合检索服务

### 参考文档

- LangGraph官方文档: https://langchain-ai.github.io/langgraph/
- LangChain工具文档: https://python.langchain.com/docs/modules/tools/
- MCP协议: https://modelcontextprotocol.io/

---

**文档版本**: v2.0  
**最后更新**: 2026-01-22  
**维护者**: AI Assistant
