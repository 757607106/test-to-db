"""
SQL生成代理
负责根据模式信息和用户查询生成高质量的SQL语句

优化历史:
- 2026-01-19: 集成样本检索功能，自动从 QA 库中检索相似样本
  - 避免了独立 sample_retrieval_agent 的 ReAct 调度延迟（原 2+ 分钟）
  - 先快速检查是否有样本，没有则跳过检索步骤
- 2026-01-21: 支持快速模式 (Fast Mode) - 借鉴官方简洁性思想
  - 当 skip_sample_retrieval=True 时，跳过样本检索，直接生成 SQL
"""
from typing import Dict, Any, List
import logging
import asyncio
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.schemas.agent_message import ToolResponse, SQLGenerationResult

logger = logging.getLogger(__name__)


def _fetch_qa_samples_sync(user_query: str, schema_info: Dict[str, Any], connection_id: int) -> List[Dict[str, Any]]:
    """
    同步包装器：获取 QA 样本
    
    在同步上下文中安全地调用异步检索方法
    根据配置决定是否启用样本召回
    """
    try:
        from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
        from app.core.config import settings
        
        # 检查是否启用QA样本召回
        if not settings.QA_SAMPLE_ENABLED:
            logger.info("QA样本召回已禁用 (QA_SAMPLE_ENABLED=false)")
            return []
        
        logger.info(f"开始QA样本召回 - top_k={settings.QA_SAMPLE_TOP_K}, "
                   f"min_similarity={settings.QA_SAMPLE_MIN_SIMILARITY}, "
                   f"timeout={settings.QA_SAMPLE_TIMEOUT}s")
        
        # 在新的事件循环中运行异步代码
        def _run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    HybridRetrievalEnginePool.quick_retrieve(
                        user_query=user_query,
                        schema_context=schema_info,
                        connection_id=connection_id,
                        top_k=settings.QA_SAMPLE_TOP_K,
                        min_similarity=settings.QA_SAMPLE_MIN_SIMILARITY
                    )
                )
            finally:
                loop.close()
        
        # 检查是否在事件循环中
        try:
            loop = asyncio.get_running_loop()
            # 有运行中的事件循环，使用线程池
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_run_async)
                samples = future.result(timeout=settings.QA_SAMPLE_TIMEOUT)
                
                # 根据配置过滤样本
                filtered_samples = _filter_qa_samples(samples)
                logger.info(f"QA样本召回成功: 原始{len(samples)}个, 过滤后{len(filtered_samples)}个")
                return filtered_samples
        except RuntimeError:
            # 没有运行中的事件循环
            samples = _run_async()
            filtered_samples = _filter_qa_samples(samples)
            logger.info(f"QA样本召回成功: 原始{len(samples)}个, 过滤后{len(filtered_samples)}个")
            return filtered_samples
            
    except Exception as e:
        logger.warning(f"QA样本召回失败: {e}, 将使用基础模式生成SQL")
        if settings.QA_SAMPLE_FAST_FALLBACK:
            return []
        raise


