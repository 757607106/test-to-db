# Text-to-SQL 与 Dashboard 洞察链路审计报告（2026-01-30）

## 范围

- Text-to-SQL：从 API 入口 → LangGraph 状态 → schema 检索 → SQL 生成（含 Skill 模式）→ 错误恢复
- Dashboard 洞察：洞察生成/刷新 API → 后台任务 → 数据聚合与条件过滤 → 溯源字段写入与读取

## 关键结论（可执行）

1. **连接权限边界需在 Query API 入口统一收口**：此前 `/query` 与 `/query/chat*` 系列未按 tenant 验证 connection_id，存在跨租户越权风险；已修复为统一使用 get_verified_connection。
2. **多表 JOIN 的“强约束”缺了一块**：Skill 模式虽能加载 join_rules，但此前未注入 SQL prompt，导致多表 JOIN 仍容易靠模型猜；已补齐 join_rules 注入，但仍缺少“JOIN ON 关系校验”。
3. **洞察条件过滤原实现存在高概率误筛/漏筛**：时间范围用字符串比较，且 date_column 选择依赖字段名关键词；已改为优先解析 datetime 并按区间比较，同时支持维度过滤 IN。
4. **API 错误信息泄漏风险**：部分洞察 API 会返回 `detail=str(e)` 或打印 traceback；已改为只记录服务端日志，客户端返回通用错误文案。

## 已落地修复（含定位）

### 1) Query API：按 tenant 验证 connection_id + tenant_id 注入状态

- 修改点：
  - `/query`（deprecated）、`/query/chat`、`/query/chat/resume`、`/query/chat/stream`
  - 统一调用 `deps.get_verified_connection(db, connection_id, current_user)`
  - `process_query(..., tenant_id=current_user.tenant_id)`；SSE 初始状态也注入 tenant_id
- 文件：
  - backend/app/api/api_v1/endpoints/query.py

### 2) SQL 生成：Skill join_rules 注入 prompt（减少 JOIN 幻觉）

- 修改点：
  - Skill 模式下将 `loaded_skill_content.join_rules`（最多 8 条）注入 prompt
  - 明确强调“必须优先使用、禁止自行猜测关联字段”
- 文件：
  - backend/app/agents/agents/sql_generator_agent.py

### 3) Dashboard 洞察：条件过滤更健壮（时间范围 + IN 过滤）

- 修改点：
  - 时间筛选：解析 row 值与 start/end 为 datetime 后再比较
  - date_column：优先选择“首行可解析为 datetime”的列，其次才使用关键词兜底
  - dimension_filters：若 value 为 list/tuple/set，按 IN 过滤
- 文件：
  - backend/app/services/dashboard_insight_service.py

### 4) Dashboard 洞察 API：避免向客户端泄漏内部异常细节

- 修改点：
  - 去除 traceback 输出、去除 `detail=str(e)` 风格的错误回传
  - 统一为 logger.exception 记录服务端日志 + 返回通用错误
- 文件：
  - backend/app/api/api_v1/endpoints/dashboard_insights.py

## 现状审计：多表 JOIN 推断与约束链路

### 表/列与关系信息从哪里来

- **相关表检索**：`retrieve_relevant_schema` 使用 Neo4j + LLM/关键词匹配，得到相关表集合；并可通过关系扩展加入邻接表，但不输出“join path”，只返回 tables/columns/relationships。
  - backend/app/services/text2sql/schema/retriever.py
- **关系来源**：
  - MySQL 元数据（SchemaRelationship）与 Neo4j 图谱（REFERENCES 边）均可参与；在 prompt 侧最终以 relationships 列表呈现（source_table/column → target_table/column）。
  - backend/app/services/graph_relationship_service.py
  - backend/app/services/schema_loading_strategy.py
- **Skill JOIN 规则来源**：
  - Skill 模式下由 `skill_service.load_skill(...).join_rules` 提供（Neo4j JoinRule 节点/或 Skill 配置关联）。
  - backend/app/services/skill_service.py
  - backend/app/services/join_rule_service.py

### 仍存在的主要风险（建议后续补齐）

- **缺少 JOIN ON 的“关系一致性校验”**：当前有列名白名单校验（可防止虚构字段），但无法防止模型用“存在的列”拼出“错误的关联条件”。
- **JOIN 路由优先级仍偏弱**：
  - 现在 prompt 注入 join_rules 能显著降低幻觉，但当 join_rules 未配置时仍依赖 relationships + 模型推理，正确率受 schema 质量影响较大。

## 洞察刷新链路审计（含缺口）

### 刷新/生成流程

- `POST /dashboards/{dashboard_id}/insights`：创建占位洞察 widget（status=processing）并添加后台任务 `process_dashboard_insights_task`
- `PUT /widgets/{widget_id}/refresh-insights`：将 updated_conditions 写入请求，重新触发洞察任务
- 数据来源：洞察聚合依赖各数据 widget 的 `data_cache["data"]`，再在服务侧做条件过滤与分析
  - backend/app/api/api_v1/endpoints/dashboard_insights.py
  - backend/app/services/dashboard_insight_service.py

### 仍存在的功能缺口

- `InsightRefreshRequest.force_requery` 目前未被使用：即“强制重查数据源”不会触发数据 widget 重新执行 SQL，只会对已有缓存再分析。

## 测试与基准（本地）

- 通过：
  - `PYTHONPATH=backend pytest -q backend/tests/test_http_api.py`
- 环境/仓库现状导致的失败（不归因于本次改动）：
  - 直接在 backend/ 下跑 pytest 缺少 PYTHONPATH，会出现 `ModuleNotFoundError: No module named 'app'`
  - 多个 e2e/skill 测试依赖外部 MySQL/Neo4j/LLM 或特定账户配置，当前环境出现 MySQL 账号无密码拒绝等问题

## 建议的下一步（若要继续补齐正确性）

1. **增加 JOIN 一致性校验**：解析 SQL 的 JOIN ON 引用，必须匹配 relationships 或 join_rules（允许别名映射）。
2. **实现 force_requery**：刷新洞察时可选重新执行相关数据 widget 的 SQL，再写入 data_cache 后分析。
3. **统一测试入口**：在 backend 目录提供标准 pytest 运行方式（例如固定 PYTHONPATH 或以模块方式运行），避免收集期失败。

