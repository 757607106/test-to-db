# 上下文工程与LangGraph记忆体使用分析

## 📋 执行摘要

本项目**已实现**上下文工程技术，但**未完全实现**LangGraph记忆体功能。

### 快速结论

✅ **上下文工程**: 已广泛使用  
⚠️ **LangGraph记忆体**: 配置存在但未激活  
📊 **会话管理**: 基础实现，无持久化

---

## 1. 上下文工程使用情况

### 1.1 系统提示词工程 ✅

项目中大量使用了精心设计的系统提示词（System Prompts）。

#### 核心Agent的系统提示词

**位置**: 各个Agent的 `_create_system_prompt()` 方法

1. **Schema Agent** (`schema_agent.py`)
```python
def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig):
    connection_id = extract_connection_id(state)
    system_msg = f"""你是一个专业的数据库模式分析专家。
    **重要：当前数据库connection_id是 {connection_id}**
    
你的任务是：
1. 分析用户的自然语言查询，理解其意图和涉及的实体
2. 获取与查询相关的数据库表结构信息
3. 验证获取的模式信息是否足够完整
"""
```

**特点**:
- 动态注入 `connection_id` 上下文
- 明确角色定位和任务
- 结构化的工作流程说明

2. **SQL Generator Agent** (`sql_generator_agent.py`)

```python
def _create_system_prompt(self) -> str:
    return """你是一个专业的SQL生成专家。你的任务是：

1. 根据用户查询和数据库模式信息生成准确的SQL语句
2. 生成时就考虑SQL的正确性和安全性（因为不再有验证步骤）
3. 提供SQL查询的详细解释

SQL生成原则（重要 - 因为不再有验证步骤）：
- 确保语法绝对正确
- 使用适当的连接方式
- 应用正确的过滤条件
- 生成时就考虑基本性能优化
- 限制结果集大小（除非明确要求）
- 使用正确的值映射
- 充分利用样本提供的最佳实践
- 避免危险操作（DROP, DELETE, UPDATE等）
"""
```

**特点**:
- 强调质量和安全性
- 明确约束条件
- 提供详细的生成原则

3. **SQL Executor Agent** (`sql_executor_agent.py`)

```python
def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig):
    connection_id = extract_connection_id(state)
    system_msg = f"""你是一个SQL执行专家。当前数据库connection_id是 {connection_id}。

**重要规则 - 必须严格遵守**:
1. 使用 execute_sql_query 工具执行SQL查询 **仅一次**
2. 工具调用完成后，**立即结束**，不要做任何其他事情
3. **绝对不要**重复调用工具

执行流程（严格按照此流程）:
Step 1: 调用 execute_sql_query 工具一次
Step 2: 立即结束任务
"""
```

**特点**:
- 强调执行约束（防止重复调用）
- 明确的步骤指导
- 注入动态上下文

4. **Supervisor Agent** (`supervisor_agent.py`)

```python
def _get_supervisor_prompt(self) -> str:
    system_msg = f"""你是一个智能的SQL Agent系统监督者。
你管理以下专门代理：

🔍 **schema_agent**: 分析用户查询，获取相关数据库表结构
⚙️ **sql_generator_agent**: 根据模式信息生成高质量SQL语句
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
📊 **chart_generator_agent**: 根据查询结果生成数据可视化图表
🔧 **error_recovery_agent**: 处理错误并提供修复方案

**工作原则:**
1. 根据当前任务阶段选择合适的代理
2. 确保工作流程的连续性和一致性
3. 智能处理错误和异常情况
4. 一次只分配给一个代理，不要并行调用
5. 不要自己执行任何具体工作

**标准流程:**
用户查询 → schema_agent → sql_generator_agent → sql_executor_agent → 
[可选] chart_generator_agent → 完成
"""
```

**特点**:
- 清晰的Agent职责说明
- 明确的工作流程
- 路由决策指导

### 1.2 动态上下文注入 ✅

**实现位置**: 各个Agent的工具调用

#### Schema检索上下文

