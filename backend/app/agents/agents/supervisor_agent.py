"""
监督代理 - 使用 LangGraph Supervisor

核心职责：
- 协调各个专门代理的工作流程
- 由 LLM 决策调度，不依赖硬编码逻辑
- 管理标准流程：Schema → Clarification → SQL 生成 → 执行 → 分析

设计原则：
- 让 LLM 决策，不写复杂的 if-else
- 每个 Agent 职责边界清晰
- 流程简洁，易于维护
"""
from typing import Dict, Any, List, Optional
import logging

from langgraph_supervisor import create_supervisor
from langgraph.errors import GraphInterrupt
from langchain_core.messages import trim_messages as langchain_trim_messages

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SUPERVISOR

logger = logging.getLogger(__name__)

# ===== 消息裁剪配置 =====
MAX_MESSAGES_FOR_LLM = 30


def trim_messages_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    消息历史裁剪钩子 - 使用官方 trim_messages 确保 tool_call/tool 消息配对完整
    
    官方依据: https://python.langchain.com/docs/how_to/trim_messages
    关键参数:
    - start_on="human": 确保消息从 human 开始
    - end_on=("human", "tool"): 确保消息以 human 或 tool 结束
    - include_system=True: 保留系统消息
    """
    messages = state.get("messages", [])
    
    if len(messages) <= MAX_MESSAGES_FOR_LLM:
        return {"llm_input_messages": messages}
    
    # 使用官方 trim_messages，自动处理 tool_call 和 tool 消息的配对关系
    trimmed = langchain_trim_messages(
        messages,
        strategy="last",
        token_counter=len,  # 按消息数量计算
        max_tokens=MAX_MESSAGES_FOR_LLM,
        start_on="human",  # 确保从 human 消息开始（避免孤立的 tool 消息）
        end_on=("human", "tool"),  # 确保以 human 或 tool 结束
        include_system=True,  # 保留系统消息
        allow_partial=False,  # 不允许部分消息
    )
    
    logger.debug(f"消息裁剪: {len(messages)} -> {len(trimmed)}")
    return {"llm_input_messages": trimmed}


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
        from app.agents.agents.schema_agent import schema_agent
        from app.agents.agents.clarification_agent import clarification_agent
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        from app.agents.agents.sql_validator_agent import sql_validator_agent
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        from app.agents.agents.data_analyst_agent import data_analyst_agent

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
            add_handoff_back_messages=False,
            output_mode="last_message",
            pre_model_hook=trim_messages_hook,
            state_schema=SQLMessageState,  # 使用自定义 state，包含 connection_id
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
        """获取监督代理提示词"""
        
        # 根据是否启用澄清，生成不同的流程
        if self.enable_clarification:
            standard_flow = "用户查询 → schema_agent → clarification_agent → sql_generator_agent → sql_validator_agent → sql_executor_agent → data_analyst_agent → [可选] chart_generator_agent → 完成"
            clarification_section = """
**clarification_agent**: 检测查询模糊性，必要时请求用户澄清
   - 在 schema_agent 之后执行
   - 基于 Schema 信息检测模糊性（如"最近"、"大客户"）
   - 如果需要澄清，会暂停流程等待用户确认
   - 如果不需要澄清，直接传递给下一个 Agent
"""
        else:
            standard_flow = "用户查询 → schema_agent → sql_generator_agent → sql_validator_agent → sql_executor_agent → data_analyst_agent → [可选] chart_generator_agent → 完成"
            clarification_section = ""
        
        return f"""你是一个智能的 SQL Agent 系统监督者。

**你管理的代理**：

**schema_agent**: 分析用户查询，获取相关数据库表结构
   - 这是第一步，必须首先执行
   - 输出表结构信息供后续 Agent 使用
{clarification_section}
**sql_generator_agent**: 根据 Schema 信息生成 SQL 语句
   - 自动适配目标数据库语法
   - 严禁擅自对模糊条件设定默认值

**sql_validator_agent**: 验证 SQL 语法和安全性

**sql_executor_agent**: 执行 SQL 并返回结果
   - 只负责执行，不做数据分析

**data_analyst_agent**: 分析查询结果，生成数据洞察
   - SQL 执行成功后必须调用

**chart_generator_agent**: 生成数据可视化图表
   - 可选，当用户需要图表时调用

**error_recovery_agent**: 处理错误并提供修复方案

---

**标准流程**：
{standard_flow}

---

**核心原则**：

1. **路由前必须说明**：在调用任何代理之前，必须先向用户说明即将执行的动作，例如"现在我将获取相关数据库表结构"或"接下来生成SQL查询语句"
2. **严格按顺序执行**：必须先 schema_agent，再后续步骤
3. **一次调用一个代理**：不要并行调用
4. **严禁擅自决策**：如果用户说"最近"但没有具体范围，不要默认30天，必须通过 clarification_agent 询问用户
5. **错误时调用 error_recovery_agent**：任何阶段出错都交给它处理

---

**职责边界**：
- sql_executor_agent 只执行 SQL，不分析数据
- 数据分析必须由 data_analyst_agent 完成
- clarification_agent 只负责检测模糊性和请求用户确认

请根据当前状态选择最合适的代理。"""

    async def supervise(self, state: SQLMessageState, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        监督整个流程
        
        设计：让 Supervisor LLM 自然调度所有 Agent，不做硬编码控制
        """
        try:
            config = {"configurable": {"thread_id": thread_id}} if thread_id else None
            
            logger.info("开始 Supervisor 流程调度")
            
            if config is not None:
                result = await self.supervisor.ainvoke(state, config=config)
            else:
                result = await self.supervisor.ainvoke(state)
            
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
