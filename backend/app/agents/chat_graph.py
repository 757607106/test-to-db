"""
智能 SQL 代理图 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 AsyncPostgresSaver 进行异步状态持久化
2. 使用原生条件边 (conditional_edges) 进行路由
3. 使用 add_messages reducer 管理消息历史
4. 完全异步实现，避免同步异步混用

架构说明:
- 使用 LangGraph 的 StateGraph 管理整体流程
- 包含多个核心节点: intent_router、load_custom_agent、fast_mode_detect、clarification、cache_check、supervisor
- clarification 节点使用 interrupt() 实现人机交互
- supervisor 节点协调 Worker Agents 处理查询

图结构 (2026-01-22 更新):
    START → intent_router → [data_query_flow | general_chat → END]
    data_query_flow: load_custom_agent → fast_mode_detect → clarification → cache_check → [supervisor | END]

修复历史:
- 2026-01-22: 添加 checkpointer 回退机制，确保 interrupt 能正常工作
- 2026-01-22: 添加意图路由，区分闲聊和数据查询
"""
from typing import Dict, Any, List, Optional, Literal
import logging
import asyncio
import re

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StreamWriter
from langchain_core.messages import AIMessage

from app.core.state import SQLMessageState, detect_fast_mode
from app.agents.agents.supervisor_subgraph import supervisor_subgraph_node, get_supervisor_subgraph
from app.agents.nodes.thread_history_check_node import thread_history_check_node
from app.agents.nodes.clarification_node import clarification_node
from app.agents.nodes.cache_check_node import cache_check_node
from app.agents.nodes.question_recommendation_node import question_recommendation_node
from app.agents.nodes.table_filter_clarification_node import table_filter_clarification_node
from app.models.agent_profile import AgentProfile

logger = logging.getLogger(__name__)

# 全局默认 checkpointer（用于非 API Server 场景）
_default_checkpointer = None


def _get_default_checkpointer():
    """
    获取默认的内存 checkpointer（单例模式）
    
    LangGraph 官方文档：interrupt() 必须配合 checkpointer 使用
    这是用于直接调用场景的回退机制
    """
    global _default_checkpointer
    if _default_checkpointer is None:
        _default_checkpointer = InMemorySaver()
        logger.info("✓ 初始化默认内存 Checkpointer")
    return _default_checkpointer


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
# 意图识别辅助函数 (LLM 版本)
# ============================================================================

# LLM 意图识别 + 问题改写提示词
INTENT_ANALYSIS_PROMPT = """你是一个专业的数据查询意图分析专家。请分析用户的输入，完成以下任务：

**用户输入**: {query}

**任务1: 意图分类**
判断用户意图属于哪一类：
- "data_query": 数据查询（需要查询数据库，如：统计、查询、分析、对比、排名等）
- "general_chat": 闲聊（打招呼、感谢、询问助手功能等，不涉及数据查询）

**任务2: 问题改写** (仅当意图为 data_query 时)
将用户的口语化表达改写为更清晰、规范的数据查询描述：
- 保持原意不变
- 补充省略的主语或宾语
- 将模糊表达具体化（如果可以推断）
- 如果原查询已经很清晰，保持原样

**任务3: 早期澄清检测** (仅当意图为 data_query 时)
检测查询是否存在以下明显模糊性，需要提前澄清：
- 时间范围完全不明确（如"最近"但不知道指多久）
- 关键业务对象不明确（如"大客户"的标准）
- 数量范围不明确（如"前几名"的具体数量）

**注意**：只有当模糊性会严重影响查询时才需要澄清，一般性的查询可以先执行。

请返回 JSON 格式：
{{
    "intent": "data_query" | "general_chat",
    "rewritten_query": "改写后的查询（仅data_query时有值，否则为null）",
    "needs_early_clarification": true | false,
    "clarification_reason": "需要澄清的原因（如不需要则为null）",
    "clarification_questions": [
        {{
            "id": "q1",
            "question": "澄清问题",
            "type": "choice",
            "options": ["选项1", "选项2", "选项3"]
        }}
    ]
}}

只返回JSON，不要其他内容。"""


