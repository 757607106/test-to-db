# Agent消息和Tools返回格式问题分析

## 核心问题总结

### 1. **Tool返回格式不统一**

#### 问题描述
后端tools返回的内容格式混乱，有的返回Dict，有的返回JSON字符串，前端需要多重判断才能正确渲染。

#### 具体表现

**A. Tool函数直接返回Dict对象**
```python
# backend/app/agents/agents/sql_executor_agent.py:24
@tool
def execute_sql_query(sql_query: str, connection_id, timeout: int = 30) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {...},
        "error": None,
        # ...
    }
```

**B. Agent手动创建ToolMessage时包装成JSON字符串**
```python
# backend/app/agents/agents/sql_executor_agent.py:360
tool_message = ToolMessage(
    content=json.dumps(result, ensure_ascii=False),  # ← 手动序列化
    tool_call_id=tool_call_id,
    name="execute_sql_query",
)
```

**C. MCP工具包装器的双重序列化**
```python
# backend/app/core/message_utils.py:114
result = await self.mcp_tool.ainvoke(kwargs if kwargs else {})
return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
```

**结果**: 前端收到的tool result可能是：
- 原始Dict对象
- JSON字符串
- 嵌套JSON字符串（二次序列化）

---

### 2. **前端渲染判断逻辑过于复杂**

