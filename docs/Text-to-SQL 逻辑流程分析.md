# Text-to-SQL 逻辑流程分析（优缺点与问题）

> 基于当前代码实现的“真实链路”梳理，而非仅按设计文档推断。重点围绕：入口 → LangGraph 流程 → Schema/SQL/执行/恢复 → 缓存与安全边界。

---

## 1. 系统总览：你现在的 Text-to-SQL 是“LangGraph Supervisor + 多节点流水线”

核心流程在 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L1-L475)：

- 架构：Supervisor（中心）+ Worker 节点（schema/sql/execution/analysis/chart/...）的 Hub-and-Spoke。
- 路由依据：`state.current_stage` + 少量标志位（如 `route_decision`、`skip_chart_generation`、`error_recovery_context`）。
- 关键特性：
  - P2：查询规划（intent/route/multi-step）
  - P4：多轮上下文改写（follow-up query rewriting）
  - 错误恢复：`error_recovery` 阶段由 Supervisor 决策“重跑 schema 还是重跑 sql_generator”。

---

## 2. 入口与权限：API 层做了 connection_id 的租户校验

入口在 [query.py](file:///Users/pusonglin/chat-to-db/backend/app/api/api_v1/endpoints/query.py#L20-L218)（以及 SSE 的 `/chat/stream` 同文件后半）：

- `POST /query/chat`、`POST /query/chat/stream` 调用 `IntelligentSQLGraph.process_query(...)`。
- 每次请求会先做连接权限校验：`deps.get_verified_connection(db, connection_id, current_user)`  
  校验逻辑在 [deps.py](file:///Users/pusonglin/chat-to-db/backend/app/api/deps.py#L171-L259)：
  - 必须有 `tenant_id`
  - `connection_id` 必须属于该 `tenant_id`

这部分多租户隔离做得是“硬校验”，属于比较扎实的安全基座。

---

## 3. 端到端流程（按真实执行顺序）

### 3.1 Supervisor 路由与阶段机

- 路由与阶段映射在 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L250-L379)
- 正常路径（简化描述）：
  1. `init` → `query_planning`
  2. `planning_done` → `schema_agent`
  3. `schema_done` → `clarification`（可被“简化流程”跳过）
  4. `sql_generated` → `sql_executor`
  5. `execution_done` → `data_analyst`
  6. `analysis_done` → `chart_generator` 或直接跳过图表进入 `recommendation`
  7. `completed` 汇总输出

此外还有 `multi_step_mode`：一个 query_plan 被拆成多个子任务，Supervisor 会循环执行子任务并最终 `result_aggregator` 聚合（实现也在 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L128-L184)）。

---

### 3.2 Query Planning（意图识别 + 路由 + 多轮改写）

