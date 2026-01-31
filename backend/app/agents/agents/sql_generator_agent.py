"""
SQL生成代理
负责根据模式信息和用户查询生成高质量的SQL语句

Skill 模式支持：
- 读取 skill_context 中的业务规则 (business_rules)
- 读取 skill_context 中的 JOIN 规则 (join_rules)
- 将规则注入到 SQL 生成提示中

数据库方言支持：
- 根据 db_type 注入对应的语法规则指南
- 确保生成的 SQL 符合目标数据库语法
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.config import get_stream_writer

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.schemas.stream_events import create_stage_message_event
from app.services.db_dialect import get_syntax_guide_for_prompt, get_dialect


@tool
def generate_sql_query(
    user_query: str,
    schema_info: Dict[str, Any],
    value_mappings: Dict[str, Any] = None,
    db_type: str = "mysql",
    sample_qa_pairs: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    根据用户查询和模式信息生成SQL语句

    Args:
        user_query: 用户的自然语言查询
        schema_info: 数据库模式信息
        value_mappings: 值映射信息
        db_type: 数据库类型
        sample_qa_pairs: 相关的SQL问答对样本

    Returns:
        生成的SQL语句和相关信息
    """
    try:
        # 获取数据库语法指南
        syntax_guide = get_syntax_guide_for_prompt(db_type)
        dialect = get_dialect(db_type)
        
        # 构建详细的上下文信息
        context = f"""
数据库类型: {db_type}

{syntax_guide}

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
"""

        # 构建SQL生成提示
        prompt = f"""
基于以下信息生成SQL查询：

用户查询: {user_query}

{context}

{sample_context}

请生成一个准确、高效的SQL查询语句。要求：
1. 只返回SQL语句，不要其他解释
2. 【重要】严格遵循上述数据库语法规则
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
        
        return {
            "success": True,
            "sql_query": sql_query,
            "context_used": context
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def generate_sql_with_samples(
    user_query: str,
    schema_info: Dict[str, Any],
    sample_qa_pairs: List[Dict[str, Any]],
    value_mappings: Dict[str, Any] = None,
    db_type: str = "mysql"
) -> Dict[str, Any]:
    """
    基于样本生成高质量SQL查询

    Args:
        user_query: 用户的自然语言查询
        schema_info: 数据库模式信息
        sample_qa_pairs: 相关的SQL问答对样本
        value_mappings: 值映射信息
        db_type: 数据库类型

    Returns:
        生成的SQL语句和样本分析
    """
    try:
        if not sample_qa_pairs:
            # 如果没有样本，回退到基本生成
            return generate_sql_query(user_query, schema_info, value_mappings, db_type)

        # 过滤并分析最佳样本
        min_similarity_threshold = 0.6

        # 先过滤低质量样本
        high_quality_samples = [
            sample for sample in sample_qa_pairs
            if sample.get('final_score', 0) >= min_similarity_threshold
        ]

        if not high_quality_samples:
            # 如果没有高质量样本，回退到基本生成
            return generate_sql_query(user_query, schema_info, value_mappings, db_type)

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

        # 获取数据库语法指南
        syntax_guide = get_syntax_guide_for_prompt(db_type)

        # 构建增强的生成提示
        prompt = f"""
作为SQL专家，请基于以下信息生成高质量的SQL查询：

用户查询: {user_query}

数据库类型: {db_type}

{syntax_guide}

数据库模式:
{schema_info}

{sample_analysis}

值映射信息:
{value_mappings if value_mappings else '无'}

请按照以下步骤生成SQL：
1. 分析用户查询的意图和需求
2. 【重要】严格遵循上述数据库语法规则
3. 参考最相关样本的SQL结构和模式
4. 根据当前数据库模式调整表名和字段名
5. 添加适当的限制条件

