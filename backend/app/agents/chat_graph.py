"""
智能SQL代理图 - 高级接口和图构建
专注于图的构建和便捷接口，supervisor逻辑委托给SupervisorAgent

核心职责:
1. 提供系统的高级入口接口
2. 管理LangGraph状态图的构建和编译
3. 支持动态加载自定义分析专家Agent
4. 提供便捷的查询处理方法

架构说明:
- 使用LangGraph的StateGraph管理整体流程
- 包含两个核心节点: load_custom_agent 和 supervisor
- supervisor节点委托给SupervisorAgent处理具体的Agent协调
"""
from typing import Dict, Any, List, Optional
import logging

from app.core.state import SQLMessageState
from app.agents.agents.supervisor_agent import create_intelligent_sql_supervisor
from app.models.agent_profile import AgentProfile

# 配置日志
logger = logging.getLogger(__name__)


def extract_connection_id_from_messages(messages) -> int:
    """
    从消息历史中提取数据库连接ID
    
    Args:
        messages: LangChain消息列表
        
    Returns:
        int: 数据库连接ID，默认为15
        
    说明:
        - 从最新的人类消息的additional_kwargs中提取connection_id
        - 如果未找到，返回默认值15
        - 用于确定查询应该在哪个数据库连接上执行
    """
    connection_id = 15  # 默认值

    # 反向遍历消息列表，查找最新的人类消息
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    break

    return connection_id


def extract_agent_id_from_messages(messages) -> Optional[int]:
    """
    从消息历史中提取自定义Agent ID
    
    Args:
        messages: LangChain消息列表
        
    Returns:
        Optional[int]: Agent ID，如果未找到返回None
        
    说明:
        - 用于识别用户是否指定了自定义分析专家
        - 如果找到agent_id，系统会动态加载对应的自定义Agent
        - 自定义Agent可以有特定的提示词和LLM配置
    """
    # 反向遍历消息列表，查找最新的人类消息
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                agent_id = message.additional_kwargs.get('agent_id')
                if agent_id:
                    return agent_id
    return None


