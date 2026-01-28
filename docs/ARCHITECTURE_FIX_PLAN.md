# Chat BI 架构修复计划

## 概述

本文档详细描述了 Chat BI 项目的架构修复计划，包括问题修复、LangSmith 监控集成和全面测试方案。

**更新日期**: 2026-01-28
**状态**: ✅ 核心模块已完成，测试通过

---

## 一、修复优先级

| 优先级 | 问题 | 影响 | 预计工时 | 状态 |
|--------|------|------|----------|------|
| P0 | Checkpointer 异步/同步混用 | 可能导致死锁 | 2h | ✅ 完成 |
| P0 | LLM 调用缺乏统一重试/超时 | 服务不稳定 | 3h | ✅ 完成 |
| P1 | LangSmith 监控集成 | 缺乏可观测性 | 2h | ✅ 完成 |
| P1 | 统一 LLM 调用包装器 | 代码重复 | 2h | ✅ 完成 |
| P2 | Schema 加载策略优化 | 大库性能问题 | 3h | 待实施 |
| P2 | 请求追踪 (trace_id) | 调试困难 | 1h | ✅ 完成 |

---

## 二、已完成的修复

### 2.1 新增核心模块

| 模块 | 文件路径 | 功能 |
|------|----------|------|
| LLM 包装器 | `app/core/llm_wrapper.py` | 统一重试、超时、错误分类、性能监控 |
| Checkpointer V2 | `app/core/checkpointer_v2.py` | 纯异步模式、连接池管理、健康检查 |
| 请求追踪 | `app/core/tracing.py` | trace_id 生成、上下文管理、LangSmith 集成 |

### 2.2 测试覆盖

| 测试文件 | 测试数量 | 状态 |
|----------|----------|------|
| `tests/test_architecture_fixes.py` | 20 | ✅ 全部通过 |
| `tests/test_e2e_integration.py` | 14 | ✅ 12 通过, 2 跳过 |

---

## 三、LangSmith 监控集成

### 3.1 环境配置

```bash
# .env 新增配置
# ==========================================
# LangSmith 监控配置
# ==========================================
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your-api-key-here
LANGCHAIN_PROJECT=chatbi-production
```

### 3.2 集成方案

LangSmith 会自动追踪所有 LangChain/LangGraph 调用，只需配置环境变量即可。

### 3.3 使用方式

```python
# 使用带追踪的 LLM 包装器
from app.core.llms import get_wrapped_llm

wrapper = get_wrapped_llm(caller="sql_generator")
response = await wrapper.ainvoke(messages, trace_id="req-123")

# 获取性能指标
from app.core.llms import get_llm_metrics
metrics = get_llm_metrics()
```

---

## 四、详细修复方案

### 4.1 P0: Checkpointer 统一异步模式 ✅

**问题**: 在同步上下文中创建异步 Checkpointer 可能导致死锁

**修复方案**: 
- 创建 `CheckpointerManager` 单例类
- 使用 `AsyncConnectionPool` 管理数据库连接
- 提供 `checkpointer_lifespan` 用于 FastAPI 生命周期管理

**使用方式**:
```python
from app.core.checkpointer_v2 import checkpointer_lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with checkpointer_lifespan():
        yield
```

### 4.2 P0: 统一 LLM 调用包装器 ✅

**问题**: 多处 LLM 调用使用不同的重试策略

**修复方案**: 
- 创建 `LLMWrapper` 类，提供统一的调用接口
- 支持指数退避重试（默认 3 次）
- 支持超时控制（默认 60 秒）
- 错误分类（timeout/rate_limit/server_error/auth_error 等）
- 性能指标收集

**使用方式**:
```python
from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig

config = LLMWrapperConfig(max_retries=3, timeout=60.0)
wrapper = LLMWrapper(llm=my_llm, config=config)

# 异步调用
response = await wrapper.ainvoke(messages, trace_id="req-123")

# 获取指标
metrics = wrapper.get_metrics()
```

### 4.3 P1: 请求追踪 ✅

**问题**: 跨多个 Agent 的请求缺乏统一的 trace_id

**修复方案**: 
- 创建 `TraceContext` 上下文管理器
- 支持子操作追踪 (SpanContext)
- 自动注入 trace_id 到 state
- 与 LangSmith 元数据集成

**使用方式**:
```python
from app.core.tracing import TraceContext, inject_trace_to_state

with TraceContext() as ctx:
    ctx.add_metadata("user_id", "user-123")
    
    # 创建子操作追踪
    with ctx.create_child_span("sql_generation"):
        # ... 执行操作
        pass
    
    # 注入到 state
    state = inject_trace_to_state(state)
```

---

## 五、测试计划

### 5.1 单元测试 ✅
- [x] Checkpointer 异步创建
- [x] LLM 包装器重试逻辑
- [x] 错误分类
- [x] 追踪上下文管理

### 5.2 集成测试 ✅
- [x] State 管理
- [x] 错误恢复流程
- [x] SQL 验证
- [x] Schema 加载
- [x] 缓存机制
- [ ] LangSmith 追踪（需要 API Key）

### 5.3 性能测试 ✅
- [x] LLM 包装器延迟
- [x] 并发请求处理

---

## 六、后续工作

1. **Schema 加载策略优化** (P2)
   - 实现分层加载策略
   - 添加 Schema 缓存

2. **Skill 路由策略优化** (P2)
   - 支持多种路由策略
   - 添加路由性能监控

3. **生产环境部署**
   - 配置 LangSmith API Key
   - 监控 Dashboard 设置
