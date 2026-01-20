# 异步优化实战示例

## 1. 流式响应API实现

### 1.1 SSE (Server-Sent Events) 流式API

**场景**: 实时推送agent执行进度，提升用户体验

```python
# backend/app/api/api_v1/endpoints/query.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
from typing import AsyncGenerator

router = APIRouter()

@router.post("/chat/stream")
async def chat_query_stream(
    chat_request: schemas.ChatQueryRequest,
    db: Session = Depends(deps.get_db)
) -> EventSourceResponse:
    """
    流式聊天查询接口
    
    实时推送:
    - 节点执行进度
    - 中间结果
    - 最终结果
    
    前端使用EventSource接收
    """
    
    async def event_generator() -> AsyncGenerator[dict, None]:
        """生成SSE事件流"""
        try:
            # 创建图实例
            thread_id = chat_request.conversation_id or str(uuid4())
            graph = IntelligentSQLGraph()
            
            # 构建初始状态
            initial_state = SQLMessageState(
                messages=[HumanMessage(content=chat_request.natural_language_query)],
                connection_id=chat_request.connection_id,
                thread_id=thread_id,
                current_stage="schema_analysis"
            )
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # 流式执行图
            async for chunk in graph.graph.astream(
                initial_state, 
                config=config,
                stream_mode="updates"  # 每个节点执行后推送更新
            ):
                for node_name, node_output in chunk.items():
                    # 格式化节点输出
                    event_data = {
                        "type": "node_update",
                        "node": node_name,
                        "stage": node_output.get("current_stage", "processing"),
                        "timestamp": time.time()
                    }
                    
                    # 添加节点特定数据
                    if node_name == "cache_check":
                        event_data["cache_hit"] = node_output.get("cache_hit", False)
                    
                    elif node_name == "clarification":
                        if node_output.get("needs_clarification"):
                            event_data["clarification_questions"] = node_output.get("clarification_questions", [])
                    
                    elif node_name == "supervisor":
                        # 提取SQL和执行结果
                        if node_output.get("generated_sql"):
                            event_data["sql"] = node_output["generated_sql"]
                        if node_output.get("execution_result"):
                            exec_result = node_output["execution_result"]
                            event_data["result_preview"] = {
                                "success": exec_result.success,
                                "row_count": len(exec_result.data) if exec_result.data else 0
                            }
                    
                    # 推送事件
                    yield {
                        "event": "update",
                        "data": json.dumps(event_data, ensure_ascii=False)
                    }
                    
                    # 小延迟，避免前端处理不过来
                    await asyncio.sleep(0.1)
            
            # 发送完成事件
            yield {
                "event": "complete",
                "data": json.dumps({
                    "type": "complete",
                    "thread_id": thread_id
                })
            }
        
        except Exception as e:
            # 错误事件
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e)
                })
            }
    
    return EventSourceResponse(event_generator())
```

---

### 1.2 前端集成 (TypeScript/React)

```typescript
// frontend/chat/src/hooks/useStreamingChat.ts

import { useEffect, useState } from 'react';

interface StreamEvent {
  type: 'node_update' | 'complete' | 'error';
  node?: string;
  stage?: string;
  cache_hit?: boolean;
  sql?: string;
  result_preview?: {
    success: boolean;
    row_count: number;
  };
  error?: string;
}

export function useStreamingChat(queryRequest: ChatQueryRequest) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStage, setCurrentStage] = useState<string>('');

  useEffect(() => {
    if (!queryRequest.natural_language_query) return;

    setIsStreaming(true);
    setEvents([]);

    // 创建EventSource连接
    const eventSource = new EventSource('/api/query/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(queryRequest)
    });

    eventSource.addEventListener('update', (e) => {
      const data: StreamEvent = JSON.parse(e.data);
      setEvents(prev => [...prev, data]);
      
      // 更新UI状态
      if (data.stage) {
        setCurrentStage(getStageLabel(data.stage));
      }
    });

    eventSource.addEventListener('complete', () => {
      setIsStreaming(false);
      eventSource.close();
    });

    eventSource.addEventListener('error', (e) => {
      console.error('Stream error:', e);
      setIsStreaming(false);
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [queryRequest]);

  return { events, isStreaming, currentStage };
}

function getStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    'cache_check': '🔍 检查缓存...',
    'schema_analysis': '📊 分析数据库结构...',
    'sql_generation': '⚙️ 生成SQL查询...',
    'sql_execution': '🚀 执行查询...',
    'chart_generation': '📈 生成可视化图表...',
    'completed': '✅ 完成'
  };
  return labels[stage] || '⏳ 处理中...';
}
```

