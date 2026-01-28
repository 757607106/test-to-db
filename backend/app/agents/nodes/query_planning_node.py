"""
查询规划节点 (Query Planning Node)

P2 阶段核心节点：在查询处理流程的早期阶段进行意图分析和规划。
P3 阶段增强：集成 Skills-SQL-Assistant 路由。
P4 阶段增强：多轮对话上下文改写（Context-Aware Query Rewriting）。

职责：
1. 多轮对话上下文改写（P4 新增）
2. 分析用户查询意图
3. 分类查询类型
4. 生成执行计划
5. 设置路由标志
6. (P3) Skill 路由决策
"""
from typing import Dict, Any, List, Optional
import logging
import time

from langgraph.config import get_stream_writer
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from app.core.state import SQLMessageState, extract_connection_id
from app.agents.query_planner import (
    query_planner,
    query_router,
    QueryPlan,
    QueryType
)
from app.schemas.stream_events import create_sql_step_event

logger = logging.getLogger(__name__)


# ============================================================================
# P4: 多轮对话上下文改写
# ============================================================================

def _is_follow_up_query(query: str) -> bool:
    """
    检测查询是否是跟进查询（需要结合上下文理解）
    
    跟进查询的特征：
    - 包含指代词（这个、那个、它、上面、刚才等）
    - 包含修改词（改成、换成、要、不要等）
    - 查询过短且缺乏完整语义
    - 纯数量修改请求（如"前20条"、"我要20个"，但不包含完整查询语义）
    
    注意：
    - "查询库存最多的前5个产品" 是完整查询，不是跟进查询
    - "我要前20条" 是跟进查询，因为缺乏查询主体
    """
    import re
    
    query_lower = query.lower().strip()
    
    # 指代词
    reference_words = [
        "这个", "那个", "它", "它们", "上面", "刚才", "之前", "前面",
        "这些", "那些", "该", "此", "其", "上述",
        "this", "that", "it", "them", "above", "previous"
    ]
    
    # 修改词
    modification_words = [
        "改成", "换成", "改为", "换为", "变成",
        "不要", "加上", "去掉", "删除", "添加",
        "更多", "更少", "增加", "减少",
        "change", "modify", "add", "remove", "more", "less"
    ]
    
    # 完整查询的关键词（表示这是一个独立的查询，不是跟进）
    complete_query_keywords = [
        "查询", "统计", "显示", "列出", "获取", "分析", "计算", "汇总",
        "哪些", "多少", "什么", "谁", "哪个",
        "select", "query", "show", "list", "get", "find", "count"
    ]
    
    # 检测是否是完整查询（包含查询动词或疑问词）
    is_complete_query = any(kw in query_lower for kw in complete_query_keywords)
    
    # 检测指代词
    has_reference = any(word in query_lower for word in reference_words)
    
    # 检测修改词
    has_modification = any(word in query_lower for word in modification_words)
    
    # 检测纯数量修改请求（如"前20条"、"我要20个"，但不是完整查询）
    # 关键：如果查询包含完整查询关键词，则不认为是纯数量修改
    quantity_pattern = re.search(r'^[我要给看]*\s*[前后]?\s*\d+\s*[条个行项]', query_lower)
    is_pure_quantity_request = bool(quantity_pattern) and not is_complete_query
    
    # 查询过短（少于10个字符且不是完整句子）
    is_too_short = len(query_lower) < 10 and not is_complete_query
    
    # 如果是完整查询，即使包含指代词也不认为是跟进查询
    # 例如："查询这个月的销售额" 是完整查询
    if is_complete_query and not has_modification:
        # 但如果同时有修改词，仍然认为是跟进查询
        # 例如："把查询改成按月份显示"
        return False
    
    return has_reference or has_modification or is_pure_quantity_request or is_too_short


def _extract_conversation_context(messages: List[BaseMessage], max_turns: int = 3) -> List[Dict[str, str]]:
    """
    提取最近的对话上下文
    
    Args:
        messages: 消息列表
        max_turns: 最大轮数
        
    Returns:
        对话上下文列表 [{"role": "user/assistant", "content": "..."}]
    """
    context = []
    turn_count = 0
    
    # 从后往前遍历，跳过最后一条（当前查询）
    for msg in reversed(messages[:-1] if len(messages) > 1 else []):
        if turn_count >= max_turns * 2:  # 每轮包含 user + assistant
            break
            
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                context.insert(0, {"role": "user", "content": str(content)})
                turn_count += 1
            elif msg.type == 'ai':
                content = msg.content
                if content and not content.startswith("{"):  # 跳过工具调用结果
                    context.insert(0, {"role": "assistant", "content": str(content)[:500]})
                    turn_count += 1
    
    return context


