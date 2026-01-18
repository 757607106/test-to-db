# Text-to-SQL 系统架构分析文档

## 📋 目录

1. [系统概述](#系统概述)
2. [核心架构](#核心架构)
3. [工作流程](#工作流程)
4. [核心组件详解](#核心组件详解)
5. [状态管理](#状态管理)
6. [Agent详解](#agent详解)
7. [优化历史](#优化历史)
8. [关键技术点](#关键技术点)

---

## 系统概述

### 系统定位
这是一个基于 LangGraph 的智能 Text-to-SQL 系统，能够将用户的自然语言查询转换为 SQL 语句并执行，同时支持数据可视化和智能分析。

### 核心特性
- 🤖 **多Agent协作**: 使用 LangGraph Supervisor 模式协调多个专业 Agent
- 🔄 **智能路由**: 自动识别查询类型并选择合适的处理流程
- 🛡️ **错误恢复**: 完善的错误处理和自动恢复机制
- 📊 **数据可视化**: 自动生成适合的图表展示数据
- 🎯 **自定义Agent**: 支持动态加载用户自定义的分析专家

### 技术栈
- **框架**: LangGraph (状态图编排)
- **LLM**: 支持多种大语言模型 (通过配置切换)
- **数据库**: 支持 MySQL, PostgreSQL, SQLite 等
- **可视化**: 集成 MCP Chart Server

---

## 核心架构

### 整体架构图

```
用户查询
    ↓
[IntelligentSQLGraph] ← 高级接口层
    ↓
[Load Custom Agent Node] ← 动态加载自定义Agent
    ↓
[Supervisor Agent] ← 协调中心
    ↓
┌─────────────────────────────────────────┐
│  Worker Agents (专业Agent池)             │
├─────────────────────────────────────────┤
│  1. Schema Agent      - 模式分析         │
│  2. SQL Generator     - SQL生成          │
│  3. SQL Executor      - SQL执行          │
│  4. Chart Generator   - 图表生成         │
│  5. Error Recovery    - 错误恢复         │
└─────────────────────────────────────────┘
    ↓
返回结果 (SQL结果 + 图表配置)
```

### 架构层次

#### 1. 接口层 (`chat_graph.py`)
- **IntelligentSQLGraph**: 主要入口类
- **全局图实例管理**: 单例模式管理图实例
- **便捷函数**: 提供简化的调用接口

#### 2. 协调层 (`supervisor_agent.py`)
- **SupervisorAgent**: 使用 LangGraph 内置 supervisor
- **智能路由**: 根据任务阶段选择合适的 Worker Agent
- **流程控制**: 管理整个查询处理流程

#### 3. 执行层 (各个 Worker Agents)
- **专业化分工**: 每个 Agent 负责特定任务
- **工具调用**: 使用 LangChain Tools 执行具体操作
- **状态更新**: 更新共享状态供其他 Agent 使用

#### 4. 服务层 (`services/`)
- **数据库服务**: 连接管理、查询执行
- **Schema服务**: 表结构检索、值映射
- **混合检索服务**: 语义+结构化检索

---

## 工作流程

### 标准查询流程

```
1. 用户输入查询
   ↓
2. [Load Custom Agent] - 检查是否需要加载自定义分析专家
   ↓
3. [Supervisor] - 分析查询，决定路由
   ↓
4. [Schema Agent] - 分析查询意图，获取相关表结构
   │  ├─ analyze_user_query: 提取关键实体和意图
   │  └─ retrieve_database_schema: 获取表结构和值映射
   ↓
5. [SQL Generator Agent] - 生成SQL语句
   │  ├─ generate_sql_query: 基础SQL生成
   │  ├─ generate_sql_with_samples: 基于样本生成(如果有)
   │  └─ explain_sql_query: 解释SQL逻辑
   ↓
6. [SQL Executor Agent] - 执行SQL
   │  └─ execute_sql_query: 直接执行(带缓存)
   ↓
7. [Chart Generator Agent] - 生成图表(可选)
   │  ├─ should_generate_chart: 判断是否需要图表
   │  ├─ analyze_data_for_chart: 分析数据特征
   │  └─ 调用MCP Chart工具生成图表
   ↓
8. 返回结果
```

### 错误处理流程

```
任何阶段出错
   ↓
[Error Recovery Agent]
   ├─ analyze_error_pattern: 分析错误模式
   ├─ generate_recovery_strategy: 制定恢复策略
   └─ auto_fix_sql_error: 尝试自动修复
   ↓
判断是否可恢复
   ├─ 是 → 返回对应阶段重试
   └─ 否 → 返回错误信息给用户
```

---

## 核心组件详解

### 1. IntelligentSQLGraph (chat_graph.py)

**职责**: 系统的高级接口和入口点

**核心方法**:
```python
# 创建图实例
def __init__(self, active_agent_profiles=None, custom_analyst=None)

# 加载自定义Agent
async def _load_custom_agent_node(self, state)

# Supervisor节点包装
async def _supervisor_node(self, state)

# 处理查询的便捷方法
async def process_query(self, query, connection_id)
```

**关键特性**:
- 支持动态加载自定义分析专家
- 从消息中提取 connection_id 和 agent_id
- 提供全局单例访问

### 2. SupervisorAgent (supervisor_agent.py)

**职责**: 协调所有 Worker Agents，智能路由决策

**核心配置**:
```python
# Worker Agents列表
worker_agents = [
    schema_agent,
    sql_generator_agent,
    sql_executor_agent,
    error_recovery_agent,
    chart_generator_agent  # 或自定义分析专家
]

# Supervisor配置
create_supervisor(
    model=llm,
    agents=worker_agents,
    prompt=supervisor_prompt,
    add_handoff_back_messages=True,
    output_mode="full_history"
)
```

**路由策略**:
- 根据 `current_stage` 字段决定下一个Agent
- 标准流程: schema → sql_generation → sql_execution → [chart_generation] → completed
- 错误流程: 任何阶段 → error_recovery → 重试或终止

**重要说明**:
- SQL Validator Agent 已被移除(2026-01-16)
- 原因: 简化流程，提升响应速度
- 备份位置: `backend/backups/agents_backup_20260116_175357`

### 3. Agent Factory (agent_factory.py)

**职责**: 动态创建自定义Agent实例

**核心功能**:
```python
def create_custom_analyst_agent(profile, db):
    """
    根据AgentProfile创建自定义分析专家
    - 获取自定义LLM配置
    - 应用自定义提示词
    - 返回ChartGeneratorAgent实例
    """
```

**使用场景**:
- 用户创建自定义分析专家
- 需要特定领域的数据分析能力
- 替换默认的图表生成Agent

---

## 状态管理

### SQLMessageState (state.py)

这是整个系统的核心状态对象，所有Agent共享此状态。

**核心字段分类**:

#### 1. 基础信息
```python
connection_id: int = 15          # 数据库连接ID
agent_id: Optional[int] = None   # 自定义Agent ID
thread_id: Optional[str] = None  # 会话线程ID
user_id: Optional[str] = None    # 用户ID
```

#### 2. 查询处理
```python
query_analysis: Dict              # 查询分析结果
schema_info: SchemaInfo          # 数据库模式信息
generated_sql: str               # 生成的SQL
execution_result: SQLExecutionResult  # 执行结果
```

#### 3. 流程控制
```python
current_stage: Literal[...]      # 当前处理阶段
retry_count: int = 0             # 重试计数
max_retries: int = 3             # 最大重试次数
route_decision: Literal[...]     # 路由决策
```

#### 4. 错误处理
```python
error_history: List[Dict]        # 错误历史
```

#### 5. 可视化
```python
chart_config: Dict               # 图表配置
analysis_result: Dict            # 分析结果
```

#### 6. Agent通信
```python
agent_messages: Dict[str, Any]   # Agent间消息
messages: List[BaseMessage]      # LangChain消息历史
```

### 状态流转

```
初始状态
  current_stage = "schema_analysis"
  retry_count = 0
  ↓
Schema分析完成
  current_stage = "sql_generation"
  schema_info = {...}
  ↓
SQL生成完成
  current_stage = "sql_execution"
  generated_sql = "SELECT ..."
  ↓
SQL执行完成
  current_stage = "completed" 或 "chart_generation"
  execution_result = {...}
  ↓
(可选)图表生成完成
  current_stage = "completed"
  chart_config = {...}
```

---

## Agent详解

### 1. Schema Agent (schema_agent.py)

**职责**: 分析用户查询，获取相关数据库模式信息

**工具列表**:
1. `analyze_user_query`: 使用LLM分析查询意图，提取关键实体
2. `retrieve_database_schema`: 从数据库检索相关表结构和值映射

**工作流程**:
```python
1. 接收用户查询
2. 调用 analyze_user_query 分析意图
   - 提取实体(表名、字段名)
   - 识别查询类型(聚合、过滤、排序等)
3. 调用 retrieve_database_schema 获取模式
   - 使用混合检索(语义+关键词)
   - 获取表结构、关系、值映射
4. 返回完整的schema_context
```

**关键技术**:
- 使用 `retrieve_relevant_schema` 进行智能检索
- 支持值映射(自然语言→数据库值)
- ReAct模式: LLM决定工具调用顺序

**输出示例**:
```python
{
    "schema_context": {
        "products": {
            "columns": ["id", "name", "category", "price"],
            "relationships": [...]
        }
    },
    "value_mappings": {
        "category": {
            "手机": "mobile_phone",
            "电脑": "computer"
        }
    }
}
```

### 2. SQL Generator Agent (sql_generator_agent.py)

**职责**: 根据模式信息生成高质量SQL语句

**工具列表**:
1. `generate_sql_query`: 基础SQL生成
2. `generate_sql_with_samples`: 基于历史样本生成(更高质量)
3. `explain_sql_query`: 解释SQL逻辑

**工作流程**:
```python
1. 接收用户查询和schema信息
2. 检查是否有样本检索结果
3. 选择生成策略:
   - 有高质量样本 → generate_sql_with_samples
   - 无样本 → generate_sql_query
4. 生成SQL并清理格式
5. (可选)解释SQL逻辑
```

**生成策略**:
- **基础生成**: 直接根据schema和查询生成
- **样本增强**: 参考历史成功案例，提高质量
- **约束条件**: 
  - 确保语法正确(因为不再有验证步骤)
  - 添加LIMIT限制
  - 使用正确的值映射
  - 避免危险操作

**重要变更**:
- 简化流程后，SQL生成后直接执行，不再验证
- 因此生成时必须确保高质量

**输出示例**:
```python
{
    "success": True,
    "sql_query": "SELECT brand FROM products WHERE category='手机' ORDER BY sales DESC LIMIT 1",
    "samples_used": 2,
    "best_sample_score": 0.85
}
```

### 3. SQL Executor Agent (sql_executor_agent.py)

**职责**: 安全执行SQL查询并返回结果

**工具列表**:
1. `execute_sql_query`: 执行SQL(带缓存机制)

**核心特性**:

#### 缓存机制
```python
# 防止重复执行
cache_key = f"{connection_id}:{hash(sql_query)}"

# 缓存策略
- 只缓存查询操作(SELECT)
- 缓存有效期: 5分钟
- 最大缓存数: 100条
- 自动清理旧缓存
```

#### 并发控制
```python
# 防止并发重复执行
_cache_lock = {}  # 执行锁

if cache_key in _cache_lock:
    # 等待正在执行的查询完成
    return cached_result
```

#### 直接工具调用
```python
# 不使用ReAct模式，直接调用工具
# 原因: 避免LLM重复调用工具
result = execute_sql_query.invoke({
    "sql_query": sql_query,
    "connection_id": connection_id
})
```

**执行流程**:
```python
1. 检查缓存
   - 命中 → 直接返回
   - 未命中 → 继续
2. 检查执行锁
   - 正在执行 → 等待
   - 未执行 → 加锁
3. 获取数据库连接
4. 执行SQL查询
5. 格式化结果
6. 缓存结果(如果是查询)
7. 释放锁
```

**输出示例**:
```python
{
    "success": True,
    "data": {
        "columns": ["brand"],
        "data": [["Apple"]],
        "row_count": 1
    },
    "execution_time": 0.05,
    "from_cache": False
}
```

### 4. Chart Generator Agent (chart_generator_agent.py)

**职责**: 根据查询结果生成数据可视化图表

**工具来源**:
- 本地工具: `should_generate_chart`, `analyze_data_for_chart`, `generate_chart_config`
- MCP工具: 通过 `@antv/mcp-server-chart` 提供的图表生成工具

**工作流程**:
```python
1. 判断是否需要生成图表
   - 检查用户意图(关键词)
   - 检查数据特征(数值列、行数)
   - 数据量检查(2-1000行)
2. 分析数据特征
   - 识别数值列、文本列、日期列
   - 分析数据分布
3. 推荐图表类型
   - 趋势分析 → 折线图
   - 比较分析 → 柱状图
   - 占比分析 → 饼图
   - 相关性分析 → 散点图
4. 调用MCP工具生成图表
```

**图表类型推荐逻辑**:
```python
# 基于查询关键词
"趋势", "时间" → line chart
"比较", "排名" → bar chart
"占比", "分布" → pie chart

# 基于数据特征
2列(1文本+1数值) + 少量行 → pie chart
2列(1文本+1数值) + 较多行 → bar chart
多个数值列 → scatter plot
```

**自定义支持**:
```python
def __init__(self, custom_prompt=None, llm=None):
    """
    支持自定义提示词和LLM
    用于创建特定领域的分析专家
    """
```

**输出示例**:
```python
{
    "chart_config": {
        "type": "bar",
        "data": [...],
        "xField": "brand",
        "yField": "sales",
        "title": "品牌销量对比"
    }
}
```

### 5. Error Recovery Agent (error_recovery_agent.py)

**职责**: 分析错误、制定恢复策略、自动修复

**工具列表**:
1. `analyze_error_pattern`: 分析错误模式
2. `generate_recovery_strategy`: 生成恢复策略
3. `auto_fix_sql_error`: 自动修复SQL错误

**错误分类**:
```python
error_types = {
    "syntax_error": "SQL语法错误",
    "connection_error": "数据库连接错误",
    "permission_error": "权限不足",
    "timeout_error": "查询超时",
    "unknown_error": "未知错误"
}
```

**恢复策略**:
```python
strategies = {
    "syntax_error": {
        "primary_action": "regenerate_sql_with_constraints",
        "auto_fixable": True,
        "confidence": 0.8
    },
    "timeout_error": {
        "primary_action": "optimize_query_performance",
        "auto_fixable": True,
        "confidence": 0.7
    },
    "connection_error": {
        "primary_action": "check_database_connection",
        "auto_fixable": False,
        "confidence": 0.6
    }
}
```

**自动修复能力**:
```python
# 语法错误修复
- 添加缺失的分号
- 修正关键字大小写
- 修复未闭合的引号

# 性能问题修复
- 添加LIMIT子句
- 优化JOIN顺序

# 权限问题修复
- 简化SELECT字段
- 移除敏感操作
```

**恢复流程**:
```python
1. 分析错误历史
   - 统计错误类型
   - 识别重复模式
2. 制定恢复策略
   - 选择主要动作
   - 评估成功率
3. 尝试自动修复
   - 应用修复规则
   - 验证修复结果
4. 决定下一步
   - 修复成功 → 重试
   - 修复失败 → 人工干预
```

---

## 优化历史

### 1. SQL Validator移除 (2026-01-16)

**背景**:
- 原流程: Schema → SQL生成 → SQL验证 → SQL执行
- 问题: 验证步骤增加延迟，且大多数SQL本身就是正确的

**改进**:
- 移除SQL Validator Agent
- SQL生成后直接执行
- 在生成阶段就确保质量

**效果**:
- LLM调用减少1-2次
- 响应时间提升30-50%
- 简化了流程复杂度

**备份位置**: `backend/backups/agents_backup_20260116_175357`

### 2. SQL Executor优化

**问题**: execute_sql_query工具被重复调用4次

**原因**: ReAct模式下LLM可能多次调用工具

**解决方案**:
```python
# 方案1: 工具级缓存
_execution_cache = {}  # 缓存执行结果

# 方案2: 直接工具调用
# 不使用ReAct agent，直接调用工具
result = execute_sql_query.invoke(...)
```

**效果**:
- 工具调用从4次降到1次
- 执行时间减少75%
- 避免了重复的数据库查询

### 3. 消息历史修复

**问题**: ToolCall和ToolMessage不匹配导致错误

**解决方案**:
```python
# 在supervisor执行前后验证并修复消息历史
state["messages"] = validate_and_fix_message_history(state["messages"])
```

**修复逻辑**:
- 检测孤立的ToolCall
- 自动添加占位ToolMessage
- 确保消息对的完整性

---

## 关键技术点

### 1. LangGraph Supervisor模式

**优势**:
- 内置的Agent协调机制
- 自动的消息路由
- 支持handoff机制

**配置**:
```python
supervisor = create_supervisor(
    model=llm,
    agents=worker_agents,
    prompt=supervisor_prompt,
    add_handoff_back_messages=True,  # 自动添加返回消息
    output_mode="full_history"       # 保留完整历史
)
```

### 2. ReAct Agent模式

**原理**: Reasoning + Acting
- LLM推理决定使用哪个工具
- 执行工具获取结果
- 基于结果继续推理
- 循环直到完成任务

**创建方式**:
```python
agent = create_react_agent(
    llm,
    tools,
    prompt=system_prompt,
    name=agent_name
)
```

**适用场景**:
- Schema Agent: 需要灵活的工具调用顺序
- SQL Generator: 需要根据情况选择生成策略
- Chart Generator: 需要多步骤的图表生成

**不适用场景**:
- SQL Executor: 只需执行一次，直接调用更好

### 3. 状态共享机制

**核心思想**: 所有Agent共享同一个状态对象

**优势**:
- Agent间无需显式通信
- 状态变更自动传播
- 支持复杂的工作流

**实现**:
```python
class SQLMessageState(AgentState):
    # 继承自LangGraph的AgentState
    # 自动支持状态更新和传播
    pass
```

### 4. 工具缓存机制

**目的**: 避免重复执行相同的操作

**实现**:
```python
_execution_cache = {}
_cache_timestamps = {}

def execute_sql_query(sql_query, connection_id):
    cache_key = f"{connection_id}:{hash(sql_query)}"
    
    if cache_key in _execution_cache:
        # 检查缓存有效期
        if time.time() - _cache_timestamps[cache_key] < 300:
            return _execution_cache[cache_key]
    
    # 执行查询
    result = ...
    
    # 缓存结果
    _execution_cache[cache_key] = result
    _cache_timestamps[cache_key] = time.time()
    
    return result
```

### 5. 动态Agent加载

**场景**: 用户创建自定义分析专家

**实现流程**:
```python
1. 从消息中提取agent_id
2. 从数据库加载AgentProfile
3. 使用agent_factory创建自定义Agent
4. 替换默认的chart_generator_agent
5. 重新创建supervisor
```

**关键代码**:
```python
async def _load_custom_agent_node(self, state):
    agent_id = extract_agent_id_from_messages(state["messages"])
    
    if agent_id:
        profile = crud_agent_profile.get(db, id=agent_id)
        custom_analyst = create_custom_analyst_agent(profile, db)
        
        # 重新创建supervisor
        self.supervisor_agent = create_intelligent_sql_supervisor(
            custom_analyst=custom_analyst
        )
```

### 6. MCP工具集成

**MCP**: Model Context Protocol

**集成方式**:
```python
# 初始化MCP客户端
client = MultiServerMCPClient({
    "mcp-server-chart": {
        "command": "npx",
        "args": ["-y", "@antv/mcp-server-chart"]
    }
})

# 获取工具
chart_tools = await client.get_tools()

# 包装工具
wrapped_tools = [MCPToolWrapper(tool, tool.name) for tool in chart_tools]

# 添加到Agent
agent = create_react_agent(llm, wrapped_tools, ...)
```

**优势**:
- 标准化的工具接口
- 易于扩展新工具
- 支持远程工具调用

---

## 总结

### 系统优势

1. **模块化设计**: 每个Agent职责清晰，易于维护和扩展
2. **智能协调**: Supervisor自动路由，无需硬编码流程
3. **错误恢复**: 完善的错误处理和自动修复机制
4. **性能优化**: 缓存、直接调用等优化手段
5. **可扩展性**: 支持自定义Agent和工具

### 最佳实践

1. **状态管理**: 使用共享状态而非消息传递
2. **工具设计**: 单一职责，可组合
3. **错误处理**: 分层处理，自动恢复
4. **性能优化**: 缓存常用结果，避免重复计算
5. **可观测性**: 详细的日志记录

### 未来改进方向

1. **流式输出**: 支持实时返回中间结果
2. **并行执行**: 某些Agent可以并行运行
3. **更智能的路由**: 基于历史数据优化路由决策
4. **更多数据源**: 支持更多类型的数据库和API
5. **增强的可视化**: 更丰富的图表类型和交互

---

## 附录

### 相关文件清单

**核心文件**:
- `backend/app/agents/chat_graph.py` - 主入口
- `backend/app/agents/agent_factory.py` - Agent工厂
- `backend/app/agents/agents/supervisor_agent.py` - 协调器
- `backend/app/core/state.py` - 状态定义

**Worker Agents**:
- `backend/app/agents/agents/schema_agent.py`
- `backend/app/agents/agents/sql_generator_agent.py`
- `backend/app/agents/agents/sql_executor_agent.py`
- `backend/app/agents/agents/chart_generator_agent.py`
- `backend/app/agents/agents/error_recovery_agent.py`

**服务层**:
- `backend/app/services/text2sql_service.py`
- `backend/app/services/text2sql_utils.py`
- `backend/app/services/db_service.py`
- `backend/app/services/schema_service.py`

### 参考文档

- LangGraph官方文档: https://langchain-ai.github.io/langgraph/
- LangChain工具文档: https://python.langchain.com/docs/modules/tools/
- MCP协议: https://modelcontextprotocol.io/

---

**文档版本**: v1.0  
**最后更新**: 2026-01-18  
**维护者**: AI Assistant
