# Text-to-SQL 系统测试计划

## 测试目标

系统性地测试 Text-to-SQL 系统的各个场景，确保所有流程节点正常工作。

## 测试环境

- 数据库: erp_inventory (connection_id=7)
- 服务地址: http://localhost:8002
- LangGraph Server: http://localhost:2024

## 测试场景

### 1. 正常场景测试

#### 1.1 简单查询（快速模式）
**测试用例**: "查询产品数量"
**预期流程**:
```
load_custom_agent → fast_mode_detect → clarification → cache_check → supervisor
  ├─ schema_agent
  ├─ sql_generator_agent
  ├─ sql_executor_agent
  └─ completed (跳过图表生成)
```

**预期结果**:
- ✅ 快速模式自动检测
- ✅ 跳过样本检索
- ✅ 跳过图表生成
- ✅ 返回 SQL 和执行结果
- ✅ 不包含分析专家的详细分析

**验证点**:
1. 状态字段 `fast_mode=true`
2. 状态字段 `skip_sample_retrieval=true`
3. 状态字段 `skip_chart_generation=true`
4. 最终 stage 为 `completed`

---

#### 1.2 复杂查询（完整模式）
**测试用例**: "分析最近7天各个仓库的库存变化趋势"
**预期流程**:
```
load_custom_agent → fast_mode_detect → clarification → cache_check → supervisor
  ├─ schema_agent
  ├─ sql_generator_agent
  ├─ sql_executor_agent
  ├─ chart_generator_agent (分析专家)
  └─ completed
```

**预期结果**:
- ✅ 完整模式
- ✅ 进行样本检索
- ✅ 调用分析专家
- ✅ 返回数据洞察和业务建议

**验证点**:
1. 状态字段 `fast_mode=false`
2. 调用了 `chart_generator_agent.process()`
3. 包含分析专家的详细分析
4. 最终 stage 为 `completed`

---

#### 1.3 自定义分析专家
**测试用例**: "分析库存分布" (指定 agent_id=<自定义分析专家ID>)
**预期流程**:
```
load_custom_agent (加载自定义专家) → ... → chart_generator_agent (使用自定义 LLM 和提示词)
```

**预期结果**:
- ✅ 加载自定义分析专家
- ✅ 使用自定义的 system_prompt
- ✅ 使用自定义的 LLM 配置
- ✅ 返回符合自定义提示词风格的分析

**验证点**:
1. 日志显示 "成功加载自定义分析专家"
2. 分析内容符合自定义提示词要求
3. 如果配置了自定义 LLM，使用该 LLM

---

### 2. 异常场景测试

#### 2.1 SQL 语法错误
**测试用例**: 构造一个会导致 SQL 语法错误的查询
**预期流程**:
```
... → sql_generator_agent → sql_executor_agent (执行失败) → error_recovery_agent
```

**预期结果**:
- ✅ 检测到 SQL 执行错误
- ✅ 进入 error_recovery 阶段
- ✅ 分析错误类型（syntax_error）
- ✅ 尝试重新生成 SQL（如果未达到重试限制）

**验证点**:
1. 状态字段 `current_stage=error_recovery`
2. `error_history` 包含错误记录
3. 错误类型识别正确
4. 重试次数未超过 `max_retries`

---

#### 2.2 表/字段不存在
**测试用例**: "查询不存在的表 xyz_table"
**预期流程**:
```
... → sql_executor_agent (执行失败) → error_recovery_agent → schema_agent (重新分析)
```

**预期结果**:
- ✅ 检测到 not_found_error
- ✅ 恢复策略建议重新分析 schema
- ✅ 如果可以自动修复，返回 schema_analysis 阶段

**验证点**:
1. 错误类型 = `not_found_error`
2. 恢复策略 = `verify_schema`
3. 如果自动修复，`current_stage` 回到 `schema_analysis`

---

#### 2.3 数据库连接失败
**测试用例**: 使用无效的 connection_id
**预期流程**:
```
... → schema_agent (失败) → error_recovery_agent
```

**预期结果**:
- ✅ 检测到 connection_error
- ✅ 恢复策略标记为不可自动修复
- ✅ 返回错误消息给用户

**验证点**:
1. 错误类型 = `connection_error`
2. `auto_fixable = false`
3. 最终 stage 为 `completed`（带错误消息）

---

#### 2.4 达到最大重试次数
**测试用例**: 构造一个持续失败的查询
**预期流程**:
```
... → error_recovery_agent → ... (重试) → error_recovery_agent (达到最大次数) → completed
```

**预期结果**:
- ✅ 重试 3 次后停止
- ✅ 返回失败消息给用户
- ✅ 建议人工干预

