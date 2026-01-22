"""
智能 SQL 代理图 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 AsyncPostgresSaver 进行异步状态持久化
2. 使用原生条件边 (conditional_edges) 进行路由
3. 使用 add_messages reducer 管理消息历史
4. 完全异步实现，避免同步异步混用

架构说明:
- 使用 LangGraph 的 StateGraph 管理整体流程
- 包含多个核心节点: load_custom_agent、fast_mode_detect、clarification、cache_check、supervisor
- clarification 节点使用 interrupt() 实现人机交互
- supervisor 节点协调 Worker Agents 处理查询

图结构:
    START → load_custom_agent → fast_mode_detect → clarification → cache_check → [supervisor | END]
"""
from typing import Dict, Any, List, Optional
import logging
import asyncio

from langgraph.graph import StateGraph, END

from app.core.state import SQLMessageState, detect_fast_mode
from app.agents.agents.supervisor_agent import SupervisorAgent, create_intelligent_sql_supervisor
from app.agents.nodes.clarification_node import clarification_node
from app.agents.nodes.cache_check_node import cache_check_node
from app.models.agent_profile import AgentProfile

logger = logging.getLogger(__name__)


# ============================================================================
# 辅助函数
# ============================================================================

def extract_connection_id_from_messages(messages) -> Optional[int]:
    """
    从消息历史中提取数据库连接 ID
    """
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    return msg_connection_id
    return None


def extract_agent_id_from_messages(messages) -> Optional[int]:
    """
    从消息历史中提取自定义 Agent ID
    """
    for message in reversed(messages if messages else []):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                agent_id = message.additional_kwargs.get('agent_id')
                if agent_id:
                    return agent_id
    return None


# ============================================================================
# 主图类
# ============================================================================

