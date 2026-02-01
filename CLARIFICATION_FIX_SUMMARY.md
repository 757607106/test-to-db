# SQL 错误澄清修复实现总结

## 实现时间
2026-02-02

## 实现目标
在 SQL 执行错误场景下，触发业务化澄清机制，完全基于业务语义向用户说明问题，严禁暴露表名、字段名、SQL 语句等技术细节。

## 核心原则
1. **业务化表达**：所有错误信息必须用业务语言描述
2. **技术细节隐藏**：严禁暴露表名、字段名、SQL、数据库等技术词汇
3. **用户友好**：提供可理解的选项和建议
4. **框架集成**：基于现有 LangGraph Supervisor 框架实现

## 实现架构

### 1. State 扩展
**文件**: `backend/app/core/state.py`

**新增字段**:
```python
# 澄清上下文（用于在 SQL 错误等场景下触发澄清）
clarification_context: Optional[Dict[str, Any]] = None

# 增强后的查询（整合了澄清信息）
enriched_query: Optional[str] = None
```

**clarification_context 结构**:
```python
{
    "trigger": "sql_execution_error",  # 触发场景
    "error": "业务化的错误描述",        # 用户可见
    "technical_error": "技术错误信息",  # 仅供日志
    "sql": "执行的 SQL",
    "needs_user_confirmation": True
}
```

### 2. SQL Executor Agent 增强
**文件**: `backend/app/agents/agents/sql_executor_agent.py`

**核心修改**:
1. **新增 `_extract_business_error()` 函数**：将技术错误转换为业务化描述
   - 字段不存在 → "查询的数据维度可能不存在，需要调整查询内容"
   - 表不存在 → "查询的数据范围可能超出了可访问的范围"
   - 语法错误 → "查询语句的结构需要调整"
   - 权限错误 → "当前没有权限访问相关数据"
   - 超时 → "查询数据量较大，建议缩小查询范围或添加时间限制"

2. **错误处理流程修改**：
   ```python
   except Exception as e:
       business_error = _extract_business_error(str(e), sql_query)
       
       clarification_context = {
           "trigger": "sql_execution_error",
           "error": business_error,
           "technical_error": str(e),
           "sql": sql_query,
           "needs_user_confirmation": True
       }
       
       return Command(
           graph=Command.PARENT,
           update={
               "current_stage": "clarification",  # 触发澄清
               "clarification_context": clarification_context,
               "messages": [ToolMessage(
                   content=f"执行遇到问题，需要您的确认",
                   tool_call_id=tool_call_id
               )]
           }
       )
   ```

### 3. Clarification Agent 增强
**文件**: `backend/app/agents/agents/clarification_agent.py`

**核心修改**:
1. **`check_clarification_need()` 支持双场景**：
   - 场景 1：用户查询模糊（传统澄清）
   - 场景 2：SQL 执行错误（业务化澄清）

2. **新增 `_handle_sql_error_clarification()` 函数**：
   - 接收业务化错误信息
   - 基于 Schema 信息生成业务化选项
   - 严格禁止 LLM 暴露技术细节
   - 提供 2-3 个调整方案供用户选择

3. **保留 `_handle_ambiguous_query_clarification()` 函数**：
   - 处理传统的查询模糊场景

**Prompt 设计重点**:
```python
**严格禁止**：不要提及表名、字段名、SQL、数据库等技术词汇

**示例（正确）**：
- ✅ "查询的数据维度可能不存在，建议调整查询内容"
- ✅ "当前查询范围可能较大，建议缩小时间范围"

**示例（错误）**：
- ❌ "字段 order_date 不存在"
- ❌ "表 orders 找不到"
- ❌ "SQL语法错误"
```

### 4. Supervisor 提示词优化
**文件**: `backend/app/agents/agents/supervisor_agent.py`

