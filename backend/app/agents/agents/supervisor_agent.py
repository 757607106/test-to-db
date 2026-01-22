"""
监督代理 (Supervisor Agent) - 使用 LangGraph 原生模式重构

遵循 LangGraph 官方最佳实践:
1. 移除 langgraph_supervisor 第三方库依赖
2. 使用原生条件边 (conditional_edges) 实现路由
3. 使用 LLM 进行智能路由决策
4. 简化消息管理，避免消息重复

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output
- https://langchain-ai.github.io/langgraph/concepts/low_level

核心职责:
1. 协调所有 Worker Agents 的工作流程
2. 根据任务阶段智能路由到合适的 Agent
3. 管理 Agent 间的消息传递和状态更新
4. 支持快速模式 (Fast Mode)
"""
from typing import Dict, Any, List, Optional, Literal
import logging
import json

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.message_utils import validate_and_fix_message_history

logger = logging.getLogger(__name__)


# ============================================================================
# 路由决策 Schema (用于结构化输出)
# ============================================================================

class RouteDecision(BaseModel):
    """路由决策 - 用于 LLM 结构化输出"""
    next_agent: Literal[
        "schema_agent",
        "sql_generator_agent", 
        "sql_executor_agent",
        "chart_generator_agent",
        "error_recovery_agent",
        "FINISH"
    ] = Field(description="下一个要执行的 Agent 或 FINISH 表示完成")
    reason: str = Field(description="路由决策的简要原因")


# ============================================================================
# Supervisor 实现 (原生 LangGraph 模式)
# ============================================================================

class SupervisorAgent:
    """
    监督代理 - 使用 LangGraph 原生条件边模式
    
    重要变更 (2026-01-22):
    - 移除了 langgraph_supervisor 第三方库依赖
    - 使用原生条件边实现路由
    - 支持结构化输出进行路由决策
    
    架构模式:
    - 基于状态的路由：根据 current_stage 字段路由
    - LLM 辅助决策：复杂情况下使用 LLM 判断
    - 简化消息管理：避免消息重复
    """
    
    def __init__(self, worker_agents: List[Any] = None, custom_analyst=None):
        """
        初始化 Supervisor
        
        Args:
            worker_agents: 工作智能体列表（可选）
            custom_analyst: 自定义数据分析专家（可选）
        """
        self.llm = get_default_model()
        self.custom_analyst = custom_analyst
        self.worker_agents = worker_agents or self._create_worker_agents()
        
        # 尝试启用结构化输出
        try:
            self.router_llm = self.llm.with_structured_output(RouteDecision)
            logger.info("✓ Supervisor 路由器已启用结构化输出")
        except Exception as e:
            logger.warning(f"⚠ Supervisor 结构化输出不可用: {e}")
            self.router_llm = None
    
    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理"""
        from app.agents.agents.schema_agent import schema_agent
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        
        agents = [
            schema_agent,
            sql_generator_agent,
            sql_executor_agent,
            error_recovery_agent,
        ]
        
        # 添加图表生成代理
        if self.custom_analyst:
            logger.info("使用自定义分析专家")
            agents.append(self.custom_analyst)
        else:
            agents.append(chart_generator_agent)
        
        return agents
    
    def _get_agent_by_name(self, name: str):
        """根据名称获取 Agent"""
        for agent in self.worker_agents:
            if hasattr(agent, 'name') and agent.name == name:
                return agent
        return None
    
    def route_by_stage(self, state: SQLMessageState) -> str:
        """
        基于状态的简单路由 (无需 LLM)
        
        这是推荐的路由方式：
        - 快速，无 LLM 调用
        - 基于 current_stage 字段
        - 明确的状态机转换
        """
        current_stage = state.get("current_stage", "schema_analysis")
        fast_mode = state.get("fast_mode", False)
        skip_chart = state.get("skip_chart_generation", False)
        
        # 状态机路由
        if current_stage == "schema_analysis":
            return "schema_agent"
        
        elif current_stage == "sql_generation":
            return "sql_generator_agent"
        
        elif current_stage == "sql_execution":
            return "sql_executor_agent"
        
        elif current_stage == "chart_generation":
            if skip_chart:
                return "FINISH"
            return "chart_generator_agent"
        
        elif current_stage == "error_recovery":
            return "error_recovery_agent"
        
        elif current_stage == "completed":
            return "FINISH"
        
        else:
            logger.warning(f"未知的 stage: {current_stage}, 默认到 schema_analysis")
            return "schema_agent"
    
    async def route_with_llm(self, state: SQLMessageState) -> RouteDecision:
        """
        使用 LLM 进行智能路由 (复杂情况)
        
        仅在需要复杂决策时使用
        """
        if not self.router_llm:
            # 回退到简单路由
            next_agent = self.route_by_stage(state)
            return RouteDecision(next_agent=next_agent, reason="基于状态路由")
        
        # 构建路由上下文
        context = f"""
当前状态:
- current_stage: {state.get('current_stage')}
- fast_mode: {state.get('fast_mode', False)}
- skip_chart_generation: {state.get('skip_chart_generation', False)}
- has_generated_sql: {bool(state.get('generated_sql'))}
- has_execution_result: {bool(state.get('execution_result'))}
- error_count: {len(state.get('error_history', []))}
- retry_count: {state.get('retry_count', 0)}