---

### 1.3 UI组件示例

```tsx
// frontend/chat/src/components/StreamingChatInterface.tsx

export function StreamingChatInterface() {
  const [query, setQuery] = useState('');
  const { events, isStreaming, currentStage } = useStreamingChat({
    natural_language_query: query,
    connection_id: 15
  });

  return (
    <div className="streaming-chat">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="请输入查询..."
      />
      
      {isStreaming && (
        <div className="progress-indicator">
          <div className="spinner"></div>
          <span>{currentStage}</span>
        </div>
      )}

      <div className="events-timeline">
        {events.map((event, idx) => (
          <EventCard key={idx} event={event} />
        ))}
      </div>
    </div>
  );
}

function EventCard({ event }: { event: StreamEvent }) {
  return (
    <div className={`event-card ${event.type}`}>
      <div className="event-header">
        <span className="node-name">{event.node}</span>
        <span className="timestamp">{new Date().toLocaleTimeString()}</span>
      </div>
      
      {event.cache_hit && (
        <div className="cache-hit">
          ⚡ 缓存命中，快速返回结果
        </div>
      )}
      
      {event.sql && (
        <pre className="sql-preview">
          <code>{event.sql}</code>
        </pre>
      )}
      
      {event.result_preview && (
        <div className="result-preview">
          {event.result_preview.success ? (
            `✅ 查询成功，返回 ${event.result_preview.row_count} 条记录`
          ) : (
            `❌ 查询失败`
          )}
        </div>
      )}
    </div>
  );
}
```

---

## 2. 并行缓存检查优化

### 2.1 优化前 (串行检查)

```python
# 当前实现 - 串行检查L1和L2缓存
async def cache_check_node(state: SQLMessageState) -> Dict[str, Any]:
    cache_service = get_cache_service()
    
    # 先检查精确匹配 (L1)
    exact_hit = await cache_service.check_exact_cache(query, conn_id)
    if exact_hit:
        return format_cache_result(exact_hit)
    
    # 未命中，再检查语义匹配 (L2)
    semantic_hit = await cache_service.check_semantic_cache(query, conn_id)
    if semantic_hit:
        return format_cache_result(semantic_hit)
    
    return {"cache_hit": False}

# 性能: L1 (100ms) + L2 (300ms) = 400ms
```

---

### 2.2 优化后 (并行检查)

```python
# backend/app/agents/nodes/cache_check_node_optimized.py

import asyncio
from typing import Optional, Union

async def cache_check_node_parallel(state: SQLMessageState) -> Dict[str, Any]:
    """
    并行检查L1和L2缓存，先返回的结果生效
    
    性能提升:
    - 串行: L1 + L2 = 100ms + 300ms = 400ms
    - 并行: max(L1, L2) = max(100ms, 300ms) = 300ms
    - 提升: 25%
    """
    logger.info("=== 并行缓存检查 ===")
    
    cache_service = get_cache_service()
    query = extract_user_query(state.get("messages", []))
    conn_id = state.get("connection_id", 15)
    
    # 创建并行任务
    l1_task = asyncio.create_task(
        cache_service.check_exact_cache(query, conn_id),
        name="L1_exact_cache"
    )
    
    l2_task = asyncio.create_task(
        cache_service.check_semantic_cache(query, conn_id),
        name="L2_semantic_cache"
    )
    
    # 等待第一个完成的任务
    done, pending = await asyncio.wait(
        {l1_task, l2_task},
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # 获取第一个完成的结果
    first_result: Optional[CacheHit] = None
    for task in done:
        result = task.result()
        if result:  # 命中缓存
            first_result = result
            logger.info(f"缓存命中: {task.get_name()}")
            break
    
    # 取消未完成的任务
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    if first_result:
        return {
            "cache_hit": True,
            "cache_hit_type": first_result.hit_type,
            "generated_sql": first_result.sql,
            # ...
        }
    
    # 等待所有任务完成，检查是否有其他命中
    if pending:
        remaining_results = await asyncio.gather(*pending, return_exceptions=True)
        for result in remaining_results:
            if isinstance(result, CacheHit):
                return format_cache_result(result)
    
    return {"cache_hit": False}
```

