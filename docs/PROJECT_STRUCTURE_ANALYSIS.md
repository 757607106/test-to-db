# Chat-To-DB 项目全景指南与源码深度解析

> **致开发者（特别是初学者）**：
> 本文档旨在为你提供一份“保姆级”的项目指南。我们将不仅仅列出文件结构，还会带你深入理解每一行代码背后的业务逻辑，以及它们是如何协同工作来完成“用户说一句话，系统画一张图”这个神奇过程的。

---

## 1. 项目是做什么的？

**Chat-To-DB** 是一个智能助手，它能听懂你的话（自然语言），然后去数据库里帮你查数据，最后把结果画成图表展示给你。

**简单来说，它就像给你的数据库配了一个 24 小时待命的数据分析师。**

### 核心流程
1. **你问**：“上个月销售额最高的前 5 个产品是哪些？”
2. **它想**：分析你的意图，找数据库表结构，写 SQL 代码。
3. **它查**：去数据库执行 SQL。
4. **它画**：拿到数据，分析趋势，自动生成柱状图。
5. **你还在问**：如果觉得结果不对，它还会反问你来确认细节。

---

## 2. 项目结构详解（逐文件解析）

为了让你不迷路，我们将目录结构拆解得非常细致。

### 📂 根目录
- `backend/`: **后端大脑**。所有的智能逻辑、数据库连接、API 接口都在这里。
- `frontend/`: **前端门面**。
  - `admin/`: **后台管理系统**。管理员在这里配置数据库连接、查看表结构。
  - `chat/`: **聊天界面**。普通用户在这里和机器人对话。
- `docs/`: **说明书**。你现在看的文档就在这。

### 📂 后端结构 (`backend/app`) —— 核心重地

这是你需要花费 80% 时间研究的地方。

```text
backend/app/
├── agents/                 # [核心] 智能体军团
│   ├── agents/             # 具体每个智能体的实现代码
│   │   ├── supervisor_agent.py   # 队长：负责分派任务
│   │   ├── schema_agent.py       # 业务员：负责懂数据库表结构
│   │   ├── sql_generator_agent.py# 程序员：负责写 SQL
│   │   ├── sql_executor_agent.py # DBA：负责执行 SQL
│   │   ├── chart_generator_agent.py # 美工：负责画图
│   │   └── ... (其他辅助智能体)
│   ├── chat_graph.py       # [关键] 这里的代码定义了智能体之间如何协作（工作流）
│   └── *_graph.py          # 其他场景的工作流（如并行处理、仪表盘分析）
│
├── api/                    # [入口] 对外提供的接口
│   └── api_v1/endpoints/
│       ├── query.py        # 聊天接口：前端发来的聊天请求从这里进入
│       └── connections.py  # 连接管理：增删改查数据库连接
│
├── core/                   # [基石] 基础设施
│   ├── config.py           # 配置：读取 .env 文件里的密码、Key
│   ├── llms.py             # 模型工厂：负责连接 OpenAI/阿里通义千问
│   └── state.py            # 状态定义：定义了智能体之间传递的消息格式
│
├── db/                     # [存储] 自身数据的存储
│   └── session.py          # 负责连接 SQLite/Postgres（存用户、历史记录等）
│
├── models/                 # [模型] 数据库表定义 (ORM)
│   ├── db_connection.py    # 定义了“数据库连接”这张表长什么样
│   └── query_history.py    # 定义了“查询历史”这张表长什么样
│
└── services/               # [业务] 纯业务逻辑（不含智能体）
    ├── db_service.py       # 负责真正的数据库连接操作
    └── text2sql_service.py # 封装了 Text-to-SQL 的具体调用逻辑
```

---

## 3. 业务逻辑全链路推演：一个请求的“一生”

让我们通过一个真实的例子，看看代码是如何跑起来的。

**场景**：用户在聊天框输入 **“查询最近 30 天的订单总额”**。

### 第一阶段：前端发起 (Frontend)
1. 用户点击发送。
2. `frontend/chat` 调用后端 API：`POST /api/v1/query/chat`。
3. 请求体包含：`{"natural_language_query": "查询最近 30 天的订单总额", "connection_id": 1}`。

### 第二阶段：后端接收 (API Layer)
**代码位置**：`backend/app/api/api_v1/endpoints/query.py`

1. **接收请求**：`chat_query` 函数接收请求。
2. **初始化状态**：它创建一个 `SQLMessageState` 对象，把用户的这句话放进去。就像给即将出发的智能体团队发了一个“任务包”。
3. **启动工作流**：调用 `graph.supervisor_agent.supervise(initial_state)`，把任务包交给“队长”。

### 第三阶段：智能体协作 (Agent Layer)
**代码位置**：`backend/app/agents/chat_graph.py` & `backend/app/agents/agents/*.py`

这里是魔法发生的地方。

