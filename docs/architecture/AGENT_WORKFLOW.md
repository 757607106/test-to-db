# Agent 核心逻辑流程图

## 一、主图流程 (IntelligentSQLGraph)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            用户发送查询                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     1️⃣ load_custom_agent 节点                               │
│  - 从消息中提取 agent_id 和 connection_id                                   │
│  - 如果有 agent_id，从数据库加载自定义分析专家                                │
│  - 替换默认的 chart_generator_agent                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     2️⃣ fast_mode_detect 节点 (2026-01-21 新增)              │
│  - 检测查询复杂度，决定是否启用快速模式                                       │
│  - 简单查询 → 跳过样本检索、图表生成                                         │
│  - 复杂查询 → 完整模式                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     3️⃣ clarification 节点                                   │
│  - 检测用户查询是否模糊/歧义                                                 │
│  - 如果模糊 → 使用 interrupt() 暂停，等待用户回复                            │
│  - 使用 LangGraph 标准 interrupt() 模式实现人机交互                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            需要澄清 ▼                       不需要澄清 ▼
    ┌───────────────────────┐         ┌───────────────────────┐
    │ interrupt() 暂停执行  │         │   继续下一步          │
    │ 返回澄清问题给客户端  │         └───────────────────────┘
    │        ↓              │                      │
    │ Command(resume=...)   │                      │
    │ (用户回复后恢复执行)   │                      ▼
    └───────────────────────┘  ┌─────────────────────────────────────────────┐
                               │             4️⃣ cache_check 节点              │
                               │  - L1: 精确匹配缓存 (相同查询+连接ID)         │
                               │       存储: 内存 OrderedDict                │
                               │       容量: 1000条, TTL: 1小时              │
                               │  - L2: 语义匹配缓存 (相似度 >= 95%)           │
                               │       存储: Milvus 向量数据库                │
                               └─────────────────────────────────────────────┘
                                               │
                               ┌───────────────┴───────────────┐
                               │                               │
                       缓存命中 ▼                       缓存未命中 ▼
               ┌───────────────────────┐       ┌───────────────────────┐
               │ 直接返回缓存结果       │       │  继续到 supervisor    │
               │ (直接执行缓存的SQL)    │       └───────────────────────┘
               │        ↓              │                    │
               │      END              │                    ▼
               └───────────────────────┘  ┌─────────────────────────────────────┐
                                          │        5️⃣ supervisor 节点           │
                                          │    (协调 Worker Agents 完成任务)     │
                                          └─────────────────────────────────────┘
                                                          │
                                                          ▼
                                          ┌─────────────────────────────────────┐
                                          │       存储结果到缓存                  │
                                          │        ↓                            │
                                          │      END                            │
                                          └─────────────────────────────────────┘
```

---

## 二、Supervisor 内部流程 (Worker Agents 协调)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Supervisor (LLM决策中心)                             │
│  - 根据当前状态智能选择下一个 Worker Agent                                    │
│  - 一次只调用一个 Agent，不并行                                              │
│  - output_mode="last_message"：只返回最后的总结消息                          │
│  - add_handoff_back_messages=False：避免消息重复                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🔍 schema_agent                                        │
│  - 分析用户查询意图                                                         │
│  - 检索相关数据库表结构                                                      │
│  - 获取字段类型、值映射                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ⚙️ sql_generator_agent                                  │
│  - 内置样本检索（参考历史 QA 对）- 快速模式可跳过                             │
│  - 根据 schema 信息生成高质量 SQL                                            │
│  - 使用 with_structured_output 确保输出一致性                                │
│  - 已移除 explain_sql_query 等优化工具以提升速度                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🚀 sql_executor_agent                                  │
│  - 安全执行 SQL 语句                                                        │
│  - 格式化查询结果                                                           │
│  - 内置缓存机制，防止重复执行                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
               执行成功 ▼                      执行失败 ▼
    ┌───────────────────────────┐    ┌───────────────────────────┐
    │  检查是否需要图表可视化    │    │  🔧 error_recovery_agent   │
    │  (用户意图/数据适合性)     │    │  - 错误模式识别            │
    │  快速模式可跳过此步骤      │    │  - 提供修复方案            │
    └───────────────────────────┘    │  - 最多重试一次            │
                │                    └───────────────────────────┘
        ┌───────┴───────┐                      │
        │               │                      │
   需要图表 ▼      不需要/跳过 ▼                │
┌─────────────┐  ┌─────────────┐              │
│ 📊 chart_   │  │    完成     │              │
│ generator_  │  │             │              │
│ agent       │  │             │              │
│ - 生成可视化│  │             │              │
│   图表配置  │  │             │              │
└─────────────┘  └─────────────┘              │
        │               │                      │
        └───────┬───────┘◀─────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             返回最终结果                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**注意**：`sample_retrieval_agent` 已临时禁用（由于 ReAct agent 调度延迟问题，该步骤会导致 2+ 分钟的等待）。
样本检索功能已集成到 `sql_generator_agent` 内部，先快速检查是否有样本，没有则跳过。

---

## 三、状态流转 (current_stage)

```
clarification → cache_check → schema_analysis → sql_generation → sql_execution
                    ↓                                                  ↓
              (缓存命中)                              ┌─── error_recovery ─┐
                    ↓                                 ↓                    ↓
               completed ← ─── ─── chart_generation ←─┘    (快速模式可跳过)
