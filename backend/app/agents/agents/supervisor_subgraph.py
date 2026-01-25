"""
Supervisor 子图 - 使用 LangGraph 原生模式

遵循 LangGraph 官方最佳实践:
1. 使用 StateGraph 定义子图
2. 使用 conditional_edges 实现路由
3. 基于状态字段路由，无需 LLM 决策
4. 简洁的错误恢复机制

架构:
    START → schema_agent → schema_clarification → sql_generator → sql_executor
          → [error_handler → sql_generator] (失败时重试)
          → data_analyst → chart_generator → END

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/subgraph/
- https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
"""
from typing import Dict, Any, Literal
import logging
import time

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState

logger = logging.getLogger(__name__)


def _load_custom_agent_by_id(agent_id: int, agent_type: str = "data_analyst"):
    """
    根据 agent_id 动态加载自定义 Agent
    
    这个函数在每次需要时动态创建 Agent，避免将不可序列化的对象存储到 State
    
    Args:
        agent_id: AgentProfile 的 ID
        agent_type: Agent 类型（目前支持 data_analyst）
        
    Returns:
        Agent 实例，如果加载失败则返回 None
    """
    if agent_type != "data_analyst":
        return None
    
    try:
        from app.db.session import get_db_session
        from app.crud import agent_profile as crud_agent_profile
        from app.agents.agent_factory import create_custom_analyst_agent
        
        with get_db_session() as db:
            # 查询 AgentProfile
            profile = crud_agent_profile.get(db, id=agent_id)
            
            if not profile:
                logger.warning(f"未找到 agent_id={agent_id} 对应的 AgentProfile")
                return None
            
            if not profile.is_active:
                logger.warning(f"AgentProfile {profile.name} 未激活")
                return None
            
            logger.info(f"动态加载 AgentProfile: {profile.name} (id={profile.id})")
            
            # 创建自定义 agent
            return create_custom_analyst_agent(profile, db)
            
    except Exception as e:
        logger.error(f"动态加载自定义 agent 失败: {e}", exc_info=True)
        return None


# ============================================================================
# 节点函数
# ============================================================================

