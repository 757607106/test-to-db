# 多轮推理与分析师 Agent 功能说明

## 功能概述

本次更新在原有的 Text-to-SQL 系统基础上，新增了两个核心功能：

### 1. 多轮推理澄清机制
AI 自动检测用户查询是否存在模糊或不明确之处，并主动向用户提出澄清问题，确保准确理解用户意图。

### 2. 分析师 Agent
在查询执行后，自动分析结果数据，生成业务洞察、趋势分析、异常检测和可行建议。

---

## 新增组件

### 后端组件

#### 1. **Clarification Agent** (`backend/app/agents/agents/clarification_agent.py`)
- **功能**: 检测查询模糊、生成澄清问题、处理用户回复
- **工具函数**:
  - `detect_ambiguity`: 检测查询中的模糊点
  - `generate_clarification_questions`: 生成澄清问题（选择题或文本题）
  - `process_user_clarification`: 处理用户回复并生成增强查询

#### 2. **Analyst Agent** (`backend/app/agents/agents/analyst_agent.py`)
- **功能**: 智能分析查询结果，生成业务洞察
- **工具函数**:
  - `detect_analysis_need`: 智能判断是否需要分析
  - `generate_data_summary`: 生成数据摘要统计
  - `analyze_trends`: 时间序列趋势分析
  - `detect_data_anomalies`: 异常和离群值检测
  - `generate_business_recommendations`: 生成业务建议

#### 3. **分析工具模块** (`backend/app/services/analyst_utils.py`)
提供统计计算、时间序列检测、增长率计算、异常检测等工具函数。

#### 4. **扩展的状态管理** (`backend/app/core/state.py`)
新增字段支持澄清和分析功能：
- `clarification_history`: 澄清历史
- `clarification_round`: 澄清轮次
- `analyst_insights`: 分析洞察结果
- `conversation_id`: 对话ID

#### 5. **新 API 端点** (`backend/app/api/api_v1/endpoints/query.py`)
- `/api/v1/query/chat`: 支持多轮对话的查询接口

### 前端组件

#### 1. **ClarificationCard** (`frontend/chat/src/components/ClarificationCard.tsx`)
展示澄清问题的卡片组件，支持选择题和文本输入。

#### 2. **AnalystInsightsCard** (`frontend/chat/src/components/AnalystInsightsCard.tsx`)
展示数据分析洞察的卡片组件，包括：
- 数据摘要
- 趋势分析
- 异常检测
- 业务建议

---

## 工作流程

### 完整流程图

```
用户输入查询
    ↓
Clarification Agent 检测
    ↓
需要澄清？
    ├── 是 → 展示澄清问题 → 用户回答 → 继续
    └── 否 → 直接进入 Schema Agent
    ↓
Schema Agent（分析模式）
    ↓
SQL Generator Agent（生成SQL）
    ↓
SQL Executor Agent（执行查询）
    ↓
Analyst Agent（智能分析）
    ↓
需要分析？
    ├── 是 → 生成洞察（摘要、趋势、异常、建议）
    └── 否 → 跳过分析
    ↓
Chart Generator Agent（可选）
    ↓
返回结果
```

### 澄清机制详细流程

1. **首次查询**:
   - Clarification Agent 使用 `detect_ambiguity` 检测模糊点
   - 如发现模糊（时间范围、字段、条件等），调用 `generate_clarification_questions`
   - 生成最多 3 个澄清问题（优先选择题）

2. **用户回复**:
   - 前端收集用户回答
   - 调用 `/api/v1/query/chat` 时携带 `clarification_responses`
   - Clarification Agent 使用 `process_user_clarification` 整合信息

3. **澄清限制**:
   - 最多 2 轮澄清（可配置）
   - 超过限制后基于现有信息继续执行

### 分析师工作流程

1. **触发判断** (智能触发):
   - SQL 执行成功后自动调用 Analyst Agent
   - 使用 `detect_analysis_need` 判断是否需要深度分析
   - 判断依据：
     - 数据行数（2-1000 行适合深度分析）
     - 是否包含数值列
     - 是否包含时间列
     - 用户查询意图（通过 LLM 判断）

2. **分析执行**:
   - **数据摘要**: 对所有查询生成基础统计
   - **趋势分析**: 检测到时间序列时自动执行
   - **异常检测**: 对数值列进行离群值检测
   - **业务建议**: 基于分析结果生成可操作建议

3. **结果返回**:
   - 分析结果存储在 `analyst_insights` 字段
   - 前端使用 `AnalystInsightsCard` 展示

---

## API 使用示例

### 1. 普通查询（无澄清）

**请求**:
```json
POST /api/v1/query/chat
{
  "connection_id": 15,
  "natural_language_query": "查询2024年1月的销售总额"
}
```

**响应**:
```json
{
  "conversation_id": "uuid-1234",
  "needs_clarification": false,
  "sql": "SELECT SUM(amount) FROM sales WHERE date >= '2024-01-01' AND date < '2024-02-01'",
  "results": [{"sum": 150000}],
  "analyst_insights": {
    "summary": {
      "total_rows": 1,
      "key_metrics": {"总销售额": 150000}
    },
    "recommendations": [
      {"type": "洞察", "content": "2024年1月销售额达到15万..."}
    ]
  },
  "stage": "completed"
}
```