async def _rewrite_query_with_context(
    current_query: str,
    conversation_context: List[Dict[str, str]],
    connection_id: Optional[int] = None
) -> str:
    """
    使用 LLM 结合对话上下文改写查询
    
    Args:
        current_query: 当前用户查询
        conversation_context: 对话上下文
        connection_id: 数据库连接 ID
        
    Returns:
        改写后的完整查询
    """
    from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
    
    if not conversation_context:
        return current_query
    
    # 构建上下文字符串
    context_str = ""
    for turn in conversation_context:
        role = "用户" if turn["role"] == "user" else "助手"
        context_str += f"{role}: {turn['content']}\n"
    
    prompt = f"""你是一个查询改写专家。用户正在进行多轮对话，当前的查询可能是对之前查询的跟进或修改。

**对话历史**:
{context_str}

**当前查询**: {current_query}

**任务**: 
1. 分析当前查询是否是对之前查询的跟进或修改
2. 如果是，将当前查询改写为一个完整、独立、明确的查询
3. 如果当前查询已经是完整的，直接返回原查询

**改写规则**:
- 保留用户的核心意图
- 将指代词（这个、那个、它等）替换为具体内容
- 将修改请求（前20条、更多等）整合到查询中
- 改写后的查询应该是一个完整的数据查询请求

**示例**:
- 历史: "查询库存最多的前5个产品" → 当前: "我要前20条" → 改写: "查询库存最多的前20个产品"
- 历史: "统计各部门销售额" → 当前: "按月份显示" → 改写: "按月份统计各部门销售额"
- 历史: "查询订单列表" → 当前: "只要今天的" → 改写: "查询今天的订单列表"

**输出**: 只输出改写后的查询，不要任何解释。如果不需要改写，直接输出原查询。
"""
    
    try:
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        rewritten = response.content.strip()
        
        # 清理可能的引号
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        if rewritten.startswith("'") and rewritten.endswith("'"):
            rewritten = rewritten[1:-1]
        
        # 如果改写结果为空或太短，返回原查询
        if not rewritten or len(rewritten) < 5:
            return current_query
        
        logger.info(f"查询改写: '{current_query}' → '{rewritten}'")
        return rewritten
        
    except Exception as e:
        logger.warning(f"查询改写失败: {e}")
        return current_query


