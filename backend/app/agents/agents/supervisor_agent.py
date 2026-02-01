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
from app.agents.utils.supervisor_guards import (
    run_all_guards,
    update_guard_state,
    get_stage_for_agent,
    MAX_SUPERVISOR_TURNS,
)

logger = logging.getLogger(__name__)

# ===== 消息裁剪配置 =====
MAX_TOKENS_FOR_LLM = 4000  # Token 限制（根据模型上下文窗口调整）


def trim_messages_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    消息历史裁剪钩子 - 使用官方推荐方式
    
    使用 llm_input_messages 键（官方推荐）:
    - 不修改原始消息历史
    - 只为 LLM 提供裁剪后的输入
    - 避免 RemoveMessage 被发送到前端
    
    官方依据: https://langchain-ai.github.io/langgraph/reference/agents
    """
    messages = state.get("messages", [])
    
    if not messages:
        return {}
    
    # 使用官方 trim_messages，自动处理 tool_call 和 tool 消息的配对关系
    trimmed = langchain_trim_messages(
        messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=MAX_TOKENS_FOR_LLM,
        start_on="human",  # 确保从 human 消息开始
        include_system=True,  # 保留系统消息
        allow_partial=False,  # 不允许部分消息
    )
    
    # 如果没有裁剪，不需要更新
    if len(trimmed) == len(messages):
        return {}
    
    logger.info(f"消息裁剪: {len(messages)} -> {len(trimmed)} 条")
    
    # 官方推荐：使用 llm_input_messages 键，不修改原始历史
    return {"llm_input_messages": trimmed}


def guard_check_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    防护检查钩子 - 在每次 LLM 调用前检查防护条件
    
    检查项：
    - 最大轮次限制
    - Agent 循环检测
    """
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
        
        return {
            "messages": state.get("messages", []) + [stop_message],
            "should_stop": True,
        }
    
    # 更新轮次计数
    turn_count = state.get("supervisor_turn_count", 0)
    
    return {
        "supervisor_turn_count": turn_count + 1,
    }


def combined_pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    组合的 pre_model_hook - 同时处理消息裁剪和防护检查
    """
    updates = {}
    
    # 1. 防护检查
    guard_updates = guard_check_hook(state)
    updates.update(guard_updates)
    
    # 如果防护触发停止，直接返回
    if guard_updates.get("should_stop"):
        return updates
    
    # 2. 消息裁剪 - 返回 llm_input_messages（不修改原始历史）
    trim_updates = trim_messages_hook(state)
    if trim_updates:
        updates.update(trim_updates)
    
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
            add_handoff_back_messages=True,  # 让 Supervisor 看到 Agent 返回结果，支持动态决策
            output_mode="last_message",
            pre_model_hook=combined_pre_model_hook,  # 组合 hook：防护检查 + 消息裁剪
            state_schema=SQLMessageState,
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
        获取监督代理提示词
        
        设计原则：
        - 只描述每个 Agent 的能力和使用场景
        - 不规定固定的执行顺序
        - 让 LLM 根据当前状态自主决策
        """
        
        # 构建 Agent 能力描述
        clarification_desc = ""
        if self.enable_clarification:
            clarification_desc = """
**clarification_agent** - 澄清用户意图
  - 能力：检测查询中的模糊性，生成澄清问题
  - 使用场景：用户查询存在模糊性时（如"最近"、"大客户"、"主要产品"）
  - 前提：需要已有 Schema 信息
  - 输出：澄清问题或确认可以继续
"""
        
        return f"""你是一个智能的 SQL 查询助手，负责协调多个专业代理完成用户的数据查询需求。

## 可用的专业代理

**schema_agent** - 获取数据库结构
  - 能力：分析用户查询，获取相关表和字段信息
  - 使用场景：需要了解数据库结构时（通常是第一步）
  - 输出：相关表结构、字段信息、关系
{clarification_desc}
**sql_generator_agent** - 生成 SQL 语句
  - 能力：根据用户查询和 Schema 信息生成 SQL
  - 使用场景：需要生成查询语句时
  - 前提：必须已有 Schema 信息
  - 输出：SQL 语句

**sql_validator_agent** - 验证 SQL 语法
  - 能力：检查 SQL 语法正确性和安全性
  - 使用场景：SQL 生成后，执行前
  - 输出：验证结果

**sql_executor_agent** - 执行 SQL 查询
  - 能力：执行 SQL 并返回结果
  - 使用场景：SQL 验证通过后
  - 前提：必须有已生成的 SQL
  - 输出：查询结果数据

**data_analyst_agent** - 分析数据结果
  - 能力：分析查询结果，生成洞察和建议
  - 使用场景：查询成功后，需要解读数据时
  - 前提：必须有查询结果
  - 输出：数据洞察、趋势分析、业务建议

**chart_generator_agent** - 生成可视化图表
  - 能力：根据数据生成图表配置
  - 使用场景：用户需要可视化时（可选）
  - 前提：必须有查询结果
  - 输出：图表配置

**error_recovery_agent** - 错误恢复
  - 能力：诊断错误原因，尝试修复
  - 使用场景：任何阶段出错时
  - 输出：修复方案或错误说明

## 决策原则

1. **根据状态决策**：查看当前已有的信息，选择最合适的下一步
2. **前提条件检查**：调用 Agent 前确保其前提条件已满足
3. **一次一个**：每次只调用一个 Agent
4. **观察反馈**：根据 Agent 返回结果决定下一步
5. **及时完成**：任务完成后及时结束

## 重要约束

- **严禁替用户做业务决策**：如果查询中有"最近"、"大"、"主要"等模糊词且没有具体定义，必须先澄清
- **严禁跳过必要步骤**：生成 SQL 前必须有 Schema，执行前必须有 SQL
- **错误时求助**：遇到错误调用 error_recovery_agent

## 工作方式

1. 理解用户的查询意图
2. 评估当前状态（已有哪些信息）
3. 选择最合适的下一个 Agent
4. 执行并观察结果
5. 重复直到任务完成

请根据当前对话状态，选择最合适的代理来推进任务。"""

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
