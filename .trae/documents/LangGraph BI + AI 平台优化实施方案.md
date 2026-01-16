# BI + AI 智能化分析平台优化方案

基于当前 `chat-to-db` 项目结构（LangGraph 架构）及您的需求，制定以下优化实施方案：

## 1. Admin 后台管理端：模型配置 (Model Management)

当前 LLM 配置依赖环境变量 (`.env`)，无法动态切换。我们将实现基于数据库的动态配置。

### 技术实现
*   **数据库设计**: 新增 `LLMConfiguration` 表
    *   字段: `id`, `provider` (OpenAI, Deepseek, AliYun...), `api_key`, `base_url`, `model_name`, `model_type` (chat/embedding), `is_active`
*   **后端 API**:
    *   `POST /api/v1/llm-configs`: 创建配置
    *   `POST /api/v1/llm-configs/test`: 连接测试 (调用 simple invoke 验证)
    *   `PUT/DELETE`: 编辑与删除
*   **LangGraph 集成**:
    *   修改 `app/core/llms.py` 中的 `get_default_model` 等工厂函数。
    *   使其优先从数据库读取 `is_active=True` 的配置，而非仅依赖 `settings`。

## 2. Admin 后台管理端：智能体配置 (Agent Configuration)

实现智能体的动态编排与配置，让用户自定义分析维度。

### 技术实现
*   **数据库设计**: 新增 `AgentProfile` 表
    *   字段: `id`, `name` (e.g., "销售分析师"), `role_description`, `system_prompt`, `tools` (JSON list), `model_config_id` (关联 LLM 配置)
*   **LangGraph 集成**:
    *   **Supervisor 升级**: 修改 `SupervisorAgent` (`app/agents/agents/supervisor_agent.py`)。
    *   在构建 Graph 时，不再硬编码 worker list，而是从数据库加载激活的 Agent Profile，动态生成 `create_react_agent` 实例并注册到 Supervisor。
    *   支持用户在界面选择 "当前会话使用哪个 Agent 组合"。

## 3. Admin 后台管理端：多源数据支持

扩展现有 `DBConnection` 支持主流数据库。

### 技术实现
*   **现有分析**: `DBConnection` 模型已存在 (`app/models/db_connection.py`)，且 `db_type` 为字符串，具备扩展性。
*   **连接层升级 (`app/services/db_service.py`)**:
    *   **SQLite**: 增加文件路径处理或上传逻辑（对于本地 SQLite）。
    *   **PostgreSQL/MySQL**: 完善驱动支持 (`psycopg2`, `pymysql`) 及连接串构建逻辑。
    *   **连接测试**: 增强 `test_connection` 接口，针对不同数据库类型执行特定的 "Ping" 操作。

## 4. Chat 对话：相似问题与图表生成 (BI + AI 核心)

### A. 相似问题推荐 (Similar Questions)
利用向量检索技术，根据用户当前问题推荐历史相似问题。
*   **实现**:
    1.  集成向量库（利用现有的 Milvus 或简单实现基于 PGVector/Chroma）。
    2.  **嵌入模型**: 使用后台配置的 Embedding 模型。
    3.  **流程**: 用户提问 -> Embedding -> 检索历史高频/相似 Query -> 展示给用户。

### B. AntV 图表生成 (MCP 集成)
基于 MCP (Model Context Protocol) 连接阿里云 AntV 可视化服务。

*   **当前状态**: `ChartGeneratorAgent` 目前尝试使用 stdio 方式调用本地 MCP。
*   **升级方案**:
    *   **SSE Client**: 修改 `_initialize_chart_client`，支持 SSE (Server-Sent Events) 传输协议。
    *   **配置注入**: 将您提供的 MCP 配置（URL, Headers）注入到 `MultiServerMCPClient`。
    *   **Graph 路由**: 确保 `Supervisor` 能够准确识别 "画图"、"可视化" 意图，并将任务路由给 `chart_generator_agent`。
    *   **工具增强**: 确保 Agent 能调用 MCP 提供的 `create_chart` 等工具，并将生成的 JSON 配置返回给前端渲染。

## 实施路线图
1.  **基础设施**: 创建数据库表 (`LLMConfiguration`, `AgentProfile`) 及 CRUD API。
2.  **数据源**: 完善多数据库连接支持。
3.  **核心 Agent**: 改造 `Supervisor` 和 `ChartGeneratorAgent` 以支持动态配置和 MCP SSE 连接。
4.  **前端/交互**: 对接新 API，展示图表和相似问题。
