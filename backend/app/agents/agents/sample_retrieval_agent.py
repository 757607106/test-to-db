"""
样本检索代理
负责从混合检索服务中查询与用户问题相关的SQL问答对，为高质量SQL生成提供准确的样本提示
"""
from typing import Dict, Any, List, Optional
import asyncio
import logging
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.services.hybrid_retrieval_service import HybridRetrievalEngine, VectorServiceFactory, HybridRetrievalEnginePool
from app.services.text2sql_utils import analyze_query_with_llm
from app.schemas.agent_message import ToolResponse

# 配置日志
logger = logging.getLogger(__name__)


@tool
def retrieve_similar_qa_pairs(
    user_query: str,
    schema_context: Dict[str, Any],
    connection_id: Optional[int] = None,
    top_k: int = 5,
    timeout: int = 15  # 超时设置（秒）
) -> ToolResponse:
    """
    从混合检索服务中检索与用户查询相似的SQL问答对
    
    Args:
        user_query: 用户的自然语言查询
        schema_context: 数据库模式上下文信息
        connection_id: 数据库连接ID
        top_k: 返回的样本数量
        timeout: 超时时间（秒），默认15秒
        
    Returns:
        ToolResponse: 检索到的相似问答对列表和相关信息
    """
    logger.info(f"开始检索SQL样本 - 查询: '{user_query[:50]}...', connection_id: {connection_id}, top_k: {top_k}, timeout: {timeout}s")
    
    try:
        async def _do_retrieve():
            """执行实际的检索操作"""
            # 使用池化的检索引擎实例（避免重复初始化）
            logger.debug(f"正在从引擎池获取检索引擎实例 (connection_id={connection_id})...")
            
            try:
                # 从池中获取或创建引擎实例（自动处理初始化）
                engine = await HybridRetrievalEnginePool.get_engine(connection_id)
                logger.debug("成功获取检索引擎实例（已初始化）")
            except Exception as init_error:
                logger.error(f"获取检索引擎失败: {init_error}")
                # 如果获取失败，抛出详细错误
                raise RuntimeError(f"检索服务初始化失败 - {type(init_error).__name__}: {str(init_error)}")
            
            # 执行混合检索
            logger.debug(f"正在执行混合检索...")
            results = await engine.hybrid_retrieve(
                query=user_query,
                schema_context=schema_context,
                connection_id=connection_id,
                top_k=top_k
            )
            
            logger.debug(f"检索完成，找到 {len(results)} 个结果")
            return results
        
        async def _retrieve_with_timeout():
            """添加超时控制的检索"""
            try:
                return await asyncio.wait_for(_do_retrieve(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"检索超时（{timeout}秒）")
                raise
        
        # 运行异步检索 - 使用线程池避免阻塞事件循环
        import concurrent.futures
        
        def _run_in_new_loop():
            """在新的事件循环中运行异步代码"""
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(_retrieve_with_timeout())
            finally:
                new_loop.close()
        
        try:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 有运行中的事件循环，使用线程池执行避免阻塞
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_in_new_loop)
                    results = future.result(timeout=timeout + 5)  # 给线程池额外5秒
            except RuntimeError:
                # 没有运行中的事件循环，直接创建并运行
                results = _run_in_new_loop()
        except concurrent.futures.TimeoutError:
            logger.warning(f"检索在线程池中超时（{timeout + 5}秒）")
            raise asyncio.TimeoutError(f"检索超时（{timeout}秒）")
        
        # 格式化结果并过滤低质量样本
        formatted_results = []
        min_similarity_threshold = 0.6  # 最小相似度阈值

        for result in results:
            # 只保留相似度大于等于0.6的样本
            if result.final_score >= min_similarity_threshold:
                qa_pair = result.qa_pair
                formatted_results.append({
                    "id": qa_pair.id,
                    "question": qa_pair.question,
                    "sql": qa_pair.sql,
                    "query_type": qa_pair.query_type,
                    "difficulty_level": qa_pair.difficulty_level,
                    "success_rate": qa_pair.success_rate,
                    "verified": qa_pair.verified,
                    "semantic_score": result.semantic_score,
                    "structural_score": result.structural_score,
                    "pattern_score": result.pattern_score,
                    "final_score": result.final_score,
                    "explanation": result.explanation
                })

        logger.info(f"检索成功 - 找到 {len(formatted_results)} 个高质量样本（过滤前: {len(results)}个）")
        
        return ToolResponse(
            status="success",
            data={
                "qa_pairs": formatted_results,
                "total_found": len(formatted_results),
                "total_retrieved": len(results),
                "filtered_count": len(results) - len(formatted_results),
                "min_threshold": min_similarity_threshold,
                "query_analyzed": user_query
            },
            metadata={
                "execution_time": f"< {timeout}秒"
            }
        )
        
    except asyncio.TimeoutError:
        error_msg = f"检索超时（{timeout}秒）- 可能是数据库连接问题或服务响应慢"
        logger.error(error_msg)
        return ToolResponse(
            status="error",
            error=error_msg,
            data={"qa_pairs": []},
            metadata={
                "error_type": "TimeoutError",
                "suggestion": "请检查以下服务是否正常运行: 1) Milvus向量数据库 2) Neo4j图数据库 3) 网络连接",
                "troubleshooting": {
                    "check_milvus": "docker ps | grep milvus",
                    "check_neo4j": "docker ps | grep neo4j",
                    "timeout_seconds": timeout
                }
            }
        )
    
    except RuntimeError as e:
        # 初始化失败
        error_msg = str(e)
        logger.error(f"检索服务初始化失败: {error_msg}")
        return ToolResponse(
            status="error",
            error=error_msg,
            data={"qa_pairs": []},
            metadata={
                "error_type": "InitializationError",
                "suggestion": "检索服务初始化失败，请确认Milvus和Neo4j服务已启动",
                "troubleshooting": {
                    "milvus_status": "检查Milvus是否运行: docker ps | grep milvus",
                    "neo4j_status": "检查Neo4j是否运行: docker ps | grep neo4j",
                    "logs": "查看服务日志以获取更多信息"
                }
            }
        )
    
    except Exception as e:
        # 其他错误
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"检索失败 - {error_type}: {error_msg}", exc_info=True)
        return ToolResponse(
            status="error",
            error=error_msg,
            data={"qa_pairs": []},
            metadata={
                "error_type": error_type,
                "suggestion": f"检索过程中出现 {error_type} 错误，系统将使用基础模式生成SQL（无样本参考）",
                "details": "查看后端日志获取详细错误信息"
            }
        )