class IntelligentSQLGraph:
    """
    智能 SQL 代理图 - 系统的高级接口类
    
    职责:
    1. 管理整个 Text-to-SQL 系统的状态图
    2. 提供便捷的查询处理接口
    3. 支持动态加载自定义分析专家
    4. 协调 Supervisor 和 Worker Agents
    5. 支持澄清模式（使用 interrupt 机制）
    
    LangGraph 官方最佳实践:
    - 图的创建是同步的，编译后返回 CompiledGraph
    - Checkpointer 由 LangGraph API 在运行时自动注入
    - 参考: https://langchain-ai.github.io/langgraph/concepts/langgraph_server/
    """
    
    def __init__(self, active_agent_profiles: List[AgentProfile] = None, custom_analyst=None):
        """
        初始化智能 SQL 图
        
        注意: 图在初始化时同步创建，不依赖异步 checkpointer
        """
        self.supervisor_agent = create_intelligent_sql_supervisor(custom_analyst=custom_analyst)
        self._checkpointer = None
        
        # 同步创建图 - LangGraph API 要求图工厂函数返回编译好的图
        self.graph = self._create_graph_sync()
        self._initialized = True
    
    def _create_graph_sync(self):
        """
        同步创建 LangGraph 状态图
        
        LangGraph 官方最佳实践:
        - 图的定义和编译是同步的
        - Checkpointer 由 LangGraph API Server 自动管理
        - 不需要在图创建时初始化 checkpointer
        """
        graph = StateGraph(SQLMessageState)
        
        # 添加节点
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        graph.add_node("fast_mode_detect", self._fast_mode_detect_node)
        graph.add_node("clarification", clarification_node)
        graph.add_node("cache_check", cache_check_node)
        graph.add_node("supervisor", self._supervisor_node)
        
        # 设置入口点
        graph.set_entry_point("load_custom_agent")
        
        # 定义边
        graph.add_edge("load_custom_agent", "fast_mode_detect")
        graph.add_edge("fast_mode_detect", "clarification")
        graph.add_edge("clarification", "cache_check")
        
        # 条件边: cache_check → [supervisor | END]
        graph.add_conditional_edges(
            "cache_check",
            self._after_cache_check,
            {
                "supervisor": "supervisor",
                "end": END
            }
        )
        
        # supervisor → END
        graph.add_edge("supervisor", END)
        
        # 编译图 - 不指定 checkpointer，由 LangGraph API 注入
        logger.info("✓ 编译 SQL Agent 图 (checkpointer 由 LangGraph API 管理)")
        return graph.compile()
    
    async def _ensure_initialized(self):
        """
        确保图已初始化（保持向后兼容）
        
        注意: 现在图在 __init__ 中同步创建，此方法主要用于兼容
        """
        if not self._initialized:
            self.graph = self._create_graph_sync()
            self._initialized = True
    
    async def _create_graph_async(self):
        """
        异步创建 LangGraph 状态图（用于需要自定义 checkpointer 的场景）
        
        使用 AsyncPostgresSaver 进行异步状态持久化
        """
        from app.core.checkpointer import get_checkpointer_async
        
        graph = StateGraph(SQLMessageState)
        
        # 添加节点
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        graph.add_node("fast_mode_detect", self._fast_mode_detect_node)
        graph.add_node("clarification", clarification_node)
        graph.add_node("cache_check", cache_check_node)
        graph.add_node("supervisor", self._supervisor_node)
        
        # 设置入口点
        graph.set_entry_point("load_custom_agent")
        
        # 定义边
        graph.add_edge("load_custom_agent", "fast_mode_detect")
        graph.add_edge("fast_mode_detect", "clarification")
        graph.add_edge("clarification", "cache_check")
        
        # 条件边: cache_check → [supervisor | END]
        graph.add_conditional_edges(
            "cache_check",
            self._after_cache_check,
            {
                "supervisor": "supervisor",
                "end": END
            }
        )
        
        # supervisor → END
        graph.add_edge("supervisor", END)
        
        # 获取异步 Checkpointer
        try:
            checkpointer = await get_checkpointer_async()
            if checkpointer:
                logger.info("✓ 使用 AsyncPostgresSaver 编译图")
                self._checkpointer = checkpointer
                return graph.compile(checkpointer=checkpointer)
            else:
                logger.warning("Checkpointer 未启用，图将无状态运行")
                return graph.compile()
        except Exception as e:
            logger.error(f"Checkpointer 初始化失败: {e}")
            logger.warning("回退到无状态模式")
            return graph.compile()
    
    def _after_cache_check(self, state: SQLMessageState) -> str:
        """判断缓存检查后的下一步"""
        cache_hit = state.get("cache_hit", False)
        
        if cache_hit:
            logger.info("缓存命中，跳过 supervisor 直接返回")
            return "end"
        else:
            logger.info("缓存未命中，继续到 supervisor")
            return "supervisor"
    
    async def _load_custom_agent_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        加载自定义智能体节点
        """
        # 从消息中提取 connection_id
        messages = state.get("messages", [])
        extracted_connection_id = extract_connection_id_from_messages(messages)
        
        updates = {}
        
        if extracted_connection_id and extracted_connection_id != state.get("connection_id"):
            logger.info(f"从消息中提取到 connection_id={extracted_connection_id}")
            updates["connection_id"] = extracted_connection_id
        
        # 从消息中提取 agent_id
        agent_id = extract_agent_id_from_messages(messages)
        
        if agent_id:
            logger.info(f"检测到 agent_id={agent_id}，开始加载自定义分析专家")
            try:
                from app.db.session import SessionLocal
                from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
                from app.agents.agent_factory import create_custom_analyst_agent
                
                db = SessionLocal()
                try:
                    profile = crud_agent_profile.get(db=db, id=agent_id)
                    
                    if profile and not profile.is_system:
                        custom_analyst = create_custom_analyst_agent(profile, db)
                        self.supervisor_agent = create_intelligent_sql_supervisor(
                            custom_analyst=custom_analyst
                        )
                        logger.info(f"成功加载自定义分析专家: {profile.name}")
                    else:
                        logger.warning(f"Agent {agent_id} 不存在或是系统 Agent")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"加载自定义 Agent 失败: {e}")
        
        return updates if updates else {}
    
    async def _fast_mode_detect_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        快速模式检测节点
        """
        messages = state.get("messages", [])
        user_query = None
        
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content
                if isinstance(user_query, list):
                    user_query = user_query[0].get("text", "") if user_query else ""
                break
        
        if not user_query:
            logger.info("无法提取用户查询，使用默认完整模式")
            return {}
        
        detection = detect_fast_mode(user_query)
        
        mode_str = "快速模式" if detection["fast_mode"] else "完整模式"
        logger.info(f"=== 模式检测: {mode_str} ===")
        logger.info(f"  原因: {detection['reason']}")
        
        return {
            "fast_mode": detection["fast_mode"],
            "skip_sample_retrieval": detection["skip_sample_retrieval"],
            "skip_chart_generation": detection["skip_chart_generation"],
            "enable_query_checker": detection["enable_query_checker"]
        }
    
    async def _supervisor_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        Supervisor 节点
        """
        result = await self.supervisor_agent.supervise(state)
        
        if result.get("success"):
            final_result = result.get("result", state)
        else:
            logger.error(f"Supervisor 执行失败: {result.get('error')}")
            final_result = state
        
        # 存储结果到缓存
        await self._store_result_to_cache(state, final_result)
        
        return final_result
    
    async def _store_result_to_cache(self, original_state: SQLMessageState, result: SQLMessageState) -> None:
        """
        将执行结果存储到缓存
        """
        try:
            from app.services.query_cache_service import get_cache_service
            from app.agents.nodes.cache_check_node import extract_user_query
            import re
            import json as json_module
            from langchain_core.messages import ToolMessage
            
            messages = original_state.get("messages", [])
            user_query = extract_user_query(messages)
            
            if not user_query:
                return
            
            connection_id = original_state.get("connection_id")
            
            # 提取 SQL
            generated_sql = None
            execution_result = None
            
            result_messages = result.get("messages", [])
            
            for msg in result_messages:
                if hasattr(msg, 'content'):
                    content = msg.content
                    if isinstance(content, list):
                        content = " ".join(
                            str(part.get("text")) if isinstance(part, dict) and part.get("text") else str(part)
                            for part in content
                        )
                    elif isinstance(content, dict):
                        content = str(content.get("text", ""))
                    
                    if '```sql' in content.lower():
                        sql_match = re.search(r'```sql\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
                        if sql_match:
                            generated_sql = sql_match.group(1).strip()
                            break
            
            # 从 ToolMessage 提取执行结果
            if not execution_result:
                for msg in reversed(result_messages):
                    if isinstance(msg, ToolMessage) and getattr(msg, 'name', '') == 'execute_sql_query':
                        try:
                            tool_content = msg.content
                            if isinstance(tool_content, str):
                                parsed_result = json_module.loads(tool_content)
                                if isinstance(parsed_result, dict):
                                    execution_result = {
                                        "success": parsed_result.get("success", False),
                                        "data": parsed_result.get("data"),
                                        "error": parsed_result.get("error")
                                    }
                                    break
                        except Exception:
                            continue
            
            if generated_sql:
                cache_service = get_cache_service()
                cache_service.store_result(
                    query=user_query,
                    connection_id=connection_id,
                    sql=generated_sql,
                    result=execution_result
                )
                logger.info(f"缓存存储成功: query='{user_query[:50]}...'")
                
        except Exception as e:
            logger.warning(f"缓存存储失败: {e}")
    
    async def process_query(
        self,
        query: str,
        connection_id: Optional[int] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理 SQL 查询 - 便捷的异步接口
        """
        try:
            from langchain_core.messages import HumanMessage
            from uuid import uuid4
            
            # 确保图已初始化
            await self._ensure_initialized()
            
            # 生成 thread_id
            if thread_id is None:
                thread_id = str(uuid4())
                logger.info(f"生成新的 thread_id: {thread_id}")
            else:
                logger.info(f"使用现有 thread_id: {thread_id}")
            
            # 初始化状态
            initial_state = {
                "messages": [HumanMessage(content=query)],
                "connection_id": connection_id,
                "thread_id": thread_id,
                "current_stage": "schema_analysis",
                "retry_count": 0,
                "max_retries": 3,
                "error_history": []
            }
            
            # 构建配置
            config = {"configurable": {"thread_id": thread_id}}
            
            # 执行图
            result = await self.graph.ainvoke(initial_state, config=config)
            
            return {
                "success": True,
                "result": result,
                "thread_id": thread_id,
                "final_stage": result.get("current_stage", "completed")
            }
            
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "thread_id": thread_id if 'thread_id' in locals() else None,
                "final_stage": "error"
            }
    
    @property
    def worker_agents(self):
        """获取工作代理列表"""
        return self.supervisor_agent.worker_agents


