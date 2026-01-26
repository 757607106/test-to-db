"""
智能 SQL 代理图 - Hub-and-Spoke 架构

遵循 LangGraph 官方 Supervisor 模式:
- Supervisor 作为中心枢纽，所有 Worker Agent 向 Supervisor 报告
- Supervisor 统一决策和汇总结果
- 支持澄清机制 (interrupt) 和三级缓存

P2 新增: 智能规划
- 查询规划节点：分析意图、分类查询、生成执行计划
- 智能路由：根据查询类型选择最佳处理路径

图结构:
    START → supervisor → [planning] → [Worker Agents] → supervisor → ... → FINISH
"""
from typing import Dict, Any, List, Optional
import logging

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import AIMessage, HumanMessage

from app.core.state import SQLMessageState
from app.models.agent_profile import AgentProfile

# 导入统一的 Worker 节点
from app.agents.nodes.worker_nodes import (
    schema_agent_node,
    sql_generator_node,
    sql_executor_node,
    data_analyst_node,
    chart_generator_node,
    error_recovery_node,
    general_chat_node,
    clarification_node_wrapper,
)

# P2: 导入规划节点
from app.agents.nodes.query_planning_node import query_planning_node
# P2.1: 导入结果聚合节点
from app.agents.nodes.result_aggregator_node import result_aggregator_node

logger = logging.getLogger(__name__)


# ============================================================================
# Supervisor 节点
# ============================================================================

