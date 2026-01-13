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
        """创建工作代理"""

        # 这些import语句定义了监督代理可以调度的各种专业代理
        # 每个代理负责SQL查询处理流水线中的特定任务
        from app.agents.agents.clarification_agent import clarification_agent    # 新增：负责检测查询模糊并生成澄清问题
        from app.agents.agents.schema_agent import schema_agent          # 负责分析用户查询并获取相关数据库模式
        from app.agents.agents.sample_retrieval_agent import sample_retrieval_agent  # 负责检索相关的SQL查询样本作为参考
        from app.agents.agents.sql_generator_agent import sql_generator_agent      # 负责根据模式和样本生成SQL查询
        # 已禁用：SQL验证代理
        # from app.agents.agents.sql_validator_agent import sql_validator_agent      # 负责验证SQL查询的正确性、安全性
        from app.agents.agents.sql_executor_agent import sql_executor_agent        # 负责安全地执行SQL查询
        from app.agents.agents.analyst_agent import analyst_agent        # 新增：负责分析查询结果并生成业务洞察
        from app.agents.agents.error_recovery_agent import error_recovery_agent    # 负责处理错误和异常情况
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 负责根据查询结果生成图表可视化

        # 返回agent对象而不是包装类
        return [
            clarification_agent.agent,       # 新增：澄清代理 - 检测模糊并生成澄清问题（第一位，优先执行）
            schema_agent.agent,              # 数据库模式分析代理 - 分析用户查询并获取相关数据库结构
            # sample_retrieval_agent.agent,  # 样本检索代理 - 检索相关SQL查询样本 (暂未启用)
            sql_generator_agent.agent,       # SQL生成代理 - 根据模式和样本生成SQL查询
            # 已禁用：SQL验证代理
            # sql_validator_agent.agent,       # SQL验证代理 - 验证SQL语法、安全性及性能
            # parallel_sql_validator_agent.agent,  # 并行SQL验证代理 (暂未启用)
            sql_executor_agent.agent,        # SQL执行代理 - 安全执行SQL查询
            analyst_agent.agent,             # 新增：分析师代理 - 分析结果并生成业务洞察
            error_recovery_agent.agent,      # 错误恢复代理 - 处理错误和异常情况
            chart_generator_agent.agent      # 图表生成代理 - 根据查询结果生成数据可视化图表
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

    # 📚 ** sample_retrieval_agent **: 检索相关的SQL问答对样本，提供高质量参考
    # sample_retrieval_agent →

    # ** 样本检索优化: **
    # - 基于用户查询语义检索相似问答对
    # - 结合数据库结构进行结构化匹配
    # - 提供高质量SQL生成参考样本
    def _get_supervisor_prompt(self) -> str:
        """获取监督代理提示"""
        # print("=== 提取连接ID ===")
        # print(f"状态类型: {type(state)}")
        # print(state)
        # # 从消息中提取连接ID
        # connection_id = None  # 默认值
        # messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        #
        # for message in reversed(messages):
        #     if hasattr(message, 'type') and message.type == 'human':
        #         if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
        #             msg_connection_id = message.additional_kwargs.get('connection_id')
        #             if msg_connection_id:
        #                 connection_id = msg_connection_id
        #                 print(f"从消息中提取到连接ID: {connection_id}")
        #                 break
        #
        # # 更新state中的connection_id，确保所有后续agents都能获取到正确的连接ID
        # if isinstance(state, dict):
        #     state['connection_id'] = connection_id
        # else:
        #     state.connection_id = connection_id
        #
        # print(f"最终使用连接ID: {connection_id}")
        # print(f"已更新state.connection_id = {connection_id}")
        # print("==================")

        system_msg = f"""你是一个智能的SQL Agent系统监督者。
你管理以下专门代理：

🤔 **clarification_agent**: 分析查询是否需要澄清，生成澄清问题
🔍 **schema_agent**: 分析用户查询，获取相关数据库表结构
⚙️ **sql_generator_agent**: 根据模式信息和样本生成高质量SQL语句
# 🔍 **sql_validator_agent**: 验证SQL的语法、安全性和性能（已禁用）
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
📊 **analyst_agent**: 分析查询结果，生成业务洞察和建议
📈 **chart_generator_agent**: 根据查询结果生成数据可视化图表
🔧 **error_recovery_agent**: 处理错误并提供修复方案

**工作原则:**
1. 根据当前任务阶段选择合适的代理
2. 确保工作流程的连续性和一致性
3. 智能处理错误和异常情况
4. 一次只分配给一个代理，不要并行调用
5. 不要自己执行任何具体工作

**新工作流程（含澄清和分析）:**
用户查询 → clarification_agent → [可选澄清] → schema_agent → sql_generator_agent → sql_executor_agent → analyst_agent → [可选] chart_generator_agent → 完成

**澄清机制:**
- 首次查询时调用 clarification_agent 检测是否需要澄清
- 如需澄清，等待用户回复后继续流程
- 最多 2 轮澄清
- 明确的查询直接跳过澄清

**分析触发条件:**
- SQL 执行成功后，自动调用 analyst_agent
- analyst_agent 会智能判断是否需要深度分析
- 数据量适中、包含时间/数值字段时进行深度分析
- 数据量大时仅提供摘要
- 数据量小（<2行）时跳过分析

**图表生成条件:**
- 用户查询包含可视化意图（如"图表"、"趋势"、"分布"、"比较"等关键词）
- 查询结果包含数值数据且适合可视化
- 数据量适中（2-1000行）

**错误处理:**
任何阶段出错 → error_recovery_agent → 重试相应阶段

请根据当前状态和任务需求做出最佳的代理选择决策。特别注意：
- 优先进行澄清检测，避免执行模糊查询
- 执行后自动进行智能分析
- 根据分析结果决定是否生成图表"""

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
