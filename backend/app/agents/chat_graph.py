"""
智能 SQL 代理图 - Hub-and-Spoke 架构版本

遵循 LangGraph 官方 Supervisor 模式:
1. Supervisor 作为中心枢纽
2. 所有 Worker Agent 向 Supervisor 报告
3. Supervisor 统一决策和汇总

架构说明:
- 使用 LangGraph 的 StateGraph 管理整体流程
- Supervisor 是唯一入口和决策中心
- Worker Agents: schema_agent, sql_generator, sql_executor, data_analyst, chart_generator
- 支持澄清机制 (interrupt)
- 支持三级缓存

图结构:
    START → supervisor → [Worker Agents] → supervisor → ... → FINISH
    
重构历史:
- 2026-01-24: 从 Pipeline 架构重构为 Hub-and-Spoke 架构
"""
from typing import Dict, Any, List, Optional, Literal
import logging
import time

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, StreamWriter
from langchain_core.messages import AIMessage, HumanMessage

from app.core.state import SQLMessageState
from app.models.agent_profile import AgentProfile

logger = logging.getLogger(__name__)

# 全局默认 checkpointer
_default_checkpointer = None


def _get_default_checkpointer():
    """获取默认的内存 checkpointer"""
    global _default_checkpointer
    if _default_checkpointer is None:
        _default_checkpointer = InMemorySaver()
        logger.info("✓ 初始化默认内存 Checkpointer")
    return _default_checkpointer


# ============================================================================
# Worker Agent 节点
# ============================================================================

