# Implementation Plan: LangGraph System Design & Enhancements

I will implement the approved design in three phases, ensuring strict adherence to the requirements.

## Phase 1: Backend Core & API Implementation
### 1. Model & Database Schema Update
- [x] Modify `AgentProfile` model in `backend/app/models/agent_profile.py` to add `is_system` (Boolean, default=False) field.
- [x] Update Pydantic schemas in `backend/app/schemas/agent_profile.py` to include `is_system`.
- [x] Create/Update database migration to apply the schema change.
- [x] Update `init_db.py` to ensure core system agents (`sql_generator_core`, `chart_analyst_core`, `router_core`) are initialized with `is_system=True`.

### 2. API Enhancements
- [x] Update `GET /agent-profiles/` in `backend/app/api/api_v1/endpoints/agent_profiles.py` to support filtering (default behavior: return all, but allow frontend to filter or separate endpoints). *Refinement: Better to filter by default or add a query param.*
- [x] Implement `POST /agent-profiles/optimize-prompt` endpoint:
    - Input: Simple user description.
    - Logic: Use a Meta-Prompt to generate a professional System Prompt.
    - Output: Optimized prompt text.

## Phase 2: Admin Frontend Implementation
### 1. Agent Management Page (`AgentProfile/index.tsx`)
- [x] Update API service `frontend/admin/src/services/agentProfile.ts` to include `optimizePrompt` method.
- [x] Modify the list view to **hide** agents where `is_system=True`.
- [x] Add "✨ Smart Optimize" button to the "System Prompt" field in the Create/Edit modal.
- [x] Implement the click handler to call the optimization API and fill the textarea.

### 2. LLM Configuration Page (`LLMConfig/index.tsx`)
- [x] Verify "System Core Agents" section correctly handles the new `is_system` flag (it should effectively manage the `is_system=True` agents).

## Phase 3: Chat Frontend & Routing Logic
### 1. Chat Interface
- [x] Update agent fetching logic in Chat UI to **exclude** `is_system=True` agents from the user selection list.
- [x] Ensure the "Default Assistant" is available as a fallback or explicit option.

### 2. Router & Supervisor Logic
- [x] Verify `backend/app/agents/agents/supervisor_agent.py` correctly handles the substitution logic:
    - If a custom agent is selected, ensure it replaces the default `chart_generator_agent` but inherits its tools.
