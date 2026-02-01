"""
智能SQL代理图 - 高级接口和图构建

增强功能：
- 意图识别与路由
- Dashboard Insight 支持
- 澄清机制集成
- 多轮对话上下文改写
- QA 样本检索增强（可配置）
"""
from typing import Dict, Any, Optional, Literal, List
import logging

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.errors import GraphInterrupt
from langchain_core.messages import HumanMessage, BaseMessage

from app.core.state import SQLMessageState
from app.agents.agents.supervisor_agent import create_intelligent_sql_supervisor
from app.agents.agents.intent_detection_agent import (
    detect_intent_fast,
    detect_intent,
    IntentResult,
    QueryType,
)
from app.agents.utils.context_rewriter import (
    process_context_rewrite,
    is_follow_up_query,
)
from app.agents.utils.skill_routing import (
    SkillRoutingResult,
    perform_skill_routing,
    format_skill_context_for_prompt,
)

logger = logging.getLogger(__name__)


# ===== QA 样本检索配置 =====
# 默认配置（当数据库配置不可用时使用）
QA_SAMPLE_CONFIG_DEFAULT = {
    "enabled": True,  # 全局开关：是否启用 QA 样本检索
    "top_k": 3,  # 最多检索的样本数量
    "min_similarity": 0.6,  # 最低相似度阈值
    "timeout_seconds": 5,  # 检索超时时间
}


def get_qa_sample_config() -> Dict[str, Any]:
    """从数据库获取 QA 样本检索配置，失败时使用默认值"""
    try:
        from app.db.session import SessionLocal
        from app.crud import system_config
        
        db = SessionLocal()
        try:
            config = system_config.get_qa_sample_config(db)
            logger.debug(f"[QA配置] 从数据库获取: {config}")
            return config
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[QA配置] 无法从数据库获取配置: {e}, 使用默认值")
        return QA_SAMPLE_CONFIG_DEFAULT