async def query_planning_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    查询规划节点
    
    在 schema_agent 之前执行，分析查询意图并生成执行计划。
    
    P4 新增: 多轮对话上下文改写
    - 检测当前查询是否是跟进查询
    - 如果是，结合历史上下文改写为完整查询
    - 改写后的查询不需要触发澄清（因为已经明确了）
    
    输出状态:
        - query_plan: 查询执行计划
        - route_decision: 路由决策 (general_chat/standard/analysis_enhanced/multi_step)
        - query_type: 查询类型
        - current_stage: 下一阶段
        - enriched_query: 改写后的完整查询（P4 新增）
        - query_rewritten: 是否进行了改写（P4 新增）
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
        
        # ==========================================
        # P4: 多轮对话上下文改写
        # ==========================================
        query_rewritten = False
        enriched_query = original_query
        
        # 检测是否是跟进查询
        if _is_follow_up_query(user_query) and len(messages) > 1:
            logger.info(f"检测到跟进查询: '{user_query}'，尝试上下文改写")
            
            # 提取对话上下文
            conversation_context = _extract_conversation_context(messages, max_turns=3)
            
            if conversation_context:
                # 使用 LLM 改写查询
                enriched_query = await _rewrite_query_with_context(
                    current_query=user_query,
                    conversation_context=conversation_context,
                    connection_id=state.get("connection_id")
                )
                
                if enriched_query != original_query:
                    query_rewritten = True
                    logger.info(f"查询已改写: '{original_query}' → '{enriched_query}'")
                    
                    # 发送改写事件
                    if writer:
                        writer(create_sql_step_event(
                            step="query_rewrite",
                            status="completed",
                            result=f"改写: {enriched_query[:100]}",
                            time_ms=int((time.time() - start_time) * 1000)
                        ))
        
        # 执行查询规划（使用改写后的查询）
        logger.info(f"开始查询规划: {enriched_query[:50]}...")
        plan = await query_planner.create_plan(enriched_query)
        
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
            rewrite_info = f" (已改写)" if query_rewritten else ""
            writer(create_sql_step_event(
                step="intent_analysis",
                status="completed",
                result=f"查询类型: {plan.query_type.value}, 复杂度: {plan.complexity}, 路由: {route}{rewrite_info}",
                time_ms=elapsed_ms
            ))
        
        logger.info(f"查询规划完成: type={plan.query_type.value}, complexity={plan.complexity}, route={route}, rewritten={query_rewritten} [{elapsed_ms}ms]")
        
        # 根据路由决策设置状态
        result = {
            "original_query": original_query,
            "enriched_query": enriched_query,  # P4: 使用改写后的查询
            "query_rewritten": query_rewritten,  # P4: 标记是否改写
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
        
        # P4: 查询改写后，仍然需要经过澄清节点判断
        # 澄清节点会检测改写后的查询是否仍然模糊
        # 如果模糊，会使用 LangGraph interrupt() 等待用户确认
        if query_rewritten:
            logger.info("查询已改写，将由澄清节点判断是否需要进一步澄清")
        
        # ==========================================
        # P3: Skills-SQL-Assistant 路由集成
        # ==========================================
        # 只在非闲聊且非缓存命中时执行 Skill 路由
        if plan.query_type != QueryType.GENERAL_CHAT:
            skill_context = await _perform_skill_routing(
                query=enriched_query,  # P4: 使用改写后的查询
                connection_id=state.get("connection_id"),
                writer=writer
            )
            result.update(skill_context)
        
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


async def _perform_skill_routing(
    query: str,
    connection_id: int,
    writer: Any = None
) -> Dict[str, Any]:
    """
    执行 Skill 路由决策
    
    P3: Skills-SQL-Assistant 集成
    Phase 3 优化: 支持通过 SKILL_MODE_ENABLED 环境变量全局禁用
    
    Args:
        query: 用户查询
        connection_id: 数据库连接 ID
        writer: Stream writer for events
        
    Returns:
        Dict 包含 Skill 路由结果，可直接合并到 state
    """
    from app.core.config import settings
    from app.services.skill_router import (
        skill_router, 
        RoutingStrategy,
        should_use_skill_mode
    )
    from app.services.skill_service import skill_service
    
    # 默认返回值（零配置兼容）
    result = {
        "skill_mode_enabled": False,
        "selected_skill_name": None,
        "skill_confidence": 0.0,
        "loaded_skill_content": None,
        "skill_business_rules": None,
        "skill_routing_strategy": None,
        "skill_routing_reasoning": "Skill 功能已禁用",
    }
    
    # ==========================================
    # Phase 3: 全局开关检查
    # 如果 SKILL_MODE_ENABLED=false，直接跳过 Skill 路由
    # ==========================================
    if not settings.SKILL_MODE_ENABLED:
        logger.debug("Skill 功能已通过 SKILL_MODE_ENABLED=false 禁用，跳过路由")
        return result
    
    if not connection_id:
        result["skill_routing_reasoning"] = "未指定数据库连接"
        return result
    
    try:
        # 检查是否配置了 Skills
        has_skills = await should_use_skill_mode(connection_id)
        
        if not has_skills:
            logger.debug(f"connection_id={connection_id} 未配置 Skills，使用默认模式")
            result["skill_routing_reasoning"] = "未配置 Skills"
            return result
        
        # 执行 Skill 路由
        start_time = time.time()
        routing_result = await skill_router.route(
            query=query,
            connection_id=connection_id,
            strategy=RoutingStrategy.KEYWORD  # 默认使用关键词路由（快速）
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 发送 Skill 路由事件
        if writer:
            from app.schemas.stream_events import create_sql_step_event
            writer(create_sql_step_event(
                step="skill_routing",
                status="completed",
                result=f"Skill: {routing_result.selected_skill.display_name if routing_result.selected_skill else '无匹配'}",
                time_ms=elapsed_ms
            ))
        
        # 如果有匹配的 Skill
        if routing_result.selected_skill and not routing_result.fallback_to_default:
            skill_name = routing_result.selected_skill.skill_name
            
            # 加载 Skill 内容
            try:
                skill_content = await skill_service.load_skill(skill_name, connection_id)
                
                result.update({
                    "skill_mode_enabled": True,
                    "selected_skill_name": skill_name,
                    "skill_confidence": routing_result.selected_skill.confidence,
                    "loaded_skill_content": skill_content.model_dump(),
                    "skill_business_rules": skill_content.business_rules,
                    "skill_routing_strategy": routing_result.strategy_used,
                    "skill_routing_reasoning": routing_result.reasoning,
                })
                
                logger.info(
                    f"Skill 路由成功: {skill_name} "
                    f"(confidence={routing_result.selected_skill.confidence:.2f}) [{elapsed_ms}ms]"
                )
                
            except Exception as e:
                logger.warning(f"加载 Skill 内容失败: {e}")
                result["skill_routing_reasoning"] = f"Skill 内容加载失败: {e}"
        else:
            result["skill_routing_strategy"] = routing_result.strategy_used
            result["skill_routing_reasoning"] = routing_result.reasoning
            logger.debug(f"Skill 路由无匹配: {routing_result.reasoning}")
        
        return result
        
    except Exception as e:
        logger.error(f"Skill 路由异常: {e}")
        result["skill_routing_reasoning"] = f"路由异常: {e}"
        return result