---

### 2.3 高级优化 - 超时和退化

```python
async def cache_check_node_with_timeout(state: SQLMessageState) -> Dict[str, Any]:
    """
    带超时的并行缓存检查
    
    如果缓存查询超时，直接跳过缓存继续执行
    避免缓存服务故障影响主流程
    """
    try:
        # 设置总超时时间
        return await asyncio.wait_for(
            cache_check_node_parallel(state),
            timeout=2.0  # 2秒超时
        )
    except asyncio.TimeoutError:
        logger.warning("缓存查询超时，跳过缓存继续执行")
        return {
            "cache_hit": False,
            "cache_timeout": True
        }
    except Exception as e:
        logger.error(f"缓存查询异常: {e}")
        # 降级处理，继续执行
        return {
            "cache_hit": False,
            "cache_error": str(e)
        }
```

---

## 3. 异步ORM迁移示例

### 3.1 当前同步实现

```python
# backend/app/agents/chat_graph.py (当前)

async def _load_custom_agent_node(self, state):
    """加载自定义agent - 使用同步数据库"""
    from app.db.session import SessionLocal
    
    # ⚠️ 同步数据库会话
    db = SessionLocal()
    try:
        # ⚠️ 同步查询 - 阻塞事件循环
        profile = crud_agent_profile.get(db=db, id=agent_id)
        
        if profile and not profile.is_system:
            custom_analyst = create_custom_analyst_agent(profile, db)
            # ...
    finally:
        db.close()
```

---

### 3.2 迁移到异步ORM

#### Step 1: 配置异步引擎

```python
# backend/app/db/async_session.py (新增)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from app.core.config import settings

# 创建异步引擎
async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI.replace(
        "mysql://", "mysql+aiomysql://"
    ),
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_async_db():
    """异步数据库依赖注入"""
    async with AsyncSessionLocal() as session:
        yield session
```

---

#### Step 2: 改写CRUD操作

```python
# backend/app/crud/async_crud_agent_profile.py (新增)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent_profile import AgentProfile

class AsyncCRUDAgentProfile:
    """异步Agent Profile CRUD"""
    
    async def get(
        self, 
        db: AsyncSession, 
        id: int
    ) -> Optional[AgentProfile]:
        """异步查询单个profile"""
        result = await db.execute(
            select(AgentProfile).where(AgentProfile.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[AgentProfile]:
        """异步查询多个profiles"""
        result = await db.execute(
            select(AgentProfile)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create(
        self,
        db: AsyncSession,
        obj_in: AgentProfileCreate
    ) -> AgentProfile:
        """异步创建profile"""
        db_obj = AgentProfile(**obj_in.dict())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

async_agent_profile = AsyncCRUDAgentProfile()
```

---

#### Step 3: 更新节点使用异步查询

```python
# backend/app/agents/chat_graph.py (更新)

async def _load_custom_agent_node(self, state):
    """✅ 使用异步数据库加载自定义agent"""
    from app.db.async_session import AsyncSessionLocal
    from app.crud.async_crud_agent_profile import async_agent_profile
    
    agent_id = extract_agent_id_from_messages(state.get("messages", []))
    
    if agent_id:
        # ✅ 异步数据库会话
        async with AsyncSessionLocal() as db:
            # ✅ 异步查询 - 不阻塞事件循环
            profile = await async_agent_profile.get(db=db, id=agent_id)
            
            if profile and not profile.is_system:
                # ✅ 异步创建自定义agent
                custom_analyst = await create_custom_analyst_agent_async(
                    profile, 
                    db
                )
                
                self.supervisor_agent = create_intelligent_sql_supervisor(
                    custom_analyst=custom_analyst
                )
                
                logger.info(f"成功加载自定义agent: {profile.name}")
    
    return state
```

