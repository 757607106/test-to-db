"""
监督代理 - 使用LangGraph自带supervisor
负责协调各个专门代理的工作流程
pip install langgraph-supervisor
"""
from typing import Dict, Any, List

from langchain_core.runnables import RunnableConfig
from langgraph_supervisor import create_supervisor

from app.core.state import SQLMessageState
from app.core.llms import get_default_model

class SupervisorAgent:
    """监督代理 - 基于LangGraph自带supervisor"""

    def __init__(self, worker_agents: List[Any] = None):
        self.llm = get_default_model()
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理 - 精简版（保留核心4个agent，保证准确率）"""

        # 核心代理：保证SQL查询的准确性和可靠性
        from app.agents.agents.schema_agent import schema_agent          # 核心：分析用户查询并获取准确的数据库模式
        from app.agents.agents.sql_generator_agent import sql_generator_agent      # 核心：生成准确的SQL查询（已增强智能处理模糊查询）
        from app.agents.agents.sql_executor_agent import sql_executor_agent        # 核心：安全地执行SQL查询
        from app.agents.agents.error_recovery_agent import error_recovery_agent    # 保障：处理错误并修正，提高准确率

        # 已移除的代理（不影响准确率，提升速度）：
        # - clarification_agent: 由SQL生成agent的智能假设替代
        # - analyst_agent: 只是结果分析，不影响SQL准确性
        # - chart_generator_agent: 只是可视化，不影响查询准确性
        # - sample_retrieval_agent: 暂未启用
        # - sql_validator_agent: 已禁用

        # 返回精简的核心agent列表
        return [
            schema_agent.agent,              # 1. 获取准确的数据库结构
            sql_generator_agent.agent,       # 2. 生成准确的SQL（智能处理模糊查询）
            sql_executor_agent.agent,        # 3. 安全执行SQL
            error_recovery_agent.agent       # 4. 错误修正（提高准确率）
        ]

    # def pre_model_hook(self, state):
    #     print("哈哈哈哈哈：：：：", state)
    def _create_supervisor(self):
        """创建LangGraph supervisor"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=True,
            # pre_model_hook=self.pre_model_hook,
            # parallel_tool_calls=True,
            output_mode="full_history",
        )

        return supervisor.compile()

    def _get_supervisor_prompt(self) -> str:
        """获取监督代理提示 - 精简高效版"""
        
        system_msg = """你是高效的SQL查询系统监督者。

你管理4个核心代理（精简版，保证准确率和速度）：

🔍 **schema_agent**: 分析用户查询，获取准确的数据库表结构
⚙️ **sql_generator_agent**: 生成准确的SQL（已增强：智能处理模糊查询）
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
🔧 **error_recovery_agent**: 处理错误并修正SQL，提高准确率

**核心工作流程（快速高效）:**
用户查询 → schema_agent → sql_generator_agent → sql_executor_agent → 完成

**工作原则:**
1. 快速响应，简洁高效
2. SQL生成agent会智能处理模糊查询（无需额外澄清）
3. 确保SQL准确性，优先正确执行
4. 一次只分配一个代理
5. 不要自己执行任何具体工作

**模糊查询处理:**
- sql_generator_agent已增强，能智能处理模糊词：
  - "最好"/"最高" → 自动按关键指标降序
  - "最近" → 自动使用最近30天
  - "销售" → 自动选择销售额字段
- 无需额外澄清，直接生成准确SQL

**错误处理:**
任何阶段出错 → error_recovery_agent → 分析错误 → 修正SQL → 重试对应阶段

**准确率保障:**
1. schema_agent: 准确获取数据库结构
2. sql_generator_agent: 智能假设 + 准确SQL
3. sql_executor_agent: 安全执行
4. error_recovery_agent: 错误修正

请根据当前状态选择合适的代理，保持流程简洁高效，确保SQL准确性。"""

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

def create_supervisor_agent(worker_agents: List[Any] = None) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents)

def create_intelligent_sql_supervisor() -> SupervisorAgent:
    """创建智能SQL监督代理的便捷函数"""
    return SupervisorAgent()
