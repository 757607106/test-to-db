# Text-to-SQL 前后端对接分析报告

## 概述

本报告详细分析了 Text-to-SQL 系统的前后端对接逻辑，重点关注：
- LangGraph 流式响应处理
- 澄清中断（Clarification Interrupt）机制
- 数据库连接和智能体配置传递
- 错误处理和状态同步

---

## 1. 架构概览

### 1.1 前端关键组件

| 组件 | 文件 | 职责 |
|------|------|------|
| StreamProvider | `providers/Stream.tsx` | 流式连接管理，事件处理 |
| ClarificationInterruptView | `components/thread/messages/clarification-interrupt.tsx` | 澄清问题UI展示 |
| AssistantMessage | `components/thread/messages/ai.tsx` | AI消息和中断渲染 |
| QueryPipeline | `components/thread/messages/QueryPipeline.tsx` | SQL步骤进度展示 |
| Thread | `components/thread/index.tsx` | 主对话界面 |

### 1.2 后端关键节点

| 节点 | 文件 | 职责 |
|------|------|------|
| clarification_node | `agents/nodes/clarification_node.py` | 语义澄清检测 |
| table_filter_clarification_node | `agents/nodes/table_filter_clarification_node.py` | 表过滤澄清 |
| cache_check_node | `agents/nodes/cache_check_node.py` | 缓存检查和流式事件发送 |
| error_recovery_agent | `agents/agents/error_recovery_agent.py` | 错误恢复 |

---

## 2. 流式通信机制

### 2.1 流式模式配置

**前端提交配置** (`Thread.tsx:268-287`):
```typescript
stream.submit({
  messages: [...toolMessages, newHumanMessage],
  context: { connectionId: selectedConnectionId },
}, {
  streamMode: ["values", "messages", "custom"],  // 三种模式并行
  streamSubgraphs: true,
  streamResumable: true,  // 支持中断恢复
});
```

### 2.2 自定义事件处理

**前端事件处理** (`Stream.tsx:190-274`):
```typescript
onCustomEvent: (event, options) => {
  if (isStreamEvent(event)) {
    switch (streamEvent.type) {
      case "cache_hit": // 缓存命中
      case "intent_analysis": // 意图解析
      case "sql_step": // SQL步骤进度
      case "data_query": // 数据查询结果
      case "similar_questions": // 相似问题
    }
  }
}
```

### 2.3 后端事件发送

**StreamWriter 使用** (`cache_check_node.py:152-263`):
```python
from langgraph.types import StreamWriter

async def cache_check_node(state: SQLMessageState, writer: StreamWriter):
    # 发送缓存命中事件
    writer(create_cache_hit_event(
        hit_type="exact",
        similarity=cache_hit.similarity,
        time_ms=elapsed_ms
    ))
```

---

## 3. 澄清中断机制

### 3.1 后端中断触发

**clarification_node.py:164-179**:
```python
from langgraph.types import interrupt

# 使用 interrupt() 暂停执行
interrupt_data = {
    "type": "clarification_request",
    "questions": formatted_questions,
    "reason": check_result.get("reason"),
    "original_query": user_query
}
user_response = interrupt(interrupt_data)
```

### 3.2 前端中断检测

**ai.tsx:65-105**:
```typescript
function Interrupt({ interrupt, isLastMessage, hasNoAIOrToolMessages }) {
  const clarificationData = extractClarificationData(interrupt);
  const isClarification = clarificationData !== null;
  
  if (isClarification && clarificationData) {
    return <ClarificationInterruptView interrupt={clarificationData} />;
  }
}
```

### 3.3 用户回复提交

**clarification-interrupt.tsx:79-104**:
```typescript
const handleSubmit = async () => {
  const formattedResponses = {
    session_id: interrupt.session_id,
    answers: questions.map((q) => ({
      question_id: q.id,
      answer: responses[q.id],
    })),
  };
  
  stream.submit({}, {
    command: { resume: formattedResponses },  // 恢复执行
    streamMode: ["values", "messages"],
    streamSubgraphs: true,
  });
};
```

---

## 4. 数据库连接传递

### 4.1 前端选择器

**Thread.tsx:619-623**:
```typescript
<DatabaseConnectionSelector
  value={selectedConnectionId}
  onChange={setSelectedConnectionId}
  onLoaded={setConnectionCount}
/>
```

### 4.2 消息携带

**Thread.tsx:247-259**:
```typescript
const newHumanMessage: Message = {
  id: uuidv4(),
  type: "human",
  content: [...],
  additional_kwargs: {
    connection_id: selectedConnectionId,  // 放入additional_kwargs
    agent_id: selectedAgentId,
  },
};
```

### 4.3 上下文传递

**Thread.tsx:263-271**:
```typescript
const context = {
  connectionId: selectedConnectionId,
};
stream.submit({
  messages: [...],
  context: Object.keys(context).length > 0 ? context : undefined,
});
```

---

## 5. 发现的问题

### 5.1 [高优先级] connection_id 传递不一致

**问题描述**: 
- 前端通过两种方式传递 connection_id：
  1. `message.additional_kwargs.connection_id`
  2. `context.connectionId`
- 后端可能只读取其中一种，导致不一致

