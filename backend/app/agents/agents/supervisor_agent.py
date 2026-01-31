"""
监督代理 - 使用LangGraph自带supervisor
负责协调各个专门代理的工作流程

增强功能：
- 集成澄清机制 (clarification)
- 支持意图路由
- 支持 Dashboard Insight
- 支持自定义数据分析 Agent
- 消息历史裁剪优化 token 消耗
"""
from typing import Dict, Any, List, Optional
import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import RemoveMessage
from langgraph_supervisor import create_supervisor
from langgraph.types import interrupt

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SUPERVISOR

logger = logging.getLogger(__name__)

# ===== 消息裁剪配置 =====
MAX_MESSAGES_FOR_LLM = 10  # Supervisor LLM 最多看到的消息数（5轮对话 × 2）
KEEP_SYSTEM_MESSAGES = True  # 保留系统消息


def trim_messages_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    消息历史裁剪钩子 - 在调用 Supervisor LLM 前执行
    
    策略：
    - 保留最近 N 条消息，避免 token 溢出
    - 始终保留第一条系统消息（如果有）
    - 始终保留最后一条用户消息
    
    Args:
        state: 当前图状态
        
    Returns:
        包含裁剪后消息的状态更新
    """
    messages = state.get("messages", [])
    
    if len(messages) <= MAX_MESSAGES_FOR_LLM:
        # 消息数量在限制内，无需裁剪
        return {"llm_input_messages": messages}
    
    # 裁剪策略
    trimmed = []
    
    # 1. 保留系统消息（通常是第一条）
    if KEEP_SYSTEM_MESSAGES and messages:
        first_msg = messages[0]
        if hasattr(first_msg, 'type') and first_msg.type == 'system':
            trimmed.append(first_msg)
    
    # 2. 保留最近的消息
    recent_count = MAX_MESSAGES_FOR_LLM - len(trimmed)
    recent_messages = messages[-recent_count:]
    trimmed.extend(recent_messages)
    
    logger.debug(
        f"消息裁剪: {len(messages)} -> {len(trimmed)} "
        f"(保留最近 {recent_count} 条)"
    )
    
    return {"llm_input_messages": trimmed}


class SupervisorAgent:
    """监督代理 - 基于LangGraph自带supervisor"""

    def __init__(
        self, 
        worker_agents: List[Any] = None, 
        enable_clarification: bool = True,
        custom_analyst_id: Optional[int] = None
    ):
        """
        初始化监督代理
        
        Args:
            worker_agents: 工作代理列表，None则自动创建
            enable_clarification: 是否启用澄清机制
            custom_analyst_id: 自定义数据分析 Agent 的 ID（可选）
        """
        self.llm = get_agent_llm(CORE_AGENT_SUPERVISOR)
        self.enable_clarification = enable_clarification
        self.custom_analyst_id = custom_analyst_id
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理"""
        # 导入各个功能代理模块
        from app.agents.agents.schema_agent import schema_agent          # Schema分析代理：分析用户查询并获取相关数据库表结构
        from app.agents.agents.sql_generator_agent import sql_generator_agent  # SQL生成代理：根据模式信息生成高质量SQL语句
        from app.agents.agents.sql_validator_agent import sql_validator_agent  # SQL验证代理：验证SQL语法、安全性和性能
        from app.agents.agents.sql_executor_agent import sql_executor_agent    # SQL执行代理：安全执行SQL并返回结果
        from app.agents.agents.error_recovery_agent import error_recovery_agent  # 错误恢复代理：处理错误并提供修复方案
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 图表生成代理：根据查询结果生成数据可视化图表
        from app.agents.agents.data_analyst_agent import data_analyst_agent    # 数据分析代理：分析查询结果，生成数据洞察和业务建议

        # 获取数据分析 agent（支持自定义）
        analyst_agent = self._get_data_analyst_agent()

        # 返回agent对象而不是包装类
        return [
            schema_agent.agent,
            sql_generator_agent.agent,
            sql_validator_agent.agent,
            sql_executor_agent.agent,
            analyst_agent.agent if hasattr(analyst_agent, 'agent') else analyst_agent,
            error_recovery_agent.agent,
            chart_generator_agent.agent
        ]

    def _get_data_analyst_agent(self):
        """
        获取数据分析 Agent（支持自定义配置）
        
        如果设置了 custom_analyst_id，则从数据库加载自定义配置；
        否则使用默认的 data_analyst_agent。
        """
        from app.agents.agents.data_analyst_agent import data_analyst_agent, DataAnalystAgent
        
        if not self.custom_analyst_id:
            logger.debug("使用默认数据分析 Agent")
            return data_analyst_agent
        
        try:
            from app.db.session import get_db_session
            from app.crud import agent_profile as crud_agent_profile
            from app.core.agent_config import get_custom_agent_llm
            
            with get_db_session() as db:
                profile = crud_agent_profile.get(db, id=self.custom_analyst_id)
                
                if not profile:
                    logger.warning(f"未找到自定义 Agent (id={self.custom_analyst_id})，使用默认")
                    return data_analyst_agent
                
                if not profile.is_active:
                    logger.warning(f"自定义 Agent '{profile.name}' 未激活，使用默认")
                    return data_analyst_agent
                
                # 创建自定义数据分析 Agent
                custom_llm = get_custom_agent_llm(profile, db)
                custom_prompt = profile.system_prompt if profile.system_prompt else None
                
                logger.info(f"使用自定义数据分析 Agent: {profile.name} (id={profile.id})")
                return DataAnalystAgent(custom_prompt=custom_prompt, llm=custom_llm)
                
        except Exception as e:
            logger.error(f"加载自定义 Agent 失败: {e}，使用默认")
            return data_analyst_agent

    def _create_supervisor(self):
        """创建LangGraph supervisor"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=True,
            output_mode="last_message",  # 优化：只返回最后一条消息，减少 token
            pre_model_hook=trim_messages_hook,  # 消息历史裁剪
        )

        return supervisor.compile()

    def _get_supervisor_prompt(self) -> str:
        """获取监督代理提示"""
        system_msg = f"""你是一个智能的SQL Agent系统监督者。
