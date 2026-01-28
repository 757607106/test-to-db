# Chat BI 系统优化总结 (2026-01)

## 📋 优化概览

本次优化针对以下核心问题进行了改进：

1. **Schema 加载完整性** - 确保表的完整性，可以多但绝不能少
2. **旧版 text2sql_service 清理** - 安全删除废弃代码
3. **LangGraph 架构兼容性** - 确认 create_react_agent 使用正确
4. **SQL 表名验证** - 防止 LLM 生成使用不存在表的 SQL（幻觉问题）
5. **意图路由修复** - 对比/趋势查询正确路由到增强分析模式
6. **配置灵活性** - 新增环境变量支持

---

## 🔧 具体改动

### 1. Schema 加载策略优化

**新增文件**: `backend/app/services/schema_loading_strategy.py`

**核心改进**:
- 新增 `SchemaLoadingStrategy` 枚举，支持三种加载策略：
  - `FULL_LOAD`: 全量加载所有表（默认，确保完整性）
  - `SMART_FILTER`: 智能过滤（LLM 语义匹配）
  - `SKILL_BASED`: 基于 Skill 加载

**决策逻辑**:
```python
# Skill 模式启用 → SKILL_BASED
# 表数量 <= 100 → FULL_LOAD（确保完整性）
# 表数量 > 100 → SMART_FILTER（避免 Token 超限）
# 环境变量强制配置 → 使用配置值（仅 smart_filter/skill_based 会覆盖）
```

**环境变量配置**:
```bash
# 加载策略: full_load | smart_filter | skill_based
SCHEMA_LOADING_STRATEGY=full_load

# 全量加载阈值（超过此数量自动降级）
SCHEMA_FULL_LOAD_THRESHOLD=100
```

### 2. SQL 表名验证功能

**修改文件**: `backend/app/services/sql_helpers.py`

**新增函数**:
- `extract_table_names_from_sql(sql)`: 从 SQL 中提取表名
- `validate_sql_tables(sql, allowed_tables)`: 验证 SQL 中的表是否在允许列表中
- `suggest_similar_table(table_name, allowed_tables)`: 为无效表名建议相似的有效表名

**集成位置**: `backend/app/agents/agents/sql_generator_agent.py`
- 在 SQL 修正步骤中验证表名
- 验证失败时记录警告但不阻止执行（避免误杀）
- 提供相似表名建议帮助调试

### 3. 旧版 text2sql_service 清理

**删除文件**: `backend/app/services/text2sql_service.py`

**改动说明**:
- `POST /query/` 端点已标记为 `deprecated`
- 内部实现已重定向到 LangGraph 架构
- 保持向后兼容，返回格式不变

**迁移建议**:
```python
# 旧接口（已废弃）
POST /api/v1/query/

# 新接口（推荐）
POST /api/v1/query/chat
POST /api/v1/query/chat/stream
```

### 4. 意图路由修复

**修改文件**: `backend/app/agents/query_planner.py`

**问题**: 对比查询（comparison）和趋势查询（trend）被错误路由到 `multi_step`

**修复**: `_create_multi_step_plan` 方法现在保留原始查询类型
- comparison → analysis_enhanced（增强分析模式）
- trend → analysis_enhanced（增强分析模式）
- simple/aggregate 分解后 → multi_step

### 5. LangGraph 版本兼容性

**当前版本**: `langgraph~=0.6.11`

**使用情况**:
- `schema_agent.py`: 使用 `langgraph.prebuilt.create_react_agent`
- `sql_generator_agent.py`: 使用 `langgraph.prebuilt.create_react_agent`

**兼容性说明**:
- LangGraph 0.3+ 将 `create_react_agent` 移至 `langgraph-prebuilt` 包
- 当前版本 0.6.11 仍支持从 `langgraph.prebuilt` 导入
- 无需立即迁移，但建议关注后续版本更新

---

## 📊 架构说明

### Schema 加载流程（优化后）