async def supervisor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 中心节点
    
    职责:
    - 检测新消息并重置状态
    - P2.1: 多步执行循环 - 管理子任务的顺序执行
    - 汇总各 Agent 的执行结果
    """
    current_stage = state.get("current_stage", "init")
    
    # 检测是否有新的用户消息需要处理
    if current_stage in ["completed", "recommendation_done"]:
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            is_human_message = _is_human_message(last_msg)
            
            if is_human_message:
                logger.info("[Supervisor] 检测到新的用户消息，重置状态")
                return {
                    "current_stage": "init",
                    "execution_result": None,
                    "generated_sql": None,
                    "analyst_insights": None,
                    "chart_config": None,
                    "recommended_questions": [],
                    "final_response": None,
                    "cache_hit": False,
                    "thread_history_hit": False,
                    "enriched_query": None,
                    "original_query": None,
                    "schema_info": None,
                    # P2.1: 重置多步执行状态
                    "multi_step_mode": False,
                    "current_sub_task_index": 0,
                    "sub_task_results": [],
                    "multi_step_completed": False,
                }
    
    # P2.1: 多步执行循环处理
    if state.get("multi_step_mode") and current_stage == "execution_done":
        return _handle_multi_step_execution(state)
    
    # 如果推荐完成或已完成，构造最终响应
    if current_stage in ["recommendation_done", "completed"]:
        return _aggregate_results(state)
    
    return {}


def _is_human_message(msg: Any) -> bool:
    """判断消息是否为用户消息"""
    if hasattr(msg, 'type'):
        return msg.type == "human"
    if isinstance(msg, dict):
        return msg.get("type") == "human"
    if hasattr(msg, '__class__'):
        return msg.__class__.__name__ == "HumanMessage"
    return False


def _handle_multi_step_execution(state: SQLMessageState) -> Dict[str, Any]:
    """
    P2.1: 处理多步执行循环
    
    每次子任务执行完成后:
    1. 保存当前子任务的结果
    2. 检查是否还有下一个子任务
    3. 如果有，准备下一个子任务并返回 schema_agent
    4. 如果没有，标记多步完成并进入聚合
    """
    query_plan = state.get("query_plan", {})
    sub_tasks = query_plan.get("sub_tasks", [])
    current_index = state.get("current_sub_task_index", 0)
    sub_task_results = state.get("sub_task_results", []).copy()
    
    # 保存当前子任务结果
    current_result = {
        "task_index": current_index,
        "task_id": sub_tasks[current_index]["id"] if current_index < len(sub_tasks) else f"task_{current_index}",
        "task_query": sub_tasks[current_index]["query"] if current_index < len(sub_tasks) else None,
        "sql": state.get("generated_sql"),
        "execution_result": _serialize_execution_result(state.get("execution_result")),
    }
    sub_task_results.append(current_result)
    
    next_index = current_index + 1
    
    # 检查是否有更多子任务（排除聚合任务）
    executable_tasks = [t for t in sub_tasks if t["id"] != "task_aggregate"]
    
    if next_index < len(executable_tasks):
        # 还有下一个子任务
        next_task = executable_tasks[next_index]
        logger.info(f"[Supervisor] 多步执行: 切换到子任务 {next_index + 1}/{len(executable_tasks)}: {next_task['query'][:50]}...")
        
        return {
            "current_sub_task_index": next_index,
            "sub_task_results": sub_task_results,
            # 重置单步执行状态
            "current_stage": "multi_step_next",  # 特殊阶段，路由到 schema_agent
            "generated_sql": None,
            "execution_result": None,
            "schema_info": None,
            # 替换查询为子任务查询
            "enriched_query": next_task["query"],
        }
    else:
        # 所有子任务完成
        logger.info(f"[Supervisor] 多步执行完成: 共 {len(sub_task_results)} 个子任务")
        
        return {
            "current_sub_task_index": next_index,
            "sub_task_results": sub_task_results,
            "multi_step_completed": True,
            "current_stage": "multi_step_done",  # 进入聚合阶段
        }


def _serialize_execution_result(result: Any) -> Optional[Dict[str, Any]]:
    """序列化执行结果为字典"""
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    if hasattr(result, '__dict__'):
        return {
            "success": getattr(result, 'success', True),
            "data": getattr(result, 'data', None),
            "error": getattr(result, 'error', None),
        }
    return {"data": result}


def _aggregate_results(state: SQLMessageState) -> Dict[str, Any]:
    """汇总所有执行结果"""
    execution_result = state.get("execution_result")
    data = None
    if execution_result:
        if hasattr(execution_result, 'data'):
            data = execution_result.data
        elif isinstance(execution_result, dict):
            data = execution_result.get("data")
    
    final_response = {
        "success": state.get("current_stage") not in ["error_recovery", "error"],
        "query": state.get("enriched_query") or state.get("original_query"),
        "sql": state.get("generated_sql"),
        "data": data,
        "analysis": state.get("analyst_insights"),
        "chart": state.get("chart_config"),
        "recommendations": state.get("recommended_questions", []),
        "source": _determine_source(state),
        "metadata": {
            "connection_id": state.get("connection_id"),
            "cache_hit_type": state.get("cache_hit_type"),
            "fast_mode": state.get("fast_mode", False),
            "retry_count": state.get("retry_count", 0)
        }
    }
    
    if not final_response["success"]:
        error_history = state.get("error_history", [])
        if error_history:
            final_response["error"] = error_history[-1].get("error", "Unknown error")
    
    logger.info("[Supervisor] 结果汇总完成")
    
    return {
        "final_response": final_response,
        "current_stage": "completed"
    }


def _determine_source(state: SQLMessageState) -> str:
    """确定结果来源"""
    if state.get("thread_history_hit"):
        return "thread_history_cache"
    if state.get("cache_hit"):
        return f"{state.get('cache_hit_type', 'exact')}_cache"
    return "generated"


# ============================================================================
# 路由函数
# ============================================================================

# 阶段路由映射表
STAGE_ROUTES = {
    "init": "query_planning",           # P2: 先进行查询规划
    "planning_done": "schema_agent",    # 规划完成后进入 schema 分析
    "schema_done": "clarification",
    "clarification_done": "sql_generator",
    "schema_analysis": "sql_generator",
    "sql_generated": "sql_executor",
    "execution_done": "data_analyst",
    "chart_done": "recommendation",
    # P2.1: 多步执行路由
    "multi_step_next": "schema_agent",  # 下一个子任务
    "multi_step_done": "result_aggregator",  # 所有子任务完成，进入聚合
}


def supervisor_route(state: SQLMessageState) -> str:
    """
    Supervisor 路由决策
    
    基于 current_stage 和状态标志决定下一个节点。
    P2 新增: 支持智能规划路由
    P2.1 新增: 支持多步执行路由
    """
    current_stage = state.get("current_stage", "init")
    route_decision = state.get("route_decision")
    logger.info(f"[Route] 当前阶段: {current_stage}, 路由决策: {route_decision}")
    
    # 完成状态检查
    if current_stage in ["completed", "recommendation_done"]:
        logger.info("[Route] 已完成 → FINISH")
        return "FINISH"
    
    # P2: 基于规划的路由决策
    if route_decision == "general_chat":
        logger.info("[Route] 规划决策 → general_chat")
        return "general_chat"
    
    # 闲聊检测 (仅在初始阶段，作为 fallback)
    if current_stage == "init" and not state.get("query_plan"):
        if _is_general_chat(state):
            logger.info("[Route] 检测到闲聊 → general_chat")
            return "general_chat"
    
    # 缓存命中检查
    if state.get("thread_history_hit") or state.get("cache_hit"):
        logger.info("[Route] 缓存命中 → FINISH")
        return "FINISH"
    
    # 错误恢复检查
    if current_stage == "error_recovery":
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        if retry_count >= max_retries:
            logger.info(f"[Route] 达到重试上限 ({retry_count}/{max_retries}) → FINISH")
            return "FINISH"
        logger.info(f"[Route] 错误恢复 ({retry_count}/{max_retries}) → sql_generator")
        return "sql_generator"
    
    # P2.1: 多步执行模式下，execution_done 由 supervisor 处理，不直接路由到 data_analyst
    # (这个逻辑在 supervisor_node 的 _handle_multi_step_execution 中处理)
    
    # 分析完成后的路由（检查是否跳过图表）
    if current_stage == "analysis_done":
        if state.get("skip_chart_generation"):
            return "recommendation"
        return "chart_generator"
    
    # 基于映射表路由
    next_agent = STAGE_ROUTES.get(current_stage, "FINISH")
    logger.info(f"[Route] {current_stage} → {next_agent}")
    return next_agent


def _is_general_chat(state: SQLMessageState) -> bool:
    """检测是否为闲聊"""
    messages = state.get("messages", [])
    if not messages:
        return False
    
    last_msg = messages[-1]
    if hasattr(last_msg, 'content'):
        content = last_msg.content
    elif isinstance(last_msg, dict):
        content = last_msg.get('content', '')
    else:
        content = str(last_msg)
    
    if isinstance(content, list):
        content = ' '.join(str(c) for c in content)
    content = str(content) if content else ''
    
    chat_keywords = ["你好", "谢谢", "帮助", "你是谁", "hello", "hi", "thanks"]
    return any(kw in content.lower() for kw in chat_keywords)


# ============================================================================
# 图构建
# ============================================================================

def create_hub_spoke_graph() -> CompiledStateGraph:
    """
    创建 Hub-and-Spoke 架构的图
    
    P2 新增: 查询规划节点 (query_planning)
    
    注意: 不传入 checkpointer，由 LangGraph API 框架在运行时自动管理。
    """
    from app.agents.nodes.question_recommendation_node import question_recommendation_node
    
    logger.info("创建 Hub-and-Spoke 图 (P2: 含智能规划)...")
    
    graph = StateGraph(SQLMessageState)
    
    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("query_planning", query_planning_node)  # P2: 查询规划节点
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("error_recovery", error_recovery_node)
    graph.add_node("general_chat", general_chat_node)
    graph.add_node("clarification", clarification_node_wrapper)
    graph.add_node("recommendation", question_recommendation_node)
    graph.add_node("result_aggregator", result_aggregator_node)  # P2.1: 结果聚合节点
    
    # 入口点
    graph.set_entry_point("supervisor")
    
    # Hub-and-Spoke: 所有 Worker 返回 Supervisor
    worker_nodes = [
        "query_planning",  # P2: 规划节点也返回 supervisor
        "schema_agent", "sql_generator", "sql_executor",
        "data_analyst", "chart_generator", "error_recovery",
        "general_chat", "clarification", "recommendation",
        "result_aggregator",  # P2.1: 结果聚合节点
    ]
    for node in worker_nodes:
        graph.add_edge(node, "supervisor")
    
    # Supervisor 条件路由
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "query_planning": "query_planning",  # P2: 查询规划
            "schema_agent": "schema_agent",
            "sql_generator": "sql_generator",
            "sql_executor": "sql_executor",
            "data_analyst": "data_analyst",
            "chart_generator": "chart_generator",
            "error_recovery": "error_recovery",
            "general_chat": "general_chat",
            "clarification": "clarification",
            "recommendation": "recommendation",
            "result_aggregator": "result_aggregator",  # P2.1: 结果聚合
            "FINISH": END
        }
    )
    
    compiled = graph.compile()
    logger.info("Hub-and-Spoke 图创建完成 (P2: 含智能规划)")
    return compiled


# ============================================================================
# 主图类
# ============================================================================

class IntelligentSQLGraph:
    """
    智能 SQL 代理图 - Hub-and-Spoke 架构
    
    保持与原有架构的 API 兼容。
    """
    
    def __init__(
        self, 
        active_agent_profiles: List[AgentProfile] = None, 
        custom_analyst=None
    ):
        self.graph = create_hub_spoke_graph()
        self._initialized = True
    
    async def _ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            self.graph = create_hub_spoke_graph()
            self._initialized = True
    
    async def process_query(
        self,
        query: str,
        connection_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        处理 SQL 查询
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID
            thread_id: 会话线程ID
            tenant_id: 租户ID (多租户隔离)
        """
        try:
            from uuid import uuid4
            
            await self._ensure_initialized()
            
            if thread_id is None:
                thread_id = str(uuid4())
                logger.info(f"生成新的 thread_id: {thread_id}")
            
            initial_state = {
                "messages": [HumanMessage(content=query)],
                "connection_id": connection_id,
                "thread_id": thread_id,
                "tenant_id": tenant_id,
                "current_stage": "init",
                "retry_count": 0,
                "max_retries": 3,
                "error_history": [],
                "context": {
                    "connectionId": connection_id,
                    "tenantId": tenant_id
                }
            }
            
            config = {"configurable": {"thread_id": thread_id}}
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
        from app.agents.agents.schema_agent import schema_agent
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        from app.agents.agents.data_analyst_agent import data_analyst_agent
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        
        return [
            schema_agent,
            sql_generator_agent,
            sql_executor_agent,
            data_analyst_agent,
            chart_generator_agent
        ]


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


# 全局实例管理
_global_graph: Optional[IntelligentSQLGraph] = None


def get_global_graph() -> IntelligentSQLGraph:
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


async def get_global_graph_async() -> IntelligentSQLGraph:
    """异步获取全局图实例"""
    graph = get_global_graph()
    await graph._ensure_initialized()
    return graph


def graph():
    """
    图工厂函数 - 供 LangGraph API 使用
    
    返回编译好的图实例
    """
    return create_hub_spoke_graph()