```python
# text2sql_service.py
def construct_prompt(schema_context, query, value_mappings, db_type):
    """为LLM构建增强上下文和指令的提示"""
    
    # 格式化表结构信息
    schema_str = format_schema_for_prompt(schema_context)
    
    # 添加值映射
    mappings_str = ""
    if value_mappings:
        mappings_str = "-- 值映射:\n"
        for column, mappings in value_mappings.items():
            mappings_str += f"-- 对于 {column}:\n"
            for nl_term, db_value in mappings.items():
                mappings_str += f"--   自然语言中的'{nl_term}'指数据库中的'{db_value}'\n"
    
    # 根据数据库类型添加特定语法说明
    db_syntax_guide = ""
    if db_type.lower() == "mysql":
        db_syntax_guide = """### MySQL 语法要求（重要）:
- 日期截断：使用 DATE_FORMAT(date_column, '%Y-%m-01')
- 月份提取：使用 DATE_FORMAT(date_column, '%Y-%m')
- 当前日期：使用 NOW() 或 CURRENT_DATE
"""
```

**特点**:
- 动态注入数据库Schema
- 值映射上下文（自然语言→数据库值）
- 数据库类型特定的语法指导

#### 样本增强上下文

```python
# sql_generator_agent.py
@tool
def generate_sql_with_samples(user_query, schema_info, sample_qa_pairs, value_mappings):
    """基于样本生成高质量SQL查询"""
    
    # 构建样本分析
    sample_analysis = "最相关的样本分析:\n"
    for i, sample in enumerate(best_samples, 1):
        sample_analysis += f"""
样本{i} (相关性: {sample.get('final_score', 0):.3f}):
- 问题: {sample.get('question', '')}
- SQL: {sample.get('sql', '')}
- 查询类型: {sample.get('query_type', '')}
- 成功率: {sample.get('success_rate', 0):.2f}
"""
    
    # 构建增强的生成提示
    prompt = f"""
作为SQL专家，请基于以下信息生成高质量的SQL查询：

用户查询: {user_query}
数据库模式: {schema_info}
{sample_analysis}
值映射信息: {value_mappings}
"""
```

**特点**:
- Few-shot learning（样本学习）
- 历史成功案例作为上下文
- 相关性评分指导

### 1.3 上下文工程技术总结

| 技术 | 使用情况 | 位置 | 效果 |
|------|---------|------|------|
| **System Prompts** | ✅ 广泛使用 | 所有Agents | 定义角色和行为 |
| **Dynamic Context** | ✅ 动态注入 | Schema/SQL生成 | 提供实时信息 |
| **Few-shot Learning** | ✅ 样本增强 | SQL生成 | 提高生成质量 |
| **Chain-of-Thought** | ✅ 步骤指导 | Supervisor | 引导推理过程 |
| **Constraint Prompting** | ✅ 约束条件 | SQL执行 | 防止错误行为 |
| **Role Prompting** | ✅ 角色定位 | 所有Agents | 明确职责 |

---

## 2. LangGraph记忆体使用情况

### 2.1 配置存在但未激活 ⚠️

#### 配置文件

**位置**: `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    # LangGraph Checkpointer 配置
    CHECKPOINT_MODE: str = os.getenv("CHECKPOINT_MODE", "memory")  
    # 选项: memory | mysql | postgres
    
    CHECKPOINT_DB_PATH: str = os.getenv("CHECKPOINT_DB_PATH", "./data/checkpoints.db")
    CHECKPOINT_POSTGRES_URI: Optional[str] = os.getenv("CHECKPOINT_POSTGRES_URI", None)
```

**当前状态**:
- 默认模式: `memory` (内存模式，非持久化)
- 数据库文件存在: `backend/checkpoints.db`
- 但**未在代码中实际使用**

### 2.2 会话ID字段存在 ✅

**位置**: `backend/app/core/state.py`

```python
class SQLMessageState(AgentState):
    # 会话相关字段
    conversation_id: Optional[str] = None  # 对话ID
    thread_id: Optional[str] = None        # 线程ID
    user_id: Optional[str] = None          # 用户ID
```

**使用情况**:
- `conversation_id`: ✅ 在API层使用
- `thread_id`: ❌ 定义但未使用
- `user_id`: ❌ 定义但未使用

### 2.3 API层的会话管理

**位置**: `backend/app/api/api_v1/endpoints/query.py`

```python
@router.post("/chat", response_model=schemas.ChatQueryResponse)
async def chat_query(chat_request: schemas.ChatQueryRequest, db: Session = Depends(get_db)):
    # 生成或使用现有的对话ID
    conversation_id = chat_request.conversation_id or str(uuid4())
    
    # 构建状态
    initial_state = SQLMessageState(
        messages=[HumanMessage(content=query_text)],
        connection_id=chat_request.connection_id,
        conversation_id=conversation_id,  # 传递会话ID
        original_query=chat_request.natural_language_query,
        current_stage="clarification",
    )
```

