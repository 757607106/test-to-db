# 工具显示和重复调用问题分析

## 问题1: 工具显示格式不正确

### 现象
- `analyze_user_query` 显示正确（有绿色勾号，显示为 "analyze_user_query"）
- `retrieve_samples`、`generate_sql_query` 等工具显示不正确

### 根本原因分析

通过对比代码发现，问题在于**工具定义的一致性**：

#### ✅ 正确的工具定义 (analyze_user_query)
```python
@tool
def analyze_user_query(query: str) -> Dict[str, Any]:
    """
    分析用户的自然语言查询，提取关键实体和意图
    
    Args:
        query: 用户的自然语言查询
        
    Returns:
        包含实体、关系和查询意图的分析结果
    """
```

#### ❌ 可能有问题的工具定义

需要检查以下工具：
1. `retrieve_samples` - 可能是 `retrieve_similar_qa_pairs` 的别名问题
2. `generate_sql_query` - 工具名称和函数名称是否一致

### 前端显示逻辑

前端 `tool-calls.tsx` 中的关键代码：
```typescript
const toolName = toolCall?.name?.trim() || "Unknown Tool";
```

前端依赖后端返回的 `tool_calls` 数组中的 `name` 字段。如果：
- `name` 为空或格式不正确 → 显示 "Unknown Tool"
- `name` 存在但没有对应的 `ToolMessage` → 显示为 pending 状态

### 需要检查的点

1. **工具注册名称**：检查 `@tool` 装饰器是否正确设置了工具名称
2. **Agent 工具列表**：确认 agent 的 `self.tools` 列表中的工具名称
3. **消息流转**：确认 LangGraph 返回的消息中 `tool_calls` 的格式

## 问题2: execute_sql_query 重复调用

### 现象
从截图看，`execute_sql_query` 被调用了 4 次

### 可能的原因

#### 1. ReAct Agent 的重试机制
`sql_executor_agent` 使用 `create_react_agent`，这是一个 ReAct (Reasoning + Acting) 模式的 agent。

```python
self.agent = create_react_agent(
    self.llm,
    self.tools,
    prompt=self._create_system_prompt,
    name=self.name
)
```

ReAct agent 的工作流程：
1. **Thought**: LLM 思考下一步做什么
2. **Action**: 调用工具
3. **Observation**: 观察工具结果
4. **重复**: 如果 LLM 认为需要，会继续思考和行动

#### 2. 可能导致重复调用的情况

**情况A: 工具返回格式不明确**
```python
# 当前的返回格式
return {
    "success": True,
    "data": {...},
    "error": None,
    ...
}
```

如果 LLM 认为结果不够明确，可能会重试。

**情况B: System Prompt 不够明确**
当前的 prompt：
```python
system_msg = f"""你是一个专业的SQL执行专家。
使用 execute_sql_query 执行SQL查询
"""
```

缺少明确的"执行一次后立即返回"的指示。

**情况C: 没有明确的终止条件**
ReAct agent 需要明确的信号来知道任务已完成。

#### 3. 调试方法

查看完整的消息历史，确认：
1. 每次调用的参数是否相同
2. 每次调用的结果是什么
3. LLM 在每次调用后的"思考"内容

### 解决方案建议

#### 针对问题1: 工具显示

1. **统一工具命名**：确保所有工具使用一致的命名方式
2. **检查工具注册**：验证每个 agent 的 `self.tools` 列表
3. **添加日志**：在工具调用时记录工具名称

#### 针对问题2: 重复调用

**方案A: 优化 System Prompt**
```python
system_msg = f"""你是一个专业的SQL执行专家。
你的任务是：
1. 使用 execute_sql_query 工具执行SQL查询 **一次**
2. 获得结果后，**立即**总结并返回，不要重复执行
3. 如果执行成功，直接报告结果
4. 如果执行失败，报告错误信息

重要：每个SQL查询只执行一次！
"""
```

**方案B: 修改工具返回格式**
```python
return {
    "success": True,
    "data": {...},
    "message": "SQL查询执行成功，返回 X 行数据",  # 添加明确的成功消息
    "should_continue": False  # 明确指示不需要继续
}
```

**方案C: 使用直接工具调用而非 ReAct**
```python
# 不使用 ReAct agent，直接调用工具
async def process(self, state: SQLMessageState):
    sql_query = state.get("generated_sql")
    
    # 直接调用工具，不经过 LLM 推理
    result = execute_sql_query.invoke({
        "sql_query": sql_query,
        "connection_id": state.get("connection_id")
    })
    
    return result
```

**方案D: 限制 ReAct 的最大步数**
```python
self.agent = create_react_agent(
    self.llm,
    self.tools,
    prompt=self._create_system_prompt,
    name=self.name,
    max_iterations=1  # 限制只执行一次
)
```

## 下一步行动

1. **立即检查**：
   - 查看实际的工具调用日志
   - 确认工具名称的一致性
   - 检查消息历史中的 tool_calls 格式

2. **快速修复**：
   - 优化 `sql_executor_agent` 的 system prompt
   - 考虑使用直接工具调用替代 ReAct（最简单有效）

3. **长期优化**：
   - 统一所有工具的命名和返回格式规范
   - 添加工具调用的监控和日志