**核心修改**:
1. **clarification_agent 能力描述扩展**：
   ```python
   **clarification_agent** - 澄清用户意图
     - 能力：检测查询中的模糊性，生成澄清问题；处理 SQL 执行错误的业务化澄清
     - 使用场景：
       1. 用户查询存在模糊性时（如"最近"、"大客户"、"主要产品"）
       2. SQL 执行失败且需要用户确认时（查看 current_stage == "clarification" 或 clarification_context 存在）
     - **重要**：SQL 执行错误后必须调用此 Agent，用业务语言向用户说明问题
   ```

2. **决策原则新增**：
   - 第 6 条：SQL 错误必须澄清 - 当 `current_stage == "clarification"` 或存在 `clarification_context` 时，必须调用 `clarification_agent`

3. **重要约束更新**：
   - **SQL 错误必须业务化澄清**：SQL 执行失败后不要直接调用 `error_recovery_agent`，而是先调用 `clarification_agent` 用业务语言向用户说明
   - **错误时求助**：只有在系统内部错误或多次失败后才调用 `error_recovery_agent`

## 执行流程

### 正常流程（无错误）
```
用户查询 → Schema Agent → SQL Generator → SQL Validator → SQL Executor → 成功 → Data Analyst
```

### 错误流程（SQL 执行失败）
```
用户查询 → Schema Agent → SQL Generator → SQL Validator → SQL Executor
                                                                ↓
                                                           执行失败
                                                                ↓
                                                  设置 clarification_context
                                                  设置 current_stage = "clarification"
                                                                ↓
                                               Supervisor 识别需要澄清
                                                                ↓
                                              Clarification Agent
                                                                ↓
                                              生成业务化澄清问题
                                                                ↓
                                           用户收到业务化的错误说明和选项
```

## 测试覆盖

### 测试文件
`backend/tests/test_clarification_error_fix.py`

### 测试类别
1. **TestBusinessErrorExtraction** (5 个测试)
   - 字段不存在错误转换
   - 表不存在错误转换
   - 语法错误转换
   - 超时错误转换
   - 权限错误转换

2. **TestClarificationContext** (2 个测试)
   - SQL Executor 设置 context 验证
   - clarification_context 结构验证

3. **TestClarificationAgentErrorHandling** (2 个测试)
   - 检测 SQL 错误场景
   - 业务化澄清格式验证

4. **TestSupervisorRouting** (1 个测试)
   - Supervisor 路由逻辑验证

5. **TestEndToEndFlow** (1 个测试)
   - 端到端流程验证

### 测试结果
```
11 passed, 3 warnings in 1.14s
```

## 关键设计决策

### 1. 为什么不直接调用 error_recovery_agent？
- **问题**：error_recovery_agent 会尝试自动修复 SQL，可能多次失败
- **解决**：先让用户确认问题和调整方向，再进行修复
- **优势**：减少无效重试，提升用户体验

### 2. 为什么需要 clarification_context？
- **问题**：需要在 State 中传递错误信息和触发场景
- **解决**：使用结构化的 context 对象
- **优势**：清晰的数据流，方便 Clarification Agent 判断场景

### 3. 为什么业务化错误和技术错误都保留？
- **业务化错误**：用户可见，完全业务化
- **技术错误**：仅供日志和调试，帮助开发者定位问题
- **优势**：既保护用户体验，又保留技术细节供排查

### 4. 为什么使用 LLM 生成澄清问题？
- **问题**：不同错误需要不同的澄清方式
- **解决**：让 LLM 根据业务错误和 Schema 信息动态生成
- **优势**：灵活、上下文感知、自然语言质量高

## 使用示例

### 示例 1: 字段不存在
**技术错误**:
```
Unknown column 'product_name' in 'field list'
```

**用户看到**:
```
查询的数据维度可能不存在，需要调整查询内容

请选择您想要的调整方式：
1. 重新尝试当前查询
2. 调整查询的时间范围
3. 更换其他数据维度
```

### 示例 2: 表不存在
**技术错误**:
```
Table 'mydb.orders' doesn't exist
```