---

### 3.3 性能对比

**场景: 100个并发请求，每个需要查询1次数据库**

| 模式 | 数据库查询时间 | 总响应时间 | QPS | 备注 |
|------|-------------|-----------|-----|------|
| 同步ORM | 50ms (阻塞) | 8.5秒 | 12 | 阻塞事件循环 |
| 异步ORM | 50ms (非阻塞) | 1.2秒 | 85 | 完全异步 |

**提升: 7倍吞吐量**

---

## 4. 自定义StreamWriter实现

### 4.1 SQL执行进度流式推送

```python
# backend/app/agents/agents/sql_executor_agent.py (增强)

from langgraph.types import StreamWriter
from typing import Optional

async def sql_executor_node_streaming(
    state: SQLMessageState,
    writer: Optional[StreamWriter] = None
) -> SQLMessageState:
    """
    支持流式进度推送的SQL执行节点
    
    推送事件:
    - validating: SQL验证中
    - executing: 执行查询中
    - formatting: 格式化结果中
    - completed: 执行完成
    """
    
    # 推送验证阶段
    if writer:
        writer({
            "type": "progress",
            "stage": "validating",
            "message": "正在验证SQL查询..."
        })
    
    # 验证SQL
    sql = state.get("generated_sql", "")
    if not sql:
        raise ValueError("未找到SQL查询")
    
    # 推送执行阶段
    if writer:
        writer({
            "type": "progress",
            "stage": "executing",
            "message": "正在执行查询...",
            "sql": sql
        })
    
    # 执行SQL
    connection_id = state.get("connection_id", 15)
    start_time = time.time()
    
    result = execute_sql_query.invoke({
        "sql_query": sql,
        "connection_id": connection_id,
        "timeout": 30
    })
    
    execution_time = time.time() - start_time
    
    # 推送格式化阶段
    if writer:
        writer({
            "type": "progress",
            "stage": "formatting",
            "message": "正在格式化结果...",
            "execution_time": execution_time
        })
    
    # 格式化结果
    if result.get("success"):
        data = result.get("data", [])
        
        execution_result = SQLExecutionResult(
            success=True,
            data=data,
            error=None,
            execution_time=execution_time,
            rows_affected=len(data)
        )
        
        # 推送完成事件
        if writer:
            writer({
                "type": "progress",
                "stage": "completed",
                "message": f"查询成功，返回 {len(data)} 条记录",
                "row_count": len(data),
                "execution_time": execution_time
            })
        
        return {
            "execution_result": execution_result,
            "current_stage": "sql_execution_completed"
        }
    
    else:
        # 错误推送
        if writer:
            writer({
                "type": "error",
                "stage": "failed",
                "message": "查询执行失败",
                "error": result.get("error")
            })
        
        raise RuntimeError(f"SQL执行失败: {result.get('error')}")
```

---

### 4.2 前端实时接收进度

```typescript
// 前端监听自定义事件流

async function executeSQLWithProgress(query: string) {
  const eventSource = new EventSource('/api/query/chat/stream');
  
  eventSource.addEventListener('progress', (e) => {
    const progress = JSON.parse(e.data);
    
    switch (progress.stage) {
      case 'validating':
        showProgress('验证SQL...', 10);
        break;
      
      case 'executing':
        showProgress('执行查询...', 40);
        showSQL(progress.sql);
        break;
      
      case 'formatting':
        showProgress('格式化结果...', 80);
        showExecutionTime(progress.execution_time);
        break;
      
      case 'completed':
        showProgress('完成!', 100);
        showResults(progress.row_count);
        break;
    }
  });
}
```

---

## 5. 批处理优化

### 5.1 批量查询处理

