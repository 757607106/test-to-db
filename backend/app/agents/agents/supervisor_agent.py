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

from langgraph_supervisor import create_supervisor
from langgraph.errors import GraphInterrupt
from langchain_core.messages import trim_messages as langchain_trim_messages, AIMessage
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
MAX_TOKENS_FOR_LLM = 4000  # Token 限制（根据模型上下文窗口调整）


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


def combined_pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    组合的 pre_model_hook - 同时处理消息裁剪、状态追踪、防护检查和 connection_id 提取
    """
    updates = {}
    messages = state.get("messages", [])
    
    # 0. 确保 connection_id 和 db_type 正确设置
    if not state.get("connection_id"):
        connection_id = extract_connection_id(state)
        if connection_id:
            updates["connection_id"] = connection_id
            logger.info(f"pre_model_hook 提取 connection_id: {connection_id}")
    
    # 确保 db_type 有默认值
    if not state.get("db_type"):
        # 尝试从数据库连接中获取 db_type
        connection_id = state.get("connection_id") or updates.get("connection_id")
        logger.info(f"[pre_model_hook] db_type 未设置，尝试从 connection_id={connection_id} 获取")
        if connection_id:
            try:
                from app.services.db_service import get_db_connection_by_id
                connection = get_db_connection_by_id(connection_id)
                if connection and connection.db_type:
                    updates["db_type"] = connection.db_type.lower()
                    logger.info(f"[pre_model_hook] 成功设置 db_type: {updates['db_type']}")
                else:
                    logger.warning(f"[pre_model_hook] connection 为空或无 db_type，使用默认值 mysql")
                    updates["db_type"] = "mysql"
            except Exception as e:
                logger.error(f"[pre_model_hook] 获取 db_type 失败: {e}")
                updates["db_type"] = "mysql"  # 默认值
        else:
            logger.warning("[pre_model_hook] connection_id 未设置，使用默认 db_type=mysql")
            updates["db_type"] = "mysql"
    else:
        logger.debug(f"[pre_model_hook] db_type 已存在: {state.get('db_type')}")
    
    # 1. 自动状态追踪：识别最后执行的 Agent 并更新 completed_stages 和 agent_call_history
    # 这样防护机制（Guards）就能准确感知当前进度
    last_agent = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.name and msg.name != "supervisor":
            last_agent = msg.name
            break
    
    if last_agent and last_agent != state.get("last_agent_called"):
        # 发现新完成的 Agent 任务，更新状态
        stage = get_stage_for_agent(last_agent)
        tracking_updates = update_guard_state(state, last_agent, stage)
        state.update(tracking_updates)  # 更新本地 state 以供后续 hook 使用
        updates.update(tracking_updates) # 传播更新
        logger.info(f"自动追踪：检测到 {last_agent} 执行完成，阶段更新为 {stage}")

    # 1. 防护检查（获取状态更新，不处理消息）
    guard_updates = guard_check_hook(state)
    
    # 提取防护状态键（排除内部标记）
    for key, value in guard_updates.items():
        if not key.startswith("_"):
            updates[key] = value
    
    # 2. 处理防护触发情况
    if guard_updates.get("_guard_triggered"):
        stop_message = guard_updates.get("_guard_stop_message")
        if stop_message:
            # 官方规范：使用 llm_input_messages 传递给 LLM，不修改原始历史
            updates["llm_input_messages"] = messages + [stop_message]
        else:
            updates["llm_input_messages"] = messages
        return updates
    
    # 3. 消息裁剪 - 使用官方 trim_messages
    trimmed = langchain_trim_messages(
        messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=MAX_TOKENS_FOR_LLM,
        start_on="human",
        include_system=True,
        allow_partial=False,
    )
    
    if len(trimmed) != len(messages):
        logger.info(f"消息裁剪: {len(messages)} -> {len(trimmed)} 条")
    
    # 官方规范：必须返回 llm_input_messages（确保符合 API 要求）
    updates["llm_input_messages"] = trimmed
    
    return updates


class SupervisorAgent:
    """
    监督代理 - 基于 LangGraph Supervisor
    
    职责：协调各个 Worker Agent，由 LLM 决策调度流程
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
        from app.agents.agents.schema_agent import schema_agent  # 1. 获取数据库结构
        from app.agents.agents.clarification_agent import clarification_agent  # 2. 澄清用户意图（可选）
        from app.agents.agents.sql_generator_agent import sql_generator_agent  # 3. 生成 SQL 语句
        from app.agents.agents.sql_validator_agent import sql_validator_agent  # 4. 验证 SQL 语法
        from app.agents.agents.sql_executor_agent import sql_executor_agent  # 5. 执行 SQL 查询
        from app.agents.agents.error_recovery_agent import error_recovery_agent  # 6. 错误恢复（按需）
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 7. 生成图表配置（可选）
        from app.agents.agents.data_analyst_agent import data_analyst_agent  # 8. 数据分析

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
        from app.agents.agents.data_analyst_agent import data_analyst_agent, DataAnalystAgent
        
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

    def _create_supervisor(self):
        """创建 LangGraph Supervisor"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=True,  # 让 Supervisor 看到 Agent 返回结果，支持动态决策
            output_mode="full_history",  # 保留完整消息历史，避免 Agent 返回后清除之前的消息
            pre_model_hook=combined_pre_model_hook,  # 组合 hook：防护检查 + 消息裁剪
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
