"""
监督代理 (Supervisor Agent) - 使用LangGraph内置supervisor模式

核心职责:
1. 协调所有Worker Agents的工作流程
2. 根据任务阶段智能路由到合适的Agent
3. 管理Agent间的消息传递和状态更新
4. 处理错误和异常情况

架构模式:
- 使用LangGraph的create_supervisor创建协调器
- 采用Supervisor-Worker模式
- Worker Agents包括: schema, sql_generator, sql_executor, error_recovery, chart_generator

工作流程:
用户查询 → Supervisor分析 → 选择Worker Agent → Agent执行 → 
更新状态 → Supervisor再次分析 → 继续或结束

依赖:
pip install langgraph-supervisor

历史变更:
- 2026-01-16: 移除SQL Validator Agent以简化流程
- 备份位置: backend/backups/agents_backup_20260116_175357
"""

from typing import Dict, Any, List, Optional
import logging

from langchain_core.runnables import RunnableConfig
from langgraph_supervisor import create_supervisor

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.message_utils import validate_and_fix_message_history

# 配置日志
logger = logging.getLogger(__name__)


class SupervisorAgent:
    """监督代理 - 基于LangGraph自带supervisor"""

    def __init__(self, worker_agents: List[Any] = None, custom_analyst = None):
        """
        初始化Supervisor
        
        Args:
            worker_agents: 工作智能体列表（可选）
            custom_analyst: 自定义数据分析专家（可选），如果提供则替换默认的chart_analyst_core
        """
        self.llm = get_default_model()
        self.custom_analyst = custom_analyst
        self.worker_agents = worker_agents or self._create_worker_agents()
        self.supervisor = self._create_supervisor()

    def _create_worker_agents(self) -> List[Any]:
        """创建工作代理
        
        如果提供了custom_analyst，使用它替换默认的chart_generator_agent
        
        注意：SQL Validator Agent已被移除以简化流程
        - 移除原因：减少不必要的验证步骤，提升响应速度
        - 移除时间：2026-01-16
        - 备份位置：backend/backups/agents_backup_20260116_175357
        """

        # 导入各个专业代理
        from app.agents.agents.schema_agent import schema_agent  # 数据库模式分析代理
        from app.agents.agents.sample_retrieval_agent import sample_retrieval_agent  # SQL样本检索代理
        from app.agents.agents.sql_generator_agent import sql_generator_agent  # SQL生成代理
        # 已移除：from app.agents.agents.sql_validator_agent import sql_validator_agent
        from app.agents.agents.sql_executor_agent import sql_executor_agent  # SQL执行代理
        from app.agents.agents.error_recovery_agent import error_recovery_agent  # 错误恢复代理
        from app.agents.agents.chart_generator_agent import chart_generator_agent  # 图表生成代理

        # 返回agent对象而不是包装类 简化后只包含5个核心代理

        agents = [
            schema_agent.agent,
            # 临时禁用 sample_retrieval_agent - 由于 ReAct agent 调度延迟问题，该步骤会导致 2+ 分钟的等待
            # 在问题修复前，SQL 生成器可以在无样本参考的情况下正常工作
            # sample_retrieval_agent.agent,
            sql_generator_agent.agent,
            # 已移除：sql_validator_agent.agent  # 验证步骤已移除
            # parallel_sql_validator_agent.agent,
            sql_executor_agent.agent,
            error_recovery_agent.agent,
        ]
        
        # 如果提供了自定义分析专家，使用它；否则使用默认的
        if self.custom_analyst:
            logger.info("Using custom analyst agent instead of default chart_generator_agent")
            agents.append(self.custom_analyst.agent)
        else:
            logger.info("Using default chart_generator_agent")
            agents.append(chart_generator_agent.agent)
        
        return agents

    # def pre_model_hook(self, state):
    #     print("哈哈哈哈哈哈松林测试：：：：", state)
    def _create_supervisor(self):
        """创建LangGraph supervisor"""
        supervisor = create_supervisor(
            model=self.llm,
            agents=self.worker_agents,
            prompt=self._get_supervisor_prompt(),
            add_handoff_back_messages=False,  # ✅ 修复消息重复：不添加handoff消息
            # pre_model_hook=self.pre_model_hook,
            # parallel_tool_calls=True,
            output_mode="last_message",  # ✅ 修复消息重复：只返回最后的总结消息
        )

        return supervisor.compile()

    # 📚 样本检索功能已集成到 sql_generator_agent 中
    # 
    # 优化历史 (2026-01-19):
    # - 原 sample_retrieval_agent 作为独立 ReAct agent 存在调度延迟问题（2+ 分钟）
    # - 现已将样本检索集成到 sql_generator_agent 内部
    # - 特点：先快速检查是否有样本，没有则跳过；有则自动检索

    def _get_supervisor_prompt(self) -> str:
        """
        获取监督代理提示 简化后的流程不包含SQL验证步骤
        """

        system_msg = f"""你是一个智能的SQL Agent系统监督者。
你管理以下专门代理：

🔍 **schema_agent**: 分析用户查询，获取相关数据库表结构
⚙️ **sql_generator_agent**: 根据模式信息生成高质量SQL语句（内置样本检索，自动参考历史QA对）
🚀 **sql_executor_agent**: 安全执行SQL并返回结果
📊 **chart_generator_agent**: 根据查询结果生成数据可视化图表
🔧 **error_recovery_agent**: 处理错误并提供修复方案

**工作原则:**
1. 根据当前任务阶段选择合适的代理
2. 确保工作流程的连续性和一致性
3. 智能处理错误和异常情况
4. 一次只分配给一个代理，不要并行调用
5. 不要自己执行任何具体工作

**标准流程:**
用户查询 → schema_agent → sql_generator_agent → sql_executor_agent → [可选] chart_generator_agent → 完成

**图表生成条件:**
- 用户查询包含可视化意图（如"图表"、"趋势"、"分布"、"比较"等关键词）
- 查询结果包含数值数据且适合可视化
- 数据量适中（2-1000行）

**错误处理:**
任何阶段出错 → error_recovery_agent → 尝试修复一次 → 如果仍失败则返回错误信息

请根据当前状态和任务需求做出最佳的代理选择决策。特别注意：
- 当用户查询包含可视化意图时，在SQL执行完成后应考虑调用chart_generator_agent
- 当查询结果适合可视化时，主动建议生成图表
- SQL生成后直接执行，不需要验证步骤"""

        return system_msg

    async def supervise(
        self, 
        state: SQLMessageState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        监督整个流程 - 支持配置传递和多轮对话
        
        Args:
            state: SQL消息状态
            config: LangGraph配置（可选）
                   - 包含thread_id等配置信息
                   - 用于状态持久化和会话恢复
                   
        Returns:
            Dict[str, Any]: 执行结果
                - success: bool - 是否成功
                - result: Dict - 执行结果
                - error: str - 错误信息（如果失败）
                
        说明:
            - 在执行前后验证并修复消息历史
            - 自动修剪消息历史以控制token使用
            - 如果提供了config，将传递给LangGraph以启用持久化
            - 支持多轮对话和会话恢复
        """
        # ✅ Phase 3: 在执行前修剪消息历史
        from app.core.message_history import auto_trim_messages, get_message_stats
        
        if "messages" in state and state["messages"]:
            # 获取修剪前的统计信息
            before_stats = get_message_stats(state["messages"])
            logger.info(f"执行前消息统计: {before_stats}")
            
            # 自动修剪消息（如果需要）
            state["messages"] = auto_trim_messages(state["messages"])
            
            # 获取修剪后的统计信息
            after_stats = get_message_stats(state["messages"])
            if after_stats["total"] < before_stats["total"]:
                logger.info(
                    f"消息历史已修剪: {before_stats['total']} -> {after_stats['total']} "
                    f"(估算token: {before_stats['estimated_tokens']} -> {after_stats['estimated_tokens']})"
                )
        
        # 在执行前先验证并修复消息历史
        if "messages" in state and state["messages"]:
            original_count = len(state["messages"])
            state["messages"] = validate_and_fix_message_history(state["messages"])
            fixed_count = len(state["messages"])
            
            if fixed_count > original_count:
                logger.info(
                    f"执行前修复消息历史: 添加了 {fixed_count - original_count} 个占位ToolMessage"
                )
        
        try:
            # ✅ 执行supervisor，传递config以启用状态持久化
            if config:
                logger.info(f"使用 config 执行 supervisor: {config.get('configurable', {})}")
                result = await self.supervisor.ainvoke(state, config=config)
            else:
                logger.info("不使用 config 执行 supervisor（无状态模式）")
                result = await self.supervisor.ainvoke(state)
            
            # 执行后再次验证并修复消息历史
            if "messages" in result:
                original_count = len(result["messages"])
                result["messages"] = validate_and_fix_message_history(result["messages"])
                fixed_count = len(result["messages"])
                
                # 如果添加了占位消息，记录日志
                if fixed_count > original_count:
                    logger.info(
                        f"执行后修复消息历史: 添加了 {fixed_count - original_count} 个占位ToolMessage"
                    )
            
            return {
                "success": True,
                "result": result
            }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Supervisor执行出错: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }


def create_supervisor_agent(worker_agents: List[Any] = None, custom_analyst = None) -> SupervisorAgent:
    """
    创建监督代理实例
    
    Args:
        worker_agents: 工作智能体列表（可选）
        custom_analyst: 自定义数据分析专家（可选）
    """
    return SupervisorAgent(worker_agents, custom_analyst)

def create_intelligent_sql_supervisor(custom_analyst = None) -> SupervisorAgent:
    """
    创建智能SQL监督代理的便捷函数
    
    Args:
        custom_analyst: 自定义数据分析专家（可选）
    """
    return SupervisorAgent(custom_analyst=custom_analyst)