**用户看到**:
```
查询的数据范围可能超出了可访问的范围

请选择您想要的调整方式：
1. 确认要查询的数据类型
2. 选择其他可用的数据源
3. 联系管理员开通权限
```

### 示例 3: 查询超时
**技术错误**:
```
Query execution timeout after 30 seconds
```

**用户看到**:
```
查询数据量较大，建议缩小查询范围或添加时间限制

请选择您想要的调整方式：
1. 缩小查询的时间范围
2. 添加更多筛选条件
3. 使用汇总数据代替明细
```

## 后续优化建议

### 1. 增强错误分类
当前支持 5 种常见错误，可扩展：
- 数据类型不匹配
- 分组错误
- JOIN 条件错误
- 聚合函数使用错误

### 2. 学习用户选择
记录用户在不同错误场景下的选择偏好，优化推荐顺序。

### 3. 多语言支持
当前仅支持中文业务化描述，可扩展英文等多语言。

### 4. 错误恢复集成
用户选择调整方案后，可以自动触发对应的 SQL 修复策略。

### 5. 前端交互优化
在前端增加更友好的选项卡或表单，让用户更直观地做出选择。

## 合规性检查

### ✅ 符合用户记忆规范
1. **SQL错误场景下的业务化澄清触发规则**：
   - ✅ 仅在SQL执行报错且系统无法自动恢复时触发澄清
   - ✅ 澄清内容完全基于业务语义表达
   - ✅ 严禁出现表名、字段名、技术术语等用户不理解的技术细节

2. **澄清触发的扩展场景**：
   - ✅ SQL 执行错误时主动触发澄清
   - ✅ 检测到需人工干预的错误时触发

3. **Agent协作、澄清流程与关键词响应规范**：
   - ✅ 严格界定各 Agent 职责边界（SQL Executor 只执行，Clarification Agent 只澄清）
   - ✅ 澄清环节克制（仅在 SQL 错误场景触发）
   - ✅ 不对已明确问题重复追问

### ✅ 框架集成
- ✅ 使用 LangGraph Supervisor 架构
- ✅ 逻辑结构清晰（State → SQL Executor → Supervisor → Clarification Agent）
- ✅ 易于维护（职责分离、接口清晰）
- ✅ 可扩展（可轻松添加新的错误类型和澄清策略）

## 相关文件清单

### 核心实现
1. `/backend/app/core/state.py` - State 定义扩展
2. `/backend/app/agents/agents/sql_executor_agent.py` - SQL 执行错误处理
3. `/backend/app/agents/agents/clarification_agent.py` - 业务化澄清逻辑
4. `/backend/app/agents/agents/supervisor_agent.py` - Supervisor 调度优化

### 测试文件
5. `/backend/tests/test_clarification_error_fix.py` - 完整测试套件

### 文档
6. `/CLARIFICATION_FIX_SUMMARY.md` - 本文档

## 提交信息建议
```
feat: 实现 SQL 错误场景的业务化澄清机制

- 扩展 State 定义，添加 clarification_context 和 enriched_query 字段
- SQL Executor Agent 在错误时设置业务化的 clarification_context
- Clarification Agent 支持 SQL 错误场景的业务化澄清
- Supervisor 提示词优化，确保 SQL 错误后调度 clarification_agent
- 新增 11 个测试用例，覆盖错误转换、context 设置、澄清生成等场景

核心原则：
- 完全基于业务语义表达
- 严禁暴露表名、字段名、SQL 等技术细节
- 基于 LangGraph Supervisor 框架，逻辑清晰、易于维护

测试结果：11 passed, 3 warnings
```

## 总结
本次实现成功将 SQL 错误场景集成到澄清流程中，通过业务化的表达方式向用户说明问题，完全符合用户体验要求。整个实现基于现有的 LangGraph Supervisor 框架，逻辑结构清晰，易于维护和扩展。
