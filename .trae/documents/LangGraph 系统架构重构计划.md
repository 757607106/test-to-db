# 系统重构与优化方案 (基于 LangGraph)

基于对当前项目的深度分析，我制定了以下重构计划，旨在增强系统的架构合理性、配置灵活性以及用户体验。

## 1. 架构优化：引入顶层路由 (Router)
**现状**：所有用户输入直接进入重型的 SQL Supervisor，导致闲聊也消耗昂贵资源且容易出错。
**方案**：在 LangGraph 的入口处增加一个 **语义分类节点 (Router Node)**。
- **流程**：`Start` -> `Router`
    - 分支 A (`General`): 指向 **通用聊天 Agent** (处理 "你好", "你是谁" 等)。
    - 分支 B (`Data`): 指向 **SQL Supervisor** (处理数据查询、分析)。
- **收益**：大幅降低 Token 消耗，提升非数据类问题的响应速度和准确度。

## 2. 核心功能增强：模型配置颗粒度
**现状**：代码中存在 TODO，目前所有 Agent 共用默认模型。
**方案**：
- **落实配置**：修改 Agent 创建逻辑，使其真正读取 `AgentProfile.llm_config_id`。
- **差异化策略**：
    - **SQL Agent**: 使用高逻辑能力的模型 (如 DeepSeek-V3, GPT-4o)。
    - **Data Analyst**: 使用长窗口/高文本能力的模型 (如 Claude 3 Opus)。
    - **Router/General**: 使用轻量级模型 (如 GPT-4o-mini)。

## 3. 业务逻辑升级：智能体多选与动态加载
**现状**：Supervisor 一次性加载所有 Active Agents，且只支持单选逻辑。
**方案**：
- **前端支持**：设计支持多选 Agent 的上下文逻辑。
- **后端动态加载**：
    - 修改 `SupervisorAgent`，不再加载所有 Agent。
    - 仅将**用户当前选中**的 Agent 注入到 Supervisor 的工具列表和 Prompt 中。
    - **默认行为**：若未选择，则根据系统配置使用默认 Agent 或仅使用基础 SQL 能力。

## 实施步骤
1.  **重构 `SupervisorAgent`**:
    - 支持传入 `agent_ids` 列表。
    - 修复模型加载逻辑，支持 `llm_config_id`。
2.  **实现 `RouterAgent`**:
    - 创建一个新的轻量级 Agent 用于意图分类。
3.  **重构 `IntelligentSQLGraph`**:
    - 重新编排 Graph 结构，添加 Conditional Edges (条件边)。
    - 整合 Router 和 General Agent。

请确认是否按照此方案进行开发？