**特点**:
- 生成唯一的 `conversation_id`
- 但**不持久化**到数据库
- 每次请求都是独立的，无状态保存

### 2.4 LangGraph Checkpointer未集成

**问题分析**:

1. **配置存在但未使用**
   ```python
   # 配置了checkpointer，但在创建图时未传入
   supervisor = create_supervisor(
       model=llm,
       agents=worker_agents,
       prompt=supervisor_prompt,
       # ❌ 缺少: checkpointer=...
   )
   ```

2. **图编译时未指定checkpointer**
   ```python
   # chat_graph.py
   return graph.compile()  # ❌ 应该是: graph.compile(checkpointer=...)
   ```

3. **没有使用thread_id进行状态恢复**
   ```python
   # 当前实现
   result = await self.supervisor_agent.supervisor.ainvoke(state)
   
   # ❌ 缺少thread_id配置
   # 应该是:
   # result = await self.supervisor_agent.supervisor.ainvoke(
   #     state,
   #     config={"configurable": {"thread_id": thread_id}}
   # )
   ```

### 2.5 记忆体功能对比

| 功能 | 当前状态 | 应有状态 | 影响 |
|------|---------|---------|------|
| **Checkpointer配置** | ⚠️ 配置存在 | ✅ 应集成 | 无持久化 |
| **会话ID生成** | ✅ 已实现 | ✅ 正常 | 可追踪单次会话 |
| **状态持久化** | ❌ 未实现 | ✅ 应实现 | 无法恢复历史 |
| **多轮对话** | ❌ 不支持 | ✅ 应支持 | 每次独立处理 |
| **断点续传** | ❌ 不支持 | ✅ 应支持 | 无法恢复中断 |

---

## 3. 详细分析

### 3.1 上下文工程的优势

#### 已实现的优势

1. **角色明确**: 每个Agent都有清晰的角色定位
2. **约束清晰**: 通过提示词约束Agent行为
3. **动态适应**: 根据数据库类型、Schema动态调整上下文
4. **样本学习**: 利用历史成功案例提高质量
5. **步骤引导**: 明确的工作流程指导

#### 实际效果

```python
# 示例: SQL生成的上下文增强
上下文层次:
1. 系统角色: "你是SQL生成专家"
2. 数据库Schema: 表结构、字段、关系
3. 值映射: 自然语言→数据库值
4. 数据库语法: MySQL/PostgreSQL特定语法
5. 历史样本: 相似查询的成功案例
6. 约束条件: 安全性、性能要求

结果: 高质量、准确的SQL生成
```

### 3.2 记忆体缺失的影响

#### 当前限制

1. **无多轮对话能力**
   ```
   用户: "查询销售数据"
   系统: [返回结果]
   用户: "按月份分组" ❌ 系统不记得上一次查询
   ```

2. **无状态恢复**
   ```
   如果处理中断，无法从断点继续
   必须重新开始整个流程
   ```

3. **无历史追踪**
   ```
   无法查看用户的历史查询
   无法分析用户行为模式
   ```

4. **无上下文累积**
   ```
   每次查询都是独立的
   无法利用对话历史优化响应
   ```

### 3.3 如何启用LangGraph记忆体

#### 步骤1: 创建Checkpointer

```python
# 在 chat_graph.py 中添加
from langgraph.checkpoint.sqlite import SqliteSaver
from app.core.config import settings

def create_checkpointer():
    """创建checkpointer实例"""
    if settings.CHECKPOINT_MODE == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    elif settings.CHECKPOINT_MODE == "sqlite":
        return SqliteSaver.from_conn_string(settings.CHECKPOINT_DB_PATH)
    elif settings.CHECKPOINT_MODE == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver.from_conn_string(settings.CHECKPOINT_POSTGRES_URI)
```

#### 步骤2: 集成到图编译

```python
# 修改 _create_graph_with_agent_loader
def _create_graph_with_agent_loader(self):
    from langgraph.graph import StateGraph, END
    
    graph = StateGraph(SQLMessageState)
    graph.add_node("load_custom_agent", self._load_custom_agent_node)
    graph.add_node("supervisor", self._supervisor_node)
    graph.set_entry_point("load_custom_agent")
    graph.add_edge("load_custom_agent", "supervisor")
    graph.add_edge("supervisor", END)
    
    # ✅ 添加checkpointer
    checkpointer = create_checkpointer()
    return graph.compile(checkpointer=checkpointer)
```

#### 步骤3: 使用thread_id