@tool
def analyze_sample_relevance(
    user_query: str,
    qa_pairs: List[Dict[str, Any]],
    schema_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    分析检索到的样本与用户查询的相关性，并提供使用建议
    
    Args:
        user_query: 用户的自然语言查询
        qa_pairs: 检索到的问答对列表
        schema_context: 数据库模式上下文
        
    Returns:
        样本相关性分析结果和使用建议
    """
    try:
        if not qa_pairs:
            return {
                "success": True,
                "analysis": "没有找到相关的样本",
                "recommendations": [],
                "best_samples": []
            }
        
        # 构建分析提示
        samples_text = "\n".join([
            f"样本{i+1}:\n问题: {qa['question']}\nSQL: {qa['sql']}\n相关性分数: {qa.get('final_score', 0):.3f}\n"
            for i, qa in enumerate(qa_pairs[:3])  # 只分析前3个样本
        ])
        
        prompt = f"""
        请分析以下SQL样本与用户查询的相关性：
        
        用户查询: {user_query}
        
        检索到的样本:
        {samples_text}
        
        数据库模式信息:
        {schema_context}
        
        请提供：
        1. 每个样本的相关性分析
        2. 最适合参考的样本推荐
        3. 如何利用这些样本生成更好的SQL
        4. 需要注意的差异点
        
        请以JSON格式返回分析结果。
        """
        
        llm = get_default_model()
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 提取最佳样本（基于分数排序）
        best_samples = sorted(qa_pairs, key=lambda x: x.get('final_score', 0), reverse=True)[:2]
        
        return {
            "success": True,
            "analysis": response.content,
            "best_samples": best_samples,
            "total_analyzed": len(qa_pairs),
            "recommendations": [
                "参考最高分样本的SQL结构",
                "注意表名和字段名的差异",
                "保持查询逻辑的一致性"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "analysis": "",
            "best_samples": []
        }


@tool
def extract_sql_patterns(qa_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    从检索到的问答对中提取SQL模式和最佳实践
    
    Args:
        qa_pairs: 检索到的问答对列表
        
    Returns:
        提取的SQL模式和最佳实践
    """
    try:
        if not qa_pairs:
            return {
                "success": True,
                "patterns": [],
                "best_practices": []
            }
        
        # 分析SQL模式
        patterns = []
        query_types = {}
        
        for qa in qa_pairs:
            query_type = qa.get('query_type', 'UNKNOWN')
            if query_type not in query_types:
                query_types[query_type] = []
            query_types[query_type].append(qa)
        
        # 提取每种查询类型的模式
        for qtype, samples in query_types.items():
            if samples:
                best_sample = max(samples, key=lambda x: x.get('success_rate', 0))
                patterns.append({
                    "query_type": qtype,
                    "example_sql": best_sample.get('sql', ''),
                    "example_question": best_sample.get('question', ''),
                    "success_rate": best_sample.get('success_rate', 0),
                    "sample_count": len(samples)
                })
        
        # 生成最佳实践建议
        best_practices = []
        
        # 基于成功率高的样本提取实践
        high_success_samples = [qa for qa in qa_pairs if qa.get('success_rate', 0) > 0.8]
        if high_success_samples:
            best_practices.append("参考高成功率样本的SQL结构")
            best_practices.append("使用验证过的查询模式")
        
        # 基于验证状态
        verified_samples = [qa for qa in qa_pairs if qa.get('verified', False)]
        if verified_samples:
            best_practices.append("优先参考已验证的SQL样本")
        
        return {
            "success": True,
            "patterns": patterns,
            "best_practices": best_practices,
            "pattern_count": len(patterns),
            "high_quality_samples": len(high_success_samples)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patterns": [],
            "best_practices": []
        }


class SampleRetrievalAgent:
    """样本检索代理"""

    def __init__(self):
        self.name = "sample_retrieval_agent"
        self.llm = get_default_model()
        self.tools = [
            retrieve_similar_qa_pairs,
            analyze_sample_relevance,
            extract_sql_patterns
        ]

        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )

    def _create_system_prompt(self) -> str:
        """创建系统提示
        
        注意：此Agent已被禁用，样本检索功能已集成到sql_generator_agent中
        保留此代码用于向后兼容和未来可能的独立使用场景
        """
        return """你是一个专业的SQL样本检索专家。

**核心职责**: 检索与用户查询相关的高质量SQL问答对

**工作流程**:
1. 使用 retrieve_similar_qa_pairs 工具检索样本
2. 如果有高质量样本，使用 analyze_sample_relevance 分析
3. **只返回样本信息，不生成SQL**

**质量控制**:
- 只保留相似度 >= 0.6 的样本
- 没有高质量样本时直接结束

**快速降级策略**:
- 检索失败或超时时，立即结束
- 不要因为检索问题阻塞查询流程

**禁止的行为**:
- ❌ 不要生成SQL语句
- ❌ 不要重复调用工具
- ❌ 不要进行繁复的分析

**输出格式**: 只返回样本列表和相关性分析"""

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理样本检索任务"""
        import time
        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_sql_step_event, create_similar_questions_event
        
        # 获取 stream writer
        try:
            writer = get_stream_writer()
        except Exception:
            writer = None
        
        try:
            # 发送 few_shot 步骤开始事件
            step_start_time = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="few_shot",
                    status="running",
                    result=None,
                    time_ms=0
                ))
            
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
                    schema_info = self._extract_schema_from_messages(schema_agent_result.get("messages", []))

            # 构建模式上下文
            schema_context = {
                "tables": schema_info.get("tables", []) if schema_info else [],
                "user_query": user_query
            }

            # 准备输入消息
            messages = [
                HumanMessage(content=f"""