class IntelligentSQLGraph:
    """
    智能SQL代理图 - 系统的高级接口类
    
    职责:
    1. 管理整个Text-to-SQL系统的状态图
    2. 提供便捷的查询处理接口
    3. 支持动态加载自定义分析专家
    4. 协调Supervisor和Worker Agents的工作
    
    架构:
    用户查询 → load_custom_agent节点 → supervisor节点 → 结束
    
    特性:
    - 支持自定义分析专家的动态加载
    - 使用LangGraph管理状态流转
    - 提供同步和异步接口
    """

    def __init__(self, active_agent_profiles: List[AgentProfile] = None, custom_analyst = None):
        """
        初始化智能SQL图
        
        Args:
            active_agent_profiles: 活跃的智能体配置列表（已废弃，保留向后兼容）
            custom_analyst: 自定义数据分析智能体（可选）
                          如果提供，将替换默认的chart_generator_agent
        
        说明:
            - 创建SupervisorAgent实例来协调所有Worker Agents
            - 构建包含自定义Agent加载逻辑的LangGraph状态图
            - 编译图以供后续执行
        """
        # 使用SupervisorAgent来处理所有supervisor逻辑
        # 传入自定义智能体（如果有）
        self.supervisor_agent = create_intelligent_sql_supervisor(custom_analyst=custom_analyst)
        
        # 创建并编译LangGraph状态图
        self.graph = self._create_graph_with_agent_loader()
    
    def _create_graph_with_agent_loader(self):
        """
        创建带有智能体加载器的LangGraph状态图
        
        Returns:
            CompiledGraph: 编译后的状态图
            
        图结构:
            START → load_custom_agent → supervisor → END
            
        说明:
            - load_custom_agent: 检查并加载自定义Agent（如果需要）
            - supervisor: 执行主要的查询处理流程
            - 使用SQLMessageState作为状态类型
            - 集成Checkpointer实现多轮对话和状态持久化
        """
        from langgraph.graph import StateGraph, END
        from app.core.checkpointer import get_checkpointer
        import logging
        
        logger = logging.getLogger(__name__)
        
        # 创建一个包装图，在执行前检查并加载自定义智能体
        graph = StateGraph(SQLMessageState)
        
        # 添加智能体加载节点
        # 职责: 从消息中提取agent_id，如果存在则加载自定义Agent
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        
        # 添加supervisor节点
        # 职责: 协调所有Worker Agents完成查询处理
        graph.add_node("supervisor", self._supervisor_node)
        
        # 设置入口点 - 所有查询首先进入load_custom_agent节点
        graph.set_entry_point("load_custom_agent")
        
        # 定义边: load_custom_agent → supervisor
        # 无条件转移，总是执行supervisor
        graph.add_edge("load_custom_agent", "supervisor")
        
        # 定义边: supervisor → END
        # Supervisor完成后结束整个流程
        graph.add_edge("supervisor", END)
        
        # ✅ 获取Checkpointer并编译图
        # 如果Checkpointer已启用，图将支持状态持久化和多轮对话
        checkpointer = get_checkpointer()
        
        if checkpointer:
            logger.info("✓ 使用 Checkpointer 编译图（支持多轮对话和状态持久化）")
            return graph.compile(checkpointer=checkpointer)
        else:
            logger.info("✓ 不使用 Checkpointer 编译图（无状态模式）")
            return graph.compile()
    
    async def _load_custom_agent_node(self, state: SQLMessageState) -> SQLMessageState:
        """
        加载自定义智能体节点 - LangGraph节点函数
        
        Args:
            state: 当前的SQL消息状态
            
        Returns:
            SQLMessageState: 更新后的状态（通常不修改）
            
        工作流程:
        1. 从消息历史中提取agent_id
        2. 如果存在agent_id，从数据库加载AgentProfile
        3. 验证是否为非系统Agent（只有用户自定义Agent可以加载）
        4. 使用agent_factory创建自定义分析专家实例
        5. 重新创建supervisor，使用新的自定义Agent替换默认的chart_generator
        
        说明:
            - 这个节点在每次查询开始时执行
            - 如果没有agent_id或加载失败，使用默认配置
            - 自定义Agent可以有特定的提示词和LLM配置
            - 错误不会中断流程，会回退到默认Agent
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 从消息中提取agent_id
        agent_id = extract_agent_id_from_messages(state.get("messages", []))
        
        if agent_id:
            logger.info(f"检测到 agent_id={agent_id}，开始加载自定义分析专家")
            try:
                # 导入必要的模块
                from app.db.session import SessionLocal
                from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
                from app.agents.agent_factory import create_custom_analyst_agent
                
                # 获取数据库会话
                db = SessionLocal()
                try:
                    # 从数据库加载Agent配置
                    profile = crud_agent_profile.get(db=db, id=agent_id)
                    
                    # 验证Agent存在且不是系统Agent
                    if profile and not profile.is_system:
                        # 使用工厂函数创建自定义智能体实例
                        # 会应用自定义的提示词和LLM配置
                        custom_analyst = create_custom_analyst_agent(profile, db)
                        
                        # 重新创建supervisor，使用自定义分析专家
                        # 这会替换默认的chart_generator_agent
                        self.supervisor_agent = create_intelligent_sql_supervisor(
                            custom_analyst=custom_analyst
                        )
                        
                        logger.info(f"成功加载自定义分析专家: {profile.name}")
                    else:
                        logger.warning(
                            f"Agent {agent_id} 不存在或是系统Agent，使用默认配置"
                        )
                finally:
                    # 确保关闭数据库连接
                    db.close()
            except Exception as e:
                # 加载失败不应中断流程
                logger.error(f"加载自定义Agent {agent_id} 失败: {e}", exc_info=True)
                logger.info("回退到默认分析专家")
        
        # 返回状态（通常不修改）
        return state
    
    async def _supervisor_node(self, state: SQLMessageState) -> SQLMessageState:
        """
        Supervisor节点 - LangGraph节点函数
        
        Args:
            state: 当前的SQL消息状态
            
        Returns:
            SQLMessageState: Supervisor执行后的状态
            
        说明:
            - 这是主要的处理节点
            - 调用SupervisorAgent的内部图来协调所有Worker Agents
            - Supervisor会根据current_stage决定调用哪个Worker Agent
            - 返回的状态包含所有Agent的执行结果
        """
        # 调用supervisor的内部图执行查询处理
        # supervisor.ainvoke会触发整个Agent协调流程
        result = await self.supervisor_agent.supervisor.ainvoke(state)
        return result

    async def process_query(
        self, 
        query: str, 
        connection_id: int = 15,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理SQL查询 - 便捷的异步接口（支持多轮对话）
        
        Args:
            query: 用户的自然语言查询
            connection_id: 数据库连接ID，默认为15
            thread_id: 会话线程ID（可选）
                      - 如果提供，将恢复该会话的历史状态
                      - 如果不提供，将创建新的会话
                      
        Returns:
            Dict[str, Any]: 查询结果字典
                - success: bool - 是否成功
                - result: Dict - 执行结果（如果成功）
                - error: str - 错误信息（如果失败）
                - thread_id: str - 会话线程ID（用于后续多轮对话）
                - final_stage: str - 最终阶段
                
        工作流程:
        1. 创建初始状态（包含用户查询和连接信息）
        2. 如果提供了thread_id，设置到状态中以恢复历史
        3. 构建config字典，传递thread_id给LangGraph
        4. 委托给supervisor处理
        5. 解析并返回结果（包含thread_id）
        
        说明:
            - 这是推荐的查询处理方式
            - 自动处理状态初始化
            - 支持多轮对话（通过thread_id）
            - 提供统一的错误处理
            - thread_id用于会话持久化和恢复
        """
        try:
            from langchain_core.messages import HumanMessage
            from uuid import uuid4
            
            # ✅ 生成或使用提供的thread_id
            if thread_id is None:
                thread_id = str(uuid4())
                logger.info(f"生成新的 thread_id: {thread_id}")
            else:
                logger.info(f"使用现有 thread_id: {thread_id}")
            
            # 初始化状态
            # 设置初始阶段为schema_analysis，由supervisor决定后续流程
            initial_state = SQLMessageState(
                messages=[HumanMessage(content=query)],  # 用户查询
                connection_id=connection_id,              # 数据库连接
                thread_id=thread_id,                      # ✅ 会话线程ID
                current_stage="schema_analysis",          # 初始阶段
                retry_count=0,                            # 重试计数
                max_retries=3,                            # 最大重试次数
                error_history=[]                          # 错误历史
            )

            # ✅ 构建配置，传递thread_id给LangGraph
            # LangGraph使用thread_id来管理会话状态
            config = {"configurable": {"thread_id": thread_id}}

            # 委托给supervisor处理
            # supervisor会协调所有Worker Agents完成查询
            # 传递config以启用状态持久化
            result = await self.supervisor_agent.supervise(initial_state, config)

            # 解析结果
            if result.get("success"):
                return {
                    "success": True,
                    "result": result.get("result"),
                    "thread_id": thread_id,  # ✅ 返回thread_id供后续使用
                    "final_stage": result.get("result", {}).get("current_stage", "completed")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                    "thread_id": thread_id,  # ✅ 即使失败也返回thread_id
                    "final_stage": "error"
                }

        except Exception as e:
            # 顶层异常处理
            return {
                "success": False,
                "error": str(e),
                "thread_id": thread_id if 'thread_id' in locals() else None,
                "final_stage": "error"
            }

    @property
    def worker_agents(self):
        """
        获取工作代理列表 - 属性访问器
        
        Returns:
            List: Worker Agents列表
            
        说明:
            - 为了向后兼容保留的属性
            - 返回supervisor管理的所有Worker Agents
            - 包括: schema_agent, sql_generator_agent, sql_executor_agent,
                   error_recovery_agent, chart_generator_agent
        """
        return self.supervisor_agent.worker_agents


