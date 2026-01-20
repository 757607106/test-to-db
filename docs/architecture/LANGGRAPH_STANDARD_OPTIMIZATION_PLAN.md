# LangGraph标准模式优化计划

## 核心原则

**严格遵循LangGraph官方示例和标准模式，确保代码易维护、符合最佳实践。**

---

## 1. LangGraph标准节点模式

### 1.1 节点函数签名标准

根据[LangGraph官方文档](https://context7.com/langchain-ai/langgraph/llms.txt)，标准节点函数遵循：

```python
# 同步节点 (官方标准)
def my_node(state: MyState) -> dict:
    """
    标准LangGraph节点
    - 接收state (TypedDict)
    - 返回dict (部分状态更新)
    """
    # 处理逻辑
    return {"key": "value"}

# 异步节点 (官方标准)
async def my_async_node(state: MyState) -> dict:
    """
    异步LangGraph节点
    - 可以使用await
    - 返回dict
    """
    result = await some_async_operation()
    return {"key": result}
```

**关键点**:
- ✅ 简单的函数签名
- ✅ 返回dict而不是完整state
- ✅ LangGraph自动合并返回的dict到state
- ❌ 不要返回完整state对象
- ❌ 不要过度设计

---

## 2. interrupt()使用标准 (Human-in-the-Loop)

### 2.1 官方示例

```python
from langgraph.types import interrupt
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def approval_node(state: ApprovalState) -> dict:
    """使用interrupt()暂停等待用户确认"""
    # ✅ 使用interrupt()暂停执行
    user_response = interrupt({
        "question": f"Approve action: {state['action']}?",
        "options": ["yes", "no"]
    })
    
    # 执行到这里说明用户已回复
    # user_response包含用户的输入
    approved = (user_response == "yes")
    
    return {"approved": approved}

# ✅ 必须使用checkpointer
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# 启动执行 (会在interrupt处暂停)
config = {"configurable": {"thread_id": "thread-1"}}
for chunk in graph.stream(initial_state, config):
    print(chunk)  # 打印到interrupt为止

# 恢复执行
from langgraph.types import Command
for chunk in graph.stream(Command(resume="yes"), config):
    print(chunk)  # 从interrupt继续执行
```

**关键点**:
- ✅ `interrupt()`返回用户输入
- ✅ 必须有checkpointer
- ✅ 使用`Command(resume=...)`恢复
- ❌ 不需要复杂的状态标记
- ❌ 不需要手动管理pending状态

---

## 3. 优化任务分解

### Phase 1: 澄清机制标准化 (基于interrupt)

**文件**: `backend/app/agents/nodes/clarification_node.py`

**当前问题**:
- 使用`pending_clarification`状态标记
- 手动管理多轮对话
- 代码复杂，难以维护

**优化方案** (LangGraph标准):

```python
from langgraph.types import interrupt
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    澄清节点 - LangGraph标准interrupt模式
    
    遵循官方示例: https://context7.com/langchain-ai/langgraph/llms.txt
    """
    logger.info("=== 澄清节点 ===")
    
    # 1. 提取用户查询
    messages = state.get("messages", [])
    user_query = None
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break
    
    if not user_query:
        return {"current_stage": "schema_analysis"}
    
    # 2. 规范化查询
    if isinstance(user_query, list):
        user_query = user_query[0].get("text", "") if user_query else ""
    
    # 3. 检查是否需要澄清
    connection_id = state.get("connection_id", 15)
    check_result = quick_clarification_check(
        query=user_query,
        connection_id=connection_id
    )
    
    if not check_result.get("needs_clarification"):
        # 不需要澄清
        return {
            "original_query": user_query,
            "current_stage": "schema_analysis"
        }
    
    # 4. ✅ 使用interrupt()暂停等待用户确认 (LangGraph标准)
    formatted_questions = format_clarification_questions(
        check_result.get("questions", [])
    )
    
    logger.info(f"需要澄清，暂停执行等待用户回复")
    
    # interrupt()会暂停执行，返回数据给客户端
    # 用户回复后，LangGraph自动恢复执行，user_response包含用户输入
    user_response = interrupt({
        "type": "clarification_request",
        "questions": formatted_questions,
        "reason": check_result.get("reason", "查询存在模糊性"),
        "original_query": user_query
    })
    
    logger.info(f"收到用户回复: {user_response}")
    
    # 5. 处理用户回复
    parsed_answers = parse_user_clarification_response(
        user_response, 
        formatted_questions
    )
    
    if parsed_answers:
        enrich_result = enrich_query_with_clarification(
            original_query=user_query,
            clarification_responses=parsed_answers
        )
        enriched_query = enrich_result.get("enriched_query", user_query)
    else:
        enriched_query = user_query
    
    # 6. ✅ 返回状态更新 (LangGraph标准)
    return {
        "clarification_responses": parsed_answers,
        "enriched_query": enriched_query,
        "original_query": user_query,
        "current_stage": "schema_analysis"
    }
```

**需要移除**:
- ❌ `pending_clarification`字段
- ❌ `clarification_confirmed`字段
- ❌ 复杂的轮次管理逻辑
- ❌ 手动的消息历史处理

**保留**:
- ✅ `original_query`
- ✅ `enriched_query`
- ✅ `clarification_responses`

---

### Phase 2: 并行缓存检查 (标准异步模式)

**文件**: `backend/app/agents/nodes/cache_check_node.py`

**优化方案** (LangGraph + asyncio标准):

```python
import asyncio
from typing import Dict, Any

async def cache_check_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    缓存检查节点 - LangGraph标准异步节点
    
    使用Python标准asyncio实现并发
    """
    logger.info("=== 缓存检查 (并行) ===")
    
    # 提取查询
    messages = state.get("messages", [])
    user_query = extract_user_query(messages)
    connection_id = state.get("connection_id", 15)
    
    if not user_query:
        return {"cache_hit": False}
    
    cache_service = get_cache_service()
    
    # ✅ 使用asyncio.create_task并发执行 (Python标准)
    l1_task = asyncio.create_task(
        cache_service.check_exact_cache(user_query, connection_id)
    )
    l2_task = asyncio.create_task(
        cache_service.check_semantic_cache(user_query, connection_id)
    )
    
    try:
        # ✅ wait for first completed (Python asyncio标准)
        done, pending = await asyncio.wait(
            {l1_task, l2_task},
            return_when=asyncio.FIRST_COMPLETED,
            timeout=2.0
        )
        
        # 处理第一个完成的结果
        for task in done:
            result = task.result()
            if result:  # 缓存命中
                # 取消未完成的任务
                for p in pending:
                    p.cancel()
                
                logger.info(f"缓存命中: {result.hit_type}")
                return {
                    "cache_hit": True,
                    "cache_hit_type": result.hit_type,
                    "generated_sql": result.sql,
                    "execution_result": result.result
                }
        
        # 等待剩余任务
        if pending:
            remaining = await asyncio.gather(*pending, return_exceptions=True)
            for result in remaining:
                if isinstance(result, CacheHit):
                    return {
                        "cache_hit": True,
                        "cache_hit_type": result.hit_type,
                        "generated_sql": result.sql
                    }
    
    except asyncio.TimeoutError:
        logger.warning("缓存超时，跳过")
    
    return {"cache_hit": False}
```

**性能提升**: 25% (400ms → 300ms)

---

### Phase 3: SSE流式API (LangGraph astream标准)

**文件**: `backend/app/api/api_v1/endpoints/query.py`

**新增endpoint** (遵循LangGraph官方流式示例):

```python
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import json

@router.post("/chat/stream")
async def chat_stream(
    chat_request: schemas.ChatQueryRequest,
    db: Session = Depends(deps.get_db)
) -> EventSourceResponse:
    """
    SSE流式API - 基于LangGraph官方astream示例
    
    参考: https://github.com/langchain-ai/langgraph/examples
    """
    
    async def event_generator():
        thread_id = chat_request.conversation_id or str(uuid4())
        graph = IntelligentSQLGraph()
        
        initial_state = SQLMessageState(
            messages=[HumanMessage(content=chat_request.natural_language_query)],
            connection_id=chat_request.connection_id
        )
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # ✅ 使用astream流式执行 (LangGraph官方标准)
        async for chunk in graph.graph.astream(
            initial_state,
            config=config,
            stream_mode="updates"  # 官方推荐: updates模式
        ):
            # chunk格式: {node_name: node_output}
            for node_name, node_output in chunk.items():
                yield {
                    "event": "node_update",
                    "data": json.dumps({
                        "node": node_name,
                        "stage": node_output.get("current_stage"),
                        "timestamp": time.time()
                    })
                }
        
        # 完成事件
        yield {
            "event": "complete",
            "data": json.dumps({"thread_id": thread_id})
        }
    
    return EventSourceResponse(event_generator())
```

**stream_mode选项** (LangGraph官方):
- `"updates"` - 每个节点执行后的增量更新 ✅ 推荐
- `"values"` - 每个节点执行后的完整状态
- `"custom"` - 自定义StreamWriter数据

---

### Phase 4: 恢复执行API (Command标准)

**文件**: `backend/app/api/api_v1/endpoints/query.py`

**新增endpoint**:

```python
from langgraph.types import Command

@router.post("/chat/resume")
async def resume_chat(
    thread_id: str,
    user_response: Any,
    db: Session = Depends(deps.get_db)
):
    """
    恢复被interrupt暂停的执行
    
    基于LangGraph官方Command模式
    """
    graph = IntelligentSQLGraph()
    config = {"configurable": {"thread_id": thread_id}}
    
    # ✅ 使用Command(resume=...)恢复 (LangGraph标准)
    result = await graph.graph.ainvoke(
        Command(resume=user_response),
        config=config
    )
    
    return {"success": True, "result": result}
```

---

## 4. 确保Checkpointer正确配置

**文件**: `backend/app/agents/chat_graph.py`

**关键检查**:

```python
def _create_graph_with_agent_loader(self):
    from langgraph.graph import StateGraph, END
    from app.core.checkpointer import get_checkpointer
    
    graph = StateGraph(SQLMessageState)
    
    # 添加节点
    graph.add_node("clarification", clarification_node)
    graph.add_node("cache_check", cache_check_node)
    # ...
    
    # ✅ 必须有checkpointer才能使用interrupt
    checkpointer = get_checkpointer()
    if not checkpointer:
        raise RuntimeError(
            "Checkpointer未配置，无法支持interrupt澄清机制。"
            "请确保CHECKPOINT_MODE=postgres且CHECKPOINT_POSTGRES_URI已配置。"
        )
    
    return graph.compile(checkpointer=checkpointer)
```

---

## 5. 实施清单

### 高优先级 (Week 1)

- [ ] **澄清节点标准化**
  - 移除`pending_clarification`等复杂状态
  - 使用`interrupt()`替代
  - 简化代码逻辑
  - 测试interrupt暂停和恢复

- [ ] **缓存并行查询**
  - 修改为异步节点`async def`
  - 使用`asyncio.wait`并发查询L1/L2
  - 添加超时保护
  - 性能测试

- [ ] **Resume API**
  - 实现`/chat/resume` endpoint
  - 使用`Command(resume=...)`
  - 前端集成测试

### 中优先级 (Week 2)

- [ ] **SSE流式API**
  - 实现`/chat/stream` endpoint
  - 使用`graph.astream(stream_mode="updates")`
  - 前端EventSource集成

- [ ] **Checkpointer验证**
  - 确保PostgreSQL checkpointer正常工作
  - 添加健康检查
  - 错误处理优化

### 低优先级 (Week 3)

- [ ] **性能监控**
  - 添加Prometheus指标
  - 异步任务耗时追踪
  - 慢查询日志

- [ ] **测试完善**
  - interrupt测试用例
  - 并行缓存测试
  - 流式API测试

---

## 6. 关键注意事项

### ✅ DO - 遵循LangGraph标准

1. **使用标准节点签名**
   ```python
   def node(state: State) -> dict  # 或 async def
   ```

2. **使用interrupt()暂停执行**
   ```python
   response = interrupt({"question": "..."})
   ```

3. **使用Command恢复执行**
   ```python
   graph.invoke(Command(resume=user_input), config)
   ```

4. **使用astream流式执行**
   ```python
   async for chunk in graph.astream(state, stream_mode="updates"):
       ...
   ```

### ❌ DON'T - 避免过度设计

1. ❌ 不要手动管理pending状态
2. ❌ 不要返回完整state对象
3. ❌ 不要重新发明轮子（使用LangGraph内置功能）
4. ❌ 不要混用不同的并发模式

---

## 7. 性能预期

| 指标 | 优化前 | 优化后 | 提升 |
|------|-------|-------|------|
| 澄清机制 | 复杂状态管理 | interrupt()标准 | 代码简化50% |
| 缓存查询 | 400ms串行 | 300ms并行 | 25%提升 |
| 用户体验 | 无实时反馈 | SSE流式推送 | 显著提升 |
| 代码维护性 | 自定义逻辑 | LangGraph标准 | 易维护 |

---

## 8. 参考文档

- [LangGraph官方文档](https://langchain-ai.github.io/langgraph/)
- [interrupt()示例](https://context7.com/langchain-ai/langgraph/llms.txt)
- [流式执行示例](https://github.com/langchain-ai/langgraph/examples)
- [Command API](https://langchain-ai.github.io/langgraph/reference/types/)

---

**版本**: v2.0  
**日期**: 2026-01-20  
**核心原则**: 遵循LangGraph官方标准，避免过度设计，保持简洁易维护
