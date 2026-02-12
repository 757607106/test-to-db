"""
智能SQL代理图 - 统一入口

统一架构：
- LangGraph API 和 Python 直接调用走同一条路径
- Supervisor LLM 自主处理意图识别、闲聊、SQL 查询等
- 预处理（Skill 路由、QA 样本）在 pre_model_hook 中执行
- 消除外部预处理层，保留薄封装便捷接口
"""
from typing import Dict, Any, Optional, List
import logging

from langgraph.errors import GraphInterrupt
from langchain_core.messages import BaseMessage

from app.core.state import SQLMessageState
from app.agents.supervisor_agent import create_intelligent_sql_supervisor

logger = logging.getLogger(__name__)


class IntelligentSQLGraph:
    """
    智能SQL代理图 - 薄封装层
    
    架构定位：
    - 封装 SupervisorAgent 的创建和配置
    - 提供 process_query() 便捷接口（供 FastAPI 端点调用）
    - 导出 graph 属性供 LangGraph API 使用
    
    统一调用路径：
    - Python 调用: IntelligentSQLGraph.process_query() → self.graph.ainvoke()
    - LangGraph API: graph（直接使用 Supervisor 编译后的图）
    - 两者走完全相同的 Supervisor 流程
    """

    def __init__(
        self, 
        enable_clarification: bool = True,
        custom_analyst_id: Optional[int] = None,
        **kwargs  # 兼容旧参数（如 custom_analyst）
    ):
        """
        初始化智能SQL图
        
        Args:
            enable_clarification: 是否启用澄清机制
            custom_analyst_id: 自定义数据分析 Agent ID（可选）
        """
        # 兼容旧的 custom_analyst 参数
        if 'custom_analyst' in kwargs:
            logger.debug("忽略旧参数 custom_analyst，请使用 custom_analyst_id")
        
        self.enable_clarification = enable_clarification
        self.custom_analyst_id = custom_analyst_id
        self.supervisor_agent = create_intelligent_sql_supervisor(
            enable_clarification, 
            custom_analyst_id
        )
        self.graph = self.supervisor_agent.supervisor

    async def process_query(
        self, 
        query: str, 
        connection_id: Optional[int] = None,
        messages: Optional[List[BaseMessage]] = None,
        agent_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        处理查询（便捷接口）
        
        统一路径：直接构建初始状态，交给 Supervisor 处理。
        Supervisor LLM 自主判断意图（闲聊/SQL查询），不需要外部路由。
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID
            messages: 消息历史（已有的对话上下文）
            agent_id: 自定义数据分析 Agent ID（可选）
            thread_id: 会话线程ID（用于多轮对话）
            tenant_id: 租户ID
            
        Returns:
            处理结果字典
        """
        # 如果传入了 agent_id，且与实例配置不同，需要重新创建 supervisor
        effective_agent_id = agent_id if agent_id is not None else self.custom_analyst_id
        if effective_agent_id != self.custom_analyst_id:
            logger.info(f"使用自定义数据分析 Agent: id={effective_agent_id}")
            self.custom_analyst_id = effective_agent_id
            self.supervisor_agent = create_intelligent_sql_supervisor(
                self.enable_clarification,
                effective_agent_id
            )
            self.graph = self.supervisor_agent.supervisor
        
        try:
            # 直接委托给 Supervisor
            result = await self.supervisor_agent.supervise(
                state=SQLMessageState(
                    messages=[{"role": "user", "content": query}],
                    connection_id=connection_id,
                ),
                thread_id=thread_id,
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "result": result.get("result"),
                    "final_stage": result.get("result", {}).get("current_stage", "completed"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                    "final_stage": "error",
                }
                
        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"处理查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "final_stage": "error"
            }

    @property
    def worker_agents(self):
        """获取工作代理列表（向后兼容）"""
        return self.supervisor_agent.worker_agents


# ============================================================================
# 便捷函数
# ============================================================================

def create_intelligent_sql_graph(
    enable_clarification: bool = True,
    custom_analyst_id: Optional[int] = None
) -> IntelligentSQLGraph:
    """创建智能SQL图实例"""
    return IntelligentSQLGraph(enable_clarification, custom_analyst_id)


async def process_sql_query(
    query: str, 
    connection_id: Optional[int] = None,
    enable_clarification: bool = True,
    agent_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    处理SQL查询的便捷函数
    """
    graph = create_intelligent_sql_graph(enable_clarification, agent_id)
    return await graph.process_query(query, connection_id)


# 创建全局实例
_global_graph = None


def get_global_graph() -> IntelligentSQLGraph:
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


async def get_global_graph_async() -> IntelligentSQLGraph:
    """获取全局图实例（异步版本，用于测试兼容性）"""
    return get_global_graph()


# 导出 graph 用于 LangGraph 服务（langgraph.json 引用此变量）
graph = get_global_graph().graph


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        graph_instance = create_intelligent_sql_graph()
        print(f"智能SQL图创建成功: {type(graph_instance).__name__}")
        print(f"Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
        print(f"工作代理数量: {len(graph_instance.worker_agents)}")
    
    asyncio.run(test())