async def detect_intent_with_llm(query: str) -> Dict[str, Any]:
    """
    使用 LLM 进行意图识别 + 问题改写
    
    优势：
    - 语义理解能力强，能处理复杂表达
    - 同时完成意图识别和问题改写，减少 LLM 调用次数
    - 可以检测早期澄清需求
    
    Args:
        query: 用户原始查询
        
    Returns:
        Dict 包含:
        - intent: "data_query" | "general_chat"
        - rewritten_query: 改写后的查询
        - needs_early_clarification: 是否需要早期澄清
        - clarification_questions: 澄清问题列表
    """
    import json
    from langchain_core.messages import HumanMessage
    from app.core.llms import get_default_model
    
    try:
        llm = get_default_model()
        prompt = INTENT_ANALYSIS_PROMPT.format(query=query)
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # 清理 markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        # 安全处理可能为 None 的 rewritten_query
        rewritten_query = result.get('rewritten_query') or ''
        logger.info(f"LLM 意图识别结果: intent={result.get('intent')}, rewritten={rewritten_query[:50]}")
        
        return {
            "intent": result.get("intent", "data_query"),
            "rewritten_query": result.get("rewritten_query"),
            "needs_early_clarification": result.get("needs_early_clarification", False),
            "clarification_reason": result.get("clarification_reason"),
            "clarification_questions": result.get("clarification_questions", [])
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"LLM 意图识别 JSON 解析失败: {e}")
        # 降级处理：默认为数据查询
        return {
            "intent": "data_query",
            "rewritten_query": query,
            "needs_early_clarification": False,
            "clarification_questions": []
        }
    except Exception as e:
        logger.error(f"LLM 意图识别失败: {e}", exc_info=True)
        # 降级处理：默认为数据查询
        return {
            "intent": "data_query",
            "rewritten_query": query,
            "needs_early_clarification": False,
            "clarification_questions": []
        }


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
    6. 支持意图路由（区分闲聊和数据查询）
    
    LangGraph 官方最佳实践:
    - 图的创建是同步的，编译后返回 CompiledGraph
    - Checkpointer 用于支持 interrupt 机制
    - 参考: https://langchain-ai.github.io/langgraph/concepts/langgraph_server/
    """
    
    def __init__(
        self, 
        active_agent_profiles: List[AgentProfile] = None, 
        custom_analyst=None,
        use_default_checkpointer: bool = True
    ):
        """
        初始化智能 SQL 图
        
        Args:
            active_agent_profiles: 活跃的代理配置文件列表
            custom_analyst: 自定义分析专家（已废弃，保留参数兼容性）
            use_default_checkpointer: 是否使用默认 checkpointer（用于非 API Server 场景）
        """
        # 使用 LangGraph 子图模式，不再需要 SupervisorAgent 实例
        # 子图在 supervisor_subgraph.py 中定义
        self._use_default_checkpointer = use_default_checkpointer
        self._checkpointer = None
        
        # 同步创建图 - LangGraph API 要求图工厂函数返回编译好的图
        self.graph = self._create_graph_sync()
        self._initialized = True
    
    def _create_graph_sync(self, checkpointer=None):
        """
        同步创建 LangGraph 状态图
        
        修复说明 (2026-01-22):
        - 添加意图路由节点
        - 添加 checkpointer 回退机制，确保 interrupt 能正常工作
        - 添加 thread_history_check 节点，实现三级缓存策略
        - 添加 question_recommendation 节点，实现问题推荐
        
        图结构:
        START → intent_router → [data_query_flow | general_chat → END]
        data_query_flow: load_custom_agent → fast_mode_detect → thread_history_check 
                         → cache_check → clarification → supervisor → question_recommendation → END
        
        三级缓存策略:
        1. Thread 历史检查 (thread_history_check) - 同一对话内相同问题
        2. 全局精确缓存 (cache_check) - query_cache_service
        3. 全局语义缓存 (cache_check) - Milvus 向量检索
        
        Args:
            checkpointer: 可选的 checkpointer，如果不提供则使用默认值
        """
        graph = StateGraph(SQLMessageState)
        
        # ============== 添加节点 ==============
        # 意图路由节点
        graph.add_node("intent_router", self._intent_router_node)
        # 闲聊处理节点
        graph.add_node("general_chat", self._general_chat_node)
        # 数据查询流程节点
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        graph.add_node("fast_mode_detect", self._fast_mode_detect_node)
        # 三级缓存节点
        graph.add_node("thread_history_check", thread_history_check_node)
        graph.add_node("cache_check", cache_check_node)
        graph.add_node("clarification", clarification_node)
        # 表过滤澄清节点 (澄清点B)
        graph.add_node("table_filter_clarification", table_filter_clarification_node)
        graph.add_node("supervisor", self._supervisor_node)
        # 问题推荐节点 (在 supervisor 之后执行)
        graph.add_node("question_recommendation", question_recommendation_node)
        
        # ============== 设置入口点 ==============
        graph.set_entry_point("intent_router")
        
        # ============== 定义边 ==============
        # 意图路由条件边
        graph.add_conditional_edges(
            "intent_router",
            self._route_by_intent,
            {
                "data_query": "load_custom_agent",
                "general_chat": "general_chat"
            }
        )
        
        # 闲聊直接结束
        graph.add_edge("general_chat", END)
        
        # 数据查询流程 (新顺序)
        # load_custom_agent → fast_mode_detect → thread_history_check
        graph.add_edge("load_custom_agent", "fast_mode_detect")
        graph.add_edge("fast_mode_detect", "thread_history_check")
        
        # 条件边: thread_history_check → [END | cache_check]
        graph.add_conditional_edges(
            "thread_history_check",
            self._after_thread_history_check,
            {
                "cache_check": "cache_check",
                "end": END
            }
        )
        
        # 条件边: cache_check → [clarification | END]
        graph.add_conditional_edges(
            "cache_check",
            self._after_cache_check,
            {
                "clarification": "clarification",
                "end": END
            }
        )
        
        # clarification → table_filter_clarification (澄清点B)
        graph.add_edge("clarification", "table_filter_clarification")
        
        # table_filter_clarification → supervisor
        graph.add_edge("table_filter_clarification", "supervisor")
        
        # supervisor → question_recommendation (新增: 在完成后推荐问题)
        # ✅ 使用条件边处理 supervisor 执行失败的情况
        graph.add_conditional_edges(
            "supervisor",
            self._after_supervisor,
            {
                "success": "question_recommendation",
                "error": END  # 如果失败且无法恢复，直接结束
            }
        )
        
        # question_recommendation → END
        graph.add_edge("question_recommendation", END)
        
        # ============== 编译图 ==============
        # 确定使用哪个 checkpointer
        if checkpointer:
            self._checkpointer = checkpointer
            logger.info("✓ 使用提供的 Checkpointer 编译图")
            return graph.compile(checkpointer=checkpointer)
        elif self._use_default_checkpointer:
            # 使用默认内存 checkpointer（确保 interrupt 能工作）
            self._checkpointer = _get_default_checkpointer()
            logger.info("✓ 使用默认内存 Checkpointer 编译图 (interrupt 支持已启用)")
            return graph.compile(checkpointer=self._checkpointer)
        else:
            # 不使用 checkpointer（由 LangGraph API Server 注入）
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
    
    def _extract_metrics(self, query: str) -> List[str]:
        """
        从用户查询中提取指标
        """
        metrics = []
        metric_keywords = {
            "销售额": "销售额",
            "销量": "销量",
            "访问量": "访问量",
            "访问次数": "访问次数",
            "用户数": "用户数",
            "订单数": "订单数",
            "金额": "金额",
            "数量": "数量",
            "总数": "总数",
            "平均": "平均值",
            "最大": "最大值",
            "最小": "最小值",
        }
        for keyword, metric_name in metric_keywords.items():
            if keyword in query:
                metrics.append(metric_name)
        return metrics if metrics else ["默认指标"]
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """
        从用户查询中提取筛选条件
        """
        import re
        from datetime import datetime, timedelta
        
        filters = {}
        
        # 提取日期范围
        date_patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日号]?',
            r'最近(\d+)(天|周|月|年)',
            r'近(\d+)(天|周|月|年)',
            r'过去(\d+)(天|周|月|年)',
        ]
        
        dates_found = re.findall(date_patterns[0], query)
        if dates_found:
            filters["date_range"] = [f"{d[0]}-{d[1].zfill(2)}-{d[2].zfill(2)}" for d in dates_found[:2]]
        
        # 检查相对时间
        for pattern in date_patterns[1:]:
            match = re.search(pattern, query)
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                today = datetime.now()
                if unit == "天":
                    start = today - timedelta(days=num)
                elif unit == "周":
                    start = today - timedelta(weeks=num)
                elif unit == "月":
                    start = today - timedelta(days=num * 30)
                else:  # 年
                    start = today - timedelta(days=num * 365)
                filters["date_range"] = [
                    start.strftime("%Y-%m-%d"),
                    today.strftime("%Y-%m-%d")
                ]
                break
        
        return filters
    
    def _detect_query_mode(self, query: str) -> str:
        """
        检测查询模式
        """
        aggregation_keywords = ["统计", "汇总", "总计", "合计", "平均", "最大", "最小", "趋势", "对比"]
        if any(kw in query for kw in aggregation_keywords):
            return "聚合模式"
        return "明细模式"
    
    async def _intent_router_node(self, state: SQLMessageState, writer: StreamWriter) -> Dict[str, Any]:
        """
        意图路由节点 - 使用 LLM 进行意图识别 + 问题改写
        
        功能：
        1. 使用 LLM 识别用户意图（数据查询 vs 闲聊）
        2. 同时完成问题改写，生成更清晰的查询描述
        3. 检测早期澄清需求，避免后续步骤浪费
        
        Args:
            state: 当前状态
            writer: LangGraph StreamWriter
        
        返回:
            route_decision: "data_query" | "general_chat"
            enriched_query: 改写后的查询（用于后续处理）
            needs_clarification: 是否需要早期澄清
            clarification_questions: 澄清问题列表
        """
        import time
        from app.schemas.stream_events import create_intent_analysis_event
        from langgraph.types import interrupt
        
        start_time = time.time()
        
        messages = state.get("messages", [])
        user_query = None
        
        # ✅ 取最后一条 human 消息
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content
                if isinstance(user_query, list):
                    user_query = user_query[0].get("text", "") if user_query else ""
                break
        
        if not user_query:
            logger.warning("无法提取用户查询，默认为数据查询")
            return {"route_decision": "data_query"}
        
        # ✅ 使用 LLM 进行意图识别 + 问题改写
        intent_result = await detect_intent_with_llm(user_query)
        
        intent = intent_result.get("intent", "data_query")
        rewritten_query = intent_result.get("rewritten_query") or user_query
        needs_early_clarification = intent_result.get("needs_early_clarification", False)
        clarification_questions = intent_result.get("clarification_questions", [])
        clarification_reason = intent_result.get("clarification_reason")
        
        logger.info(f"=== LLM 意图识别 ===")
        logger.info(f"  原始查询: {user_query[:50]}...")
        logger.info(f"  意图: {intent}")
        logger.info(f"  改写后: {rewritten_query[:50]}...")
        logger.info(f"  需要早期澄清: {needs_early_clarification}")
        
        # 如果是数据查询，发送意图解析流式事件
        if intent == "data_query":
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 获取数据集名称
            connection_id = state.get("connection_id")
            dataset_name = "默认数据集"
            if connection_id:
                try:
                    from app.db.session import SessionLocal
                    from app.crud.crud_db_connection import db_connection as crud_connection
                    db = SessionLocal()
                    try:
                        conn = crud_connection.get(db=db, id=connection_id)
                        if conn:
                            dataset_name = conn.name or conn.database
                    finally:
                        db.close()
                except Exception:
                    pass
            
            # 发送意图解析事件
            writer(create_intent_analysis_event(
                dataset=dataset_name,
                query_mode=self._detect_query_mode(rewritten_query),
                metrics=self._extract_metrics(rewritten_query),
                filters=self._extract_filters(rewritten_query),
                time_ms=elapsed_ms
            ))
            logger.info(f"✓ 已发送意图解析流式事件")
            
            # ✅ 检查是否需要早期澄清
            if needs_early_clarification and clarification_questions:
                logger.info(f"触发早期澄清，{len(clarification_questions)} 个问题")
                
                # 使用 interrupt 暂停执行，等待用户澄清
                from app.agents.agents.clarification_agent import format_clarification_questions
                formatted_questions = format_clarification_questions(clarification_questions)
                
                user_response = interrupt({
                    "type": "clarification_request",
                    "stage": "intent_analysis",
                    "questions": formatted_questions,
                    "reason": clarification_reason or "查询存在模糊性，需要澄清",
                    "original_query": user_query
                })
                
                # 用户回复后继续
                logger.info(f"收到早期澄清回复: {user_response}")
                
                # 解析用户回复并更新改写后的查询
                from app.agents.agents.clarification_agent import (
                    parse_user_clarification_response,
                    _enrich_query_with_clarification_impl as enrich_query_with_clarification
                )
                
                parsed_answers = parse_user_clarification_response(user_response, formatted_questions)
                if parsed_answers:
                    enrich_result = enrich_query_with_clarification(
                        original_query=rewritten_query,
                        clarification_responses=parsed_answers
                    )
                    rewritten_query = enrich_result.get("enriched_query", rewritten_query)
                    logger.info(f"早期澄清后查询: {rewritten_query[:50]}...")
        
        return {
            "route_decision": intent,
            "original_query": user_query,
            "enriched_query": rewritten_query,  # 改写后的查询，供后续节点使用
            "clarification_confirmed": needs_early_clarification and bool(clarification_questions)  # 标记早期澄清已完成
        }
    
    def _route_by_intent(self, state: SQLMessageState) -> str:
        """
        根据意图决策路由到对应的处理流程
        """
        route_decision = state.get("route_decision", "data_query")
        return route_decision
    
    async def _general_chat_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        闲聊处理节点 - 处理非数据查询的闲聊请求
        """
        from app.core.llms import get_default_model
        from langchain_core.messages import HumanMessage
        
        messages = state.get("messages", [])
        user_query = None
        
        # ✅ 取最后一条 human 消息
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content
                if isinstance(user_query, list):
                    user_query = user_query[0].get("text", "") if user_query else ""
                break
        
        if not user_query:
            return {
                "messages": [AIMessage(content="您好！请问有什么可以帮助您的？")],
                "current_stage": "completed"
            }
        
        # 构建闲聊提示
        chat_prompt = f"""你是一个友好的数据查询助手。用户发送了一条闲聊消息，请给出友好、简洁的回复。

用户消息: {user_query}

注意:
1. 如果用户打招呼，友好回应并简单介绍你的功能
2. 如果用户说谢谢，礼貌回应
3. 如果用户问你是谁，介绍你是一个 Text-to-SQL 数据查询助手
4. 如果用户问如何使用，简单说明：可以用自然语言描述想查询的数据
5. 保持回复简洁友好

请回复："""
        
        try:
            llm = get_default_model()
            response = await llm.ainvoke([HumanMessage(content=chat_prompt)])
            reply = response.content
        except Exception as e:
            logger.error(f"闲聊处理失败: {e}")
            reply = "您好！我是数据查询助手，可以帮您用自然语言查询数据库。请告诉我您想查询什么数据？"
        
        return {
            "messages": [AIMessage(content=reply)],
            "current_stage": "completed"
        }
    
    async def _create_graph_async(self):
        """
        异步创建 LangGraph 状态图（用于需要自定义 checkpointer 的场景）
        
        使用 AsyncPostgresSaver 进行异步状态持久化
        
        图结构与 _create_graph_sync 保持一致，使用三级缓存策略和问题推荐
        """
        from app.core.checkpointer import get_checkpointer_async
        
        graph = StateGraph(SQLMessageState)
        
        # 添加节点
        graph.add_node("load_custom_agent", self._load_custom_agent_node)
        graph.add_node("fast_mode_detect", self._fast_mode_detect_node)
        # 三级缓存节点
        graph.add_node("thread_history_check", thread_history_check_node)
        graph.add_node("cache_check", cache_check_node)
        graph.add_node("clarification", clarification_node)
        graph.add_node("supervisor", self._supervisor_node)
        # 问题推荐节点
        graph.add_node("question_recommendation", question_recommendation_node)
        
        # 设置入口点
        graph.set_entry_point("load_custom_agent")
        
        # 定义边 (新顺序)
        graph.add_edge("load_custom_agent", "fast_mode_detect")
        graph.add_edge("fast_mode_detect", "thread_history_check")
        
        # 条件边: thread_history_check → [END | cache_check]
        graph.add_conditional_edges(
            "thread_history_check",
            self._after_thread_history_check,
            {
                "cache_check": "cache_check",
                "end": END
            }
        )
        
        # 条件边: cache_check → [clarification | END]
        graph.add_conditional_edges(
            "cache_check",
            self._after_cache_check,
            {
                "clarification": "clarification",
                "end": END
            }
        )
        
        # clarification → supervisor
        graph.add_edge("clarification", "supervisor")
        
        # supervisor → question_recommendation → END
        graph.add_edge("supervisor", "question_recommendation")
        graph.add_edge("question_recommendation", END)
        
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
    
    def _after_thread_history_check(self, state: SQLMessageState) -> str:
        """
        判断 Thread 历史检查后的下一步
        
        如果命中历史，直接返回结果（END）
        否则继续到全局缓存检查（cache_check）
        """
        thread_history_hit = state.get("thread_history_hit", False)
        
        if thread_history_hit:
            logger.info("Thread 历史命中，直接返回历史结果")
            return "end"
        else:
            logger.info("Thread 历史未命中，继续到全局缓存检查")
            return "cache_check"
    
    def _after_cache_check(self, state: SQLMessageState) -> str:
        """
        判断缓存检查后的下一步
        
        三级缓存策略:
        - 完全命中 (100%) -> 直接返回 (END)
        - 语义命中 (>=95%) -> 进入澄清节点 (clarification)
        - 未命中 -> 进入澄清节点 (clarification)
        """
        cache_hit = state.get("cache_hit", False)
        cache_hit_type = state.get("cache_hit_type")
        
        if cache_hit and cache_hit_type == "exact":
            # 精确匹配，直接返回
            logger.info("缓存精确命中，跳过后续流程直接返回")
            return "end"
        elif cache_hit and cache_hit_type in ("semantic", "exact_text"):
            # 语义匹配，需要进入澄清确认
            logger.info(f"缓存语义命中 ({cache_hit_type})，进入澄清节点确认")
            return "clarification"
        else:
            # 未命中，进入完整流程
            logger.info("缓存未命中，进入澄清节点")
            return "clarification"
    
    def _after_supervisor(self, state: SQLMessageState) -> str:
        """
        判断 Supervisor 执行后的下一步
        
        检查执行结果，决定是否继续到问题推荐节点
        
        决策逻辑:
        - 执行成功 (current_stage == "completed") -> 推荐问题
        - 错误但已达到重试上限 -> 直接结束
        - 其他情况 -> 推荐问题（但可能显示错误信息）
        """
        current_stage = state.get("current_stage", "completed")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        error_history = state.get("error_history", [])
        
        # 检查是否有严重错误（无法恢复的错误）
        if error_history:
            last_error = error_history[-1] if error_history else {}
            error_stage = last_error.get("stage", "")
            
            # 连接错误或权限错误通常无法自动恢复
            error_msg = str(last_error.get("error", "")).lower()
            if "connection" in error_msg or "permission" in error_msg or "denied" in error_msg:
                logger.warning(f"检测到无法恢复的错误类型: {error_msg[:50]}")
                return "error"
        
        # 检查是否达到重试上限且仍有错误
        if retry_count >= max_retries and current_stage != "completed":
            logger.warning(f"达到重试上限 ({retry_count}/{max_retries})，结束流程")
            return "error"
        
        # 正常情况，继续到问题推荐
        logger.info(f"Supervisor 执行完成，阶段: {current_stage}")
        return "success"
    
    async def _load_custom_agent_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        加载自定义智能体节点
        
        功能:
        1. 从消息和 context 中提取 connection_id 和 agent_id
        2. 将 agent_id 存储到 state 供子图使用（不存储 Agent 实例，避免序列化问题）
        
        注意：Agent 实例包含 LLM 对象（HTTP 客户端、线程锁等），无法被 pickle 序列化
        因此只存储 agent_id，在 supervisor_subgraph 中按需动态创建 Agent
        
        修复 (2026-01-23): 统一从 context 和 additional_kwargs 两种方式读取 connection_id
        """
        messages = state.get("messages", [])
        updates = {}
        
        # 使用统一的 extract_connection_id 函数 (已支持 context 和 additional_kwargs)
        from app.core.state import extract_connection_id
        extracted_connection_id = extract_connection_id(state)
        
        if extracted_connection_id and extracted_connection_id != state.get("connection_id"):
            logger.info(f"从消息/context中提取到 connection_id={extracted_connection_id}")
            updates["connection_id"] = extracted_connection_id
        
        # 从消息中提取 agent_id（只存储 ID，不存储 Agent 实例）
        agent_id = extract_agent_id_from_messages(messages)
        
        if agent_id:
            logger.info(f"检测到 agent_id={agent_id}，将在执行时动态加载自定义 agent")
            updates["agent_id"] = agent_id
        
        return updates if updates else {}
    
    async def _fast_mode_detect_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        快速模式检测节点
        """
        messages = state.get("messages", [])
        user_query = None
        
        # ✅ 修复：取最后一条 human 消息
        for msg in reversed(messages):
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
        Supervisor 节点 - 使用 LangGraph 子图模式
        
        调用 supervisor_subgraph 处理完整的 SQL 生成流程：
        schema_agent → sql_generator → sql_executor → data_analyst → chart_generator
        """
        # 使用新的子图处理
        final_result = await supervisor_subgraph_node(state)
        
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
        # 使用子图模式后，返回静态的 Agent 列表
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
    - Checkpointer 由 LangGraph API Server 自动管理
    
    注意: 此函数返回的图不使用默认 checkpointer，
    因为 LangGraph API Server 会自动注入 checkpointer
    
    参考: https://langchain-ai.github.io/langgraph/concepts/langgraph_server/
    """
    # 为 API Server 创建不带默认 checkpointer 的图
    api_graph = IntelligentSQLGraph(use_default_checkpointer=False)
    return api_graph.graph


def graph_with_checkpointer():
    """
    带 checkpointer 的图工厂函数 - 供直接调用使用
    
    用于非 LangGraph API Server 场景，确保 interrupt 机制能正常工作
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
    "graph_with_checkpointer",
    "warmup_services",
    "warmup_services_sync",
    "_detect_intent",
]