async def schema_agent_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema Agent 节点 - 获取数据库模式信息
    
    支持自定义 Agent：通过 state["custom_agents"]["schema_agent"] 传入
    """
    # 优先使用自定义 agent
    custom_agents = state.get("custom_agents") or {}
    agent = custom_agents.get("schema_agent")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.schema_agent import schema_agent
        agent = schema_agent
    else:
        logger.info("使用自定义 schema_agent")
    
    logger.info("=== 执行 schema_agent ===")
    start_time = time.time()
    
    try:
        result = await agent.process(state)
        elapsed = time.time() - start_time
        logger.info(f"schema_agent 完成，耗时 {elapsed:.2f}s")
        return result
    except Exception as e:
        logger.error(f"schema_agent 执行失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "schema_analysis",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def schema_clarification_node_wrapper(state: SQLMessageState) -> Dict[str, Any]:
    """
    Schema 澄清节点包装器 - 澄清点C
    
    在 schema_agent 后执行，检测字段、关系、指标等歧义
    """
    from app.agents.nodes.schema_clarification_node import schema_clarification_node
    
    logger.info("=== 执行 schema_clarification (澄清点C) ===")
    start_time = time.time()
    
    try:
        result = await schema_clarification_node(state)
        elapsed = time.time() - start_time
        logger.info(f"schema_clarification 完成，耗时 {elapsed:.2f}s")
        return result
    except Exception as e:
        logger.error(f"schema_clarification 执行失败: {e}")
        # 澄清失败不影响主流程，继续到 SQL 生成
        return {"current_stage": "sql_generation"}


async def sql_generator_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    SQL Generator 节点 - 生成 SQL 查询
    
    读取的上下文:
    - schema_info: 表结构信息
    - enriched_query / original_query: 用户查询
    - cached_sql_template: 缓存的 SQL 模板
    - error_recovery_context: 错误恢复上下文（如果是重试）
    
    支持自定义 Agent：通过 state["custom_agents"]["sql_generator"] 传入
    """
    # 优先使用自定义 agent
    custom_agents = state.get("custom_agents") or {}
    agent = custom_agents.get("sql_generator")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        agent = sql_generator_agent
    else:
        logger.info("使用自定义 sql_generator")
    
    logger.info("=== 执行 sql_generator_agent ===")
    
    # 检查是否是重试
    error_recovery_context = state.get("error_recovery_context")
    retry_count = state.get("retry_count", 0)
    if error_recovery_context:
        logger.info(f"检测到错误恢复上下文，这是第 {retry_count} 次重试")
    
    start_time = time.time()
    
    try:
        result = await agent.process(state)
        elapsed = time.time() - start_time
        logger.info(f"sql_generator_agent 完成，耗时 {elapsed:.2f}s")
        
        # 成功生成后清除错误恢复上下文
        if result.get("current_stage") == "sql_execution":
            result["error_recovery_context"] = None
        
        return result
    except Exception as e:
        logger.error(f"sql_generator_agent 执行失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_generation",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_executor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    SQL Executor 节点 - 执行 SQL 查询
    
    支持自定义 Agent：通过 state["custom_agents"]["sql_executor"] 传入
    """
    # 优先使用自定义 agent
    custom_agents = state.get("custom_agents") or {}
    agent = custom_agents.get("sql_executor")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        agent = sql_executor_agent
    else:
        logger.info("使用自定义 sql_executor")
    
    logger.info("=== 执行 sql_executor_agent ===")
    start_time = time.time()
    
    try:
        result = await agent.process(state)
        elapsed = time.time() - start_time
        logger.info(f"sql_executor_agent 完成，耗时 {elapsed:.2f}s")
        return result
    except Exception as e:
        logger.error(f"sql_executor_agent 执行失败: {e}")
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_execution",
                "error": str(e),
                "sql_query": state.get("generated_sql"),
                "timestamp": time.time()
            }]
        }


async def data_analyst_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Data Analyst 节点 - 分析查询结果
    
    读取的上下文:
    - execution_result: SQL 执行结果
    
    支持自定义 Agent：通过 state["agent_id"] 动态加载
    这是最常需要自定义的 agent，可以根据不同业务场景定制数据分析逻辑
    """
    agent = None
    
    # 根据 agent_id 动态加载自定义 agent（避免将不可序列化的对象存储到 state）
    agent_id = state.get("agent_id")
    if agent_id:
        agent = _load_custom_agent_by_id(agent_id, "data_analyst")
        if agent:
            logger.info(f"使用自定义 data_analyst (agent_id={agent_id})")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.data_analyst_agent import data_analyst_agent
        agent = data_analyst_agent
    
    logger.info("=== 执行 data_analyst_agent ===")
    
    # 检查是否有执行结果
    execution_result = state.get("execution_result")
    if not execution_result:
        logger.warning("没有执行结果，跳过数据分析")
        return {"current_stage": "chart_generation"}
    
    # 检查执行是否成功
    if hasattr(execution_result, 'success') and not execution_result.success:
        logger.warning("执行结果不成功，跳过数据分析")
        return {"current_stage": "chart_generation"}
    
    start_time = time.time()
    
    try:
        result = await agent.process(state)
        elapsed = time.time() - start_time
        logger.info(f"data_analyst_agent 完成，耗时 {elapsed:.2f}s")
        return result
    except Exception as e:
        logger.error(f"data_analyst_agent 执行失败: {e}")
        # 分析失败不影响整体流程，继续到图表生成
        return {"current_stage": "chart_generation"}


async def chart_generator_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Chart Generator 节点 - 生成图表配置
    
    读取的上下文:
    - execution_result: SQL 执行结果
    - skip_chart_generation: 是否跳过图表生成
    
    支持自定义 Agent：通过 state["custom_agents"]["chart_generator"] 传入
    """
    # 检查是否跳过图表生成
    if state.get("skip_chart_generation", False):
        logger.info("快速模式: 跳过图表生成")
        return {"current_stage": "completed"}
    
    # 优先使用自定义 agent
    custom_agents = state.get("custom_agents") or {}
    agent = custom_agents.get("chart_generator")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        agent = chart_generator_agent
    else:
        logger.info("使用自定义 chart_generator")
    
    logger.info("=== 执行 chart_generator_agent ===")
    start_time = time.time()
    
    try:
        result = await agent.process(state)
        elapsed = time.time() - start_time
        logger.info(f"chart_generator_agent 完成，耗时 {elapsed:.2f}s")
        
        # 确保设置完成状态
        result["current_stage"] = "completed"
        return result
    except Exception as e:
        logger.error(f"chart_generator_agent 执行失败: {e}")
        # 图表生成失败不影响整体结果
        return {"current_stage": "completed"}


async def error_handler_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    错误处理节点 - 使用智能 ErrorRecoveryAgent 分析错误并准备重试
    
    功能:
    - 调用 error_recovery_agent 进行智能错误分析
    - 生成用户友好的错误消息
    - 设置 error_recovery_context 供 sql_generator 使用
    
    支持自定义 Agent：通过 state["custom_agents"]["error_recovery"] 传入
    """
    # 优先使用自定义 agent
    custom_agents = state.get("custom_agents") or {}
    agent = custom_agents.get("error_recovery")
    
    if agent is None:
        # 回退到默认 agent
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        agent = error_recovery_agent
    else:
        logger.info("使用自定义 error_recovery")
    
    logger.info("=== 执行 error_handler (使用 ErrorRecoveryAgent) ===")
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    logger.info(f"当前重试次数: {retry_count}/{max_retries}")
    
    try:
        # 使用智能 ErrorRecoveryAgent 进行错误分析和恢复策略生成
        result = await agent.process(state)
        
        elapsed = time.time()
        logger.info(f"error_recovery_agent 完成")
        
        return result
    except Exception as e:
        logger.error(f"ErrorRecoveryAgent 执行失败: {e}")
        
        # 回退到简单逻辑 - 使用 error_recovery_agent 的分类函数
        from app.agents.agents.error_recovery_agent import _classify_error_type
        
        error_history = state.get("error_history", [])
        last_error = error_history[-1] if error_history else {}
        error_msg = last_error.get("error", "未知错误")
        failed_sql = state.get("generated_sql", "")
        
        if retry_count >= max_retries:
            return {
                "current_stage": "completed",
                "messages": [AIMessage(content=f"抱歉，多次尝试后仍无法生成正确的查询。")],
            }
        
        # 简单重试
        error_type = _classify_error_type(error_msg.lower())
        return {
            "retry_count": retry_count + 1,
            "current_stage": "sql_generation",
            "error_recovery_context": {
                "error_type": error_type,
                "error_message": error_msg,
                "failed_sql": failed_sql,
                "recovery_steps": ["简化查询逻辑", "检查数据库状态"],
                "retry_count": retry_count + 1
            },
            "generated_sql": None,
            "messages": [AIMessage(content=f"正在重新生成查询 (尝试 {retry_count + 1}/{max_retries})...")],
        }


# ============================================================================
# 路由函数
# ============================================================================

def route_after_schema(state: SQLMessageState) -> Literal["schema_clarification", "error_handler"]:
    """
    Schema 分析后的路由
    """
    current_stage = state.get("current_stage", "")
    
    if current_stage == "error_recovery":
        logger.info("[路由] schema_agent → error_handler (错误)")
        return "error_handler"
    
    logger.info("[路由] schema_agent → schema_clarification (澄清点C)")
    return "schema_clarification"


def route_after_schema_clarification(state: SQLMessageState) -> Literal["sql_generator", "error_handler"]:
    """
    Schema 澄清后的路由
    """
    current_stage = state.get("current_stage", "")
    
    if current_stage == "error_recovery":
        logger.info("[路由] schema_clarification → error_handler (错误)")
        return "error_handler"
    
    logger.info("[路由] schema_clarification → sql_generator (成功)")
    return "sql_generator"


def route_after_sql_gen(state: SQLMessageState) -> Literal["sql_executor", "error_handler"]:
    """
    SQL 生成后的路由
    """
    current_stage = state.get("current_stage", "")
    
    if current_stage == "error_recovery":
        logger.info("[路由] sql_generator → error_handler (错误)")
        return "error_handler"
    
    logger.info("[路由] sql_generator → sql_executor (成功)")
    return "sql_executor"


def route_after_execution(state: SQLMessageState) -> Literal["data_analyst", "error_handler", "finish"]:
    """
    SQL 执行后的路由
    """
    current_stage = state.get("current_stage", "")
    execution_result = state.get("execution_result")
    
    # 检查是否进入错误恢复
    if current_stage == "error_recovery":
        logger.info("[路由] sql_executor → error_handler (错误)")
        return "error_handler"
    
    # 检查执行结果
    if execution_result:
        if hasattr(execution_result, 'success') and not execution_result.success:
            logger.info("[路由] sql_executor → error_handler (执行失败)")
            return "error_handler"
    
    # 检查是否跳过分析（快速模式且已完成）
    if current_stage == "completed":
        logger.info("[路由] sql_executor → finish (已完成)")
        return "finish"
    
    logger.info("[路由] sql_executor → data_analyst (成功)")
    return "data_analyst"


def route_after_analysis(state: SQLMessageState) -> Literal["chart_generator", "finish"]:
    """
    数据分析后的路由
    """
    # 检查是否跳过图表生成
    if state.get("skip_chart_generation", False):
        logger.info("[路由] data_analyst → finish (跳过图表)")
        return "finish"
    
    current_stage = state.get("current_stage", "")
    if current_stage == "completed":
        logger.info("[路由] data_analyst → finish (已完成)")
        return "finish"
    
    logger.info("[路由] data_analyst → chart_generator")
    return "chart_generator"


def route_after_error(state: SQLMessageState) -> Literal["sql_generator", "finish"]:
    """
    错误处理后的路由
    """
    current_stage = state.get("current_stage", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    # 如果已达到重试上限或标记为完成
    if current_stage == "completed" or retry_count >= max_retries:
        logger.info(f"[路由] error_handler → finish (retry={retry_count}/{max_retries})")
        return "finish"
    
    logger.info(f"[路由] error_handler → sql_generator (重试 {retry_count}/{max_retries})")
    return "sql_generator"


# ============================================================================
# 子图创建
# ============================================================================

def create_supervisor_subgraph() -> CompiledStateGraph:
    """
    创建 Supervisor 子图
    
    图结构:
        START → schema_agent → schema_clarification → sql_generator → sql_executor
              → data_analyst → chart_generator → END
              
        错误处理:
        任意节点失败 → error_handler → sql_generator (重试)
                                     → END (达到上限)
    
    Returns:
        编译后的 LangGraph 子图
    """
    logger.info("创建 Supervisor 子图...")
    
    graph = StateGraph(SQLMessageState)
    
    # ============== 添加节点 ==============
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("schema_clarification", schema_clarification_node_wrapper)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("error_handler", error_handler_node)
    
    # ============== 设置入口 ==============
    graph.set_entry_point("schema_agent")
    
    # ============== 定义条件边 ==============
    # schema_agent → schema_clarification (澄清点C)
    graph.add_conditional_edges(
        "schema_agent",
        route_after_schema,
        {
            "schema_clarification": "schema_clarification",
            "error_handler": "error_handler"
        }
    )
    
    # schema_clarification → sql_generator
    graph.add_conditional_edges(
        "schema_clarification",
        route_after_schema_clarification,
        {
            "sql_generator": "sql_generator",
            "error_handler": "error_handler"
        }
    )
    
    graph.add_conditional_edges(
        "sql_generator",
        route_after_sql_gen,
        {
            "sql_executor": "sql_executor",
            "error_handler": "error_handler"
        }
    )
    
    graph.add_conditional_edges(
        "sql_executor",
        route_after_execution,
        {
            "data_analyst": "data_analyst",
            "error_handler": "error_handler",
            "finish": END
        }
    )
    
    graph.add_conditional_edges(
        "data_analyst",
        route_after_analysis,
        {
            "chart_generator": "chart_generator",
            "finish": END
        }
    )
    
    graph.add_conditional_edges(
        "error_handler",
        route_after_error,
        {
            "sql_generator": "sql_generator",
            "finish": END
        }
    )
    
    # chart_generator 直接到结束
    graph.add_edge("chart_generator", END)
    
    # ============== 编译 ==============
    compiled = graph.compile()
    logger.info("✓ Supervisor 子图创建完成")
    
    return compiled


# ============================================================================
# 全局子图实例（懒加载）
# ============================================================================

_supervisor_subgraph: CompiledStateGraph = None


def get_supervisor_subgraph() -> CompiledStateGraph:
    """
    获取 Supervisor 子图实例（单例模式）
    """
    global _supervisor_subgraph
    if _supervisor_subgraph is None:
        _supervisor_subgraph = create_supervisor_subgraph()
    return _supervisor_subgraph


# ============================================================================
# 节点包装函数（用于主图调用子图）
# ============================================================================

async def supervisor_subgraph_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 子图节点 - 用于在主图中调用
    
    这个函数将子图作为一个节点嵌入到主图中。
    子图与主图共享 SQLMessageState。
    """
    logger.info("=== 进入 Supervisor 子图 ===")
    
    subgraph = get_supervisor_subgraph()
    
    try:
        # 调用子图
        result = await subgraph.ainvoke(state)
        
        logger.info(f"=== Supervisor 子图完成，阶段: {result.get('current_stage', 'unknown')} ===")
        
        return result
    except Exception as e:
        logger.error(f"Supervisor 子图执行失败: {e}")
        return {
            "current_stage": "completed",
            "messages": [AIMessage(content=f"处理过程中遇到错误: {str(e)[:200]}")],
            "error_history": state.get("error_history", []) + [{
                "stage": "supervisor_subgraph",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "create_supervisor_subgraph",
    "get_supervisor_subgraph",
    "supervisor_subgraph_node",
]