```
用户查询
    ↓
Query Planning Node
    ↓
Schema Agent Node
    ├─ 检查 Skill 模式 → SKILL_BASED（使用 Skill 预加载的 Schema）
    ├─ 检查表数量 <= 100 → FULL_LOAD（全量加载）
    └─ 检查表数量 > 100 → SMART_FILTER（LLM 语义匹配）
    ↓
SQL Generator Node
    ├─ 生成 SQL
    └─ 验证表名（validate_sql_tables）
        ├─ 通过 → 继续执行
        └─ 失败 → 记录警告 + 建议相似表名
    ↓
SQL Executor Node
    ↓
...
```

### 意图路由流程（修复后）

```
用户查询
    ↓
Query Planning Node
    ├─ 快速规则分类（闲聊检测、简单查询）
    └─ LLM 深度分类（复杂查询）
    ↓
路由决策
    ├─ general_chat → General Chat Node
    ├─ simple/aggregate → standard 模式
    ├─ comparison/trend → analysis_enhanced 模式（即使需要分解）
    └─ multi_step（仅 simple/aggregate 分解后）→ 多步执行模式
```

### 多轮对话澄清流程

```
用户查询
    ↓
Clarification Node
    ├─ 快速预检查（should_skip_clarification）
    │   ├─ 包含具体日期 → 跳过
    │   ├─ 包含具体数量 → 跳过
    │   └─ 包含明确条件 → 跳过
    │
    └─ LLM 澄清检测（_quick_clarification_check_impl）
        ├─ 不需要澄清 → 继续执行
        └─ 需要澄清 → interrupt() 暂停
            ↓
        用户回复
            ↓
        查询增强（_enrich_query_with_clarification_impl）
            ↓
        继续执行
```

### 数据流格式

**前端 → 后端**:
```typescript
// ChatQueryRequest
{
  connection_id: number;
  natural_language_query: string;
  conversation_id?: string;
  clarification_responses?: ClarificationResponse[];
}
```

**后端 → 前端（流式事件）**:
```typescript
// SQLStepEvent
{
  type: "sql_step";
  step: "schema_agent" | "sql_generator" | "sql_executor" | ...;
  status: "running" | "completed" | "error";
  result?: string;
  time_ms: number;
}
```

---

## ✅ 验证清单

- [x] Schema 加载策略模块创建
- [x] schema_agent.py 集成全量加载
- [x] text2sql_service.py 安全删除
- [x] query.py 旧接口标记废弃
- [x] config.py 新增环境变量
- [x] sql_helpers.py 新增表名验证函数
- [x] sql_generator_agent.py 集成表名验证
- [x] query_planner.py 修复意图路由
- [x] 代码语法验证通过
- [x] 模块导入测试通过
- [x] 查询规划器测试通过

---

## 🔍 测试结果

### Schema 加载策略测试
```
表数量=50 → full_load ✓
表数量=100 → full_load ✓（边界值）
表数量=101 → smart_filter ✓
表数量=150 → smart_filter ✓
Skill模式 → skill_based ✓
```

### SQL 表名验证测试
```
SELECT * FROM orders JOIN customers → valid=True ✓
SELECT * FROM unknown_table → valid=False, invalid=['unknown_table'] ✓
建议相似表名: order_items → orders ✓
```

### 查询规划器测试
```
"你好" → general_chat ✓
"查询所有订单" → standard ✓
"统计本月销售额" → standard ✓
"对比上月和本月的销售额" → analysis_enhanced ✓
"查询销售趋势" → analysis_enhanced ✓
```

---

## 🚀 后续建议

1. **监控 Schema 加载性能**
   - 全量加载模式下关注 Token 消耗
   - 表数量超过 50 时考虑配置 Skill

2. **Skill 配置推荐**
   - 对于大型数据库（>100 表），建议配置 Skill
   - 每个 Skill 关联 5-15 个相关表

3. **LangGraph 版本升级**
   - 关注 `langgraph-prebuilt` 包的稳定性
   - 计划在 0.7.x 版本后迁移导入路径

4. **前端适配**
   - 流式事件类型已对齐
   - 建议移除对旧版 `POST /query/` 的依赖

5. **表名验证增强**
   - 考虑在验证失败时自动修正 SQL（当前只是警告）
   - 可以使用 LLM 重新生成使用正确表名的 SQL