def _filter_qa_samples(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据配置过滤QA样本
    """
    from app.core.config import settings
    
    if not samples:
        return []
    
    filtered = samples
    
    # 过滤：只保留验证过的样本
    if settings.QA_SAMPLE_VERIFIED_ONLY:
        filtered = [s for s in filtered if s.get('verified', False)]
        logger.debug(f"验证过滤: {len(samples)} -> {len(filtered)}")
    
    # 过滤：最低成功率
    if settings.QA_SAMPLE_MIN_SUCCESS_RATE > 0:
        filtered = [s for s in filtered if s.get('success_rate', 0) >= settings.QA_SAMPLE_MIN_SUCCESS_RATE]
        logger.debug(f"成功率过滤 (>={settings.QA_SAMPLE_MIN_SUCCESS_RATE}): {len(samples)} -> {len(filtered)}")
    
    return filtered


@tool
def generate_sql_query(
    user_query: str,
    schema_info: Dict[str, Any],
    value_mappings: Dict[str, Any] = None,
    db_type: str = "mysql",
    connection_id: int = None,
    sample_qa_pairs: List[Dict[str, Any]] = None
) -> ToolResponse:
    """
    根据用户查询和模式信息生成SQL语句
    
    自动集成样本检索：如果提供了 connection_id，会自动从 QA 库中检索相似样本。
    这避免了独立 sample_retrieval_agent 的 ReAct 调度延迟（原 2+ 分钟）。

    Args:
        user_query: 用户的自然语言查询
        schema_info: 数据库模式信息
        value_mappings: 值映射信息
        db_type: 数据库类型
        connection_id: 数据库连接ID（用于自动检索相关样本）
        sample_qa_pairs: 相关的SQL问答对样本（如果为空且有connection_id，会自动检索）

    Returns:
        ToolResponse: 生成的SQL语句和相关信息
    """
    try:
        # 自动检索样本：如果提供了 connection_id 且没有手动提供样本
        # ✅ 快速模式支持：通过参数控制是否跳过样本检索
        skip_sample = value_mappings.get("_skip_sample_retrieval", False) if value_mappings else False
        
        if connection_id and not sample_qa_pairs and not skip_sample:
            logger.info(f"Auto-fetching QA samples for connection_id={connection_id}")
            sample_qa_pairs = _fetch_qa_samples_sync(user_query, schema_info, connection_id)
            if sample_qa_pairs:
                logger.info(f"Found {len(sample_qa_pairs)} relevant QA samples")
            else:
                logger.info("No relevant QA samples found, proceeding without samples")
        elif skip_sample:
            logger.info("快速模式: 跳过样本检索")
        
        # 构建详细的上下文信息
        context = f"""
数据库类型: {db_type}

可用的表和字段信息:
{schema_info}
"""
        
        if value_mappings:
            context += f"""
值映射信息:
{value_mappings}
"""

        # 添加样本参考信息
        sample_context = ""
        if sample_qa_pairs:
            sample_context = "\n参考样本:\n"
            for i, sample in enumerate(sample_qa_pairs[:3], 1):  # 最多使用3个样本
                sample_context += f"""
样本{i}:
问题: {sample.get('question', '')}
SQL: {sample.get('sql', '')}
查询类型: {sample.get('query_type', '')}
成功率: {sample.get('success_rate', 0):.2f}
相似度: {sample.get('similarity', 0):.2f}
"""

        # 构建SQL生成提示
        prompt = f"""
基于以下信息生成SQL查询：

用户查询: {user_query}

{context}

{sample_context}

请生成一个准确、高效的SQL查询语句。要求：
1. 只返回SQL语句，不要其他解释
2. 确保语法正确
3. 使用适当的连接和过滤条件
4. 限制结果数量（除非用户明确要求全部数据）
5. 使用正确的值映射
6. 参考样本的SQL结构和模式，但要适应当前查询的具体需求
7. 优先参考高成功率的样本
"""
        
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 提取SQL语句
        sql_query = response.content.strip()
        
        # 简单的SQL清理
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        return ToolResponse(
            status="success",
            data={
                "sql_query": sql_query,
                "context_used": context
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


@tool
def generate_sql_with_samples(
    user_query: str,
    schema_info: Dict[str, Any],
    sample_qa_pairs: List[Dict[str, Any]],
    value_mappings: Dict[str, Any] = None
) -> ToolResponse:
    """
    基于样本生成高质量SQL查询

    Args:
        user_query: 用户的自然语言查询
        schema_info: 数据库模式信息
        sample_qa_pairs: 相关的SQL问答对样本
        value_mappings: 值映射信息

    Returns:
        ToolResponse: 生成的SQL语句和样本分析
    """
    try:
        if not sample_qa_pairs:
            # 如果没有样本，回退到基本生成
            return generate_sql_query(user_query, schema_info, value_mappings)

        # 过滤并分析最佳样本
        min_similarity_threshold = 0.6  # 与样本检索代理保持一致的阈值

        # 先过滤低质量样本
        high_quality_samples = [
            sample for sample in sample_qa_pairs
            if sample.get('final_score', 0) >= min_similarity_threshold
        ]

        if not high_quality_samples:
            # 如果没有高质量样本，回退到基本生成
            return generate_sql_query(user_query, schema_info, value_mappings)

        # 选择最佳样本
        best_samples = sorted(
            high_quality_samples,
            key=lambda x: (x.get('final_score', 0), x.get('success_rate', 0)),
            reverse=True
        )[:2]

        # 构建样本分析
        sample_analysis = "最相关的样本分析:\n"
        for i, sample in enumerate(best_samples, 1):
            sample_analysis += f"""
样本{i} (相关性: {sample.get('final_score', 0):.3f}):
- 问题: {sample.get('question', '')}
- SQL: {sample.get('sql', '')}
- 查询类型: {sample.get('query_type', '')}
- 成功率: {sample.get('success_rate', 0):.2f}
- 解释: {sample.get('explanation', '')}
"""

        # 构建增强的生成提示
        prompt = f"""
作为SQL专家，请基于以下信息生成高质量的SQL查询：

用户查询: {user_query}

数据库模式:
{schema_info}

{sample_analysis}

值映射信息:
{value_mappings if value_mappings else '无'}

请按照以下步骤生成SQL：
1. 分析用户查询的意图和需求
2. 参考最相关样本的SQL结构和模式
3. 根据当前数据库模式调整表名和字段名
4. 确保SQL语法正确且高效
5. 添加适当的限制条件

要求：
- 只返回最终的SQL语句
- 确保语法正确
- 参考样本的最佳实践
- 适应当前的数据库结构
- 优化查询性能
"""

        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = llm.invoke([HumanMessage(content=prompt)])

        # 清理SQL语句
        sql_query = response.content.strip()
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()

        return ToolResponse(
            status="success",
            data={
                "sql_query": sql_query,
                "samples_used": len(best_samples),
                "best_sample_score": best_samples[0].get('final_score', 0) if best_samples else 0,
                "sample_analysis": sample_analysis
            }
        )

    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


# ============================================================================
# 性能优化：已移除 SQL 优化工具以减少复杂度（2026-01-21）
# 移除的工具：
# - analyze_sql_optimization_need: SQL 优化需求分析
# - optimize_sql_query: SQL 查询优化
# - _get_optimization_reason: 优化原因生成
# 原因：这些工具实际使用频率极低，且增加了不必要的 LLM 调用
# ============================================================================


# ============================================================================
# 性能优化：注释掉 SQL 解释功能以减少 LLM 调用次数，提升响应速度
# 优化时间：2026-01-18
# 如需恢复此功能，取消下方注释即可
# ============================================================================
# @tool
# def explain_sql_query(sql_query: str) -> Dict[str, Any]:
#     """
#     解释SQL查询的逻辑和执行计划
#     
#     Args:
#         sql_query: SQL查询语句
#         
#     Returns:
#         SQL查询的解释和分析
#     """
#     try:
#         prompt = f"""
# 请详细解释以下SQL查询：
# 
# {sql_query}
# 
# 请提供：
# 1. 查询逻辑说明
# 2. 执行步骤分析
# 3. 可能的性能瓶颈
# 4. 结果集预期
# """
#         
#         llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
#         response = llm.invoke([HumanMessage(content=prompt)])
#         
#         return {
#             "success": True,
#             "explanation": response.content,
#             "sql_query": sql_query
#         }
#         
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e)
#         }