可用的 Agent:
- schema_agent: 分析用户查询，获取数据库模式
- sql_generator_agent: 生成 SQL 语句
- sql_executor_agent: 执行 SQL 查询
- chart_generator_agent: 生成图表可视化
- error_recovery_agent: 处理错误和恢复
- FINISH: 任务完成

请决定下一步应该调用哪个 Agent。
"""
        
        try:
            decision = await self.router_llm.ainvoke([
                SystemMessage(content="你是一个智能路由器，负责决定下一步调用哪个 Agent。"),
                HumanMessage(content=context)
            ])
            return decision
        except Exception as e:
            logger.error(f"LLM 路由失败: {e}")
            next_agent = self.route_by_stage(state)
            return RouteDecision(next_agent=next_agent, reason=f"LLM 失败，回退到状态路由: {e}")
    
    async def execute_agent(self, agent_name: str, state: SQLMessageState) -> Dict[str, Any]:
        """
        执行指定的 Agent
        
        Args:
            agent_name: Agent 名称
            state: 当前状态
            
        Returns:
            Agent 执行结果 (状态更新)
        """
        agent = self._get_agent_by_name(agent_name)
        if not agent:
            logger.error(f"找不到 Agent: {agent_name}")
            return {
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "supervisor",
                    "error": f"找不到 Agent: {agent_name}"
                }]
            }
        
        try:
            logger.info(f"执行 Agent: {agent_name}")
            
            # 调用 Agent 的处理方法
            if hasattr(agent, 'process'):
                result = await agent.process(state)
            elif hasattr(agent, 'execute'):
                result = await agent.execute(state)
            elif hasattr(agent, 'agent') and hasattr(agent.agent, 'ainvoke'):
                # 兼容 ReAct Agent
                result = await agent.agent.ainvoke(state)
            else:
                raise ValueError(f"Agent {agent_name} 没有可调用的方法")
            
            logger.info(f"Agent {agent_name} 执行完成")
            return result
            
        except Exception as e:
            logger.error(f"Agent {agent_name} 执行失败: {e}")
            return {
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": agent_name,
                    "error": str(e)
                }]
            }
    
    async def supervise(
        self, 
        state: SQLMessageState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        监督整个流程 - 主要入口方法
        
        Args:
            state: SQL 消息状态
            config: LangGraph 配置（可选）
            
        Returns:
            执行结果
        """
        # 消息历史修剪
        from app.core.message_history import auto_trim_messages, get_message_stats
        
        if "messages" in state and state["messages"]:
            before_stats = get_message_stats(state["messages"])
            state["messages"] = auto_trim_messages(state["messages"])
            after_stats = get_message_stats(state["messages"])
            
            if after_stats["total"] < before_stats["total"]:
                logger.info(f"消息已修剪: {before_stats['total']} -> {after_stats['total']}")
        
        # 验证消息历史
        if "messages" in state and state["messages"]:
            state["messages"] = validate_and_fix_message_history(state["messages"])
        
        # 检查快速模式
        fast_mode = state.get("fast_mode", False)
        if fast_mode:
            logger.info("=== 快速模式已启用 ===")
        
        try:
            # 执行循环
            max_iterations = 10
            iteration = 0
            current_state = dict(state)
            
            while iteration < max_iterations:
                iteration += 1
                
                # 路由决策
                next_agent = self.route_by_stage(current_state)
                
                if next_agent == "FINISH":
                    logger.info("任务完成")
                    break
                
                # 执行 Agent
                result = await self.execute_agent(next_agent, current_state)
                
                # 更新状态
                if result:
                    for key, value in result.items():
                        if key == "messages" and value:
                            # 追加消息而不是替换
                            current_messages = current_state.get("messages", [])
                            current_state["messages"] = current_messages + value
                        else:
                            current_state[key] = value
                
                # 检查是否完成
                if current_state.get("current_stage") == "completed":
                    logger.info("任务完成 (stage=completed)")
                    break
                
                # 检查错误重试限制
                if current_state.get("retry_count", 0) >= current_state.get("max_retries", 3):
                    logger.warning("达到最大重试次数，终止")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"达到最大迭代次数: {max_iterations}")
            
            return {
                "success": True,
                "result": current_state
            }
            
        except Exception as e:
            logger.error(f"Supervisor 执行出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# ============================================================================
# 工厂函数
# ============================================================================

def create_supervisor_agent(worker_agents: List[Any] = None, custom_analyst=None) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents, custom_analyst)


def create_intelligent_sql_supervisor(custom_analyst=None) -> SupervisorAgent:
    """创建智能 SQL 监督代理"""
    return SupervisorAgent(custom_analyst=custom_analyst)


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def supervisor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 节点函数 - 用于 LangGraph 图
    
    这个函数包装了 SupervisorAgent，可以直接在图中使用。
    """
    supervisor = SupervisorAgent()
    result = await supervisor.supervise(state)
    
    if result.get("success"):
        return result.get("result", state)
    else:
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "supervisor",
                "error": result.get("error", "Unknown error")
            }]
        }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "SupervisorAgent",
    "create_supervisor_agent",
    "create_intelligent_sql_supervisor",
    "supervisor_node",
    "RouteDecision",
]