async def schema_agent_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """Schema Agent 节点"""
    logger.info("[Worker] schema_agent 开始执行")
    start_time = time.time()
    
    # 发送开始事件
    writer({
        "type": "sql_step",
        "step": "schema_agent",
        "status": "running",
        "result": "正在分析数据库结构...",
        "time_ms": 0
    })
    
    try:
        from app.agents.agents.schema_agent import schema_agent
        result = await schema_agent.process(state)
        
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"[Worker] schema_agent 完成, 耗时 {elapsed:.2f}s")
        
        # 发送完成事件
        writer({
            "type": "sql_step",
            "step": "schema_agent",
            "status": "completed",
            "result": f"分析完成，识别到 {len(result.get('schema_info', {}).get('tables', []))} 个相关表",
            "time_ms": elapsed_ms
        })
        
        result["current_stage"] = "schema_done"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] schema_agent 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "schema_agent",
            "status": "error",
            "result": str(e),
            "time_ms": elapsed_ms
        })
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "schema_analysis",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_generator_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """SQL Generator 节点"""
    logger.info("[Worker] sql_generator 开始执行")
    start_time = time.time()
    
    # 发送开始事件
    writer({
        "type": "sql_step",
        "step": "sql_generator",
        "status": "running",
        "result": "正在生成 SQL 查询...",
        "time_ms": 0
    })
    
    try:
        from app.agents.agents.sql_generator_agent import sql_generator_agent
        result = await sql_generator_agent.process(state)
        
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"[Worker] sql_generator 完成, 耗时 {elapsed:.2f}s")
        
        # 发送完成事件
        sql_preview = result.get("generated_sql", "")[:100] + "..." if len(result.get("generated_sql", "")) > 100 else result.get("generated_sql", "")
        writer({
            "type": "sql_step",
            "step": "sql_generator",
            "status": "completed",
            "result": sql_preview,
            "time_ms": elapsed_ms
        })
        
        result["current_stage"] = "sql_generated"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] sql_generator 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "sql_generator",
            "status": "error",
            "result": str(e),
            "time_ms": elapsed_ms
        })
        return {
            "current_stage": "error_recovery",
            "retry_count": state.get("retry_count", 0) + 1,
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_generation",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def sql_executor_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """SQL Executor 节点"""
    logger.info("[Worker] sql_executor 开始执行")
    start_time = time.time()
    
    # 发送开始事件
    writer({
        "type": "sql_step",
        "step": "sql_executor",
        "status": "running",
        "result": "正在执行 SQL 查询...",
        "time_ms": 0
    })
    
    try:
        from app.agents.agents.sql_executor_agent import sql_executor_agent
        result = await sql_executor_agent.process(state)
        
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"[Worker] sql_executor 完成, 耗时 {elapsed:.2f}s")
        
        # 检查执行结果
        exec_result = result.get("execution_result")
        if exec_result:
            success = getattr(exec_result, 'success', True) if hasattr(exec_result, 'success') else exec_result.get('success', True)
            if not success:
                error_msg = getattr(exec_result, 'error', '') if hasattr(exec_result, 'error') else exec_result.get('error', '')
                writer({
                    "type": "sql_step",
                    "step": "sql_executor",
                    "status": "error",
                    "result": error_msg,
                    "time_ms": elapsed_ms
                })
                retry_count = state.get("retry_count", 0) + 1
                result["current_stage"] = "error_recovery"
                result["retry_count"] = retry_count
                result["error_history"] = state.get("error_history", []) + [{
                    "stage": "sql_execution",
                    "error": error_msg,
                    "timestamp": time.time()
                }]
                return result
        
        # 发送成功事件
        row_count = 0
        if exec_result:
            data = getattr(exec_result, 'data', None) if hasattr(exec_result, 'data') else exec_result.get('data')
            if data:
                row_count = len(data)
        writer({
            "type": "sql_step",
            "step": "sql_executor",
            "status": "completed",
            "result": f"查询成功，返回 {row_count} 条数据",
            "time_ms": elapsed_ms
        })
        
        result["current_stage"] = "execution_done"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] sql_executor 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "sql_executor",
            "status": "error",
            "result": str(e),
            "time_ms": elapsed_ms
        })
        return {
            "current_stage": "error_recovery",
            "retry_count": state.get("retry_count", 0) + 1,
            "error_history": state.get("error_history", []) + [{
                "stage": "sql_execution",
                "error": str(e),
                "timestamp": time.time()
            }]
        }


async def data_analyst_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """Data Analyst 节点"""
    logger.info("[Worker] data_analyst 开始执行")
    start_time = time.time()
    
    # 发送开始事件
    writer({
        "type": "sql_step",
        "step": "data_analyst",
        "status": "running",
        "result": "正在分析数据...",
        "time_ms": 0
    })
    
    try:
        agent_id = state.get("agent_id")
        if agent_id:
            from app.agents.agents.supervisor_subgraph import _load_custom_agent_by_id
            custom_agent = _load_custom_agent_by_id(agent_id, "data_analyst")
            if custom_agent:
                result = await custom_agent.process(state, writer=writer)
            else:
                from app.agents.agents.data_analyst_agent import data_analyst_agent
                result = await data_analyst_agent.process(state, writer=writer)
        else:
            from app.agents.agents.data_analyst_agent import data_analyst_agent
            result = await data_analyst_agent.process(state, writer=writer)
        
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"[Worker] data_analyst 完成, 耗时 {elapsed:.2f}s")
        
        # 发送完成事件
        analyst_insights = result.get("analyst_insights", {})
        analysis_summary = analyst_insights.get("summary", "数据分析完成")[:200]
        writer({
            "type": "sql_step",
            "step": "data_analyst",
            "status": "completed",
            "result": analysis_summary,
            "time_ms": elapsed_ms
        })
        
        result["current_stage"] = "analysis_done"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] data_analyst 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "data_analyst",
            "status": "error",
            "result": str(e),
            "time_ms": elapsed_ms
        })
        return {"current_stage": "analysis_done"}


async def chart_generator_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """Chart Generator 节点"""
    logger.info("[Worker] chart_generator 开始执行")
    start_time = time.time()
    
    # 发送开始事件
    writer({
        "type": "sql_step",
        "step": "chart_generator",
        "status": "running",
        "result": "正在生成图表配置...",
        "time_ms": 0
    })
    
    try:
        from app.agents.agents.chart_generator_agent import chart_generator_agent
        result = await chart_generator_agent.process(state, writer=writer)
        
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"[Worker] chart_generator 完成, 耗时 {elapsed:.2f}s")
        
        # 发送完成事件
        chart_type = result.get("chart_config", {}).get("type", "auto") if result.get("chart_config") else "无"
        writer({
            "type": "sql_step",
            "step": "chart_generator",
            "status": "completed",
            "result": f"图表类型: {chart_type}",
            "time_ms": elapsed_ms
        })
        
        result["current_stage"] = "chart_done"
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[Worker] chart_generator 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "chart_generator",
            "status": "error",
            "result": str(e),
            "time_ms": elapsed_ms
        })
        return {"current_stage": "chart_done", "chart_config": None}


async def error_recovery_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """Error Recovery 节点"""
    logger.info("[Worker] error_recovery 开始执行")
    
    writer({
        "type": "sql_step",
        "step": "error_recovery",
        "status": "running",
        "result": "正在尝试错误恢复...",
        "time_ms": 0
    })
    
    try:
        from app.agents.agents.error_recovery_agent import error_recovery_agent
        result = await error_recovery_agent.process(state)
        logger.info("[Worker] error_recovery 完成")
        
        writer({
            "type": "sql_step",
            "step": "error_recovery",
            "status": "completed",
            "result": "错误恢复完成",
            "time_ms": 0
        })
        return result
    except Exception as e:
        logger.error(f"[Worker] error_recovery 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "error_recovery",
            "status": "error",
            "result": str(e),
            "time_ms": 0
        })
        return {
            "current_stage": "completed",
            "messages": [AIMessage(content=f"抱歉，处理过程中遇到错误: {str(e)}")]
        }


async def general_chat_node(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """General Chat 节点"""
    logger.info("[Worker] general_chat 开始执行")
    
    writer({
        "type": "sql_step",
        "step": "general_chat",
        "status": "running",
        "result": "正在处理对话...",
        "time_ms": 0
    })
    
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
    
    writer({
        "type": "sql_step",
        "step": "general_chat",
        "status": "completed",
        "result": "对话处理完成",
        "time_ms": 0
    })
    
    return {
        "messages": [AIMessage(content=response.content)],
        "current_stage": "completed",
        "route_decision": "general_chat"
    }


async def clarification_node_wrapper(state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
    """
    澄清节点包装器
    
    使用现有的 clarification_node 实现，支持 interrupt
    """
    logger.info("[Worker] clarification 开始执行")
    
    writer({
        "type": "sql_step",
        "step": "clarification",
        "status": "running",
        "result": "正在分析是否需要澄清...",
        "time_ms": 0
    })
    
    try:
        from app.agents.nodes.clarification_node import clarification_node
        
        # 调用现有实现
        result = clarification_node(state)
        
        # 如果触发了 interrupt，LangGraph 会自动处理
        # 这里只需要更新阶段
        if result.get("current_stage") != "schema_analysis":
            result["current_stage"] = "clarification_done"
            writer({
                "type": "sql_step",
                "step": "clarification",
                "status": "completed",
                "result": "澄清完成",
                "time_ms": 0
            })
        
        return result
        
    except Exception as e:
        # interrupt 会抛出特殊异常，需要重新抛出
        if "interrupt" in str(type(e).__name__).lower():
            raise
        logger.error(f"[Worker] clarification 失败: {e}")
        writer({
            "type": "sql_step",
            "step": "clarification",
            "status": "error",
            "result": str(e),
            "time_ms": 0
        })
        return {"current_stage": "clarification_done"}


# ============================================================================
# Supervisor 节点
# ============================================================================

async def supervisor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 中心节点
    
    职责:
    - 汇总各 Agent 的执行结果
    - 构造统一的 final_response
    """
    current_stage = state.get("current_stage", "init")
    
    # 如果推荐完成，构造最终响应
    if current_stage == "recommendation_done":
        return _aggregate_results(state)
    
    # 如果图表完成（会继续到推荐），不汇总
    if current_stage == "chart_done":
        return {}
    
    # 分析完成且跳过图表（会继续到推荐），不汇总
    if current_stage == "analysis_done" and state.get("skip_chart_generation", False):
        return {}
    
    # 如果已完成
    if current_stage == "completed":
        return _aggregate_results(state)
    
    return {}


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

def supervisor_route(state: SQLMessageState) -> str:
    """Supervisor 路由决策"""
    current_stage = state.get("current_stage", "init")
    logger.info(f"[Route] 当前阶段: {current_stage}")
    
    # 0. 优先检查完成状态
    if current_stage in ["completed", "recommendation_done"]:
        logger.info("[Route] 已完成 → FINISH")
        return "FINISH"
    
    # 1. 检查闲聊 (仅在初始阶段)
    if current_stage == "init":
        route_decision = state.get("route_decision")
        if route_decision == "general_chat":
            return "general_chat"
        
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            # 处理不同类型的消息格式
            if hasattr(last_msg, 'content'):
                content = last_msg.content
            elif isinstance(last_msg, dict):
                content = last_msg.get('content', '')
            else:
                content = str(last_msg)
            # 确保 content 是字符串
            if isinstance(content, list):
                content = ' '.join(str(c) for c in content)
            content = str(content) if content else ''
            chat_keywords = ["你好", "谢谢", "帮助", "你是谁", "hello", "hi", "thanks"]
            if content and any(kw in content.lower() for kw in chat_keywords):
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
            logger.info(f"[Route] 达到重试上限 ({retry_count}/{max_retries}) → FINISH")
            return "FINISH"
        logger.info(f"[Route] 错误恢复 ({retry_count}/{max_retries}) → sql_generator")
        return "sql_generator"
    
    # 4. 基于阶段路由
    stage_routes = {
        "init": "schema_agent",
        "schema_done": "clarification",  # Schema完成后先检查澄清
        "clarification_done": "sql_generator",
        "schema_analysis": "sql_generator",  # 兼容现有阶段名
        "sql_generated": "sql_executor",
        "execution_done": "data_analyst",
        "analysis_done": "chart_generator" if not state.get("skip_chart_generation") else "recommendation",
        "chart_done": "recommendation",  # 图表完成后进入推荐
    }
    
    next_agent = stage_routes.get(current_stage, "FINISH")
    logger.info(f"[Route] {current_stage} → {next_agent}")
    return next_agent


# ============================================================================
# 图构建
# ============================================================================

def create_hub_spoke_graph(checkpointer=None) -> CompiledStateGraph:
    """创建 Hub-and-Spoke 架构的图"""
    logger.info("创建 Hub-and-Spoke 图...")
    
    # 导入推荐节点
    from app.agents.nodes.question_recommendation_node import question_recommendation_node
    
    graph = StateGraph(SQLMessageState)
    
    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("chart_generator", chart_generator_node)
    graph.add_node("error_recovery", error_recovery_node)
    graph.add_node("general_chat", general_chat_node)
    graph.add_node("clarification", clarification_node_wrapper)
    graph.add_node("recommendation", question_recommendation_node)  # 推荐节点
    
    # Supervisor 是入口
    graph.set_entry_point("supervisor")
    
    # 所有 Worker 返回 Supervisor (Hub-and-Spoke 核心)
    graph.add_edge("schema_agent", "supervisor")
    graph.add_edge("sql_generator", "supervisor")
    graph.add_edge("sql_executor", "supervisor")
    graph.add_edge("data_analyst", "supervisor")
    graph.add_edge("chart_generator", "supervisor")
    graph.add_edge("error_recovery", "supervisor")
    graph.add_edge("general_chat", "supervisor")
    graph.add_edge("clarification", "supervisor")
    graph.add_edge("recommendation", "supervisor")  # 推荐节点返回 Supervisor
    
    # Supervisor 条件路由
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
            "clarification": "clarification",
            "recommendation": "recommendation",  # 添加推荐路由
            "FINISH": END
        }
    )
    
    # 编译
    if checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        compiled = graph.compile(checkpointer=_get_default_checkpointer())
    
    logger.info("✓ Hub-and-Spoke 图创建完成")
    return compiled