### 2. 需要澄清的查询

**请求**:
```json
POST /api/v1/query/chat
{
  "connection_id": 15,
  "natural_language_query": "最近的销售情况"
}
```

**响应**:
```json
{
  "conversation_id": "uuid-1234",
  "needs_clarification": true,
  "clarification_questions": [
    {
      "id": "q1",
      "question": "您想查看哪个时间范围的数据？",
      "type": "choice",
      "options": ["最近7天", "最近30天", "最近3个月", "今年"],
      "related_ambiguity": "时间范围模糊"
    },
    {
      "id": "q2",
      "question": "您关注哪些指标？",
      "type": "choice",
      "options": ["销售总额", "订单数量", "平均订单金额", "全部"],
      "related_ambiguity": "字段选择模糊"
    }
  ],
  "stage": "clarification"
}
```

### 3. 提交澄清回复

**请求**:
```json
POST /api/v1/query/chat
{
  "connection_id": 15,
  "natural_language_query": "最近的销售情况",
  "conversation_id": "uuid-1234",
  "clarification_responses": [
    {"question_id": "q1", "answer": "最近30天"},
    {"question_id": "q2", "answer": "全部"}
  ]
}
```

**响应**: （包含完整查询结果和分析）

---

## 测试场景

### 澄清机制测试

#### 测试用例 1: 时间范围模糊
```
输入: "查看销售数据"
期望: 澄清时间范围
```

#### 测试用例 2: 字段不明确
```
输入: "查看订单"
期望: 澄清需要哪些字段
```

#### 测试用例 3: 完整查询（不需澄清）
```
输入: "查询2024年1月订单总数和总金额"
期望: 直接执行，不澄清
```

### 分析师测试

#### 测试用例 1: 时间序列数据
```
查询: "2024年每月销售额"
期望分析: 
- 数据摘要（总额、平均值）
- 趋势分析（增长率、趋势方向）
- 业务建议
```

#### 测试用例 2: 聚合数据
```
查询: "各产品类别的销售统计"
期望分析:
- 数据摘要（分类统计）
- 异常检测（销量异常低/高的类别）
- 业务建议
```

#### 测试用例 3: 简单查询（跳过分析）
```
查询: "查找ID为123的订单"
期望: 返回1行数据，不进行深度分析
```

---

## 配置说明

### 澄清配置
在 `SQLMessageState` 中可配置：
- `max_clarification_rounds`: 最大澄清轮数（默认2）

### 分析配置
在 `analyst_agent.py` 的 `detect_analysis_need` 中可调整：
- 最小数据行数阈值（默认2）
- 最大数据行数阈值（默认1000）
- 分析类型优先级

---

## 性能优化

### 1. 澄清检测优化
- 使用轻量级 LLM 调用
- 控制 token 使用
- 缓存常见查询模式

### 2. 分析计算优化
- 使用 pandas 向量化操作
- 并行计算多个指标
- 大数据集仅提供摘要

### 3. 缓存策略
- 相同查询的分析结果缓存 5 分钟
- 澄清问题模板缓存

---

## 故障排除

### 常见问题

#### 1. 澄清问题未显示
- 检查 `needs_clarification` 字段
- 确认 `clarification_questions` 不为空
- 查看后端日志中的澄清检测结果

#### 2. 分析洞察未生成
- 确认数据行数 >= 2
- 检查是否包含数值列
- 查看 `analyst_insights` 字段内容

#### 3. API 调用失败
- 检查 `connection_id` 是否有效
- 确认后端服务正常运行
- 查看详细错误信息

### 调试建议

1. **启用详细日志**:
```python
# 在各 Agent 的 process 方法中添加
print(f"[Debug] State: {state}")
```

2. **测试独立工具**:
```python
# 直接测试工具函数
from app.agents.agents.clarification_agent import detect_ambiguity
result = detect_ambiguity.invoke({"query": "...", "connection_id": 15})
print(result)
```

3. **前端调试**:
```typescript
// 在组件中添加
console.log("Clarification Questions:", questions);
console.log("Analyst Insights:", insights);
```

---

## 未来扩展

### 潜在改进方向

1. **澄清机制**:
   - 支持更智能的澄清策略
   - 记忆用户偏好（如常用时间范围）
   - 多语言澄清支持

2. **分析师功能**:
   - 预测分析（基于历史趋势）
   - 对比分析（同比、环比）
   - 自动生成报告
   - 集成更多可视化类型

3. **性能优化**:
   - 增量分析（只分析变化部分）
   - 异步分析（后台执行）
   - 更智能的缓存策略

---

## 总结

本次更新成功实现了：
✅ 多轮推理澄清机制（最多2轮）
✅ 智能分析师 Agent（全面分析）
✅ 前后端完整集成
✅ 无 lint 错误
✅ 完整的 API 接口

系统现在能够：
- 主动识别模糊查询并要求澄清
- 自动分析查询结果并生成洞察
- 提供可操作的业务建议
- 检测数据异常和趋势

所有功能都已经过代码验证，可以开始端到端测试！