async def retrieve_qa_samples(
    query: str,
    connection_id: int,
    schema_context: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    QA 样本检索 - 可配置的轻量级检索
    
    Args:
        query: 用户查询
        connection_id: 数据库连接 ID（按连接隔离样本）
        schema_context: 模式上下文
        config: 可选的配置覆盖
        
    Returns:
        样本检索结果，包含 qa_pairs 列表
    """
    import asyncio
    
    # 从数据库获取配置
    cfg = config or get_qa_sample_config()
    
    # 检查是否启用
    if not cfg.get("enabled", True):
        logger.debug("QA 样本检索已禁用")
        return {"qa_pairs": [], "enabled": False}
    
    try:
        from app.services.hybrid_retrieval.engine.engine_pool import HybridRetrievalEnginePool
        
        logger.info(f"[QA样本检索] 开始检索 - connection_id={connection_id}, query='{query[:50]}...'")
        
        # 使用超时保护
        timeout = cfg.get("timeout_seconds", 5)
        qa_samples = await asyncio.wait_for(
            HybridRetrievalEnginePool.quick_retrieve(
                user_query=query,
                schema_context=schema_context,
                connection_id=connection_id,
                top_k=cfg.get("top_k", 3),
                min_similarity=cfg.get("min_similarity", 0.6)
            ),
            timeout=timeout
        )
        
        logger.info(f"[QA样本检索] ✓ 完成 - 找到 {len(qa_samples)} 个高质量样本")
        
        return {
            "qa_pairs": qa_samples,
            "enabled": True,
            "connection_id": connection_id,
            "count": len(qa_samples)
        }
        
    except asyncio.TimeoutError:
        logger.warning(f"[QA样本检索] ⚠ 超时 ({cfg.get('timeout_seconds', 5)}s)")
        return {"qa_pairs": [], "enabled": True, "timeout": True}
        
    except Exception as e:
        logger.warning(f"[QA样本检索] ⚠ 检索失败: {e}")
        return {"qa_pairs": [], "enabled": True, "error": str(e)}


def extract_connection_id_from_messages(messages) -> Optional[int]:
    """从消息中提取连接ID（不设默认值，由前端传入）"""
    connection_id = None

    # 查找最新的人类消息中的连接ID
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    break

    return connection_id


def extract_user_query(state: SQLMessageState) -> str:
    """从状态中提取用户查询"""
    # 优先使用 enriched_query（多轮对话改写后的查询）
    if state.get("enriched_query"):
        return state["enriched_query"]
    
    # 从消息中获取
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            content = msg.content
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            return content
    
    return ""


class IntelligentSQLGraph:
    """
    智能SQL代理图 - 高级接口
    
    功能：
    - 意图识别：自动检测查询类型并路由
    - SQL 处理：使用 supervisor 协调 SQL 生成/验证/执行
    - Dashboard Insight：支持仪表盘洞察分析
    - 澄清机制：支持查询澄清和确认
    - 自定义 Agent：支持用户配置的自定义数据分析 Agent
    """

    def __init__(
        self, 
        enable_clarification: bool = True,
        custom_analyst_id: Optional[int] = None
    ):
        """
        初始化智能SQL图
        
        Args:
            enable_clarification: 是否启用澄清机制
            custom_analyst_id: 自定义数据分析 Agent ID（可选）
        """
        self.enable_clarification = enable_clarification
        self.custom_analyst_id = custom_analyst_id
        self.supervisor_agent = create_intelligent_sql_supervisor(
            enable_clarification, 
            custom_analyst_id
        )
        self.graph = self.supervisor_agent.supervisor
        self._dashboard_graph = None

    @property
    def dashboard_graph(self):
        """延迟加载 Dashboard Insight 图"""
        if self._dashboard_graph is None:
            try:
                from app.agents.dashboard_insight_graph import create_dashboard_insight_graph
                self._dashboard_graph = create_dashboard_insight_graph()
            except ImportError as e:
                logger.warning(f"Dashboard Insight 图不可用: {e}")
        return self._dashboard_graph

    async def detect_intent(self, query: str) -> IntentResult:
        """
        检测查询意图
        
        Args:
            query: 用户查询
            
        Returns:
            IntentResult: 意图识别结果
        """
        # 先尝试快速检测
        fast_result = detect_intent_fast(query)
        if fast_result:
            logger.info(f"快速意图检测: {fast_result.query_type.value} -> {fast_result.route}")
            return fast_result
        
        # 使用 LLM 深度分析
        result = await detect_intent(query)
        logger.info(f"LLM 意图检测: {result.query_type.value} -> {result.route}")
        return result

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
        处理SQL查询（带意图路由和多轮对话改写）
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID（必须由调用方传入）
            messages: 消息历史（用于多轮对话上下文改写）
            agent_id: 自定义数据分析 Agent ID（可选，覆盖实例配置）
            
        Returns:
            处理结果
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
            # 0. 多轮对话上下文改写
            enriched_query = query
            query_rewritten = False
            
            if messages and len(messages) > 1:
                rewrite_result = await process_context_rewrite(
                    query=query,
                    messages=messages,
                    connection_id=connection_id
                )
                enriched_query = rewrite_result["enriched_query"]
                query_rewritten = rewrite_result["query_rewritten"]
                
                if query_rewritten:
                    logger.info(f"多轮对话改写: '{query}' → '{enriched_query}'")
            
            # 1. 意图识别（使用改写后的查询）
            intent = await self.detect_intent(enriched_query)
            logger.info(f"意图识别结果: {intent.query_type.value}, 路由: {intent.route}")
            
            # 2. 根据意图路由
            if intent.route == "general_chat":
                return await self._handle_general_chat(enriched_query, intent)
            
            # SQL 相关路由需要 connection_id
            if not connection_id:
                return {
                    "success": False,
                    "error": "请先选择一个数据库连接",
                    "final_stage": "error"
                }
            
            if intent.route == "dashboard_insight":
                return await self._handle_dashboard_insight(enriched_query, connection_id, intent)
            
            else:  # sql_supervisor
                result = await self._handle_sql_query(
                    enriched_query,
                    connection_id,
                    intent,
                    thread_id=thread_id,
                    tenant_id=tenant_id
                )
                # 添加改写信息
                result["original_query"] = query
                result["enriched_query"] = enriched_query
                result["query_rewritten"] = query_rewritten
                return result
                
        except GraphInterrupt:
            # 关键：interrupt() 抛出的异常必须传播出去，让图暂停
            raise
        except Exception as e:
            logger.error(f"处理查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "final_stage": "error"
            }

    async def _handle_general_chat(
        self, 
        query: str, 
        intent: IntentResult
    ) -> Dict[str, Any]:
        """处理闲聊类查询"""
        logger.info("处理闲聊查询")
        
        # 简单的闲聊响应
        chat_responses = {
            "你好": "你好！我是智能数据查询助手，可以帮你查询数据库中的数据，生成 SQL，或者分析数据趋势。有什么可以帮到你的？",
            "hello": "Hello! I'm an intelligent data query assistant. How can I help you today?",
            "hi": "Hi! How can I assist you with your data queries?",
            "帮助": "我可以帮你：\n1. 用自然语言查询数据库\n2. 生成和执行 SQL\n3. 分析数据趋势和洞察\n4. 生成数据可视化图表\n\n请告诉我你想查询什么数据？",
            "功能": "我的主要功能包括：\n- 🔍 智能 SQL 生成\n- ✅ SQL 验证和优化\n- 📊 数据可视化\n- 📈 Dashboard 洞察分析\n- 💬 多轮对话支持",
        }
        
        query_lower = query.lower().strip()
        response = chat_responses.get(query_lower, "请告诉我你想查询什么数据？例如：'查询上月销售额' 或 '显示客户订单趋势'")
        
        return {
            "success": True,
            "result": {
                "response": response,
                "query_type": intent.query_type.value,
            },
            "final_stage": "completed",
            "is_chat": True
        }

    async def _handle_dashboard_insight(
        self, 
        query: str, 
        connection_id: int,
        intent: IntentResult
    ) -> Dict[str, Any]:
        """处理 Dashboard 洞察分析"""
        logger.info("处理 Dashboard Insight 查询")
        
        if self.dashboard_graph is None:
            # 如果 Dashboard 图不可用，回退到普通 SQL 查询
            logger.warning("Dashboard Insight 不可用，回退到 SQL 查询")
            return await self._handle_sql_query(query, connection_id, intent)
        
        try:
            # 调用 Dashboard Insight 图
            result = await self.dashboard_graph.process({
                "user_intent": query,
                "connection_id": connection_id,
                "use_graph_relationships": True,
            })
            
            return {
                "success": True,
                "result": result,
                "final_stage": "dashboard_completed",
                "is_dashboard": True,
                "query_type": intent.query_type.value,
            }
            
        except Exception as e:
            logger.error(f"Dashboard Insight 处理失败: {e}")
            # 回退到普通 SQL 查询
            return await self._handle_sql_query(query, connection_id, intent)

    async def _handle_sql_query(
        self, 
        query: str, 
        connection_id: int,
        intent: IntentResult,
        thread_id: Optional[str] = None,
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """处理 SQL 查询（使用 supervisor）"""
        logger.info("处理 SQL 查询")
        
        # 1. Skill 路由（零配置兼容）
        skill_result = await perform_skill_routing(query, connection_id)
        
        if skill_result.enabled:
            logger.info(f"Skill 路由: {skill_result.reasoning}")
        else:
            logger.info(f"Skill 路由: {skill_result.reasoning}，使用全库模式")
        
        # 2. 初始化状态
        initial_state = SQLMessageState(
            messages=[{"role": "user", "content": query}],
            connection_id=connection_id,
            current_stage="schema_analysis",
            retry_count=0,
            max_retries=3,
            error_history=[]
        )

        if thread_id:
            initial_state["thread_id"] = thread_id
        if tenant_id is not None:
            initial_state["tenant_id"] = tenant_id
        
        # 3. 添加意图信息
        initial_state["query_type"] = intent.query_type.value
        initial_state["query_complexity"] = intent.complexity
        initial_state["needs_clarification"] = intent.needs_clarification
        
        # 如果有子查询（多步查询），添加到状态
        if intent.sub_queries:
            initial_state["sub_queries"] = intent.sub_queries
        
        # 4. 添加 Skill 上下文
        initial_state["skill_context"] = {
            "enabled": skill_result.enabled,
            "matched_skills": skill_result.matched_skills,
            "schema_info": skill_result.schema_info,
            "business_rules": skill_result.business_rules,
            "join_rules": skill_result.join_rules,
            "strategy_used": skill_result.strategy_used,
            "reasoning": skill_result.reasoning,
            "prompt_context": format_skill_context_for_prompt(skill_result),
        }
        
        # 5. QA 样本检索（可配置 - 从数据库读取配置）
        qa_config = get_qa_sample_config()
        if qa_config.get("enabled", True):
            # 构建模式上下文（用于样本检索）
            schema_context = {
                "tables": skill_result.schema_info.get("tables", []) if skill_result.schema_info else [],
                "user_query": query
            }
            
            sample_result = await retrieve_qa_samples(
                query=query,
                connection_id=connection_id,
                schema_context=schema_context
            )
            
            # 将样本结果注入状态
            initial_state["sample_retrieval_result"] = sample_result
            
            if sample_result.get("qa_pairs"):
                logger.info(f"[QA样本] 注入 {len(sample_result['qa_pairs'])} 个样本到 SQL Generator")
        else:
            initial_state["sample_retrieval_result"] = {"qa_pairs": [], "enabled": False}
        
        # 6. 委托给 supervisor 处理
        result = await self.supervisor_agent.supervise(initial_state, thread_id=thread_id)

        if result.get("success"):
            return {
                "success": True,
                "result": result.get("result"),
                "final_stage": result.get("result", {}).get("current_stage", "completed"),
                "query_type": intent.query_type.value,
                "clarification_used": result.get("clarification_used", False),
                "skill_used": skill_result.primary_skill_name,
            }
        else:
            return {
                "success": False,
                "error": result.get("error"),
                "final_stage": "error",
                "query_type": intent.query_type.value
            }

    @property
    def worker_agents(self):
        """获取工作代理列表（为了向后兼容）"""
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
    
    Args:
        query: 用户查询
        connection_id: 数据库连接ID（必须由调用方传入）
        enable_clarification: 是否启用澄清机制
        agent_id: 自定义数据分析 Agent ID（可选）
    """
    graph = create_intelligent_sql_graph(enable_clarification, agent_id)
    return await graph.process_query(query, connection_id)


# 创建全局实例（为了向后兼容）
_global_graph = None


def get_global_graph() -> IntelligentSQLGraph:
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph


# 导出 graph 用于 LangGraph 服务
graph = get_global_graph().graph


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 创建图实例
        graph_instance = create_intelligent_sql_graph()
        print(f"智能SQL图创建成功: {type(graph_instance).__name__}")
        print(f"Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
        print(f"工作代理数量: {len(graph_instance.worker_agents)}")
        
        # 测试意图识别
        test_queries = [
            "你好",
            "查询销售额",
            "显示 dashboard 数据洞察",
            "对比上月和本月的销售额趋势",
        ]
        
        for query in test_queries:
            intent = await graph_instance.detect_intent(query)
            print(f"查询: {query}")
            print(f"  -> 类型: {intent.query_type.value}, 路由: {intent.route}, 复杂度: {intent.complexity}")
    
    asyncio.run(test())
