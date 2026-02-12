"""
监督代理 - 使用 LangGraph Supervisor

核心职责：
- 协调各个专门代理的工作流程
- 由 LLM 动态决策调度，不依赖硬编码流程
- 通过 Agent 能力描述和边界约束实现智能且可控的调度

设计原则：
- LLM 根据当前状态自主选择下一个 Agent
- 每个 Agent 职责边界清晰
- 防护机制确保系统稳定
"""
from typing import Dict, Any, List, Optional
import logging
import asyncio

from langgraph_supervisor import create_supervisor
from langgraph.errors import GraphInterrupt
from langchain_core.messages import trim_messages as langchain_trim_messages, AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SUPERVISOR
from app.core.state import extract_connection_id
from app.agents.utils.supervisor_guards import (
    run_all_guards,
    update_guard_state,
    get_stage_for_agent,
    MAX_SUPERVISOR_TURNS,
    should_reset_turn_count,
    reset_guard_state,
)

logger = logging.getLogger(__name__)

# ===== 消息裁剪配置 =====
DEFAULT_CONTEXT_WINDOW = 32000   # 默认上下文窗口（qwen3-max 为 32K）
SYSTEM_PROMPT_RESERVE = 2000     # 为 system prompt 和 handoff 工具描述预留
OUTPUT_TOKEN_RESERVE = 8192      # 为 LLM 输出预留（与 max_tokens 对齐）


