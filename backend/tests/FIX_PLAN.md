# 工具显示和重复调用问题修复方案

## 问题总结

### 问题1: 工具显示名称不一致
- **实际工具名**: `retrieve_similar_qa_pairs`
- **前端可能显示**: `retrieve_samples` 或其他
- **原因**: 工具名称和显示名称不匹配

### 问题2: execute_sql_query 重复调用 4 次
- **原因**: ReAct agent 没有明确的终止条件，LLM 认为需要重试
- **影响**: 性能浪费，用户体验差

## 修复方案

### 方案1: 修复 execute_sql_query 重复调用（优先级最高）

#### 选项A: 直接工具调用（推荐）⭐
**优点**: 最简单、最可靠、性能最好
**缺点**: 失去 LLM 的灵活性（但对于 SQL 执行来说不需要）

修改 `backend/app/agents/agents/sql_executor_agent.py`:

```python
async def process(self, state: SQLMessageState) -> Dict[str, Any]:
    """处理SQL执行任务 - 直接调用工具，不使用 ReAct"""
    try:
        # 获取生成的SQL
        sql_query = state.get("generated_sql")
        if not sql_query:
            raise ValueError("没有找到需要执行的SQL语句")
        
        connection_id = state.get("connection_id", 15)
        
        # 直接调用工具，不经过 LLM 推理
        result = execute_sql_query.invoke({
            "sql_query": sql_query,
            "connection_id": connection_id,
            "timeout": 30
        })
        
        # 创建执行结果
        execution_result = SQLExecutionResult(
            success=result.get("success", False),
            data=result.get("data"),
            error=result.get("error"),
            execution_time=result.get("execution_time", 0),
            rows_affected=result.get("rows_affected", 0)
        )
        
        # 更新状态
        state["execution_result"] = execution_result
        if execution_result.success:
            state["current_stage"] = "completed"
        else:
            error_info = {
                "stage": "sql_execution",
                "error": execution_result.error,
                "sql_query": sql_query,
                "retry_count": state.get("retry_count", 0)
            }
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
        
        # 创建消息用于前端显示
        from langchain_core.messages import AIMessage, ToolMessage
        
        # 创建一个 tool call 消息
        tool_call_id = f"call_{hash(sql_query)}"
        ai_message = AIMessage(
            content="",
            tool_calls=[{
                "name": "execute_sql_query",
                "args": {
                    "sql_query": sql_query,
                    "connection_id": connection_id
                },
                "id": tool_call_id
            }]
        )
        
        # 创建对应的 tool message
        tool_message = ToolMessage(
            content=json.dumps(result, ensure_ascii=False),
            tool_call_id=tool_call_id,
            name="execute_sql_query"
        )
        
        return {
            "messages": [ai_message, tool_message],
            "execution_result": execution_result,
            "current_stage": state["current_stage"]
        }
        
    except Exception as e:
        # ... 错误处理保持不变
```

#### 选项B: 限制 ReAct 迭代次数
```python
self.agent = create_react_agent(
    self.llm,
    self.tools,
    prompt=self._create_system_prompt,
    name=self.name,
    max_iterations=1  # 只允许执行一次
)
```

#### 选项C: 优化 System Prompt
```python
def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
    connection_id = extract_connection_id(state)
    system_msg = f"""你是一个专业的SQL执行专家。
    **重要：当前数据库connection_id是 {connection_id}**
    
    你的任务是：
    1. 使用 execute_sql_query 工具执行SQL查询 **仅一次**
    2. 获得结果后，**立即**返回，不要重复执行
    3. 不要尝试重试或验证结果
    
    执行原则：
    - 每个SQL查询只执行一次
    - 执行成功后立即返回结果
    - 执行失败后立即返回错误
    - 不要进行任何额外的验证或重试
    
    **关键**: 调用工具一次后，无论成功或失败，都要立即结束任务！
    """
    return [{"role": "system", "content": system_msg}] + state["messages"]
```

### 方案2: 统一工具命名显示

#### 问题分析
工具的实际名称和期望显示名称不一致：
- `retrieve_similar_qa_pairs` vs `retrieve_samples`
- `generate_sql_query` - 名称正确但可能显示有问题

#### 解决方案

**选项A: 修改工具名称（不推荐）**
会破坏现有代码

**选项B: 在前端添加名称映射（推荐）**
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx

const TOOL_NAME_DISPLAY_MAP: Record<string, string> = {
  "retrieve_similar_qa_pairs": "retrieve_samples",
  "analyze_user_query": "analyze_user_query",
  "generate_sql_query": "generate_sql_query",
  "execute_sql_query": "execute_sql_query",
  // ... 其他工具
};

// 在 ToolCallBox 组件中
const toolName = TOOL_NAME_DISPLAY_MAP[toolCall?.name?.trim()] || toolCall?.name?.trim() || "Unknown Tool";
```

**选项C: 使用 @tool 装饰器的 name 参数**
```python
@tool(name="retrieve_samples")
def retrieve_similar_qa_pairs(...):
    """..."""
```

但这会改变工具的实际调用名称，可能影响其他地方。

### 方案3: 检查工具调用消息格式

确保所有 agent 返回的消息格式一致：

```python
# 标准格式
{
    "messages": [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "tool_name",  # 必须有
                "args": {...},         # 必须有
                "id": "call_xxx"       # 必须有
            }]
        ),
        ToolMessage(
            content="...",
            tool_call_id="call_xxx",  # 必须匹配
            name="tool_name"           # 必须匹配
        )
    ]
}
```

## 实施步骤

### 第一步: 修复 execute_sql_query 重复调用（立即执行）

1. 采用**选项A: 直接工具调用**
2. 修改 `sql_executor_agent.py` 的 `process` 方法
3. 测试确认只调用一次

### 第二步: 检查工具显示问题

1. 添加日志记录实际的工具调用
2. 确认前端收到的 tool_calls 格式
3. 根据实际情况选择修复方案

### 第三步: 统一其他 agent 的调用方式

考虑将其他 agent 也改为直接工具调用：
- `schema_agent`: 可以保留 ReAct（需要灵活性）
- `sql_generator_agent`: 可以保留 ReAct（需要灵活性）
- `sql_executor_agent`: 改为直接调用（推荐）✅
- `chart_generator_agent`: 可以保留 ReAct

## 预期效果

### 修复后
- ✅ `execute_sql_query` 只调用一次
- ✅ 工具显示名称正确
- ✅ 性能提升（减少不必要的 LLM 调用）
- ✅ 用户体验改善

### 风险评估
- 🟢 低风险：直接工具调用不会影响其他功能
- 🟢 易回滚：如果有问题可以快速恢复
- 🟢 向后兼容：不影响其他 agent
