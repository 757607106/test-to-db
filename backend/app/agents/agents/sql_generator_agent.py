"""
SQL 生成代理 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用 InjectedState 注入状态参数
2. 工具返回标准 JSON 格式
3. 使用 with_structured_output 进行结构化输出

优化历史:
- 2026-01-19: 集成样本检索功能
- 2026-01-21: 支持快速模式 (Fast Mode)
- 2026-01-22: 使用 InjectedState 优化工具设计
- 2026-01-22: 修复异步调用问题，避免嵌套事件循环
"""
from typing import Dict, Any, List, Annotated, Optional
import logging
import json
import time

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from pydantic import BaseModel, Field

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.core.message_utils import generate_tool_call_id

logger = logging.getLogger(__name__)


# ============================================================================
# 结构化输出 Schema
# ============================================================================

class SQLGenerationResult(BaseModel):
    """SQL 生成结果 - 用于 with_structured_output"""
    sql_query: str = Field(description="生成的 SQL 查询语句")
    explanation: Optional[str] = Field(default=None, description="SQL 生成的简要说明")
    confidence: float = Field(default=0.8, ge=0, le=1, description="生成置信度 (0-1)")


# ============================================================================
# 样本检索辅助函数
# ============================================================================

async def _fetch_qa_samples_async(
    user_query: str, 
    schema_info: Dict[str, Any], 
    connection_id: int
) -> List[Dict[str, Any]]:
    """
    异步获取 QA 样本 (修复异步问题)
    
    注意: 使用纯异步实现，避免在异步环境中创建新事件循环
    """
    try:
        from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
        from app.core.config import settings
        
        if not settings.QA_SAMPLE_ENABLED:
            logger.info("QA 样本召回已禁用")
            return []
        
        logger.info(f"开始 QA 样本召回 - top_k={settings.QA_SAMPLE_TOP_K}")
        
        samples = await HybridRetrievalEnginePool.quick_retrieve(
            user_query=user_query,
            schema_context=schema_info,
            connection_id=connection_id,
            top_k=settings.QA_SAMPLE_TOP_K,
            min_similarity=settings.QA_SAMPLE_MIN_SIMILARITY
        )
        
        # 过滤样本
        filtered_samples = _filter_qa_samples(samples)
        logger.info(f"QA 样本召回成功: 原始 {len(samples)} 个, 过滤后 {len(filtered_samples)} 个")
        return filtered_samples
        
    except Exception as e:
        logger.warning(f"QA 样本召回失败: {e}")
        return []


