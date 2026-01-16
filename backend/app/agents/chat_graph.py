"""
智能SQL代理图 - 高级接口和图构建
专注于图的构建和便捷接口，supervisor逻辑委托给SupervisorAgent
"""
from typing import Dict, Any, List, Optional

from app.core.state import SQLMessageState
from app.agents.agents.supervisor_agent import create_intelligent_sql_supervisor
from app.models.agent_profile import AgentProfile


def extract_connection_id_from_messages(messages) -> int:
    """从消息中提取连接ID"""
    connection_id = 15  # 默认值

    # 查找最新的人类消息中的连接ID
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    break

    return connection_id


def extract_agent_id_from_messages(messages) -> Optional[int]:
    """从消息中提取智能体ID"""
    # 查找最新的人类消息中的智能体ID
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                agent_id = message.additional_kwargs.get('agent_id')
                if agent_id:
                    return agent_id
    return None


class IntelligentSQLGraph:
    """智能SQL代理图 - 高级接口"""

    def __init__(self, active_agent_profiles: List[AgentProfile] = None, custom_analyst = None):
        """
        初始化智能SQL图
        
        Args:
            active_agent_profiles: 活跃的智能体配置列表（已废弃，保留向后兼容）
            custom_analyst: 自定义数据分析智能体（可选）
        """
        # 使用SupervisorAgent来处理所有supervisor逻辑
        # 传入自定义智能体
        self.supervisor_agent = create_intelligent_sql_supervisor(custom_analyst=custom_analyst)
        self.graph = self._create_graph_with_agent_loader()
    
    def _create_graph_with_agent_loader(self):
        """创建带有智能体加载器的图"""
        from langgraph.graph import StateGraph, END
        
        # 创建一个包装图，在执行前检查并加载自定义智能体
        graph = StateGraph(SQLMessageState)
        
        # 添加智能体加载节点
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        
        # 添加supervisor节点
        graph.add_node("supervisor", self._supervisor_node)
        
        # 设置入口点
        graph.set_entry_point("load_custom_agent")
        
        # 从加载节点到supervisor
        graph.add_edge("load_custom_agent", "supervisor")
        
        # Supervisor到END
        graph.add_edge("supervisor", END)
        
        return graph.compile()
    
    async def _load_custom_agent_node(self, state: SQLMessageState) -> SQLMessageState:
        """加载自定义智能体节点"""
        import logging
        logger = logging.getLogger(__name__)
        
        # 从消息中提取agent_id
        agent_id = extract_agent_id_from_messages(state.get("messages", []))
        
        if agent_id:
            logger.info(f"Detected agent_id={agent_id} in messages, loading custom analyst")
            try:
                # 获取数据库会话
                from app.db.session import SessionLocal
                from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
                from app.agents.agent_factory import create_custom_analyst_agent
                
                db = SessionLocal()
                try:
                    profile = crud_agent_profile.get(db=db, id=agent_id)
                    if profile and not profile.is_system:
                        # 创建自定义智能体
                        custom_analyst = create_custom_analyst_agent(profile, db)
                        
                        # 重新创建supervisor with custom analyst
                        self.supervisor_agent = create_intelligent_sql_supervisor(custom_analyst=custom_analyst)
                        
                        logger.info(f"Successfully loaded custom analyst: {profile.name}")
                    else:
                        logger.warning(f"Agent {agent_id} not found or is a system agent, using default")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to load custom agent {agent_id}: {e}", exc_info=True)
                logger.info("Falling back to default analyst")
        
        return state
    
    async def _supervisor_node(self, state: SQLMessageState) -> SQLMessageState:
        """Supervisor节点"""
        # 调用supervisor的图
        result = await self.supervisor_agent.supervisor.ainvoke(state)
        return result

    async def process_query(self, query: str, connection_id: int = 15) -> Dict[str, Any]:
        """处理SQL查询"""
        try:
            from langchain_core.messages import HumanMessage
            
            # 初始化状态
            initial_state = SQLMessageState(
                messages=[HumanMessage(content=query)],
                connection_id=connection_id,
                current_stage="schema_analysis",
                retry_count=0,
                max_retries=3,
                error_history=[]
            )

            # 委托给supervisor处理
            result = await self.supervisor_agent.supervise(initial_state)

            if result.get("success"):
                return {
                    "success": True,
                    "result": result.get("result"),
                    "final_stage": result.get("result", {}).get("current_stage", "completed")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                    "final_stage": "error"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "final_stage": "error"
            }

    @property
    def worker_agents(self):
        """获取工作代理列表（为了向后兼容）"""
        return self.supervisor_agent.worker_agents


# 便捷函数
def create_intelligent_sql_graph(active_agent_profiles: List[AgentProfile] = None) -> IntelligentSQLGraph:
    """创建智能SQL图实例"""
    return IntelligentSQLGraph()


async def process_sql_query(query: str, connection_id: int = 15, active_agent_profiles: List[AgentProfile] = None) -> Dict[str, Any]:
    """处理SQL查询的便捷函数"""
    graph = create_intelligent_sql_graph()
    return await graph.process_query(query, connection_id)


# 全局实例
_global_graph = None


def get_global_graph():
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


def graph():
    """
    图工厂函数 - 供 LangGraph API 使用
    
    langgraph.json 中引用此函数: ./app/agents/chat_graph.py:graph
    返回编译后的 StateGraph 对象
    """
    return get_global_graph().graph


if __name__ == "__main__":
    # 创建图实例
    graph_instance = create_intelligent_sql_graph()
    print(f"智能SQL图创建成功: {type(graph_instance).__name__}")
    print(f"Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
    print(f"工作代理数量: {len(graph_instance.worker_agents)}")
