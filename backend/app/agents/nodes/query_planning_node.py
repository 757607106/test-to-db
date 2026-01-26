"""
查询规划节点 (Query Planning Node)

P2 阶段核心节点：在查询处理流程的早期阶段进行意图分析和规划。

职责：
1. 分析用户查询意图
2. 分类查询类型
3. 生成执行计划
4. 设置路由标志
"""
from typing import Dict, Any
import logging
import time

from langgraph.config import get_stream_writer

from app.core.state import SQLMessageState
from app.agents.query_planner import (
    query_planner,
    query_router,
    QueryPlan,
    QueryType
)
from app.schemas.stream_events import create_sql_step_event

logger = logging.getLogger(__name__)


async def query_planning_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    查询规划节点
    
    在 schema_agent 之前执行，分析查询意图并生成执行计划。
    
    输出状态:
        - query_plan: 查询执行计划
        - route_decision: 路由决策 (general_chat/standard/analysis_enhanced/multi_step)
        - query_type: 查询类型
        - current_stage: 下一阶段
    """
    start_time = time.time()
    
    # 获取 stream writer
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None
    
    # 发送规划开始事件
    if writer:
        writer(create_sql_step_event(
            step="intent_analysis",
            status="running",
            result=None,
            time_ms=0
        ))
    
    try:
        # 获取用户查询
        messages = state.get("messages", [])
        user_query = None
        
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    user_query = content[0].get("text", "") if content else ""
                else:
                    user_query = str(content)
                break
            elif isinstance(msg, dict) and msg.get("type") == "human":
                user_query = msg.get("content", "")
                break
        
        if not user_query:
            logger.warning("无法获取用户查询")
            return {
                "current_stage": "init",
                "route_decision": "standard"
            }
        
        # 保存原始查询
        original_query = user_query
        
        # 执行查询规划
        logger.info(f"开始查询规划: {user_query[:50]}...")
        plan = await query_planner.create_plan(user_query)
        
        # 获取路由决策
        route = query_router.route(plan)
        route_config = query_router.get_route_config(route)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 构建规划结果摘要
        plan_summary = {
            "query_type": plan.query_type.value,
            "complexity": plan.complexity,
            "estimated_steps": plan.estimated_steps,
            "route": route,
            "sub_tasks": [
                {"id": t.id, "query": t.query[:100]} 
                for t in plan.sub_tasks
            ] if plan.sub_tasks else []
        }
        
        # 发送规划完成事件
        if writer:
            writer(create_sql_step_event(
                step="intent_analysis",
                status="completed",
                result=f"查询类型: {plan.query_type.value}, 复杂度: {plan.complexity}, 路由: {route}",
                time_ms=elapsed_ms
            ))
        
        logger.info(f"查询规划完成: type={plan.query_type.value}, complexity={plan.complexity}, route={route} [{elapsed_ms}ms]")
        
        # 根据路由决策设置状态
        result = {
            "original_query": original_query,
            "enriched_query": original_query,  # 可以在这里增强查询
            "query_plan": plan_summary,
            "route_decision": route,
            "query_type": plan.query_type.value,
            "current_stage": "planning_done",
            # 路由配置
            "skip_chart_generation": route_config.get("skip_chart", False),
            "fast_mode": route_config.get("fast_mode", False),
            # P2.1: 多步执行配置
            "multi_step_mode": route_config.get("multi_step_mode", False),
            "current_sub_task_index": 0,
            "sub_task_results": [],
            "multi_step_completed": False,
            # P2.2: 分析意图（用于图表推荐）
            "analysis_intent": _map_query_type_to_intent(plan.query_type.value),
        }
        
        # 闲聊直接路由
        if plan.query_type == QueryType.GENERAL_CHAT:
            result["current_stage"] = "init"  # 让 supervisor 路由到 general_chat
            result["route_decision"] = "general_chat"
        
        return result
        
    except Exception as e:
        logger.error(f"查询规划失败: {e}")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 发送错误事件
        if writer:
            writer(create_sql_step_event(
                step="intent_analysis",
                status="error",
                result=str(e),
                time_ms=elapsed_ms
            ))
        
        # 规划失败时使用默认路由，直接进入 schema_agent
        # 设置 planning_done 避免重新进入规划节点
        return {
            "current_stage": "planning_done",  # 跳过规划，直接进入下一阶段
            "route_decision": "standard",
            "query_type": "simple"
        }


def should_skip_planning(state: SQLMessageState) -> bool:
    """
    判断是否应该跳过规划
    
    跳过条件:
    - 缓存命中
    - 已经有规划结果
    - 非初始阶段
    """
    # 缓存命中
    if state.get("cache_hit") or state.get("thread_history_hit"):
        return True
    
    # 已有规划
    if state.get("query_plan"):
        return True
    
    # 非初始阶段
    current_stage = state.get("current_stage", "init")
    if current_stage not in ["init", "new_query"]:
        return True
    
    return False


def _map_query_type_to_intent(query_type: str) -> str:
    """
    将查询类型映射到分析意图（用于图表推荐）
    
    映射规则：
    - trend -> trend (趋势分析 -> 折线图/面积图)
    - comparison -> comparison (对比分析 -> 柱状图/分组柱状图)
    - aggregate -> structure (聚合统计 -> 饼图/堆叠图)
    - simple -> detail (简单查询 -> 表格)
    - multi_step -> summary (多步查询 -> 综合展示)
    """
    intent_map = {
        "trend": "trend",
        "comparison": "comparison",
        "aggregate": "structure",
        "simple": "detail",
        "multi_step": "summary",
        "general_chat": None,
    }
    return intent_map.get(query_type, "detail")