def _filter_qa_samples(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """根据配置过滤 QA 样本"""
    from app.core.config import settings
    
    if not samples:
        return []
    
    filtered = samples
    
    if settings.QA_SAMPLE_VERIFIED_ONLY:
        filtered = [s for s in filtered if s.get('verified', False)]
    
    if settings.QA_SAMPLE_MIN_SUCCESS_RATE > 0:
        filtered = [s for s in filtered if s.get('success_rate', 0) >= settings.QA_SAMPLE_MIN_SUCCESS_RATE]
    
    return filtered


# ============================================================================
# 工具定义 (使用 InjectedState)
# ============================================================================

@tool
def generate_sql_query(
    user_query: str,
    schema_info: str,
    state: Annotated[dict, InjectedState],
    value_mappings: Optional[str] = None,
    sample_qa_pairs: Optional[str] = None,
    db_type: str = "mysql"
) -> str:
    """
    根据用户查询和模式信息生成 SQL 语句（纯同步，无嵌套事件循环）
    
    Args:
        user_query: 用户的自然语言查询
        schema_info: JSON 格式的数据库模式信息
        state: 注入的状态 (自动获取 connection_id, skip_sample_retrieval 等)
        value_mappings: JSON 格式的值映射信息 (可选)
        sample_qa_pairs: JSON 格式的预获取的 QA 样本 (可选，由 process 方法异步获取后传入)
        db_type: 数据库类型
        
    Returns:
        str: JSON 格式的生成结果，包含 SQL 语句
        
    注意:
        - 使用 InjectedState 自动获取 connection_id 和快速模式设置
        - 样本由调用方异步预获取后传入，避免嵌套事件循环问题
    """
    try:
        # 从状态获取配置
        connection_id = state.get("connection_id")
        
        # 解析输入
        schema_data = json.loads(schema_info) if isinstance(schema_info, str) else schema_info
        mappings_data = json.loads(value_mappings) if value_mappings and isinstance(value_mappings, str) else value_mappings
        samples = json.loads(sample_qa_pairs) if sample_qa_pairs and isinstance(sample_qa_pairs, str) else (sample_qa_pairs or [])
        
        # 构建上下文
        context = f"""
数据库类型: {db_type}

可用的表和字段信息:
{json.dumps(schema_data, ensure_ascii=False, indent=2)}
"""
        
        if mappings_data:
            context += f"""
值映射信息:
{json.dumps(mappings_data, ensure_ascii=False, indent=2)}
"""
        
        # 添加样本参考
        sample_context = ""
        if samples:
            sample_context = "\n参考样本:\n"
            for i, sample in enumerate(samples[:3], 1):
                sample_context += f"""
样本{i}:
问题: {sample.get('question', '')}
SQL: {sample.get('sql', '')}
相似度: {sample.get('similarity', 0):.2f}
"""
        
        # 检查是否有错误恢复上下文（从状态中获取，如果有的话）
        error_recovery_hint = ""
        if state.get("error_recovery_context"):
            error_ctx = state.get("error_recovery_context", {})
            failed_sql = error_ctx.get("failed_sql", "")
            error_message = error_ctx.get("error_message", "")
            error_type = error_ctx.get("error_type", "")
            recovery_steps = error_ctx.get("recovery_steps", [])
            
            if failed_sql or error_message:
                error_recovery_hint = f"""
⚠️ 重要提示：上一次生成的 SQL 执行失败，请避免相同错误！

失败的 SQL:
```sql
{failed_sql}
```

错误信息: {error_message}
错误类型: {error_type}

修复建议:
{chr(10).join(f"- {step}" for step in recovery_steps) if recovery_steps else "- 检查列名和表名是否正确" + chr(10) + "- 避免在子查询中引用外部别名" + chr(10) + "- 使用更简单的 SQL 结构"}

请根据以上信息，生成一个修正后的 SQL 查询。
"""
        
        # 构建 SQL 生成提示
        prompt = f"""
基于以下信息生成 SQL 查询：

用户查询: {user_query}

{context}
{sample_context}
{error_recovery_hint}

请生成一个准确、高效的 SQL 查询语句。要求：
1. 只返回 SQL 语句，不要其他解释
2. 确保语法正确
3. 使用适当的连接和过滤条件
4. 限制结果数量（除非用户明确要求全部数据）
5. 使用正确的值映射
6. 【重要】避免在子查询的 WHERE 子句中引用外部查询的列别名
7. 【重要】如果需要关联子查询，确保正确使用表别名
"""
        
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 提取 SQL 语句
        sql_query = response.content.strip()
        
        # 清理 SQL
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        return json.dumps({
            "success": True,
            "sql_query": sql_query,
            "samples_used": len(samples),
            "context_used": len(context)
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"SQL 生成失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
def generate_sql_with_samples(
    user_query: str,
    schema_info: str,
    sample_qa_pairs: str,
    value_mappings: Optional[str] = None
) -> str:
    """
    基于样本生成高质量 SQL 查询
    
    Args:
        user_query: 用户的自然语言查询
        schema_info: JSON 格式的数据库模式信息
        sample_qa_pairs: JSON 格式的相关 SQL 问答对样本
        value_mappings: JSON 格式的值映射信息 (可选)
        
    Returns:
        str: JSON 格式的生成结果
    """
    try:
        # 解析输入
        samples = json.loads(sample_qa_pairs) if isinstance(sample_qa_pairs, str) else sample_qa_pairs
        
        if not samples:
            # 回退到基本生成
            return generate_sql_query.invoke({
                "user_query": user_query,
                "schema_info": schema_info,
                "value_mappings": value_mappings
            })
        
        # 过滤并分析最佳样本
        high_quality_samples = [
            s for s in samples
            if s.get('final_score', s.get('similarity', 0)) >= 0.6
        ]
        
        if not high_quality_samples:
            return generate_sql_query.invoke({
                "user_query": user_query,
                "schema_info": schema_info,
                "value_mappings": value_mappings
            })
        
        # 选择最佳样本
        best_samples = sorted(
            high_quality_samples,
            key=lambda x: (x.get('final_score', x.get('similarity', 0)), x.get('success_rate', 0)),
            reverse=True
        )[:2]
        
        # 构建样本分析
        sample_analysis = "最相关的样本分析:\n"
        for i, sample in enumerate(best_samples, 1):
            sample_analysis += f"""
样本{i} (相关性: {sample.get('final_score', sample.get('similarity', 0)):.3f}):
- 问题: {sample.get('question', '')}
- SQL: {sample.get('sql', '')}
"""
        
        # 解析 schema
        schema_data = json.loads(schema_info) if isinstance(schema_info, str) else schema_info
        mappings_data = json.loads(value_mappings) if value_mappings else None
        
        # 构建增强的生成提示
        prompt = f"""
作为 SQL 专家，请基于以下信息生成高质量的 SQL 查询：

用户查询: {user_query}

数据库模式:
{json.dumps(schema_data, ensure_ascii=False, indent=2)}

{sample_analysis}

值映射信息:
{json.dumps(mappings_data, ensure_ascii=False, indent=2) if mappings_data else '无'}

请参考样本的 SQL 结构，生成适合当前查询的 SQL。
要求：只返回 SQL 语句，不要其他内容。
"""
        
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 清理 SQL
        sql_query = response.content.strip()
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        return json.dumps({
            "success": True,
            "sql_query": sql_query,
            "samples_used": len(best_samples),
            "best_sample_score": best_samples[0].get('final_score', best_samples[0].get('similarity', 0)) if best_samples else 0
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"基于样本的 SQL 生成失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# SQL 生成代理类
# ============================================================================

class SQLGeneratorAgent:
    """
    SQL 生成代理 - 使用 InjectedState 优化
    
    重要变更:
    - generate_sql_query 使用 InjectedState 获取 connection_id 和快速模式设置
    - 支持 with_structured_output 进行结构化输出
    """
    
    def __init__(self):
        self.name = "sql_generator_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [generate_sql_query, generate_sql_with_samples]
        
        # 尝试启用结构化输出
        try:
            self.structured_llm = self.llm.with_structured_output(
                SQLGenerationResult,
                method="function_calling"
            )
            logger.info("✓ SQL 生成器已启用结构化输出")
        except Exception as e:
            logger.warning(f"⚠ with_structured_output 不可用: {e}")
            self.structured_llm = None
        
        # 创建 ReAct 代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name,
            state_schema=SQLMessageState
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业 SQL 生成专家。

**核心职责**: 根据用户查询和数据库模式信息生成准确的 SQL 语句

**工作流程**:
1. 使用 generate_sql_query 工具生成 SQL
   - connection_id 和快速模式设置会自动从状态获取
   - 工具内部会自动检索相关样本（如果启用）
2. **只返回 SQL 语句，不解释，不总结**

**生成原则**:
- 确保语法绝对正确
- 使用适当的连接方式
- 限制结果集大小（除非明确要求）
- 使用正确的值映射
- 避免危险操作（DROP, DELETE, UPDATE 等）

**禁止的行为**:
- ❌ 不要生成查询结果的预测或解读
- ❌ 不要添加 SQL 以外的内容
- ❌ 不要重复调用工具

**输出格式**: 只返回工具调用结果，包含生成的 SQL"""
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        处理 SQL 生成任务 - 返回标准工具调用格式
        
        修复说明 (2026-01-22):
        - 样本检索在此异步方法中执行，然后传递给同步工具
        - 避免嵌套事件循环导致的死锁问题
        
        缓存模板支持 (2026-01-22):
        - 如果存在 cached_sql_template，使用它作为参考生成新SQL
        - 使用 enriched_query (如果存在) 替代原始查询
        """
        from langgraph.config import get_stream_writer
        from app.schemas.stream_events import create_sql_step_event
        
        # 获取 stream writer
        try:
            writer = get_stream_writer()
        except Exception:
            writer = None
        
        try:
            # ✅ 检查错误恢复上下文（如果是重试）
            error_recovery_context = state.get("error_recovery_context")
            retry_count = state.get("retry_count", 0)
            
            if error_recovery_context:
                logger.info(f"检测到错误恢复上下文，这是第 {retry_count} 次重试")
                logger.info(f"错误类型: {error_recovery_context.get('error_type')}")
                logger.info(f"失败SQL: {error_recovery_context.get('failed_sql', '')[:100]}...")
            
            # ✅ 检查缓存模板和增强查询
            cached_sql_template = state.get("cached_sql_template")
            enriched_query = state.get("enriched_query")
            cache_hit_type = state.get("cache_hit_type")
            
            if cached_sql_template:
                logger.info(f"检测到缓存SQL模板，将基于模板生成新SQL")
            
            # 获取用户查询 (优先使用 enriched_query)
            messages = state.get("messages", [])
            user_query = None
            for msg in messages:
                if hasattr(msg, 'type') and msg.type == 'human':
                    user_query = msg.content
                    if isinstance(user_query, list):
                        user_query = user_query[0].get("text", "") if user_query else ""
                    break
            
            # 如果有增强查询，优先使用
            if enriched_query:
                logger.info(f"使用增强后的查询: {enriched_query[:50]}...")
                user_query = enriched_query
            
            if not user_query:
                raise ValueError("无法获取用户查询")
            
            # 从状态获取 schema 信息
            schema_info = state.get("schema_info")
            connection_id = state.get("connection_id")
            skip_sample = state.get("skip_sample_retrieval", False)
            
            if not schema_info:
                raise ValueError("缺少 schema 信息，请先执行 schema_agent")
            
            # 提取表名列表用于日志
            tables_data = schema_info.get("tables", {})
            if isinstance(tables_data, dict) and "tables" in tables_data:
                table_names = [t.get("name", "") for t in tables_data.get("tables", [])]
            else:
                table_names = list(tables_data.keys()) if isinstance(tables_data, dict) else []
            logger.info(f"使用 schema 信息生成 SQL, tables={table_names[:5]}{'...' if len(table_names) > 5 else ''}")
            
            # ✅ Few-shot 样本检索步骤
            sample_qa_pairs = []
            if connection_id and not skip_sample:
                # 发送 few_shot 步骤开始事件
                few_shot_start = time.time()
                if writer:
                    writer(create_sql_step_event(
                        step="few_shot",
                        status="running",
                        result=None,
                        time_ms=0
                    ))
                
                logger.info(f"异步获取 QA 样本, connection_id={connection_id}")
                start_time = time.time()
                sample_qa_pairs = await _fetch_qa_samples_async(
                    user_query=user_query,
                    schema_info=schema_info.get("tables", {}),
                    connection_id=connection_id
                )
                logger.info(f"QA 样本获取完成，耗时 {time.time() - start_time:.2f}s，获取 {len(sample_qa_pairs)} 个样本")
                
                # 发送 few_shot 步骤完成事件
                few_shot_elapsed = int((time.time() - few_shot_start) * 1000)
                if writer:
                    writer(create_sql_step_event(
                        step="few_shot",
                        status="completed",
                        result=f"检索到 {len(sample_qa_pairs)} 个相似样本",
                        time_ms=few_shot_elapsed
                    ))
            elif skip_sample:
                logger.info("快速模式: 跳过样本检索")
                # 快速模式下跳过 few_shot
                if writer:
                    writer(create_sql_step_event(
                        step="few_shot",
                        status="completed",
                        result="快速模式 - 已跳过",
                        time_ms=0
                    ))
            
            # 准备工具参数
            schema_info_json = json.dumps(schema_info.get("tables", {}), ensure_ascii=False)
            value_mappings_json = json.dumps(schema_info.get("value_mappings", {}), ensure_ascii=False) if schema_info.get("value_mappings") else None
            sample_qa_pairs_json = json.dumps(sample_qa_pairs, ensure_ascii=False) if sample_qa_pairs else None
            
            # ✅ LLM 解析步骤
            llm_parse_start = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="llm_parse",
                    status="running",
                    result="基于缓存模板生成" if cached_sql_template else None,
                    time_ms=0
                ))
            
            # ✅ 如果有缓存SQL模板，使用基于模板的生成方法
            if cached_sql_template and cache_hit_type == "semantic":
                logger.info("使用缓存SQL模板进行增强生成")
                result_json = self._generate_sql_from_template(
                    user_query=user_query,
                    cached_sql_template=cached_sql_template,
                    schema_info=schema_info.get("tables", {}),
                    value_mappings=schema_info.get("value_mappings", {}),
                    sample_qa_pairs=sample_qa_pairs
                )
            else:
                # 调用同步工具生成 SQL（样本已经异步获取好了）
                # 将错误恢复上下文也传递给工具
                result_json = generate_sql_query.invoke({
                    "user_query": user_query,
                    "schema_info": schema_info_json,
                    "state": {
                        "connection_id": connection_id,
                        "skip_sample_retrieval": skip_sample,
                        "error_recovery_context": error_recovery_context  # 传递错误恢复上下文
                    },
                    "value_mappings": value_mappings_json,
                    "sample_qa_pairs": sample_qa_pairs_json,
                    "db_type": "mysql"
                })
            
            # 发送 llm_parse 步骤完成事件
            llm_parse_elapsed = int((time.time() - llm_parse_start) * 1000)
            if writer:
                writer(create_sql_step_event(
                    step="llm_parse",
                    status="completed",
                    result="SQL 生成完成",
                    time_ms=llm_parse_elapsed
                ))
            
            # 解析结果
            result = json.loads(result_json)
            
            if not result.get("success"):
                raise ValueError(f"SQL 生成失败: {result.get('error')}")
            
            generated_sql = result.get("sql_query", "")
            
            if not generated_sql:
                raise ValueError("生成的 SQL 为空")
            
            logger.info(f"SQL 生成成功: {generated_sql[:100]}...")
            
            # ✅ SQL 修正步骤 (简化处理，直接标记完成)
            if writer:
                writer(create_sql_step_event(
                    step="sql_fix",
                    status="completed",
                    result="语法检查通过",
                    time_ms=0
                ))
            
            # ✅ 创建标准工具调用消息格式
            tool_call_id = generate_tool_call_id("generate_sql_query", {
                "user_query": user_query,
                "connection_id": connection_id
            })
            
            # AIMessage 包含 tool_calls
            ai_message = AIMessage(
                content="",  # 状态通过 QueryPipeline 组件展示，不需要文字
                tool_calls=[{
                    "name": "generate_sql_query",
                    "args": {
                        "user_query": user_query,
                        "db_type": "mysql"
                    },
                    "id": tool_call_id,
                    "type": "tool_call"
                }]
            )
            
            # ToolMessage 包含工具执行结果
            tool_result = {
                "status": "success",
                "data": {
                    "sql_query": generated_sql,
                    "explanation": result.get("explanation", ""),
                    "samples_used": result.get("samples_used", 0)
                },
                "metadata": {
                    "connection_id": connection_id
                }
            }
            
            tool_message = ToolMessage(
                content=json.dumps(tool_result, ensure_ascii=False),
                tool_call_id=tool_call_id,
                name="generate_sql_query"
            )
            
            return {
                "messages": [ai_message, tool_message],
                "generated_sql": generated_sql,
                "sample_retrieval_result": {
                    "samples_count": len(sample_qa_pairs),
                    "samples_used": result.get("samples_used", 0)
                },
                "current_stage": "sql_execution",
                # ✅ 清除错误恢复上下文，避免后续一直触发智能决策
                "error_recovery_context": None
            }
            
        except Exception as e:
            logger.error(f"SQL 生成失败: {str(e)}")
            
            # 错误时也返回标准格式
            error_tool_call_id = generate_tool_call_id("generate_sql_query", {"error": str(e), "timestamp": time.time()})
            
            ai_message = AIMessage(
                content="",  # 状态通过 QueryPipeline 组件展示，不需要文字
                tool_calls=[{
                    "name": "generate_sql_query",
                    "args": {},
                    "id": error_tool_call_id,
                    "type": "tool_call"
                }]
            )
            
            tool_message = ToolMessage(
                content=json.dumps({
                    "status": "error",
                    "error": str(e)
                }, ensure_ascii=False),
                tool_call_id=error_tool_call_id,
                name="generate_sql_query"
            )
            
            return {
                "messages": [ai_message, tool_message],
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "sql_generation",
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0),
                    "timestamp": time.time()
                }]
            }
    
    def _generate_sql_from_template(
        self,
        user_query: str,
        cached_sql_template: str,
        schema_info: Dict[str, Any],
        value_mappings: Dict[str, Any],
        sample_qa_pairs: List[Dict[str, Any]]
    ) -> str:
        """
        基于缓存SQL模板生成新SQL
        
        当语义缓存命中时，使用缓存的SQL作为模板，
        结合用户澄清后的增强查询生成最终SQL。
        
        Args:
            user_query: 用户的查询（可能是澄清后的增强查询）
            cached_sql_template: 缓存的SQL模板
            schema_info: 数据库模式信息
            value_mappings: 值映射信息
            sample_qa_pairs: QA样本对
            
        Returns:
            str: JSON格式的生成结果
        """
        try:
            # 构建模板增强的生成提示
            prompt = f"""作为 SQL 专家，请基于以下信息修改 SQL 查询：

**用户需求**: {user_query}

**参考SQL模板** (来自相似查询):
```sql
{cached_sql_template}
```

**数据库模式**:
{json.dumps(schema_info, ensure_ascii=False, indent=2)}

**值映射信息**:
{json.dumps(value_mappings, ensure_ascii=False, indent=2) if value_mappings else '无'}

**任务**: 
1. 分析用户需求与参考SQL的差异
2. 基于参考SQL的结构，修改WHERE条件、字段选择等以满足用户需求
3. 确保SQL语法正确，字段名与模式一致

**要求**: 只返回修改后的SQL语句，不要其他内容。
"""
            
            llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
            response = llm.invoke([HumanMessage(content=prompt)])
            
            # 清理 SQL
            sql_query = response.content.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.startswith("```"):
                sql_query = sql_query[3:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            
            logger.info(f"基于模板生成的SQL: {sql_query[:100]}...")
            
            return json.dumps({
                "success": True,
                "sql_query": sql_query,
                "template_based": True,
                "samples_used": 0
            }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"基于模板的SQL生成失败: {e}")
            # 降级到普通生成
            return generate_sql_query.invoke({
                "user_query": user_query,
                "schema_info": json.dumps(schema_info, ensure_ascii=False),
                "state": {},
                "value_mappings": json.dumps(value_mappings, ensure_ascii=False) if value_mappings else None,
                "sample_qa_pairs": json.dumps(sample_qa_pairs, ensure_ascii=False) if sample_qa_pairs else None,
                "db_type": "mysql"
            })
    
    def _extract_sql_from_result(self, result: Dict[str, Any]) -> str:
        """从结果中提取 SQL 语句"""
        messages = result.get("messages", [])
        for message in reversed(messages):
            if hasattr(message, 'content'):
                content = message.content
                if isinstance(content, str):
                    # 尝试解析 JSON
                    try:
                        data = json.loads(content)
                        if isinstance(data, dict) and data.get("sql_query"):
                            return data["sql_query"]
                    except json.JSONDecodeError:
                        pass
                    
                    # 尝试直接提取 SQL
                    if "SELECT" in content.upper():
                        lines = content.split('\n')
                        for line in lines:
                            if line.strip().upper().startswith('SELECT'):
                                return line.strip()
        return ""


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def sql_generator_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    SQL 生成节点函数 - 用于 LangGraph 图
    """
    agent = SQLGeneratorAgent()
    return await agent.process(state)


# ============================================================================
# 导出
# ============================================================================

# 创建全局实例（兼容现有代码）
sql_generator_agent = SQLGeneratorAgent()

__all__ = [
    "sql_generator_agent",
    "sql_generator_node",
    "generate_sql_query",
    "generate_sql_with_samples",
    "SQLGeneratorAgent",
    "SQLGenerationResult",
]
