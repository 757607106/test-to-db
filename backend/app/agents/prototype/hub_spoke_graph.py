"""
Hub-and-Spoke 图结构实现

遵循 LangGraph 官方 Supervisor 模式:
- Supervisor 是唯一入口和中心
- 所有 Worker Agent 执行完都返回 Supervisor  
- Supervisor 统一路由和汇总

图结构:
                    ┌────────────────────────────┐
                    │        SUPERVISOR          │
                    │     (中心枢纽节点)          │
                    └────────────┬───────────────┘
                                 │
         ┌───────────┬───────────┼───────────┬───────────┐
         │           │           │           │           │
         ▼           ▼           ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ schema  │ │ sql_gen │ │executor │ │ analyst │ │  chart  │
    │  agent  │ │  agent  │ │  agent  │ │  agent  │ │  agent  │
    └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
         │           │           │           │           │
         └───────────┴───────────┴───────────┴───────────┘
                                 │
                                 ▼
                         (返回 Supervisor)
"""

from typing import Dict, Any, Literal
import logging
import time

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState
from .true_supervisor import get_supervisor, TrueSupervisor

logger = logging.getLogger(__name__)


# ============================================================================
# Worker Agent 节点包装器
# ============================================================================

async def schema_agent_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema Agent 节点
    
    执行完成后更新 current_stage，供 Supervisor 决策
    """
    logger.info("[Worker] schema_agent 开始执行")
    start_time = time.time()
    
    try:
        from app.agents.agents.schema_agent import schema_agent
        result = await schema_agent.process(state)
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] schema_agent 完成, 耗时 {elapsed:.2f}s")
        
        # 更新阶段供 Supervisor 决策
        result["current_stage"] = "schema_done"
        result["agent_response"] = f"已获取数据库结构信息"
        
        return result
        
    except Exception as e:
        logger.error(f"[Worker] schema_agent 失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "schema_analysis",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_generator_node(state: SQLMessageState) -> Dict[str, Any]:
    """SQL Generator 节点"""
    logger.info("[Worker] sql_generator 开始执行")
    start_time = time.time()
    
    try:
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        result = await sql_generator_agent.process(state)
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] sql_generator 完成, 耗时 {elapsed:.2f}s")
        
        result["current_stage"] = "sql_generated"
        result["agent_response"] = f"已生成 SQL: {result.get('generated_sql', '')[:50]}..."
        
        return result
        
    except Exception as e:
        logger.error(f"[Worker] sql_generator 失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_generation",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_executor_node(state: SQLMessageState) -> Dict[str, Any]:
    """SQL Executor 节点"""
    logger.info("[Worker] sql_executor 开始执行")
    start_time = time.time()
    
    try:
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        result = await sql_executor_agent.process(state)
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] sql_executor 完成, 耗时 {elapsed:.2f}s")
        
        # 检查执行结果
        exec_result = result.get("execution_result")
        if exec_result:
            success = getattr(exec_result, 'success', True) if hasattr(exec_result, 'success') else exec_result.get('success', True)
            if not success:
                # 执行失败，增加重试计数
                retry_count = state.get("retry_count", 0) + 1
                result["current_stage"] = "error_recovery"
                result["retry_count"] = retry_count
                error_msg = getattr(exec_result, 'error', '') if hasattr(exec_result, 'error') else exec_result.get('error', '')
                result["error_history"] = state.get("error_history", []) + [{
                    "stage": "sql_execution",
                    "error": error_msg,
                    "timestamp": time.time()
                }]
                logger.info(f"[Worker] sql_executor 执行失败, retry_count={retry_count}")
                return result
        
        result["current_stage"] = "execution_done"
        result["agent_response"] = "SQL 执行成功"
        
        return result
        
    except Exception as e:
        logger.error(f"[Worker] sql_executor 失败: {e}")
        retry_count = state.get("retry_count", 0) + 1
        return {
            "current_stage": "error_recovery",
            "retry_count": retry_count,
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_execution",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def data_analyst_node(state: SQLMessageState) -> Dict[str, Any]:
    """Data Analyst 节点"""
    logger.info("[Worker] data_analyst 开始执行")
    start_time = time.time()
    
    try:
        # 检查是否有自定义 agent
        agent_id = state.get("agent_id")
        if agent_id:
            from app.agents.agents.supervisor_subgraph import _load_custom_agent_by_id
            custom_agent = _load_custom_agent_by_id(agent_id, "data_analyst")
            if custom_agent:
                result = await custom_agent.process(state)
            else:
                from app.agents.agents.data_analyst_agent import data_analyst_agent
                result = await data_analyst_agent.process(state)
        else:
            from app.agents.agents.data_analyst_agent import data_analyst_agent
            result = await data_analyst_agent.process(state)
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] data_analyst 完成, 耗时 {elapsed:.2f}s")
        
        result["current_stage"] = "analysis_done"
        result["agent_response"] = "数据分析完成"
        
        return result
        
    except Exception as e:
        logger.error(f"[Worker] data_analyst 失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "analysis",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def chart_generator_node(state: SQLMessageState) -> Dict[str, Any]:
    """Chart Generator 节点"""
    logger.info("[Worker] chart_generator 开始执行")
    start_time = time.time()
    
    try:
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        result = await chart_generator_agent.process(state)
        
        elapsed = time.time() - start_time
        logger.info(f"[Worker] chart_generator 完成, 耗时 {elapsed:.2f}s")
        
        result["current_stage"] = "chart_done"
        result["agent_response"] = "图表生成完成"
        
        return result
        
    except Exception as e:
        logger.error(f"[Worker] chart_generator 失败: {e}")
        # 图表生成失败不阻塞流程
        return {
            "current_stage": "chart_done",
            "chart_config": None
        }


async def error_recovery_node(state: SQLMessageState) -> Dict[str, Any]:
    """Error Recovery 节点"""
    logger.info("[Worker] error_recovery 开始执行")
    
    try:
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        result = await error_recovery_agent.process(state)
        
        logger.info("[Worker] error_recovery 完成")
        return result
        
    except Exception as e:
        logger.error(f"[Worker] error_recovery 失败: {e}")
        return {
            "current_stage": "completed",
            "messages": [AIMessage(content=f"抱歉，处理过程中遇到错误: {str(e)}")]
        }


async def general_chat_node(state: SQLMessageState) -> Dict[str, Any]:
    """General Chat 节点 (闲聊)"""
    logger.info("[Worker] general_chat 开始执行")
    
    from app.core.llms import get_default_model
    
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break
    
    llm = get_default_model()
    response = await llm.ainvoke([
        {"role": "system", "content": "你是一个友好的数据分析助手。请用简洁的中文回答用户的问题。"},
        {"role": "user", "content": user_query}
    ])
    
    return {
        "messages": [AIMessage(content=response.content)],
        "current_stage": "completed",
        "route_decision": "general_chat"
    }


# ============================================================================
# Supervisor 节点
# ============================================================================

async def supervisor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 中心节点
    
    在 Hub-and-Spoke 架构中:
    - 这是入口节点
    - 每个 Worker 执行完都会回到这里
    - 负责决策和汇总
    """
    supervisor = get_supervisor()
    return await supervisor.supervisor_node(state)