**影响范围**: 数据库连接选择可能失效

**修复建议**:
```python
# 后端统一读取逻辑 (chat_graph.py)
def extract_connection_id(state, messages):
    # 优先从 context 读取
    connection_id = state.get("context", {}).get("connectionId")
    if connection_id:
        return connection_id
    
    # 其次从最后一条人类消息读取
    for msg in reversed(messages):
        if hasattr(msg, 'additional_kwargs'):
            conn_id = msg.additional_kwargs.get('connection_id')
            if conn_id:
                return conn_id
    
    return state.get("connection_id")
```

### 5.2 [中优先级] 流式事件去重不完整

**问题描述**: 
前端 `Stream.tsx:219-256` 使用签名去重 SQL 步骤事件，但签名只包含 `step-status-time_ms`，可能导致：
- 相同签名的不同结果被跳过
- 状态快速变化时丢失中间状态

**影响范围**: SQL 进度展示可能不完整

**修复建议**:
```typescript
// Stream.tsx - 改进签名生成
const stepSignature = `${streamEvent.step}-${streamEvent.status}-${streamEvent.result?.substring(0, 20) || ''}-${streamEvent.time_ms || 0}`;
```

### 5.3 [中优先级] 澄清数据提取兼容性

**问题描述**: 
`extractClarificationData` 函数支持多种包装格式，但可能遗漏某些边缘情况

**影响范围**: 部分澄清请求可能无法正确显示

**已有处理** (`clarification-interrupt.tsx:307-351`):
- 直接格式
- value 包装格式
- 数组格式

**建议增加**:
```typescript
// 嵌套 interrupt 格式
if (obj.interrupt && typeof obj.interrupt === "object") {
  return extractClarificationData(obj.interrupt);
}
```

### 5.4 [低优先级] 澄清跳过后状态不完整

**问题描述**: 
用户点击"跳过"时，`handleSkip` 发送空数组，后端可能未正确处理

**代码位置**: `clarification-interrupt.tsx:106-115`

**影响范围**: 跳过澄清后可能导致查询失败

**修复建议**:
```typescript
// 前端发送明确的跳过信号
const handleSkip = () => {
  stream.submit({}, {
    command: { 
      resume: { 
        skipped: true,  // 明确标记为跳过
        session_id: interrupt.session_id 
      } 
    },
    streamMode: ["values", "messages"],
    streamSubgraphs: true,
  });
};
```

### 5.5 [低优先级] localStorage 键冲突风险

**问题描述**: 
`Stream.tsx:115` 使用 `queryContext:${tid}` 作为存储键，可能与其他应用冲突

**修复建议**:
```typescript
const getStorageKey = (tid: string) => `chat-to-db:queryContext:${tid}`;
```

---

## 6. 测试场景和预期行为

### 6.1 正常查询流程

| 步骤 | 前端行为 | 后端行为 | 预期结果 |
|------|---------|---------|---------|
| 1 | 用户输入查询 | - | 显示加载状态 |
| 2 | - | intent_router 识别意图 | 返回 data_query |
| 3 | 收到 cache_hit 事件 | cache_check_node | 显示缓存命中/未命中 |
| 4 | 收到 sql_step 事件 | sql_generator | 显示 SQL 生成进度 |
| 5 | 收到 data_query 事件 | sql_executor | 显示数据表格和图表 |
| 6 | 收到 AI 消息 | analysis_agent | 显示分析文本 |

### 6.2 澄清中断流程

| 步骤 | 前端行为 | 后端行为 | 预期结果 |
|------|---------|---------|---------|
| 1 | 用户输入模糊查询 | - | 显示加载状态 |
| 2 | - | clarification_node 检测 | 调用 interrupt() |
| 3 | 收到 interrupt | - | 显示 ClarificationInterruptView |
| 4 | 用户选择选项 | - | 收集回答 |
| 5 | 点击提交 | - | 发送 resume 命令 |
| 6 | - | clarification_node 恢复 | 解析回答，继续执行 |

### 6.3 错误恢复流程

| 步骤 | 前端行为 | 后端行为 | 预期结果 |
|------|---------|---------|---------|
| 1 | - | SQL 执行失败 | 进入 error_recovery |
| 2 | - | 分析错误类型 | 生成恢复策略 |
| 3 | - | 重试 (max 3次) | 返回 sql_generation |
| 4 | 收到 AI 消息 | - | 显示用户友好错误消息 |

---

## 7. 总结

### 7.1 对接状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 流式事件发送 | ✅ 正常 | StreamWriter 正确使用 |
| 澄清中断 | ✅ 正常 | interrupt/resume 机制完整 |
| 数据库连接传递 | ⚠️ 需优化 | 两种传递方式需统一 |
| 智能体配置 | ✅ 正常 | agent_id 正确传递 |
| 错误处理 | ✅ 正常 | 重试机制完善 |
| 状态同步 | ⚠️ 需优化 | 事件去重逻辑可改进 |

### 7.2 优先修复项

1. **统一 connection_id 读取逻辑** - 高优先级
2. **改进流式事件去重** - 中优先级
3. **完善澄清跳过处理** - 低优先级

---

*报告生成时间: 2026-01-23*