class SQLGeneratorAgent:
    """SQL生成代理"""

    def __init__(self):
        self.name = "sql_generator_agent"  # 添加name属性
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        
        # ✅ 使用 with_structured_output 确保跨模型一致性
        # 利用 Function Calling API 强制模型输出结构化格式
        # 支持 GPT-4, DeepSeek, Llama 3 等所有支持 function_calling 的模型
        try:
            self.structured_llm = self.llm.with_structured_output(
                SQLGenerationResult,
                method="function_calling"  # 使用原生 Function Calling API
            )
            logger.info("✅ SQL生成器已启用结构化输出（with_structured_output）")
        except Exception as e:
            # 如果模型不支持 with_structured_output，回退到普通模式
            logger.warning(f"⚠️  with_structured_output 不可用，回退到普通模式: {e}")
            self.structured_llm = None
        
        self.tools = [generate_sql_query, generate_sql_with_samples]
        # 性能优化：移除 explain_sql_query 以提升响应速度（2026-01-18）
        # , analyze_sql_optimization_need, optimize_sql_query
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示
        
        注意：简化流程后，SQL生成后直接执行，不再进行验证
        因此需要在生成时就确保SQL的高质量
        """
        return """你是一个专业的SQL生成专家。你的任务是：

1. 根据用户查询和数据库模式信息生成准确的SQL语句
2. 生成时就考虑SQL的正确性和安全性（因为不再有验证步骤）