# ============================================================================
# 便捷函数 - 提供简化的接口
# ============================================================================

def create_intelligent_sql_graph(active_agent_profiles: List[AgentProfile] = None) -> IntelligentSQLGraph:
    """
    创建智能SQL图实例 - 工厂函数
    
    Args:
        active_agent_profiles: 活跃的智能体配置列表（已废弃，保留向后兼容）
        
    Returns:
        IntelligentSQLGraph: 图实例
        
    说明:
        - 这是创建图实例的推荐方式
        - 使用默认配置创建
        - 如果需要自定义Agent，在查询时通过agent_id指定
    """
    return IntelligentSQLGraph()


async def process_sql_query(
    query: str, 
    connection_id: int = 15, 
    active_agent_profiles: List[AgentProfile] = None
) -> Dict[str, Any]:
    """
    处理SQL查询的便捷函数 - 一站式接口
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        active_agent_profiles: 活跃的智能体配置列表（已废弃）
        
    Returns:
        Dict[str, Any]: 查询结果
        
    说明:
        - 自动创建图实例
        - 执行查询并返回结果
        - 适合一次性查询场景
    """
    graph = create_intelligent_sql_graph()
    return await graph.process_query(query, connection_id)


# ============================================================================
# 全局实例管理 - 单例模式
# ============================================================================

# 全局图实例 - 避免重复创建
_global_graph = None


def get_global_graph():
    """
    获取全局图实例 - 单例模式
    
    Returns:
        IntelligentSQLGraph: 全局图实例
        
    说明:
        - 使用单例模式，避免重复创建图实例
        - 首次调用时创建，后续调用返回同一实例
        - 适合长期运行的服务
        - 注意: 全局实例不支持动态切换自定义Agent
    """
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


def graph():
    """
    图工厂函数 - 供 LangGraph API 使用
    
    Returns:
        CompiledGraph: 编译后的LangGraph状态图
        
    说明:
        - 这个函数被 langgraph.json 引用
        - LangGraph CLI 和 API 服务器使用此函数获取图定义
        - 配置路径: ./app/agents/chat_graph.py:graph
        - 返回的是编译后的图，可以直接执行
        
    使用场景:
        - LangGraph Studio 可视化
        - LangGraph API 服务器部署
        - LangGraph CLI 命令行工具
    """
    return get_global_graph().graph


# ============================================================================
# 测试和调试
# ============================================================================

if __name__ == "__main__":
    """
    模块测试入口
    
    功能:
        - 创建图实例
        - 打印基本信息
        - 验证配置正确性
        
    运行方式:
        python -m app.agents.chat_graph
    """
    # 创建图实例
    graph_instance = create_intelligent_sql_graph()
    print(f"智能SQL图创建成功: {type(graph_instance).__name__}")
    print(f"Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
    print(f"工作代理数量: {len(graph_instance.worker_agents)}")
    
    # 打印Worker Agents列表
    print("\nWorker Agents:")
    for i, agent in enumerate(graph_instance.worker_agents, 1):
        agent_name = getattr(agent, 'name', 'unknown')
        print(f"  {i}. {agent_name}")
