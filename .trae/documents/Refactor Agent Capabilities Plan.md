# Implementation Plan: Refactoring Agent Capabilities & Logic

I will refactor the agent configuration UI and backend logic to eliminate ambiguity by treating "Tools" as "Expert Capabilities".

## Phase 1: Admin Frontend UI Refinement
- [x] Modify [AgentProfile/index.tsx](file:///Users/pusonglin/chat-to-db/frontend/admin/src/pages/AgentProfile/index.tsx):
    - Change form label from "启用工具 (Tools)" to "专家能力配置 (Capabilities)".
    - Update the `Select` component for tools:
        - **Remove** `sql_generator_core` and `router_core` options (they are system infrastructure, not expert tools).
        - **Rename** `chart_analyst_core` option to "图表生成与可视化分析".
    - Update the "New Agent" initialization to **default select** `chart_analyst_core`.

## Phase 2: Backend Logic Enhancement
- [x] Update [supervisor_agent.py](file:///Users/pusonglin/chat-to-db/backend/app/agents/agents/supervisor_agent.py):
    - Refine the dynamic agent creation logic:
        - Check the `profile.tools` list.
        - **Only inject** chart generation tools into the custom expert if `chart_analyst_core` is explicitly present in its configuration.
        - If not present, the expert will only have text analysis capabilities.
