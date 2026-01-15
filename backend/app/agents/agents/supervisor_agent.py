"""
监督代理 - 使用LangGraph自带supervisor
负责协调各个专门代理的工作流程
pip install langgraph-supervisor
"""
from typing import Dict, Any, List, Optional

from langchain_core.runnables import RunnableConfig
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.db.session import SessionLocal
from app.models.agent_profile import AgentProfile

class SupervisorAgent:
    """监督代理 - 基于LangGraph自带supervisor"""

    def __init__(self, worker_agents: List[Any] = None, active_agent_profile: Optional[AgentProfile] = None):
        self.active_agent_profile = active_agent_profile
        self.llm = get_default_model()
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理 - 包含核心代理、图表代理及动态配置的代理"""

        # 核心代理：保证SQL查询的准确性和可靠性
        from app.agents.agents.schema_agent import schema_agent          # 核心：分析用户查询并获取准确的数据库模式
        from app.agents.agents.sql_generator_agent import sql_generator_agent      # 核心：生成准确的SQL查询
        from app.agents.agents.sql_executor_agent import sql_executor_agent        # 核心：安全地执行SQL查询
        from app.agents.agents.error_recovery_agent import error_recovery_agent    # 保障：处理错误并修正
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 可视化：图表生成

        agents = [
            schema_agent.agent,
            sql_generator_agent.agent,
            sql_executor_agent.agent,
            error_recovery_agent.agent,
            chart_generator_agent.agent
        ]

        # 动态加载数据库配置的代理
        db = SessionLocal()
        try:
            profiles = db.query(AgentProfile).filter(AgentProfile.is_active == True).all()
            
            # 确保当前选中的代理也在列表中（即使未启用，或者是刚才被禁用了等边缘情况）
            if self.active_agent_profile:
                # 如果当前选中的代理不在 profiles 中（比如 ID 匹配但对象不同），添加进去
                if not any(p.id == self.active_agent_profile.id for p in profiles):
                    profiles.append(self.active_agent_profile)

            for profile in profiles:
                # 避免重复添加同名核心代理
                if any(a.name == profile.name for a in agents):
                    continue
                
                # 创建动态代理
                # 注意：这里工具列表暂时为空，或者需要一个工具注册表来映射 profile.tools 字符串到实际函数
                # 这里我们假设动态代理主要用于对话或特定分析，使用通用 LLM
                dynamic_agent = create_react_agent(
                    model=get_default_model(), # 可以扩展支持 profile.llm_config_id
                    tools=[], # TODO: 实现工具动态加载
                    prompt=profile.system_prompt or f"你是 {profile.name}，{profile.role_description}",
                    name=profile.name
                )
                agents.append(dynamic_agent)
        except Exception as e:
            print(f"Error loading dynamic agents: {e}")
        finally:
            db.close()

        return agents

    def _create_supervisor(self):
        """创建LangGraph supervisor"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=True,
            output_mode="full_history",
        )

        return supervisor.compile()

    def _get_supervisor_prompt(self) -> str:
        """获取监督代理提示 - 动态生成"""
        
        # 基础提示
        system_msg = """你是高效的SQL查询与分析系统监督者。

你管理以下代理：

🔍 **schema_agent**: 分析用户查询，获取准确的数据库表结构
⚙️ **sql_generator_agent**: 生成准确的SQL（已增强：智能处理模糊查询）
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
🔧 **error_recovery_agent**: 处理错误并修正SQL，提高准确率
📊 **chart_generator_agent**: 将数据结果生成可视化图表
"""

        # 添加动态代理描述
        for agent in self.worker_agents:
            name = agent.name
            if name not in ["schema_agent", "sql_generator_agent", "sql_executor_agent", "error_recovery_agent", "chart_generator_agent"]:
                system_msg += f"🤖 **{name}**: 自定义代理\n"

        system_msg += """
**核心工作流程:**
1. SQL查询: 用户查询 → schema_agent → sql_generator_agent → sql_executor_agent
2. 可视化: (SQL执行后) → chart_generator_agent
3. 错误处理: 任何阶段出错 → error_recovery_agent
"""

        # 如果有选定的代理，修改工作流指令
        if self.active_agent_profile:
             system_msg += f"""
**特别指令:**
用户指定了 **{self.active_agent_profile.name}** 进行分析。
在 `sql_executor_agent` 执行成功并获得数据后，你**必须**将控制权移交给 **{self.active_agent_profile.name}**，让其根据数据进行分析。
不要直接结束，也不要使用默认的分析方式。
"""

        system_msg += """
**工作原则:**
1. 快速响应，简洁高效
2. 确保SQL准确性，优先正确执行
3. 如果用户请求包含"图表"、"画图"、"可视化"等意图，必须调用 chart_generator_agent
4. 一次只分配一个代理
5. 不要自己执行任何具体工作

请根据当前状态选择合适的代理，保持流程简洁高效。"""

        return system_msg

    async def supervise(self, state: SQLMessageState) -> Dict[str, Any]:
        """监督整个流程"""
        try:
            result = await self.supervisor.ainvoke(state)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

def create_supervisor_agent(worker_agents: List[Any] = None, active_agent_profile: Optional[AgentProfile] = None) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents, active_agent_profile)

def create_intelligent_sql_supervisor(active_agent_profile: Optional[AgentProfile] = None) -> SupervisorAgent:
    """创建智能SQL监督代理的便捷函数"""
    return SupervisorAgent(active_agent_profile=active_agent_profile)