def guard_check_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    防护检查钩子 - 在每次 LLM 调用前检查防护条件
    
    检查项：
    - 最大轮次限制
    - Agent 循环检测
    - 用户新消息时重置轮次（重要：确保每次用户请求有完整配额）
    
    返回值规范（官方文档）：
    - 必须返回 state update 字典
    - 可以包含任意状态键用于传播
    - 注意：llm_input_messages 由 combined_pre_model_hook 统一处理
    """
    updates = {}
    
    # 检查是否需要重置轮次（用户发送新消息时）
    if should_reset_turn_count(state):
        reset_updates = reset_guard_state(state)
        state.update(reset_updates)  # 立即更新状态
        updates.update(reset_updates)  # 传播到返回值
        logger.info("轮次计数已重置，开始处理新用户请求")
    
    # 运行防护检查
    guard_result = run_all_guards(state)
    
    if guard_result.get("should_stop"):
        reason = guard_result.get("reason", "达到系统限制")
        logger.warning(f"防护机制触发: {reason}")
        
        # 添加一条消息通知 Supervisor 应该停止
        stop_message = AIMessage(
            content=f"[系统提示] {reason}。请直接向用户回复当前状态并结束对话。",
            name="system_guard"
        )
        
        # 标记防护触发，让 combined_pre_model_hook 处理消息
        updates["_guard_triggered"] = True
        updates["_guard_stop_message"] = stop_message
        return updates
    
    # 更新轮次计数
    turn_count = state.get("supervisor_turn_count", 0)
    updates["supervisor_turn_count"] = turn_count + 1
    
    return updates


def create_pre_model_hook(trim_token_limit: int):
    """
    创建 pre_model_hook 闭包 - 将动态 token 限制注入 hook
    
    Args:
        trim_token_limit: 消息裁剪的 token 上限，由 SupervisorAgent 
                          根据模型上下文窗口动态计算
    
    Returns:
        async pre_model_hook 函数，符合 LangGraph Supervisor 官方规范：
        - 返回 llm_input_messages（仅影响 LLM 输入，不修改状态中的消息历史）
        - 返回其他状态键用于传播（connection_id, db_type, skill_context 等）
        - 首次调用时执行 Skill 路由和 QA 样本检索
    """
    async def combined_pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
        updates = {}
        messages = state.get("messages", [])
        
        # 0. 确保 connection_id 正确设置
        connection_id = state.get("connection_id")
        if not connection_id:
            connection_id = extract_connection_id(state)
            if connection_id:
                updates["connection_id"] = connection_id
                logger.info(f"pre_model_hook 提取 connection_id: {connection_id}")
        
        # 1. 首次调用预处理：db_type + Skill 路由 + QA 样本检索
        #    判断条件：skill_context 不存在 → 第一次进入 Supervisor
        if state.get("skill_context") is None and connection_id:
            await _first_call_preprocessing(state, updates, connection_id, messages)
        elif not state.get("db_type"):
            # 没有 connection_id 时（如闲聊），仅确保 db_type 有默认值
            updates["db_type"] = "mysql"
        
        # 2. 自动状态追踪：识别最后执行的 Agent 并更新 completed_stages
        last_agent = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.name and msg.name != "supervisor":
                last_agent = msg.name
                break
        
        if last_agent and last_agent != state.get("last_agent_called"):
            stage = get_stage_for_agent(last_agent)
            tracking_updates = update_guard_state(state, last_agent, stage)
            state.update(tracking_updates)
            updates.update(tracking_updates)
            logger.info(f"自动追踪：检测到 {last_agent} 执行完成，阶段更新为 {stage}")

        # 3. 防护检查
        guard_updates = guard_check_hook(state)
        
        for key, value in guard_updates.items():
            if not key.startswith("_"):
                updates[key] = value
        
        # 处理防护触发
        if guard_updates.get("_guard_triggered"):
            stop_message = guard_updates.get("_guard_stop_message")
            if stop_message:
                updates["llm_input_messages"] = messages + [stop_message]
            else:
                updates["llm_input_messages"] = messages
            return updates
        
        # 4. 消息裁剪
        trimmed = langchain_trim_messages(
            messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=trim_token_limit,
            start_on="human",
            include_system=True,
            allow_partial=False,
        )
        
        if len(trimmed) != len(messages):
            logger.info(f"消息裁剪: {len(messages)} -> {len(trimmed)} 条 (limit={trim_token_limit} tokens)")
        
        updates["llm_input_messages"] = trimmed
        
        return updates
    
    return combined_pre_model_hook


async def _first_call_preprocessing(
    state: Dict[str, Any],
    updates: Dict[str, Any],
    connection_id: int,
    messages: list
) -> None:
    """
    首次调用预处理 - 获取 db_type、Skill 路由、QA 样本
    
    只在 Supervisor 的第一轮 LLM 调用前执行（通过 skill_context is None 判断）。
    这些数据注入 state 后，后续 Agent 可以直接使用。
    """
    logger.info(f"[首次预处理] 开始 - connection_id={connection_id}")
    
    # 提取用户查询（取最后一条 human 消息）
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            user_query = msg.get("content", "")
            break
    
    # 1. 获取 db_type（从数据库查询，异步安全）
    try:
        from app.services.db_service import get_db_connection_by_id
        connection = await asyncio.to_thread(get_db_connection_by_id, connection_id)
        db_type = connection.db_type.lower() if connection and connection.db_type else "mysql"
        updates["db_type"] = db_type
        logger.info(f"[首次预处理] db_type={db_type}")
    except Exception as e:
        logger.warning(f"[首次预处理] 获取 db_type 失败: {e}, 使用默认值 mysql")
        updates["db_type"] = "mysql"
    
    if not user_query:
        # 没有用户查询（不太可能），跳过 Skill 和 QA
        updates["skill_context"] = {"enabled": False}
        updates["sample_retrieval_result"] = {"qa_pairs": []}
        return
    
    # 2. 并行执行 Skill 路由 + QA 样本检索
    try:
        from app.agents.utils.skill_routing import (
            perform_skill_routing,
            format_skill_context_for_prompt,
        )
        
        skill_task = perform_skill_routing(user_query, connection_id)
        qa_task = _retrieve_qa_samples_safe(user_query, connection_id)
        
        skill_result, sample_result = await asyncio.gather(
            skill_task, qa_task, return_exceptions=True
        )
        
        # 处理 Skill 路由结果
        if isinstance(skill_result, Exception):
            logger.warning(f"[首次预处理] Skill 路由失败: {skill_result}")
            updates["skill_context"] = {"enabled": False}
        else:
            updates["skill_context"] = {
                "enabled": skill_result.enabled,
                "matched_skills": skill_result.matched_skills,
                "schema_info": skill_result.schema_info,
                "business_rules": skill_result.business_rules,
                "join_rules": skill_result.join_rules,
                "strategy_used": skill_result.strategy_used,
                "reasoning": skill_result.reasoning,
                "prompt_context": format_skill_context_for_prompt(skill_result),
            }
            if skill_result.enabled:
                logger.info(f"[首次预处理] Skill 路由: {skill_result.reasoning}")
            else:
                logger.info(f"[首次预处理] Skill 路由: {skill_result.reasoning}，使用全库模式")
        
        # 处理 QA 样本结果
        if isinstance(sample_result, Exception):
            logger.warning(f"[首次预处理] QA 样本检索失败: {sample_result}")
            updates["sample_retrieval_result"] = {"qa_pairs": []}
        else:
            updates["sample_retrieval_result"] = sample_result
            if sample_result.get("qa_pairs"):
                logger.info(f"[首次预处理] QA 样本: {len(sample_result['qa_pairs'])} 个")
    
    except Exception as e:
        logger.warning(f"[首次预处理] Skill/QA 预处理失败: {e}")
        updates["skill_context"] = {"enabled": False}
        updates["sample_retrieval_result"] = {"qa_pairs": []}
    
    logger.info("[首次预处理] 完成")


async def _retrieve_qa_samples_safe(
    query: str, connection_id: int
) -> Dict[str, Any]:
    """安全的 QA 样本检索（带配置检查和超时保护）"""
    try:
        from app.db.session import SessionLocal
        from app.crud import system_config
        
        # 获取配置（同步 DB 调用，使用线程池）
        def _get_config():
            db = SessionLocal()
            try:
                return system_config.get_qa_sample_config(db)
            finally:
                db.close()
        
        cfg = await asyncio.to_thread(_get_config)
        
        if not cfg.get("enabled", True):
            return {"qa_pairs": [], "enabled": False}
        
        from app.services.hybrid_retrieval.engine.engine_pool import HybridRetrievalEnginePool
        
        timeout = cfg.get("timeout_seconds", 5)
        qa_samples = await asyncio.wait_for(
            HybridRetrievalEnginePool.quick_retrieve(
                user_query=query,
                schema_context={"tables": [], "user_query": query},
                connection_id=connection_id,
                top_k=cfg.get("top_k", 3),
                min_similarity=cfg.get("min_similarity", 0.6)
            ),
            timeout=timeout
        )
        
        return {
            "qa_pairs": qa_samples,
            "enabled": True,
            "connection_id": connection_id,
            "count": len(qa_samples)
        }
    
    except asyncio.TimeoutError:
        logger.warning("[QA样本检索] 超时")
        return {"qa_pairs": [], "enabled": True, "timeout": True}
    except Exception as e:
        logger.warning(f"[QA样本检索] 失败: {e}")
        return {"qa_pairs": [], "error": str(e)}


class SupervisorAgent:
    """
    监督代理 - Agent 调度层（Agent Orchestration Layer）
    
    架构定位：
    - 基于 langgraph-supervisor 的 create_supervisor，由 LLM 动态决策调度
    - 管理所有 Worker Agent（schema/sql_generator/sql_validator/sql_executor/
      data_analyst/error_recovery/chart_generator/clarification）
    - 通过 pre_model_hook 实现防护检查和消息裁剪
    
    调用链路：
    IntelligentSQLGraph._handle_sql_query() → SupervisorAgent.supervise()
        → LLM 决策 → handoff to Worker Agent → LLM 决策 → ... → 完成
    """

    def __init__(
        self, 
        worker_agents: List[Any] = None, 
        enable_clarification: bool = True,
        custom_analyst_id: Optional[int] = None
    ):
        self.llm = get_agent_llm(CORE_AGENT_SUPERVISOR)
        self.enable_clarification = enable_clarification
        self.custom_analyst_id = custom_analyst_id
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理列表"""
        # 导入所有 Worker Agents（按执行顺序排列）
        from app.agents.schema_agent import schema_agent  # 1. 获取数据库结构
        from app.agents.clarification_agent import clarification_agent  # 2. 澄清用户意图(可选)
        from app.agents.sql_generator_agent import sql_generator_agent  # 3. 生成 SQL 语句
        from app.agents.sql_validator_agent import sql_validator_agent  # 4. 验证 SQL 语法
        from app.agents.sql_executor_agent import sql_executor_agent  # 5. 执行 SQL 查询
        from app.agents.error_recovery_agent import error_recovery_agent  # 6. 错误恢复(按需)
        from app.agents.chart_generator_agent import chart_generator_agent  # 7. 生成图表配置(可选)
        from app.agents.data_analyst_agent import data_analyst_agent  # 8. 数据分析

        analyst_agent = self._get_data_analyst_agent()

        agents = [
            schema_agent.agent,
            sql_generator_agent.agent,
            sql_validator_agent.agent,
            sql_executor_agent.agent,
            analyst_agent.agent if hasattr(analyst_agent, 'agent') else analyst_agent,
            error_recovery_agent.agent,
            chart_generator_agent.agent,
        ]
        
        # 如果启用澄清，添加 clarification_agent
        if self.enable_clarification:
            agents.insert(1, clarification_agent.agent)  # 放在 schema_agent 之后
        
        return agents

    def _get_data_analyst_agent(self):
        """获取数据分析 Agent（支持自定义配置）"""
        from app.agents.data_analyst_agent import data_analyst_agent, DataAnalystAgent
        
        if not self.custom_analyst_id:
            return data_analyst_agent
        
        try:
            from app.db.session import get_db_session
            from app.crud import agent_profile as crud_agent_profile
            from app.core.agent_config import get_custom_agent_llm
            
            with get_db_session() as db:
                profile = crud_agent_profile.get(db, id=self.custom_analyst_id)
                
                if not profile or not profile.is_active:
                    return data_analyst_agent
                
                custom_llm = get_custom_agent_llm(profile, db)
                custom_prompt = profile.system_prompt if profile.system_prompt else None
                
                logger.info(f"使用自定义数据分析 Agent: {profile.name}")
                return DataAnalystAgent(custom_prompt=custom_prompt, llm=custom_llm)
                
        except Exception as e:
            logger.error(f"加载自定义 Agent 失败: {e}")
            return data_analyst_agent

    def _get_trim_token_limit(self) -> int:
        """根据模型上下文窗口动态计算消息裁剪的 token 上限"""
        max_output = getattr(self.llm, 'max_tokens', None) or OUTPUT_TOKEN_RESERVE
        trim_limit = max(4000, DEFAULT_CONTEXT_WINDOW - max_output - SYSTEM_PROMPT_RESERVE)
        logger.info(f"消息裁剪 token 上限: {trim_limit} "
                    f"(context={DEFAULT_CONTEXT_WINDOW}, output={max_output}, reserve={SYSTEM_PROMPT_RESERVE})")
        return trim_limit

    def _create_supervisor(self):
        """创建 LangGraph Supervisor"""
        # 根据模型动态计算 token 裁剪上限，通过闭包注入 pre_model_hook
        trim_limit = self._get_trim_token_limit()
        pre_hook = create_pre_model_hook(trim_limit)
        
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=False,  # 禁用以避免 null ID 消息干扰前端消息合并逻辑
            output_mode="full_history",  # 保留完整消息历史，避免 Agent 返回后清除之前的消息
            pre_model_hook=pre_hook,  # 组合 hook：防护检查 + 动态消息裁剪
            state_schema=SQLMessageState,
            parallel_tool_calls=True,  # 启用并行 Agent 调用（仅 OpenAI/Anthropic 支持，其他模型自动降级为串行）
        )

        try:
            from app.core.checkpointer import get_checkpointer
            checkpointer = get_checkpointer()
        except Exception as e:
            logger.warning(f"获取 Checkpointer 失败: {e}")
            checkpointer = None

        if checkpointer is not None:
            return supervisor.compile(checkpointer=checkpointer)

        return supervisor.compile()

    def _get_supervisor_prompt(self) -> str:
        """
        获取监督代理提示词 - 官方稳定性增强版 + 显性思维链
        """
        
        clarification_desc = ""
        if self.enable_clarification:
            clarification_desc = """
**clarification_agent** - 业务意图澄清
  - **前置条件**：必须在 `schema_agent` 完成之后调用，因为澄清需要基于已获取的数据结构信息。
  - **触发场景**：
    1. 用户问题存在业务歧义（如"最近"没有明确时间范围、"大客户"没有定义标准）
    2. schema_agent 返回的表/字段存在多种可能解释
    3. SQL 执行失败需要向用户解释并确认调整方案
  - **业务化原则**：澄清问题必须用业务语言表达，严禁暴露表名、字段名、SQL 等技术细节。
  - **澄清后判断**：用户回答后，根据回答内容判断是否需要重新调用 `schema_agent` 扩展或调整数据范围。
"""
        
        return f"""你是一个高级数据分析协调专家。你的目标是确保用户的问题得到准确、安全、且深度解析的回答。

## 闲聊与问候处理

如果用户的消息是闲聊或问候（如"你好"、"hello"、"帮助"、"你能做什么"），直接用友好的语言回复，不要调用任何 Agent。
回复时介绍你的核心能力：智能 SQL 生成、数据分析、数据可视化等。

## 执行链路准则 (稳定性核心)

1. **Schema 优先**：在生成任何 SQL 之前，必须确保调用过 `schema_agent` 且状态中已有 `schema_info`。
2. **澄清在 Schema 之后**：如果用户问题存在歧义，必须在 `schema_agent` 完成后、`sql_generator_agent` 之前调用 `clarification_agent`。
   - 澄清必须基于已获取的 Schema 信息，用业务语言提问（不暴露表名/字段名）。
   - 用户回答后，判断是否需要重新调用 `schema_agent` 调整数据范围。
3. **验证闭环**：`sql_generator_agent` 生成 SQL 后，严禁直接执行，必须先调用 `sql_validator_agent` 进行安全和语法检查。
4. **错误自愈**：如果执行失败，优先调用 `clarification_agent` 向用户解释业务原因，只有技术性错误才调用 `error_recovery_agent`。
5. **状态感知**：关注 `current_stage` 字段：
   - `schema_analysis` -> 调用 `schema_agent`
   - `schema_done` -> 检查是否需要澄清，若需要则调用 `clarification_agent`
   - `sql_generation` -> 调用 `sql_generator_agent`
   - `sql_validation` -> 调用 `sql_validator_agent`
   - `sql_execution` -> 调用 `sql_executor_agent`

## 专业代理能力

**schema_agent** - 领域知识提取
  - 能力：分析查询涉及的表、字段、关联关系和业务逻辑。
  - 输出：结构化 Schema 信息和查询分析报告。
{clarification_desc}
**sql_generator_agent** - SQL 专家
  - 能力：基于已有的 Schema 信息和查询分析生成高性能 SQL。
  - 约束：必须参考 `query_analysis` 中的聚合和时间维度建议。

**sql_validator_agent** - 安全与合规审计
  - 能力：防止注入，检查数据库方言兼容性。

**sql_executor_agent** - 数据获取
  - 能力：安全执行查询并返回原始数据。

**data_analyst_agent** - 商业洞察
  - 能力：不仅解读数据，还要发现趋势、异常并提供业务建议。

**error_recovery_agent** - 错误恢复
  - 能力：分析 SQL 执行错误，修复语法或逻辑问题，生成恢复方案。

**chart_generator_agent** - 数据可视化
  - 能力：根据查询结果数据和分析结论，生成适合的图表配置。

## 澄清后的重新分析判断
当 `clarification_agent` 完成用户澄清后，必须判断用户的回答是否改变了查询范围：
- **需要重新 Schema 分析**：用户明确了新的数据维度、时间范围扩大、涉及新的业务概念。
- **不需要重新分析**：用户只是确认了模糊概念的具体值（如"最近"指"最近7天"），当前 Schema 已足够。

## 决策逻辑
- 始终保持原子化操作，一次只调用一个 Agent。
- 观察上一个 Agent 的 `ToolMessage` 输出，如果包含错误信息，立即进入错误处理路径。
"""

    async def supervise(self, state: SQLMessageState, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        监督整个流程
        
        设计：让 Supervisor LLM 自然调度所有 Agent，不做硬编码控制
        """
        try:
            # 如果没有提供 thread_id 但 Checkpointer 存在，生成一个默认的
            if not thread_id:
                from uuid import uuid4
                thread_id = str(uuid4())
                logger.info(f"自动生成 thread_id: {thread_id}")
            
            config = {"configurable": {"thread_id": thread_id}}
            
            logger.info("开始 Supervisor 流程调度")
            result = await self.supervisor.ainvoke(state, config=config)
            
            return {
                "success": True,
                "result": result,
            }
            
        except GraphInterrupt:
            # interrupt() 暂停流程，需要传播出去
            raise
        except Exception as e:
            logger.error(f"监督流程失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# ============================================================================
# 便捷函数
# ============================================================================

def create_supervisor_agent(
    worker_agents: List[Any] = None,
    enable_clarification: bool = True,
    custom_analyst_id: Optional[int] = None
) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents, enable_clarification, custom_analyst_id)


def create_intelligent_sql_supervisor(
    enable_clarification: bool = True,
    custom_analyst_id: Optional[int] = None
) -> SupervisorAgent:
    """创建智能 SQL 监督代理"""
    return SupervisorAgent(
        enable_clarification=enable_clarification,
        custom_analyst_id=custom_analyst_id
    )