# ============================================================================
# 便捷函数
# ============================================================================

def create_intelligent_sql_graph(active_agent_profiles: List[AgentProfile] = None) -> IntelligentSQLGraph:
    """创建智能 SQL 图实例"""
    return IntelligentSQLGraph()


async def process_sql_query(
    query: str,
    connection_id: Optional[int] = None,
    active_agent_profiles: List[AgentProfile] = None
) -> Dict[str, Any]:
    """处理 SQL 查询的便捷函数"""
    graph = create_intelligent_sql_graph()
    return await graph.process_query(query, connection_id)


# ============================================================================
# 全局实例管理
# ============================================================================

_global_graph: Optional[IntelligentSQLGraph] = None


def get_global_graph() -> IntelligentSQLGraph:
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


async def get_global_graph_async() -> IntelligentSQLGraph:
    """异步获取全局图实例（确保已初始化）"""
    graph = get_global_graph()
    await graph._ensure_initialized()
    return graph


def graph():
    """
    图工厂函数 - 供 LangGraph API 使用
    
    LangGraph 官方最佳实践:
    - 图工厂函数必须返回一个编译好的 CompiledGraph
    - 函数可以是同步的（推荐）或异步的
    - Checkpointer 由 LangGraph API Server 自动管理，无需在此处指定
    
    参考: https://langchain-ai.github.io/langgraph/concepts/langgraph_server/
    """
    g = get_global_graph()
    return g.graph


# ============================================================================
# 预热服务
# ============================================================================

async def warmup_services(connection_ids: List[int] = None):
    """预热初始化检索服务"""
    logger.info("开始预热 SQL 检索服务...")
    
    try:
        from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
        await HybridRetrievalEnginePool.warmup(connection_ids=connection_ids)
        logger.info("✓ SQL 检索服务预热完成")
    except Exception as e:
        logger.warning(f"检索服务预热失败（不影响正常使用）: {str(e)}")


def warmup_services_sync(connection_ids: List[int] = None):
    """同步版本的预热初始化"""
    try:
        asyncio.run(warmup_services(connection_ids))
    except Exception as e:
        logger.warning(f"同步预热失败: {str(e)}")


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "IntelligentSQLGraph",
    "create_intelligent_sql_graph",
    "process_sql_query",
    "get_global_graph",
    "get_global_graph_async",
    "graph",
    "warmup_services",
    "warmup_services_sync",
]