**验证点**:
1. `retry_count >= max_retries`
2. 停止循环，进入 `completed`
3. 错误消息建议人工干预

---

### 3. 澄清场景测试

#### 3.1 明确查询（跳过澄清）
**测试用例**: "查询 inventory 表的所有记录"
**预期流程**:
```
... → clarification (快速检查通过，跳过) → cache_check → ...
```

**预期结果**:
- ✅ 快速预检查识别查询明确
- ✅ 不调用 LLM 进行澄清检测
- ✅ 直接进入 cache_check

**验证点**:
1. 日志显示 "查询明确，快速跳过澄清"
2. 无 `clarification_responses`
3. `original_query` 保持不变

---

#### 3.2 模糊查询（需要澄清）
**测试用例**: "查询库存"（缺少时间范围、缺少具体产品）
**预期流程**:
```
... → clarification (检测到模糊性) → interrupt() → 等待用户回复 → 继续执行
```

**预期结果**:
- ✅ LLM 检测到查询需要澄清
- ✅ 使用 `interrupt()` 暂停执行
- ✅ 返回澄清问题给前端
- ✅ 用户回复后恢复执行
- ✅ 生成 `enriched_query`

**验证点**:
1. 日志显示 "需要澄清，生成 X 个问题"
2. `interrupt()` 返回的数据包含 `questions`
3. 恢复后状态包含 `clarification_responses`
4. `enriched_query` 包含用户的澄清信息

**测试步骤**:
1. 发送模糊查询
2. 接收 interrupt 响应（包含澄清问题）
3. 使用 `Command(resume=...)` 恢复执行并提供回答
4. 验证增强后的查询

---

#### 3.3 用户拒绝澄清
**测试用例**: 用户在澄清阶段回复 "不需要澄清，直接查询"
**预期流程**:
```
... → clarification → interrupt() → 用户拒绝 → 使用原始查询继续
```

**预期结果**:
- ✅ 识别用户拒绝澄清
- ✅ 使用 `original_query` 继续
- ✅ `enriched_query` 等于 `original_query`

**验证点**:
1. `clarification_responses` 为空或表示拒绝
2. `enriched_query == original_query`

---

### 4. Cache Check 节点测试

#### 4.1 精确匹配缓存命中
**测试用例**: 执行相同的查询两次
**预期流程**:
```
第一次: ... → cache_check (未命中) → supervisor → ... → 存储缓存
第二次: ... → cache_check (精确命中) → completed (跳过 supervisor)
```

**预期结果**:
- ✅ 第二次查询命中精确缓存
- ✅ 直接返回缓存的 SQL 和结果
- ✅ 跳过 supervisor 流程
- ✅ 响应包含 "✨ 缓存命中 (精确匹配)"

**验证点**:
1. 状态字段 `cache_hit=true`
2. 状态字段 `cache_hit_type="exact"`
3. 没有调用 supervisor
4. 最终 stage 为 `completed`

---

#### 4.2 语义匹配缓存命中
**测试用例**: 
- 第一次: "查询产品数量"
- 第二次: "统计有多少个产品"
**预期流程**:
```
第一次: ... → cache_check (未命中) → supervisor → ... → 存储缓存
第二次: ... → cache_check (语义命中, similarity >= 0.95) → completed
```

**预期结果**:
- ✅ 第二次查询命中语义缓存
- ✅ 响应包含 "✨ 缓存命中 (语义匹配 - 相似度: XX%)"
- ✅ 返回相似查询的 SQL 和结果

**验证点**:
1. `cache_hit=true`
2. `cache_hit_type="semantic"`
3. 相似度 >= 0.95

---

#### 4.3 缓存未命中
**测试用例**: 全新的查询
**预期流程**:
```
... → cache_check (未命中) → supervisor → ...
```

**预期结果**:
- ✅ 缓存检查未命中
- ✅ 继续正常 supervisor 流程
- ✅ 执行完成后存储结果到缓存

**验证点**:
1. `cache_hit=false`
2. `cache_hit_type=None`
3. 调用了完整的 supervisor 流程

---

#### 4.4 缓存 SQL 执行失败（Schema 变更）
**测试用例**: 
1. 执行查询并缓存
2. 修改数据库 schema（删除某个列）
3. 再次执行相同查询
**预期流程**:
```
... → cache_check (命中但执行失败) → 重新开始 schema_analysis
```

**预期结果**:
- ✅ 检测到缓存 SQL 执行失败
- ✅ 自动从 schema_analysis 重新开始
- ✅ 生成新的 SQL
- ✅ 更新缓存