# ============================================================================
# 主图类 (保持 API 兼容)
# ============================================================================

class IntelligentSQLGraph:
    """
    智能 SQL 代理图 - Hub-and-Spoke 架构
    
    保持与原有 Pipeline 架构的 API 兼容
    """
    
    def __init__(
        self, 
        active_agent_profiles: List[AgentProfile] = None, 
        custom_analyst=None,
        use_default_checkpointer: bool = True
    ):
        self._use_default_checkpointer = use_default_checkpointer
        self._checkpointer = None
        self.graph = self._create_graph()
        self._initialized = True
    
    def _create_graph(self):
        """创建图"""
        if self._use_default_checkpointer:
            self._checkpointer = _get_default_checkpointer()
            return create_hub_spoke_graph(checkpointer=self._checkpointer)
        return create_hub_spoke_graph()
    
    async def _ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            self.graph = self._create_graph()
            self._initialized = True
    
    async def process_query(
        self,
        query: str,
        connection_id: Optional[int] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理 SQL 查询"""
        try:
            from uuid import uuid4
            
            await self._ensure_initialized()
            
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
                "current_stage": "init",
                "retry_count": 0,
                "max_retries": 3,
                "error_history": [],
                "context": {"connectionId": connection_id}
            }
            
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
# 便捷函数 (保持兼容)
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