智能工作流程：
1. 检查是否有样本检索结果
2. 如果有样本，优先使用 generate_sql_with_samples 工具
3. 如果没有样本，使用 generate_sql_query 工具生成基础SQL

SQL生成原则（重要 - 因为不再有验证步骤）：
- 确保语法绝对正确
- 使用适当的连接方式
- 应用正确的过滤条件
- 生成时就考虑基本性能优化
- 限制结果集大小（除非明确要求）
- 使用正确的值映射
- 充分利用样本提供的最佳实践
- 避免危险操作（DROP, DELETE, UPDATE等）

样本利用策略：
- 优先参考高相关性和高成功率的样本
- 学习样本的SQL结构和模式
- 适应当前查询的具体需求
- 保持SQL的正确性和效率

请始终生成高质量、可执行的SQL语句，并充分利用样本的指导作用。
记住：生成的SQL将直接执行，不会经过验证步骤，所以必须确保质量！"""

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL生成任务"""
        try:
            # 获取用户查询
            user_query = state["messages"][0].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取模式信息
            schema_info = state.get("schema_info")
            if not schema_info:
                # 从代理消息中提取模式信息
                schema_agent_result = state.get("agent_messages", {}).get("schema_agent")
                if schema_agent_result:
                    # 解析模式信息
                    schema_info = self._extract_schema_from_messages(schema_agent_result.get("messages", []))

            # 获取样本检索结果
            sample_retrieval_result = state.get("sample_retrieval_result")
            sample_qa_pairs = []
            if sample_retrieval_result and sample_retrieval_result.get("qa_pairs"):
                sample_qa_pairs = sample_retrieval_result["qa_pairs"]
            
            # 准备输入消息
            sample_info = ""
            if sample_qa_pairs:
                sample_info = f"\n样本数量: {len(sample_qa_pairs)}"
                if sample_retrieval_result.get("best_samples"):
                    best_sample = sample_retrieval_result["best_samples"][0]
                    sample_info += f"\n最佳样本相关性: {best_sample.get('final_score', 0):.3f}"

            messages = [
                HumanMessage(content=f"""
请为以下用户查询生成SQL语句：

用户查询: {user_query}
模式信息: {schema_info}
{sample_info}

请根据可用的样本生成、优化并解释SQL查询。
""")
            ]
            
            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 提取生成的SQL
            generated_sql = self._extract_sql_from_result(result)
            
            # 更新状态 - 简化流程：直接进入执行阶段，跳过验证
            state["generated_sql"] = generated_sql
            state["current_stage"] = "sql_execution"  # 修改：跳过sql_validation
            state["agent_messages"]["sql_generator"] = result
            
            return {
                "messages": result["messages"],
                "generated_sql": generated_sql,
                "current_stage": "sql_execution"  # 修改：跳过sql_validation
            }
            
        except Exception as e:
            # 记录错误
            error_info = {
                "stage": "sql_generation",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
            
            return {
                "messages": [AIMessage(content=f"SQL生成失败: {str(e)}")],
                "current_stage": "error_recovery"
            }
    
    def _extract_schema_from_messages(self, messages: List) -> Dict[str, Any]:
        """从消息中提取模式信息"""
        # 简化实现，实际应该更智能地解析
        for message in messages:
            if hasattr(message, 'content') and 'schema' in message.content.lower():
                return {"extracted": True, "content": message.content}
        return {}
    
    def _extract_sql_from_result(self, result: Dict[str, Any]) -> str:
        """从结果中提取SQL语句"""
        messages = result.get("messages", [])
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content
                # 简单的SQL提取逻辑
                if "SELECT" in content.upper():
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip().upper().startswith('SELECT'):
                            return line.strip()
        return ""


# 创建全局实例
sql_generator_agent = SQLGeneratorAgent()