```python
# backend/app/api/api_v1/endpoints/query.py

@router.post("/chat/batch")
async def chat_query_batch(
    batch_request: schemas.BatchChatQueryRequest,
    db: Session = Depends(deps.get_db)
) -> schemas.BatchChatQueryResponse:
    """
    批量查询处理
    
    优势:
    - 并行执行多个查询
    - 共享资源初始化
    - 批量返回结果
    """
    
    async def process_single_query(query_req: schemas.ChatQueryRequest):
        """处理单个查询"""
        try:
            graph = IntelligentSQLGraph()
            result = await graph.process_query(
                query=query_req.natural_language_query,
                connection_id=query_req.connection_id,
                thread_id=query_req.conversation_id
            )
            return {
                "success": True,
                "query_id": query_req.query_id,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "query_id": query_req.query_id,
                "error": str(e)
            }
    
    # 并行处理所有查询
    tasks = [
        process_single_query(req) 
        for req in batch_request.queries
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return schemas.BatchChatQueryResponse(
        results=results,
        total_queries=len(batch_request.queries),
        successful_queries=sum(1 for r in results if r.get("success"))
    )
```

---

### 5.2 性能对比

**场景: 处理10个查询**

| 模式 | 执行方式 | 总时间 | 吞吐量 |
|------|---------|-------|--------|
| 串行 | 逐个执行 | 150秒 (10 × 15秒) | 0.07 QPS |
| 批量异步 | 并行执行 | 18秒 (最长的查询) | 0.56 QPS |

**提升: 8.3倍**

---

## 6. 监控与调试工具

### 6.1 异步任务性能追踪

```python
# backend/app/core/async_monitor.py

import functools
import time
import asyncio
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

def async_performance_monitor(
    slow_threshold: float = 5.0
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    异步函数性能监控装饰器
    
    参数:
        slow_threshold: 慢查询阈值(秒)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            task_name = f"{func.__module__}.{func.__name__}"
            
            logger.debug(f"开始异步任务: {task_name}")
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration > slow_threshold:
                    logger.warning(
                        f"慢异步任务: {task_name} 耗时 {duration:.2f}秒"
                    )
                else:
                    logger.debug(
                        f"完成异步任务: {task_name} 耗时 {duration:.2f}秒"
                    )
                
                # 记录指标
                async_task_duration.labels(
                    task_name=task_name,
                    status="success"
                ).observe(duration)
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"异步任务失败: {task_name} 耗时 {duration:.2f}秒, 错误: {e}"
                )
                
                async_task_duration.labels(
                    task_name=task_name,
                    status="error"
                ).observe(duration)
                
                raise
        
        return wrapper
    return decorator

# 使用示例
@async_performance_monitor(slow_threshold=3.0)
async def cache_check_node(state: SQLMessageState):
    # ...
    pass
```

---

### 6.2 异步并发限流

```python
# backend/app/core/async_limiter.py

import asyncio
from typing import Callable, TypeVar

T = TypeVar('T')

class AsyncLimiter:
    """
    异步并发限流器
    
    防止过多并发任务耗尽资源
    """
    
    def __init__(self, max_concurrent: int = 100):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()
    
    async def run(self, coro: Callable[[], T]) -> T:
        """运行受限的协程"""
        async with self:
            return await coro()

# 全局限流器
query_limiter = AsyncLimiter(max_concurrent=100)

# 使用示例
async def process_query_with_limit(query: str):
    async with query_limiter:
        result = await graph.process_query(query)
        return result
```

---

## 7. 总结

以上优化方案按优先级实施:

| 优先级 | 优化方案 | 实施难度 | 性能提升 | 用户体验提升 |
|-------|---------|---------|---------|------------|
| 🔴 高 | 流式响应API | 中 | +30% | ⭐⭐⭐⭐⭐ |
| 🔴 高 | 并行缓存检查 | 低 | +25% | ⭐⭐⭐⭐ |
| 🟡 中 | 异步ORM迁移 | 高 | +40% | ⭐⭐⭐ |
| 🟡 中 | 自定义StreamWriter | 中 | +20% | ⭐⭐⭐⭐⭐ |
| 🟢 低 | 批处理优化 | 低 | +50% | ⭐⭐⭐ |

**建议实施顺序:**
1. 并行缓存检查 (Week 1)
2. 流式响应API (Week 2-3)
3. 自定义StreamWriter (Week 4)
4. 批处理优化 (Week 5)
5. 异步ORM迁移 (Week 6-8)

---

**文档版本**: v1.0  
**最后更新**: 2026-01-20
