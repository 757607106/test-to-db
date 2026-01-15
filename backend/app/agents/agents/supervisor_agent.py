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
from app.core.agent_config import CORE_AGENT_CHART_ANALYST
from app.db.session import SessionLocal
from app.models.agent_profile import AgentProfile
from app.models.llm_config import LLMConfiguration

class SupervisorAgent:
    """监督代理 - 基于LangGraph自带supervisor"""

    def __init__(self, worker_agents: List[Any] = None, active_agent_profiles: List[AgentProfile] = None):
        self.active_agent_profiles = active_agent_profiles or []
        self.llm = get_default_model()
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理 - 包含核心代理、图表代理及动态配置的代理"""

        # 核心代理：保证SQL查询的准确性和可靠性
        from app.agents.agents.schema_agent import schema_agent          # 核心：分析用户查询并获取准确的数据库模式
        from app.agents.agents.sql_generator_agent import sql_generator_agent      # 核心：生成准确的SQL查询
        from app.agents.agents.sql_validator_agent import sql_validator_agent      # 核心：验证SQL语法、安全性和性能
        from app.agents.agents.sql_executor_agent import sql_executor_agent        # 核心：安全地执行SQL查询
        from app.agents.agents.error_recovery_agent import error_recovery_agent    # 保障：处理错误并修正
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 核心：默认数据分析与可视化

        # 基础代理列表 (始终存在)
        agents = [
            schema_agent.agent,
            sql_generator_agent.agent,
            sql_validator_agent.agent,  # 重新启用 SQL 验证代理
            sql_executor_agent.agent,
            error_recovery_agent.agent
        ]

        # 逻辑分支：使用自定义专家 还是 默认分析师？
        if self.active_agent_profiles:
            # 方案：替换模式
            # 1. 不添加 chart_generator_agent (Default Data Analyst)
            # 2. 将 chart_generator_agent 的工具提取出来
            chart_tools = chart_generator_agent.tools
            
            db = SessionLocal()
            try:
                for profile in self.active_agent_profiles:
                    # 避免重复
                    if any(a.name == profile.name for a in agents):
                        continue
                    
                    # 获取特定模型配置
                    agent_llm = self.llm # 默认
                    if profile.llm_config_id:
                        llm_config = db.query(LLMConfiguration).filter(LLMConfiguration.id == profile.llm_config_id).first()
                        if llm_config:
                            agent_llm = get_default_model(config_override=llm_config)

                    # 创建动态代理 (Custom Agent)
                    # 关键：注入图表工具！
                    dynamic_agent = create_react_agent(
                        model=agent_llm, 
                        tools=chart_tools, # 继承默认分析师的工具
                        prompt=profile.system_prompt or f"你是 {profile.name}，{profile.role_description}。请分析数据，并根据需要使用图表工具生成可视化配置。",
                        name=profile.name
                    )
                    agents.append(dynamic_agent)
            except Exception as e:
                print(f"Error loading dynamic agents: {e}")
            finally:
                db.close()
        else:
            # 方案：默认模式
            # 添加默认的数据分析师
            agents.append(chart_generator_agent.agent)

        return agents

    def _create_supervisor(self):
        """创建LangGraph supervisor - 优化版"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=True,
            output_mode="last_message",  # 只保留最后消息，避免历史膨胀导致循环调用
            parallel_tool_calls=False,   # 保证顺序执行
        )

        return supervisor.compile()

    def _get_supervisor_prompt(self) -> str:
        """获取监督代理提示 - 动态生成"""
        
        # 基础提示
        system_msg = """你是高效的SQL查询与分析系统监督者。

你管理以下代理：

🔍 **schema_agent**: 分析用户查询，获取准确的数据库表结构
⚙️ **sql_generator_agent**: 生成准确的SQL（已增强：智能处理模糊查询）
✅ **sql_validator_agent**: 验证SQL语法、安全性和性能（可选但推荐）
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
🔧 **error_recovery_agent**: 处理错误并修正SQL，提高准确率
"""
        
        # 动态调整 Prompt
        if self.active_agent_profiles:
             # 替换模式：不介绍默认分析师，只介绍自定义专家
            for agent in self.worker_agents:
                name = agent.name
                if name not in ["schema_agent", "sql_generator_agent", "sql_executor_agent", "error_recovery_agent"]:
                     system_msg += f"🧠 **{name}**: 行业数据分析专家（已授权图表生成能力）\n"
        else:
            # 默认模式：介绍默认分析师
            system_msg += "📊 **chart_generator_agent**: 数据分析与可视化专家（默认）\n"


        system_msg += """
**核心工作流程:**
1. SQL查询: 用户查询 → schema_agent → sql_generator_agent → sql_validator_agent(推荐) → sql_executor_agent
2. 分析与可视化: 
   - SQL执行成功后，必须将数据移交给分析专家。
"""
        
        if self.active_agent_profiles:
             agent_names = [p.name for p in self.active_agent_profiles]
             agent_names_str = ", ".join(agent_names)
             system_msg += f"   - 当前指定专家: **{agent_names_str}** (请优先调用)\n"
        else:
             system_msg += "   - 当前分析师: chart_generator_agent\n"

        system_msg += """3. 错误处理: 任何阶段出错 → error_recovery_agent

**工作原则:**
1. 快速响应，简洁高效
2. 确保SQL准确性，优先正确执行
3. 分析阶段：专家负责解读数据，并有权调用图表工具生成可视化。
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

def create_supervisor_agent(worker_agents: List[Any] = None, active_agent_profiles: List[AgentProfile] = None) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents, active_agent_profiles)

def create_intelligent_sql_supervisor(active_agent_profiles: List[AgentProfile] = None) -> SupervisorAgent:
    """创建智能SQL监督代理的便捷函数"""
    return SupervisorAgent(active_agent_profiles=active_agent_profiles)