```python
# 修改 process_query 方法
async def process_query(self, query: str, connection_id: int = 15, thread_id: str = None):
    from langchain_core.messages import HumanMessage
    
    # 生成或使用提供的thread_id
    thread_id = thread_id or str(uuid4())
    
    initial_state = SQLMessageState(
        messages=[HumanMessage(content=query)],
        connection_id=connection_id,
        thread_id=thread_id,  # ✅ 设置thread_id
        current_stage="schema_analysis",
    )
    
    # ✅ 传递thread_id配置
    result = await self.supervisor_agent.supervise(
        initial_state,
        config={"configurable": {"thread_id": thread_id}}
    )
```

#### 步骤4: API层支持

```python
# 修改 query.py
@router.post("/chat", response_model=schemas.ChatQueryResponse)
async def chat_query(chat_request: schemas.ChatQueryRequest, db: Session = Depends(get_db)):
    # 使用conversation_id作为thread_id
    thread_id = chat_request.conversation_id or str(uuid4())
    
    # ✅ 传递thread_id
    result = await graph_instance.process_query(
        query=query_text,
        connection_id=chat_request.connection_id,
        thread_id=thread_id  # ✅ 启用记忆体
    )
```

### 3.4 启用记忆体后的效果

#### 多轮对话示例

```python
# 第一轮
用户: "查询2024年的销售数据"
系统: [返回结果，保存状态到thread_id="conv-123"]

# 第二轮 (使用相同thread_id)
用户: "按月份分组"
系统: ✅ 记得上一次查询，理解"按月份分组"是指对销售数据分组

# 第三轮
用户: "只看前3个月"
系统: ✅ 继续在同一上下文中处理
```

#### 断点续传示例

```python
# 处理中断
用户: "生成复杂报表"
系统: [处理到SQL执行阶段时中断]

# 恢复处理 (使用相同thread_id)
系统: ✅ 从SQL执行阶段继续，无需重新分析Schema
```

---

## 4. 总结与建议

### 4.1 当前状态总结

| 方面 | 状态 | 评分 |
|------|------|------|
| **上下文工程** | ✅ 优秀 | 9/10 |
| **系统提示词** | ✅ 完善 | 9/10 |
| **动态上下文** | ✅ 良好 | 8/10 |
| **Few-shot学习** | ✅ 实现 | 8/10 |
| **LangGraph记忆体** | ⚠️ 未启用 | 2/10 |
| **多轮对话** | ❌ 不支持 | 0/10 |
| **状态持久化** | ❌ 未实现 | 0/10 |

### 4.2 改进建议

#### 高优先级 🔴

1. **启用LangGraph Checkpointer**
   - 集成SqliteSaver或PostgresSaver
   - 修改图编译逻辑
   - 实现thread_id传递

2. **实现多轮对话**
   - 使用conversation_id作为thread_id
   - 在API层传递thread_id
   - 测试对话连续性

#### 中优先级 🟡

3. **增强上下文管理**
   - 实现上下文窗口管理
   - 添加历史消息摘要
   - 优化长对话性能

4. **添加状态查询API**
   - 查询历史对话
   - 恢复中断的会话
   - 导出对话历史

#### 低优先级 🟢

5. **优化Checkpointer性能**
   - 使用PostgreSQL替代SQLite
   - 实现分布式checkpointer
   - 添加缓存层

6. **增强记忆体功能**
   - 实现长期记忆
   - 用户偏好学习
   - 上下文压缩

### 4.3 实施路线图

```
Phase 1 (1-2周): 基础记忆体
├─ 集成SqliteSaver
├─ 实现thread_id传递
└─ 测试基本多轮对话

Phase 2 (2-3周): 增强功能
├─ 实现状态查询API
├─ 添加历史管理
└─ 优化性能

Phase 3 (3-4周): 高级特性
├─ 迁移到PostgreSQL
├─ 实现上下文压缩
└─ 添加分析功能
```

---

## 5. 参考资源

### LangGraph记忆体文档
- [LangGraph Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [Checkpointers](https://langchain-ai.github.io/langgraph/concepts/persistence/#checkpointers)
- [Memory Management](https://langchain-ai.github.io/langgraph/how-tos/memory/)

### 上下文工程最佳实践
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [LangChain Prompts](https://python.langchain.com/docs/modules/model_io/prompts/)
- [Few-shot Learning](https://www.promptingguide.ai/techniques/fewshot)

---

**文档版本**: v1.0  
**最后更新**: 2026-01-18  
**维护者**: AI Assistant