节点： [query_planning_node.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/query_planning_node.py#L218-L416)

做了三件关键事：

1. **跟进问题检测**：短句/指代词/修改词 → 判定需要“上下文改写”
2. **上下文改写**：抽取最近 3 轮上下文，LLM 改写为完整查询（减少后续歧义）
3. **查询规划 & 路由**：调用 `query_planner.create_plan`、`query_router.route`，产出：
   - `enriched_query` / `original_query`
   - `query_plan`（复杂度、子任务列表）
   - `route_decision`（general_chat / multi_step / standard 等）
   - `skip_chart_generation`、`fast_mode`

优点是：把“会话理解”前置了；缺点是：这一步会把上下文内容送进模型（见第 5 节风险）。

---

### 3.3 Schema Agent（当前实现：默认强制全量加载）

Schema 节点从 Worker 层进入（包装在 [worker_nodes.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/worker_nodes.py#L37-L52)），真正逻辑在 [schema_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/schema_agent.py#L300-L559)。

这里有一个非常关键的“现实与设计差异”：

- **如果启用 Skill Mode 且命中 Skill**：加载 Skill 预定义的表/列/规则（progressive disclosure）
- **否则：走“强制全量加载”**（`max_tables=9999`），并且会把“所有表名”打到日志里

这一段实现集中在 [schema_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/schema_agent.py#L444-L533)。

> 你仓库里仍然保留了 `Neo4j+LLM` 的“相关表检索器”：[retriever.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/schema/retriever.py#L1-L280)；但主链路的 SchemaAgent 已经默认不走它（除非某些旧路径/工具调用被触发）。这是一个典型的“策略漂移/重复实现”问题（见第 5 节）。

---

### 3.4 Clarification（澄清节点）

澄清节点用来判断是否需要 interrupt/澄清，同时也处理“语义缓存命中时的差异确认”（支持 `cached_sql_template` 等状态字段）。相关逻辑在 [clarification_node.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/clarification_node.py#L73-L140)。

---

### 3.5 SQL Generator（生成 + 预验证 + 列名白名单约束）

SQL 生成的核心在 [sql_generator_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_generator_agent.py)：

- 输入：`schema_info`（含 tables/columns/relationships + semantic_layer）、`enriched_query`
- 输出：`generated_sql`
- **关键安全/正确性护栏**：生成后会做 `prevalidate_sql` 全面预验证，失败则进入 error_recovery 并清空 SQL，阻止执行  
  见 [sql_generator_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_generator_agent.py#L1276-L1337)
- 针对“列名幻觉”的处理：
  - 失败时会把可用列（whitelist/hint）写进 `error_history` 和 `error_recovery_context`
  - 让后续重试能强约束“只能用真实列名”  
  见 [sql_generator_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_generator_agent.py#L1220-L1255)

---

### 3.6 SQL Executor（执行 + 结果验证 + 执行侧缓存）

执行器工具定义在 [sql_executor_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_executor_agent.py#L56-L164)：

- `execute_sql_query(sql_query, connection_id, timeout=30)` 直接通过连接执行 SQL
- 内部有一个 5 分钟的内存缓存（按 `connection_id + hash(sql_query)`）
- 注意：`timeout` 参数目前**没有实际生效**（只是入参，没有用于执行层）

执行失败时会构造错误恢复上下文，并（你前面已做过的修复）携带列名白名单信息，供重试修复列名幻觉（见你项目中 sql_executor_agent 的错误分支逻辑）。

---

### 3.7 Error Recovery：Supervisor 负责“重试走向”

Supervisor 的错误恢复分支在 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L307-L351)：

- 达到重试上限 → fallback_response（而不是直接结束）
- 如果是列名错误且提供了 `available_columns_hint` → 优先重试 `sql_generator`
- 如果像 “unknown column/table” 且是早期重试 → 可能重跑 `schema_agent`

---

## 4. 优点（你这套流程做得好的地方）

1. **阶段机明确、可演进**  
   `current_stage` + Supervisor 路由，让“增加节点/替换策略”相对可控（见 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L250-L379)）。

2. **多轮对话可用性强**  
   - Follow-up query rewriting（减少“我要前20条”这类无主体请求失败率）  
   - 澄清节点把歧义显式化

3. **SQL 生成前置了强验证**  
   - 只读限制、危险关键字、多语句禁止、LIMIT 补全、表名/一致性检查  
   主要验证器在 [sql_validator.py](file:///Users/pusonglin/chat-to-db/backend/app/services/sql_validator.py#L76-L173)，并通过 `prevalidate_sql` 被 SQL 生成阶段调用（见 [sql_generator_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_generator_agent.py#L1279-L1337)）。

4. **错误恢复链路信息“可用”**  
   你把“列名白名单/可用列提示”一路传递到重试路径，对抗列名幻觉是有效的工程手段。

5. **可扩展性（Skill / Semantic Layer）**  
   Skill Mode 的 progressive disclosure 让大库场景有希望走“可控范围”的 schema（见 [schema_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/schema_agent.py#L369-L443)）。

---

## 5. 主要问题与风险（按影响排序）

### 5.1 高优先级：缓存节点“存在但未接入主链路”（功能漂移/死代码风险）

你的节点模块里明确定义了三级缓存策略：

- Thread history： [thread_history_check_node.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/thread_history_check_node.py#L1-L342)
- 全局缓存： [cache_check_node.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/cache_check_node.py#L1-L491)

但主图 `create_hub_spoke_graph()` 实际**没有把这两个节点 add_node 进去**（见 [chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L408-L471) 只包含 query_planning/schema/sql/...）。

直接后果：

- `thread_history_hit` / `cache_hit` 相关逻辑基本不会在“主链路”触发
- 你在 Supervisor 的“缓存命中直接 FINISH”逻辑多数情况下是不可达分支（[chat_graph.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/chat_graph.py#L302-L305)）

这是典型的“看起来有缓存，实际上没跑起来”，会造成性能/体验预期与现实不一致。

---

### 5.2 高优先级：执行层缺少最终安全闸（过度信任上游）

`execute_sql_query` 会直接执行传入 SQL（[sql_executor_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/sql_executor_agent.py#L56-L164)）：

- 没有在执行层再次做只读/多语句/危险关键字校验
- `timeout` 参数未生效（传了也不控制执行时长）

虽然你目前主要依赖 SQL Generator 的 `prevalidate_sql` 把危险 SQL 拦在上游（这是有效的），但这属于“单点护栏”：

- 一旦未来出现旁路（例如缓存节点直接执行缓存 SQL、或新增“直接执行 SQL”的能力），执行层就会成为高风险入口。
- 即使不考虑恶意攻击，**超长 SQL / 慢查询** 也缺少强制中断手段，稳定性风险较大。

---

### 5.3 高优先级：text2sql/schema_cache 存在明显的缓存键错误（导致永远不命中）

在 [schema_cache.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/cache/schema_cache.py#L16-L65)：

- `schema_cache` 声明为 `Dict[int, Dict[str, Any]]`
- `is_schema_cache_valid()` 用 `if connection_id not in schema_cache:` 判断有效性（[schema_cache.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/cache/schema_cache.py#L25-L30)）
- 但 `get_cached_all_tables()` 实际写入/读取的 key 是字符串：`cache_key = f"tables:{connection_id}"`（[schema_cache.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/cache/schema_cache.py#L44-L65)）

结果：`connection_id`（int）永远不会出现在 `schema_cache`（string key），从而 `is_schema_cache_valid()` 永远返回 False，缓存基本永远不命中。

这会导致 Neo4j 表清单查询频繁发生，性能退化，并放大下游 LLM 调用频率。

---

### 5.4 高优先级：Schema 策略“强制全量加载”对大库不友好，且与旧实现并存

SchemaAgent 默认分支明确写着“强制全量加载”（[schema_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/schema_agent.py#L444-L533)），并且 max_tables=9999：

- 优点：极大降低“漏表导致幻觉”
- 代价：
  - prompt token/序列化体积可能爆炸（尤其 tables/columns 多时）
  - 首次加载延迟高，且会影响后续所有节点（SQL 生成更慢、更贵）
  - 日志里输出所有表名（见 [schema_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/schema_agent.py#L468-L474)），可能造成“结构泄露到日志”

同时你项目里仍然保留 `Neo4j + LLM` 的“相关 schema 检索器”：
- [retriever.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/schema/retriever.py#L1-L280)
- [retriever_async.py](file:///Users/pusonglin/chat-to-db/backend/app/services/text2sql/schema/retriever_async.py#L1-L277)

但主链路 SchemaAgent 已经不以它为主，这会带来：
- 重复逻辑/维护成本
- “以为在用相关表检索，实际没用”的认知偏差
- 一些优化（如 async 并行检索）形同虚设

---

### 5.5 中优先级：多租户缓存设计与实际调用不一致（容易埋坑）

`query_cache_service.check_cache()` 支持 tenant_id 并把 tenant_id 编进 cache key（[query_cache_service.py](file:///Users/pusonglin/chat-to-db/backend/app/services/query_cache_service.py#L120-L133)）。

但：
- 主链路并未接入 `cache_check_node`（见 5.1）
- 即使接入，`cache_check_node` 目前调用 `check_cache(user_query, connection_id)` **未传 tenant_id**（见 [cache_check_node.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/nodes/cache_check_node.py#L261-L342)）
- `store_result()` 也不带 tenant_id 入参，未来若启用 tenant 隔离键，会出现“写入与读取键不一致”的隐性 miss 风险（设计已经露头）

---

## 6. 改进建议（不写代码，只给方向）

按“收益/风险比”建议优先做：

1. **统一主链路与设计：要么接入缓存节点，要么删除/冻结它们**
   - 把 thread history/cache check 作为 query_planning 之前的前置阶段最合理
   - 否则建议明确标注为“未启用”，避免误判性能瓶颈

2. **执行层加最后一道硬闸**
   - 至少保证：只读、禁止多语句、危险关键字拦截、超时真正生效
   - 这样即使上游或缓存旁路出问题，执行层也不至于失守

3. **修复 schema_cache 的键一致性**
   - 这是纯性能/稳定性收益，而且属于确定性 bug（不是策略争论）

4. **明确 Schema 策略的主路线**
   - 小库：全量加载（OK）
   - 大库：Skill-based 或“相关表检索 + 兜底补全”  
   - 并明确：现存 retriever_async 是否作为主方案，否则应收敛/下线，减少维护负担

5. **收敛 SQL 校验入口**
   - 目前存在多个校验实现（`sql_validator.py`、`sql_helpers.py`、`text2sql/sql/validator.py`），容易出现规则不一致
   - 建议明确“唯一权威校验器”，其它作为兼容层或删除

---

## 7. 一句话结论

你这套 Text-to-SQL 的“主干链路”（规划→全量 schema→生成→预验证→执行→恢复）整体工程化程度较高，尤其是预验证与列名白名单传递很实用；但目前存在明显的“实现漂移/未接入能力/缓存失效 bug/执行层缺最后防线”的问题，导致性能、稳定性与安全边界都可能与预期不一致。