**验证点**:
1. 日志显示 "缓存SQL可能已过时，将重新分析数据库schema"
2. `cache_hit=false`（标记为未命中）
3. `current_stage="schema_analysis"`
4. 最终生成新的正确 SQL

---

### 5. Schema 信息传递测试

#### 5.1 正确传递 Schema 信息
**测试用例**: 任意查询
**预期流程**:
```
schema_agent (获取并存储 schema_info) → sql_generator_agent (从状态获取 schema_info)
```

**预期结果**:
- ✅ schema_agent 将信息存储到 `state["schema_info"]`
- ✅ sql_generator_agent 正确获取并使用
- ✅ 生成的 SQL 包含正确的表名和字段

**验证点**:
1. 状态包含 `schema_info` 字段
2. `schema_info` 包含 `tables`, `value_mappings`, `connection_id`
3. 生成的 SQL 使用了正确的表结构

---

### 6. 端到端集成测试

#### 6.1 完整流程（无缓存，无澄清）
**测试用例**: "查询库存数量超过 100 的产品"
**完整流程**:
```
load_custom_agent 
  → fast_mode_detect (完整模式)
  → clarification (跳过)
  → cache_check (未命中)
  → supervisor
      ├─ schema_agent (获取表结构)
      ├─ sql_generator_agent (生成 SQL)
      ├─ sql_executor_agent (执行 SQL)
      └─ chart_generator_agent (数据分析)
  → completed
  → 存储缓存
```

**预期结果**:
- ✅ 所有节点正常执行
- ✅ 返回完整的分析结果
- ✅ 结果被缓存

---

#### 6.2 完整流程（有缓存）
**测试用例**: 重复上述查询
**完整流程**:
```
load_custom_agent 
  → fast_mode_detect
  → clarification (跳过)
  → cache_check (命中) 
  → completed (直接返回)
```

**预期结果**:
- ✅ 缓存命中
- ✅ 跳过 supervisor
- ✅ 快速返回结果

---

#### 6.3 完整流程（有澄清）
**测试用例**: "查询库存" (模糊)
**完整流程**:
```
load_custom_agent 
  → fast_mode_detect
  → clarification (需要澄清) 
      → interrupt() 
      → 等待用户回复
      → 继续执行
  → cache_check
  → supervisor
  → completed
```

**预期结果**:
- ✅ 澄清流程正常工作
- ✅ 生成增强查询
- ✅ 使用增强查询进行 SQL 生成

---

## 测试执行记录

### 测试环境设置
- [ ] 服务启动正常
- [ ] 数据库连接正常
- [ ] LangGraph Studio 可访问

### 场景 1: 正常场景
- [ ] 1.1 简单查询（快速模式）
- [ ] 1.2 复杂查询（完整模式）
- [ ] 1.3 自定义分析专家

### 场景 2: 异常场景
- [ ] 2.1 SQL 语法错误
- [ ] 2.2 表/字段不存在
- [ ] 2.3 数据库连接失败
- [ ] 2.4 达到最大重试次数

### 场景 3: 澄清场景
- [ ] 3.1 明确查询（跳过澄清）
- [ ] 3.2 模糊查询（需要澄清）
- [ ] 3.3 用户拒绝澄清

### 场景 4: Cache Check
- [ ] 4.1 精确匹配缓存命中
- [ ] 4.2 语义匹配缓存命中
- [ ] 4.3 缓存未命中
- [ ] 4.4 缓存 SQL 执行失败

### 场景 5: Schema 传递
- [ ] 5.1 正确传递 Schema 信息

### 场景 6: 端到端
- [ ] 6.1 完整流程（无缓存，无澄清）
- [ ] 6.2 完整流程（有缓存）
- [ ] 6.3 完整流程（有澄清）

---

## 测试工具

### 1. 使用 LangGraph Studio
访问: http://localhost:2024/studio/
可视化查看执行流程和状态变化

### 2. 使用 curl 测试
```bash
# 创建新线程
curl -X POST http://localhost:2024/threads \
  -H "Content-Type: application/json"

# 发送查询
curl -X POST http://localhost:2024/threads/{thread_id}/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "sql_agent",
    "input": {
      "messages": [{"role": "user", "content": "查询产品数量"}],
      "connection_id": 7
    }
  }'
```

### 3. 查看日志
```bash
# 实时查看日志
tail -f backend/logs/app.log

# 过滤特定节点日志
grep "clarification_node" backend/logs/app.log
grep "cache_check_node" backend/logs/app.log
```

---

## 问题记录

| 测试场景 | 问题描述 | 严重程度 | 状态 |
|---------|---------|---------|------|
| - | - | - | - |

---

## 测试总结

待完成测试后填写。