#### 1. 队长分派 (Supervisor)
- **谁在干活**：`SupervisorAgent`
- **逻辑**：队长看了一眼任务包（State），发现用户刚问了问题，还没人处理。
- **决策**：队长喊道：“**SchemaAgent**，你先去看看数据库里有哪些表跟‘订单’有关！”

#### 2. 查表结构 (Schema Analysis)
- **谁在干活**：`SchemaAgent` (`agents/schema_agent.py`)
- **逻辑**：
    1. 它分析“订单总额”这个词。
    2. 它去数据库元数据里搜索，找到了 `orders` 表和 `total_amount` 字段。
    3. 它把这些信息写回“任务包”。
- **结果**：任务包里多了“相关表结构：orders (id, amount, date...)”。

#### 3. 写 SQL (SQL Generation)
- **谁在干活**：`SQLGeneratorAgent` (`agents/sql_generator_agent.py`)
- **逻辑**：
    1. 它拿到任务包，看到了用户问题和表结构。
    2. 它开始写代码：“用户要最近 30 天...那我要用 `WHERE date > NOW() - INTERVAL 30 DAY`...”
    3. 生成 SQL：`SELECT SUM(total_amount) FROM orders WHERE ...`
- **结果**：任务包里多了“generated_sql: ...”。

#### 4. 审代码 (SQL Validation)
- **谁在干活**：`SQLValidatorAgent` (`agents/sql_validator_agent.py`)
- **逻辑**：
    1. 检查 SQL 有没有语法错误。
    2. **安全检查**：有没有 `DELETE` 或 `DROP`？（如果有，直接报警驳回）。
- **结果**：验证通过。

#### 5. 执行查询 (SQL Execution)
- **谁在干活**：`SQLExecutorAgent` (`agents/sql_executor_agent.py`)
- **逻辑**：
    1. 真的去连接用户的数据库。
    2. 执行 SQL。
    3. 拿到结果：`50000`。
- **结果**：任务包里多了“execution_result: 50000”。

#### 6. 结果分析与画图 (Analysis & Chart)
- **谁在干活**：`AnalystAgent` & `ChartGeneratorAgent`
- **逻辑**：
    1. 分析师说：“这是一个聚合数值，增长不错。”
    2. 画图师说：“只有一个数字，不需要画折线图，直接展示大字报（KPI Card）。”
- **结果**：生成了最终回复和前端能渲染的 JSON 配置。

### 第四阶段：返回前端
后端把任务包里的最终结果打包成 JSON，返回给前端。前端解析 JSON，把“50000”显示出来，并配上分析文字。

---

## 4. 核心代码片段解析

### 4.1 智能体是怎么“思考”的？
在 `backend/app/agents/agents/supervisor_agent.py` 中，有一段 Prompt（提示词），这就是队长的“大脑说明书”：

```python
system_msg = """你是高效的SQL查询与分析系统监督者。
你管理以下代理：
🔍 **schema_agent**: 分析用户查询，获取准确的数据库表结构
⚙️ **sql_generator_agent**: 生成准确的SQL
...
工作原则:
1. 如果用户请求包含"图表"、"画图"，必须调用 chart_generator_agent
2. 一次只分配一个代理
"""
```
这段文字会被发送给 LLM（大模型），LLM 读了之后就知道自己该扮演什么角色，该怎么指挥小弟。

### 4.2 状态是如何传递的？
在 `backend/app/core/state.py` 中定义了 `SQLMessageState`：

```python
class SQLMessageState(TypedDict):
    messages: List[AnyMessage]      # 聊天记录
    connection_id: int              # 当前连的是哪个数据库
    schema_info: Dict[str, Any]     # 查到的表结构
    generated_sql: str              # 生成的 SQL
    execution_result: Dict          # 执行结果
    error: str                      # 报错信息
```
这个 State 对象就像一个接力棒，在所有智能体手中传递，每个人都往里面填自己负责的那部分信息。

---

## 5. 小白上手建议

如果你想修改这个项目，建议按以下顺序入手：

1.  **想改 Prompt（提示词）？**
    *   去 `backend/app/agents/agents/` 目录下，找到对应的 Agent 文件（如 `sql_generator_agent.py`），修改里面的 `system_prompt` 变量。这是最立竿见影的优化方式。

2.  **想加新功能？**
    *   比如加一个“导出 Excel”的功能。你需要：
        1. 在 `agents/` 下新建 `excel_export_agent.py`。
        2. 在 `supervisor_agent.py` 里注册这个新 Agent。
        3. 告诉队长（修改 Prompt）什么时候该叫这个新 Agent 出来干活。

3.  **想改前端界面？**
    *   去 `frontend/chat/src/components/` 找对应的组件。

## 6. 总结

Chat-To-DB 本质上是一个**状态机**。
- **输入**：自然语言。
- **状态流转**：通过 LLM 判断当前状态，决定下一步跳到哪个节点（Agent）。
- **输出**：结构化的数据和图表。

希望这份指南能帮你快速看懂项目！如有疑问，欢迎查阅 `README.md` 或直接阅读源码。