# ============================================================================
# 路由函数
# ============================================================================

def supervisor_route(state: SQLMessageState) -> str:
    """
    Supervisor 路由函数 (同步版本)
    
    决定下一步调用哪个 Agent
    
    注意: LangGraph 条件边需要同步函数，所以路由逻辑直接实现在这里
    """
    supervisor = get_supervisor()
    
    current_stage = state.get("current_stage", "init")
    logger.info(f"[Route] 当前阶段: {current_stage}")
    
    # 0. 优先检查完成状态 (防止无限循环)
    if current_stage in ["completed", "chart_done"]:
        logger.info("[Route] 已完成 → FINISH")
        return "FINISH"
    
    # 1. 检查是否闲聊 (仅在初始阶段)
    if current_stage == "init":
        route_decision = state.get("route_decision")
        if route_decision == "general_chat":
            logger.info("[Route] → general_chat")
            return "general_chat"
        
        # 简单关键词检测闲聊
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            chat_keywords = ["你好", "谢谢", "帮助", "你是谁", "hello", "hi", "thanks"]
            if any(kw in content.lower() for kw in chat_keywords):
                logger.info("[Route] 检测到闲聊 → general_chat")
                return "general_chat"
    
    # 2. 检查缓存命中
    if state.get("thread_history_hit") or state.get("cache_hit"):
        logger.info("[Route] 缓存命中 → FINISH")
        return "FINISH"
    
    # 3. 错误恢复
    if current_stage == "error_recovery":
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        if retry_count >= max_retries:
            logger.info("[Route] 达到重试上限 → FINISH")
            return "FINISH"
        logger.info("[Route] 错误恢复 → sql_generator")
        return "sql_generator"
    
    # 4. 基于阶段路由
    stage_routes = {
        "init": "schema_agent",
        "schema_done": "sql_generator",
        "sql_generated": "sql_executor",
        "execution_done": "data_analyst",
        "analysis_done": "chart_generator" if not state.get("skip_chart_generation") else "FINISH",
        
        # 兼容现有阶段名称
        "schema_analysis": "schema_agent",
        "sql_generation": "sql_generator",
        "sql_execution": "sql_executor",
        "analysis": "data_analyst",
        "chart_generation": "chart_generator",
    }
    
    next_agent = stage_routes.get(current_stage, "FINISH")
    logger.info(f"[Route] {current_stage} → {next_agent}")
    return next_agent