你管理以下专门代理：

🔍 **schema_agent**: 分析用户查询，获取相关数据库表结构

⚙️ **sql_generator_agent**: 根据模式信息和样本生成高质量SQL语句
🔍 **sql_validator_agent**: 验证SQL的语法、安全性和性能
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
📊 **data_analyst_agent**: 分析查询结果，生成数据洞察和业务建议
📈 **chart_generator_agent**: 根据查询结果生成数据可视化图表
🔧 **error_recovery_agent**: 处理错误并提供修复方案

**工作原则:**
1. 根据当前任务阶段选择合适的代理
2. 确保工作流程的连续性和一致性
3. 智能处理错误和异常情况
4. 一次只分配给一个代理，不要并行调用
5. 不要自己执行任何具体工作

**标准流程:**
用户查询 → schema_agent → sql_generator_agent → sql_validator_agent → sql_executor_agent → data_analyst_agent → [可选] chart_generator_agent → 完成

**数据分析必须执行:**
- SQL 执行成功后，必须调用 data_analyst_agent 分析结果
- data_analyst_agent 会生成数据洞察、趋势分析和业务建议

**图表生成条件:**
- 用户查询包含可视化意图（如"图表"、"趋势"、"分布"、"比较"等关键词）
- 查询结果包含数值数据且适合可视化
- 数据量适中（2-1000行）


**错误处理:**
任何阶段出错 → error_recovery_agent → 重试相应阶段