```

**快速模式流转** (简单查询):
```
clarification → cache_check → schema_analysis → sql_generation → sql_execution → completed
                                    (跳过样本检索)                     (跳过图表生成)
```

**完整模式流转** (复杂查询):
```
clarification → cache_check → schema_analysis → sql_generation → sql_execution → chart_generation → completed
                                 (含样本检索)                               (根据需要)
```

---

## 四、关键设计总结

| 层级 | 组件 | 职责 |
|------|------|------|
| **主图** | `IntelligentSQLGraph` | 流程控制、缓存检查、澄清机制、快速模式检测 |
| **协调层** | `SupervisorAgent` | 智能路由、Agent调度、消息历史管理 |
| **Worker层** | `schema_agent` | 数据库模式分析 |
| | `sql_generator_agent` | SQL生成（内置样本检索） |
| | `sql_executor_agent` | SQL执行（含缓存） |
| | `chart_generator_agent` | 图表生成 |
| | `error_recovery_agent` | 错误恢复 |
| | ~~`sample_retrieval_agent`~~ | ~~样本检索~~ (已禁用，集成到sql_generator) |

**核心特性：**
1. **两层架构**：主图控制流程 + Supervisor协调Agent
2. **缓存优先**：精确匹配 + 语义匹配双层缓存
3. **澄清机制**：使用 LangGraph interrupt() 模式实现人机交互
4. **自愈能力**：错误自动检测和恢复
5. **可扩展**：支持动态加载自定义分析专家
6. **快速模式** (2026-01-21 新增)：简单查询自动跳过样本检索和图表生成，提升响应速度

---

## 五、缓存系统详解

### 缓存数据存放位置

#### 1. 精确匹配缓存 (L1)
**存放位置**: **内存中** (`OrderedDict`)
- 实现类：`QueryCacheService` (单例模式)
- 数据结构：`OrderedDict[str, CacheEntry]`
- 缓存键：`MD5(normalize(query):connection_id)`
- 配置：
  - 最大容量：1000 条
  - TTL：3600 秒（1小时）
  - 淘汰策略：LRU
  - 线程安全：使用 `Lock`

**CacheEntry 结构：**
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

#### 2. 语义匹配缓存 (L2)
**存放位置**: **Milvus 向量数据库**
- 实现：复用现有的 `HybridRetrievalEnginePool`
- 数据来源：历史 QA 样本（问题-SQL对）
- 检索方式：向量语义检索
- 配置：
  - 相似度阈值：>= 0.95
  - 检索数量：top_k = 1
  - 存储内容：SQL 语句（不含执行结果）

**工作流程：**
```
1. 用户查询 → 向量化 (Embedding)
2. Milvus 语义检索 → 返回最相似的历史 QA 对
3. 判断相似度 >= 0.95 → 命中
4. 返回 SQL（执行结果需从 L1 查找或重新执行）
```

### 缓存检查流程

```
cache_check_node 接收查询
        ↓
┌────────────────────────────────┐
│ 1. 精确匹配检查 (L1)            │
│    _check_exact_cache()        │
│    ↓                           │
│    MD5(query:connection_id)    │
│    ↓                           │
│    命中？→ 返回 SQL + 结果      │
└────────────────────────────────┘
        │ 未命中
        ↓
┌────────────────────────────────┐
│ 2. 语义匹配检查 (L2)            │
│    _check_semantic_cache()     │
│    ↓                           │
│    Milvus 向量检索             │
│    ↓                           │
│    相似度 >= 0.95？            │
│    ↓                           │
│    命中 → 返回 SQL             │
│    (可能无执行结果)             │
└────────────────────────────────┘
        │ 未命中
        ↓
   继续 supervisor 流程
```

**缓存命中时的处理** (2026-01-21 优化):
- 如果有执行结果：直接返回缓存结果
- 如果只有 SQL 无结果：**在 cache_check_node 中直接执行 SQL**
  - 执行成功：返回结果并结束
  - 执行失败：清理消息历史，从 schema_analysis 重新开始（数据库 schema 可能已变更）

### 缓存存储时机

```
supervisor_node 执行完成
        ↓