# ============================================================================
# 图构建
# ============================================================================

def create_hub_spoke_graph(checkpointer=None) -> CompiledStateGraph:
    """
    创建 Hub-and-Spoke 架构的图
    
    核心特点:
    - Supervisor 是唯一入口
    - 所有 Worker 执行完返回 Supervisor
    - Supervisor 决定下一步或结束
    
    Args:
        checkpointer: 可选的 checkpointer (用于 interrupt 支持)
        
    Returns:
        编译后的 LangGraph 图
    """
    logger.info("创建 Hub-and-Spoke 图...")
    
    graph = StateGraph(SQLMessageState)
    
    # ========== 添加节点 ==========
    # 中心节点
    graph.add_node("supervisor", supervisor_node)
    
    # Worker 节点
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("error_recovery", error_recovery_node)
    graph.add_node("general_chat", general_chat_node)
    
    # ========== 设置入口 ==========
    # Supervisor 是唯一入口
    graph.set_entry_point("supervisor")
    
    # ========== 所有 Worker 返回 Supervisor ==========
    # 这是 Hub-and-Spoke 的核心: 辐射回中心
    graph.add_edge("schema_agent", "supervisor")
    graph.add_edge("sql_generator", "supervisor")
    graph.add_edge("sql_executor", "supervisor")
    graph.add_edge("data_analyst", "supervisor")
    graph.add_edge("chart_generator", "supervisor")
    graph.add_edge("error_recovery", "supervisor")
    graph.add_edge("general_chat", "supervisor")
    
    # ========== Supervisor 条件路由 ==========
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "schema_agent": "schema_agent",
            "sql_generator": "sql_generator",
            "sql_executor": "sql_executor",
            "data_analyst": "data_analyst",
            "chart_generator": "chart_generator",
            "error_recovery": "error_recovery",
            "general_chat": "general_chat",
            "FINISH": END
        }
    )
    
    # ========== 编译 ==========
    if checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        # 使用内存 checkpointer (支持 interrupt)
        compiled = graph.compile(checkpointer=InMemorySaver())
    
    logger.info("✓ Hub-and-Spoke 图创建完成")
    return compiled


# ============================================================================
# 高级接口类
# ============================================================================

class HubSpokeGraph:
    """
    Hub-and-Spoke 图的高级接口
    
    提供与 IntelligentSQLGraph 兼容的接口
    """
    
    def __init__(self, checkpointer=None):
        self.graph = create_hub_spoke_graph(checkpointer)
        self._initialized = True
    
    async def process_query(
        self,
        query: str,
        connection_id: int,
        thread_id: str = None
    ) -> Dict[str, Any]:
        """
        处理用户查询
        
        Args:
            query: 用户查询
            connection_id: 数据库连接 ID
            thread_id: 会话线程 ID
            
        Returns:
            处理结果字典
        """
        from langchain_core.messages import HumanMessage
        from uuid import uuid4
        
        thread_id = thread_id or str(uuid4())
        
        # 构建初始状态
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "connection_id": connection_id,
            "current_stage": "init",
            "retry_count": 0,
            "max_retries": 3,
            "error_history": [],
            "context": {"connectionId": connection_id}
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            # 执行图
            result = await self.graph.ainvoke(initial_state, config=config)
            
            return {
                "success": True,
                "result": result,
                "final_response": result.get("final_response"),
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error(f"查询处理失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "thread_id": thread_id
            }


# ============================================================================
# 全局实例
# ============================================================================

_hub_spoke_graph: HubSpokeGraph = None


def get_hub_spoke_graph() -> HubSpokeGraph:
    """获取 Hub-and-Spoke 图单例"""
    global _hub_spoke_graph
    if _hub_spoke_graph is None:
        _hub_spoke_graph = HubSpokeGraph()
    return _hub_spoke_graph