请根据当前状态和任务需求做出最佳的代理选择决策。特别注意：
- SQL执行完成后必须调用 data_analyst_agent 进行数据分析
- 当用户查询包含可视化意图时，在数据分析完成后应考虑调用 chart_generator_agent
- 当查询结果适合可视化时，主动建议生成图表"""

        return system_msg

    async def _check_clarification(self, state: SQLMessageState) -> Optional[Dict[str, Any]]:
        """
        检查是否需要澄清
        
        Returns:
            如果需要澄清，返回澄清信息；否则返回 None
        """
        if not self.enable_clarification:
            return None
        
        # 如果已经确认过澄清，跳过
        if state.get("clarification_confirmed", False):
            logger.info("澄清已确认，跳过检测")
            return None
        
        try:
            from app.agents.agents.clarification_agent import (
                _quick_clarification_check_impl as quick_clarification_check,
                should_skip_clarification,
                format_clarification_questions,
            )
            
            # 提取用户查询
            user_query = state.get("enriched_query")
            if not user_query:
                messages = state.get("messages", [])
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        user_query = msg.content
                        break
            
            if not user_query:
                return None
            
            # 快速检测是否可以跳过
            if should_skip_clarification(user_query):
                logger.info("查询可以跳过澄清")
                return None
            
            # 使用 LLM 检测澄清需求
            connection_id = state.get("connection_id", 15)
            schema_info = state.get("schema_info")
            
            result = quick_clarification_check(
                query=user_query,
                connection_id=connection_id,
                schema_info=schema_info
            )
            
            if result.get("needs_clarification") and result.get("questions"):
                formatted_questions = format_clarification_questions(result["questions"])
                return {
                    "needs_clarification": True,
                    "questions": formatted_questions,
                    "reason": result.get("reason", "查询存在模糊性")
                }
            
            return None
            
        except Exception as e:
            logger.error(f"澄清检测失败: {e}")
            return None

    async def supervise(self, state: SQLMessageState) -> Dict[str, Any]:
        """监督整个流程"""
        try:
            # 1. 检查是否需要澄清
            clarification_result = await self._check_clarification(state)
            
            if clarification_result:
                logger.info("需要澄清，使用 interrupt() 暂停")
                
                # 使用 LangGraph interrupt() 模式
                interrupt_data = {
                    "type": "clarification_request",
                    "questions": clarification_result["questions"],
                    "reason": clarification_result["reason"],
                }
                
                # interrupt() 会暂停执行，等待用户回复
                user_response = interrupt(interrupt_data)
                logger.info(f"收到用户澄清回复: {user_response}")
                
                # 处理用户回复
                from app.agents.agents.clarification_agent import (
                    parse_user_clarification_response,
                    _enrich_query_with_clarification_impl as enrich_query_with_clarification,
                )
                
                parsed_answers = parse_user_clarification_response(
                    user_response,
                    clarification_result["questions"]
                )
                
                if parsed_answers:
                    # 提取原始查询
                    original_query = state.get("enriched_query") or ""
                    if not original_query:
                        messages = state.get("messages", [])
                        for msg in reversed(messages):
                            if hasattr(msg, 'type') and msg.type == 'human':
                                original_query = msg.content
                                break
                    
                    enrich_result = enrich_query_with_clarification(
                        original_query=original_query,
                        clarification_responses=parsed_answers
                    )
                    
                    # 更新状态
                    state["enriched_query"] = enrich_result.get("enriched_query", original_query)
                    state["clarification_confirmed"] = True
                    logger.info(f"查询已增强: {state['enriched_query'][:100]}...")
            
            # 2. 执行 supervisor 流程
            result = await self.supervisor.ainvoke(state)
            return {
                "success": True,
                "result": result,
                "clarification_used": clarification_result is not None
            }
            
        except Exception as e:
            logger.error(f"监督流程失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


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
    """
    创建智能SQL监督代理的便捷函数
    
    Args:
        enable_clarification: 是否启用澄清机制
        custom_analyst_id: 自定义数据分析 Agent ID（可选）
    """
    return SupervisorAgent(
        enable_clarification=enable_clarification,
        custom_analyst_id=custom_analyst_id
    )