#### 问题代码
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx:299-314
if (toolResult) {
  try {
    if (typeof toolResult.content === "string") {
      toolResult_content = JSON.parse(toolResult.content);  // 尝试解析
      resultAsText = toolResult.content;
    } else {
      toolResult_content = toolResult.content;  // 直接使用
      resultAsText = JSON.stringify(toolResult.content, null, 2);
    }
  } catch {
    toolResult_content = toolResult.content;  // 解析失败，原样使用
    resultAsText = String(toolResult.content);
  }
}
```

**多重判断路径**:
1. 检查是否为字符串 → 尝试JSON.parse
2. 不是字符串 → 直接使用
3. 解析失败 → 当作普通字符串

---

### 3. **AIMessage content格式混乱**

#### A. AI消息可能包含工具返回的JSON
```typescript
// frontend/chat/src/components/thread/utils.ts:25-111
function filterToolResultJson(text: string): string {
  // 需要过滤掉混入AI消息中的工具返回JSON
  const toolResultPatterns = [
    /\{\s*["']needs_clarification["']\s*:\s*(?:true|false)[^}]*\}/gi,
    /\{\s*["']success["']\s*:\s*(?:true|false)[^}]*["']questions["']\s*:\s*\[[^\]]*\][^}]*\}/gi,
    // ... 更多模式
  ];
}
```

**问题**: AI消息的content字段混入了工具返回的JSON，需要复杂的正则表达式过滤。

#### B. Content可能是string或array
```typescript
// frontend/chat/src/components/thread/utils.ts:10-19
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") {
    return filterToolResultJson(content);
  }
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => filterToolResultJson(c.text));
  return texts.join(" ").trim();
}
```

---

### 4. **Tool Call状态判断不一致**

#### 问题代码
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx:324-342
const isHandoffTool = toolName.startsWith("transfer_to_");

const isError = toolResult_content && (
  (typeof toolResult_content === 'object' && 
   ('error' in toolResult_content || 
    'status' in toolResult_content && toolResult_content.status === 'error')) ||
  (typeof toolResult_content === 'string' && 
   toolResult_content.toLowerCase().includes('error'))
);
```

**问题**: 
- 需要多重类型检查（object vs string）
- 错误标识不统一（error字段 vs status字段 vs 字符串包含"error"）
- Handoff工具特殊处理

---

### 5. **图像提取逻辑过于复杂**

#### 问题代码
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx:61-165
function extractImagesFromText(text: string): Array<...> {
  // Pattern 1: data URL
  // Pattern 2: HTTP/HTTPS URLs
  // Pattern 3: 特定CDN URLs (Alipay, imgur, etc.)
  // Pattern 4: JSON字段中的base64
  // Pattern 5: 长base64字符串
  // ... 去重逻辑
}
```

**问题**: 需要5种不同的模式匹配来提取图像，说明返回格式不统一。

---

## 根本原因

### 1. **缺乏统一的返回格式规范**
- Tools返回Dict或字符串随意
- 没有标准的错误格式
- 没有标准的成功响应格式

### 2. **多层序列化导致格式混乱**
```
Tool返回Dict → Agent序列化为JSON → LangGraph传递 → 前端解析
              ↓
         有的直接传递Dict，有的传递JSON字符串
```

### 3. **AI消息和Tool消息混淆**
- AI消息content中混入tool返回的JSON
- 缺乏清晰的消息类型边界

### 4. **缺乏类型定义和验证**
- 后端没有Pydantic模型验证返回格式
- 前端没有TypeScript类型定义约束

---

## 建议的统一格式

### 后端 Tool 返回标准格式
```python
from typing import TypedDict, Any, Optional

class ToolResponse(TypedDict):
    """统一的Tool返回格式"""
    status: str  # "success" | "error" | "pending"
    data: Optional[Any]  # 实际数据
    error: Optional[str]  # 错误信息
    metadata: Optional[Dict[str, Any]]  # 元数据（如execution_time等）
```

### 前端类型定义
```typescript
interface ToolResult {
  status: "success" | "error" | "pending";
  data?: any;
  error?: string;
  metadata?: Record<string, any>;
}
```

---

## 需要修复的关键位置

### 后端
1. `backend/app/agents/agents/sql_executor_agent.py:24,360-364` - execute_sql_query返回格式 + ToolMessage序列化
2. `backend/app/agents/agents/sql_generator_agent.py:114-226` - generate_sql_query返回格式
3. `backend/app/agents/agents/schema_agent.py` - 所有tool返回格式
4. `backend/app/agents/agents/chart_generator_agent.py` - 所有tool返回格式
5. `backend/app/agents/agents/sample_retrieval_agent.py:131-186` - retrieve_similar_qa_pairs返回格式（多种error结构）
6. `backend/app/core/message_utils.py:114,174` - MCPToolWrapper双重序列化
7. **创建统一的ToolResponse基类**

### 前端
1. `frontend/chat/src/components/thread/messages/tool-calls.tsx:299-352` - 简化tool result解析逻辑
2. `frontend/chat/src/components/thread/messages/tool-calls.tsx:324-342` - 统一错误判断逻辑
3. `frontend/chat/src/components/thread/messages/tool-calls.tsx:521` - tool name过滤（说明后端可能返回空name）
4. `frontend/chat/src/components/thread/messages/ai.tsx:146` - tool name过滤
5. `frontend/chat/src/components/thread/utils.ts:25-111` - 移除复杂的工具JSON过滤逻辑
6. **创建统一的ToolResult类型定义**
7. **简化错误判断逻辑**

---

### 6. **Tool Name为空的问题**

#### 问题代码
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx:521
const validToolCalls = toolCalls.filter(tc => tc && tc.name && tc.name.trim() !== "");

// frontend/chat/src/components/thread/messages/ai.tsx:146
.filter((tc) => tc.name && tc.name.trim() !== ""); // Filter out empty names
```

**问题**: 前端需要过滤空name的tool calls，说明后端可能返回name为空字符串或undefined的tool calls。

**可能原因**:
- Anthropic流式工具调用解析错误
- LangGraph工具调用格式不正确
- 某些agent没有正确设置tool name

---

### 7. **Tool Call ID重复问题**

#### 问题代码
```typescript
// frontend/chat/src/components/thread/messages/tool-calls.tsx:21-37
function fixDuplicatedToolCallId(toolCallId: string): string {
  const len = toolCallId.length;
  if (len % 2 === 0) {
    const half = len / 2;
    const firstHalf = toolCallId.substring(0, half);
    const secondHalf = toolCallId.substring(half);
    if (firstHalf === secondHalf) {
      return firstHalf;  // "call_xxxcall_xxx" → "call_xxx"
    }
  }
  return toolCallId;
}
```

**问题**: Tool call ID会重复（如"call_xxxcall_xxx"），前端需要特殊处理来修复。

**影响**: 
- Tool calls无法正确匹配对应的tool results
- 渲染时可能显示错误的结果

---

## 影响范围

### 高优先级
- Tool返回格式混乱导致渲染失败
- 错误状态判断不准确
- AI消息混入JSON需要过滤

### 中优先级
- 图像提取逻辑复杂
- Content类型不统一

### 低优先级
- Handoff工具特殊处理