要求：
- 只返回最终的SQL语句
- 严格遵循目标数据库的语法规则
- 参考样本的最佳实践
- 适应当前的数据库结构
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

        return {
            "success": True,
            "sql_query": sql_query,
            "samples_used": len(best_samples),
            "best_sample_score": best_samples[0].get('final_score', 0) if best_samples else 0,
            "sample_analysis": sample_analysis
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def explain_sql_query(sql_query: str) -> Dict[str, Any]:
    """
    解释SQL查询的逻辑和执行计划
    
    Args:
        sql_query: SQL查询语句
        
    Returns:
        SQL查询的解释和分析
    """
    try:
        prompt = f"""
请详细解释以下SQL查询：

{sql_query}

请提供：
1. 查询逻辑说明
2. 执行步骤分析
3. 可能的性能瓶颈
4. 结果集预期
"""
        
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        return {
            "success": True,
            "explanation": response.content,
            "sql_query": sql_query
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class SQLGeneratorAgent:
    """SQL生成代理"""

    def __init__(self):
        self.name = "sql_generator_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [generate_sql_query, generate_sql_with_samples, explain_sql_query]
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的SQL生成专家。你的任务是：

1. 根据用户查询和数据库模式信息生成准确的SQL语句
2. 智能判断是否需要优化SQL查询
3. 仅在必要时进行SQL优化
4. 提供SQL查询的详细解释

智能工作流程：
1. 检查是否有样本检索结果
2. 如果有样本，优先使用 generate_sql_with_samples 工具
3. 如果没有样本，使用 generate_sql_query 工具生成基础SQL
4. 根据需要使用 explain_sql_query 工具解释查询逻辑

SQL生成原则：
- 确保语法正确性
- 使用适当的连接方式
- 应用正确的过滤条件
- 生成时就考虑基本性能优化
- 限制结果集大小（除非明确要求）
- 使用正确的值映射
- 充分利用样本提供的最佳实践

样本利用策略：
- 优先参考高相关性和高成功率的样本
- 学习样本的SQL结构和模式
- 适应当前查询的具体需求
- 保持SQL的正确性和效率

请始终生成高质量、可执行的SQL语句，并充分利用样本的指导作用。"""

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL生成任务"""
        try:
            # 获取用户查询
            user_query = state["messages"][0].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取数据库类型
            db_type = state.get("db_type", "mysql")
            
            # 获取数据库语法指南
            syntax_guide = get_syntax_guide_for_prompt(db_type)
            
            # 获取模式信息
            schema_info = state.get("schema_info")
            if not schema_info:
                # 从代理消息中提取模式信息
                schema_agent_result = state.get("agent_messages", {}).get("schema_agent")
                if schema_agent_result:
                    schema_info = self._extract_schema_from_messages(schema_agent_result.get("messages", []))

            # 获取样本检索结果
            sample_retrieval_result = state.get("sample_retrieval_result")
            sample_qa_pairs = []
            if sample_retrieval_result and sample_retrieval_result.get("qa_pairs"):
                sample_qa_pairs = sample_retrieval_result["qa_pairs"]
            
            # 获取 Skill 上下文（业务规则和 JOIN 规则）
            skill_context = state.get("skill_context", {})
            skill_prompt = self._build_skill_prompt(skill_context)
            
            # 准备输入消息
            sample_info = ""
            if sample_qa_pairs:
                sample_info = f"\n\n## 参考样本 (共 {len(sample_qa_pairs)} 个相似问题)"
                for i, sample in enumerate(sample_qa_pairs[:3], 1):
                    sample_info += f"""
### 样本 {i}:
- 问题: {sample.get('question', '')}
- SQL: ```sql
{sample.get('sql', '')}
```
- 相似度: {sample.get('similarity', sample.get('final_score', 0)):.2f}
- 成功率: {sample.get('success_rate', 0):.1%}
"""
                sample_info += "\n请参考以上样本的 SQL 结构和模式，生成符合当前查询的 SQL。"

            messages = [
                HumanMessage(content=f"""
请为以下用户查询生成SQL语句：

用户查询: {user_query}

数据库类型: {db_type}

{syntax_guide}

模式信息: {schema_info}
{sample_info}
{skill_prompt}

【重要】请严格遵循上述数据库语法规则生成 SQL。
""")
            ]
            
            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 提取生成的SQL
            generated_sql = self._extract_sql_from_result(result)
            
            # 更新状态
            state["generated_sql"] = generated_sql
            state["current_stage"] = "sql_validation"
            state["agent_messages"]["sql_generator"] = result
            writer = get_stream_writer()
            if writer:
                sql_preview = generated_sql.strip() if generated_sql else ""
                message = "SQL 已生成，准备执行查询。"
                if sql_preview:
                    message = f"SQL 已生成：\n{sql_preview}"
                writer(create_stage_message_event(
                    message=message,
                    step="sql_generator"
                ))
            
            return {
                "messages": result["messages"],
                "generated_sql": generated_sql,
                "current_stage": "sql_validation"
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
    
    def _build_skill_prompt(self, skill_context: Dict[str, Any]) -> str:
        """
        构建 Skill 上下文提示
        
        将业务规则和 JOIN 规则格式化为提示词片段
        """
        if not skill_context.get("enabled"):
            return ""
        
        lines = ["\n## 业务领域上下文\n"]
        
        # 匹配的 Skill
        matched_skills = skill_context.get("matched_skills", [])
        if matched_skills:
            skill_names = [s.get("display_name", s.get("name", "")) for s in matched_skills]
            lines.append(f"当前业务领域: {', '.join(skill_names)}\n")
        
        # 业务规则
        business_rules = skill_context.get("business_rules")
        if business_rules:
            lines.append("### 业务规则（必须遵循）")
            lines.append(business_rules)
            lines.append("")
        
        # JOIN 规则
        join_rules = skill_context.get("join_rules", [])
        if join_rules:
            lines.append("### JOIN 规则（优先使用）")
            for rule in join_rules[:5]:  # 最多5条
                left = f"{rule.get('left_table')}.{rule.get('left_column')}"
                right = f"{rule.get('right_table')}.{rule.get('right_column')}"
                join_type = rule.get('join_type', 'JOIN')
                lines.append(f"- {left} {join_type} {right}")
                desc = rule.get('description', '')
                if desc:
                    lines.append(f"  说明: {desc}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _extract_schema_from_messages(self, messages: List) -> Dict[str, Any]:
        """从消息中提取模式信息"""
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