_store_result_to_cache()
        ↓
提取生成的 SQL 和执行结果
        ↓
store_result() → 存入 L1 缓存
        ↓
(L2 缓存通过 QA 样本管理系统更新)
```

### 优势分析

| 层级 | 优势 | 劣势 |
|------|------|------|
| **L1 精确缓存** | 速度极快（内存）、包含执行结果 | 容量有限、进程重启丢失 |
| **L2 语义缓存** | 支持相似问题、持久化存储 | 仅有 SQL、需重新执行 |

---

## 六、已知问题与解决方案

### 问题1: 缓存无法存储执行结果 ✅ 已解决

**现象:**
- 相同查询第二次执行仍然未命中缓存
- 或者只命中 SQL 但没有执行结果，需要重新执行
- 日志显示：`has_execution_result: false`

**根本原因:**
```python
# supervisor_agent.py 第112行
output_mode="full_history"  # 只返回 messages，丢失 execution_result 等状态字段
```

`langgraph_supervisor` 的 `create_supervisor` 函数只支持两种 `output_mode`：
- `full_history`：返回完整消息历史
- `last_message`：只返回最后一条消息

**不支持 `state` 模式**，因此无法直接返回 `execution_result` 字段。

**解决方案:**

由于无法修改 supervisor 的返回模式，改为从 `ToolMessage` 中提取执行结果：

```python
# chat_graph.py - _store_result_to_cache 方法
# sql_executor_agent 将执行结果存入 ToolMessage.content（JSON格式）
for msg in reversed(result_messages):
    if isinstance(msg, ToolMessage) and msg.name == 'execute_sql_query':
        parsed_result = json.loads(msg.content)
        execution_result = {
            "success": parsed_result.get("success"),
            "data": parsed_result.get("data"),
            "error": parsed_result.get("error")
        }
        break
```

**数据流:**
```
sql_executor_agent 执行 SQL
        ↓
结果存入 ToolMessage.content (JSON)
        ↓
supervisor 返回 messages（包含 ToolMessage）
        ↓
_store_result_to_cache 解析 ToolMessage.content
        ↓
提取 execution_result 存入 L1 缓存
```

**修复时间:** 2026-01-19

**影响:**
- ✅ L1 缓存现在可以正确存储执行结果
- ✅ 相同查询第二次会直接返回缓存结果，不再重新执行
- ✅ 显著提升重复查询的响应速度

---

## 七、快速模式 (Fast Mode) - 2026-01-21 新增

借鉴官方 LangGraph SQL Agent 的简洁性思想，对于简单查询使用快速模式提升响应速度。

### 快速模式检测逻辑

```python
def detect_fast_mode(query: str) -> Dict[str, Any]:
    # 检查禁用关键词（需要可视化或分析）
    disable_keywords = ["图表", "趋势", "分布", "对比", "可视化"]
    
    # 简单查询模式匹配
    simple_patterns = [
        r'^(查询|获取|显示|列出|统计|计算).{0,20}(数量|总数|有多少)',
        r'^(查询|获取|显示|列出).{0,30}(信息|数据|记录)$',
        r'^.{0,20}(是什么|是哪个|有哪些)\??$',
    ]
    
    # 复杂查询指示词
    complex_indicators = [
        r'\b(join|group by|having|union)\b',
        r'\b(window|over|partition)\b',
        r'最近.*(\d+).*(天|周|月|年)',
    ]
```

### 快速模式配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `FAST_MODE_AUTO_DETECT` | 是否自动检测快速模式 | `True` |
| `FAST_MODE_SKIP_SAMPLE_RETRIEVAL` | 快速模式下跳过样本检索 | `True` |
| `FAST_MODE_SKIP_CHART_GENERATION` | 快速模式下跳过图表生成 | `True` |
| `FAST_MODE_ENABLE_QUERY_CHECKER` | 快速模式下启用SQL检查 | `True` |
| `FAST_MODE_QUERY_LENGTH_THRESHOLD` | 查询长度阈值 | `50` |
| `FAST_MODE_DISABLE_KEYWORDS` | 禁用快速模式的关键词 | `"图表,趋势,分布,..."` |

### 状态字段

```python
class SQLMessageState:
    fast_mode: bool = False           # 是否启用快速模式
    skip_sample_retrieval: bool = False  # 是否跳过样本检索
    skip_chart_generation: bool = False  # 是否跳过图表生成
    enable_query_checker: bool = True    # 是否启用SQL检查
    sql_check_passed: bool = False       # SQL检查是否通过
```

### 效果

- **简单查询**: 响应时间减少 30-50%（跳过样本检索和图表生成）
- **复杂查询**: 保持完整功能，确保质量

---

**文档版本**: v2.0  
**最后更新**: 2026-01-22  
**维护者**: AI Assistant