请为以下用户查询检索相关的SQL样本：

用户查询: {user_query}
模式信息: {schema_info}
连接ID: {state.get('connection_id', 15)}

请先检索样本，然后根据检索结果智能决定是否继续分析：
- 如果没有检索到样本（total_found = 0），直接结束
- 如果检索到的样本相似度都低于0.6，直接结束
- 只有在有高质量样本时才继续分析和提取模式
""")
            ]

            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })

            # 提取样本检索结果
            sample_results = self._extract_samples_from_result(result)
            
            # 计算耗时并发送完成事件
            elapsed_ms = int((time.time() - step_start_time) * 1000)
            qa_pairs = sample_results.get("qa_pairs", [])
            if writer:
                writer(create_sql_step_event(
                    step="few_shot",
                    status="completed",
                    result=f"检索到 {len(qa_pairs)} 个相关样本",
                    time_ms=elapsed_ms
                ))
                
                # 发送相似问题事件
                similar_questions = []
                for qa in qa_pairs[:5]:  # 最多5个相似问题
                    question = qa.get("question", "")
                    if question:
                        similar_questions.append(question)
                
                if similar_questions:
                    writer(create_similar_questions_event(
                        questions=similar_questions
                    ))

            # 更新状态
            state["sample_retrieval_result"] = sample_results
            state["current_stage"] = "sql_generation"
            state["agent_messages"]["sample_retrieval"] = result

            return {
                "messages": result["messages"],
                "sample_retrieval_result": sample_results,
                "current_stage": "sql_generation"
            }

        except Exception as e:
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="few_shot",
                    status="error",
                    result=str(e),
                    time_ms=0
                ))
            
            # 记录错误
            error_info = {
                "stage": "sample_retrieval",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }

            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"

            return {
                "messages": [AIMessage(content=f"样本检索失败: {str(e)}")],
                "current_stage": "error_recovery"
            }

    def _extract_schema_from_messages(self, messages: List) -> Dict[str, Any]:
        """从消息中提取模式信息"""
        # 简化的模式信息提取逻辑
        for message in messages:
            if hasattr(message, 'content') and 'tables' in str(message.content).lower():
                # 这里可以添加更复杂的解析逻辑
                return {"tables": []}
        return {"tables": []}

    def _extract_samples_from_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """从代理结果中提取样本信息"""
        # 简化的样本提取逻辑
        messages = result.get("messages", [])
        
        sample_data = {
            "qa_pairs": [],
            "patterns": [],
            "best_practices": [],
            "analysis": ""
        }
        
        # 从最后一条消息中提取信息
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                content = str(last_message.content)
                # 这里可以添加更复杂的解析逻辑来提取结构化数据
                sample_data["analysis"] = content
        
        return sample_data


# 创建代理实例
sample_retrieval_agent = SampleRetrievalAgent()
