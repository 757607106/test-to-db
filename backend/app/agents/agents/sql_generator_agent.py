"""
SQL生成代理 - 优化版
负责根据模式信息和用户查询生成高质量的SQL语句
优化：改为直接工具调用模式，避免ReAct开销
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.llms import get_default_model

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
        # 根据数据库类型添加特定语法说明
        db_syntax_guide = ""
        if db_type.lower() == "mysql":
            db_syntax_guide = """
MySQL 特定语法要求：
- 日期截断：使用 DATE_FORMAT(date_column, '%Y-%m-01') 而不是 DATE_TRUNC
- 当前日期：使用 NOW() 或 CURRENT_DATE
- 日期间隔：使用 DATE_SUB(NOW(), INTERVAL 30 DAY) 或 DATE_ADD
- 不支持 FULL OUTER JOIN，使用 LEFT JOIN UNION RIGHT JOIN 代替
- 字符串连接：使用 CONCAT() 函数
"""
        elif db_type.lower() == "postgresql":
            db_syntax_guide = """
PostgreSQL 特定语法：
- 日期截断：使用 DATE_TRUNC('month', date_column)
- 当前日期：使用 CURRENT_DATE 或 NOW()
- 日期间隔：使用 CURRENT_DATE - INTERVAL '30 days'
- 支持 FULL OUTER JOIN
- 字符串连接：使用 || 运算符或 CONCAT()
"""
        
        # 构建详细的上下文信息
        context = f"""
数据库类型: {db_type}
{db_syntax_guide}

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
2. 确保语法正确，严格遵守上述数据库类型的语法要求
3. 使用适当的连接和过滤条件
4. 限制结果数量（除非用户明确要求全部数据）
5. 使用正确的值映射
6. 参考样本的SQL结构和模式，但要适应当前查询的具体需求
7. 优先参考高成功率的样本
8. 特别注意：如果是 MySQL，不要使用 DATE_TRUNC、FULL OUTER JOIN 等 PostgreSQL 特有的语法
"""
        
        llm = get_default_model()
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
        min_similarity_threshold = 0.6  # 与样本检索代理保持一致的阈值

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

        # 根据数据库类型添加特定语法说明
        db_syntax_guide = ""
        if db_type.lower() == "mysql":
            db_syntax_guide = """
MySQL 特定语法要求：
- 日期截断：使用 DATE_FORMAT(date_column, '%Y-%m-01') 而不是 DATE_TRUNC
- 当前日期：使用 NOW() 或 CURRENT_DATE
- 日期间隔：使用 DATE_SUB(NOW(), INTERVAL 30 DAY) 或 DATE_ADD
- 不支持 FULL OUTER JOIN，使用 LEFT JOIN UNION RIGHT JOIN 代替
- 字符串连接：使用 CONCAT() 函数
"""
        elif db_type.lower() in ["postgresql", "postgres"]:
            db_syntax_guide = """
PostgreSQL 特定语法：
- 日期截断：使用 DATE_TRUNC('month', date_column)
- 当前日期：使用 CURRENT_DATE 或 NOW()
- 日期间隔：使用 CURRENT_DATE - INTERVAL '30 days'
- 支持 FULL OUTER JOIN
- 字符串连接：使用 || 运算符或 CONCAT()
"""
        elif db_type.lower() == "sqlite":
            db_syntax_guide = """
SQLite 特定语法：
- 日期格式化：使用 strftime('%Y-%m', date_column)
- 当前日期：使用 date('now')
- 日期间隔：使用 date('now', '-30 days')
- 不支持 FULL OUTER JOIN
- 字符串连接：使用 || 运算符
"""

        # 构建增强的生成提示
        prompt = f"""
作为SQL专家，请基于以下信息生成高质量的SQL查询：

数据库类型: {db_type.upper()}
{db_syntax_guide}

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
4. 确保SQL语法正确且高效，严格遵守上述 {db_type.upper()} 语法要求
5. 添加适当的限制条件

要求：
- 只返回最终的SQL语句
- 确保语法正确，严格使用 {db_type.upper()} 语法
- 参考样本的最佳实践
- 适应当前的数据库结构
- 优化查询性能
"""

        llm = get_default_model()
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
def analyze_sql_optimization_need(sql_query: str, schema_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    分析SQL查询是否需要优化

    Args:
        sql_query: SQL查询语句
        schema_info: 模式信息

    Returns:
        优化需求分析结果
    """
    try:
        # 基本的SQL复杂度分析
        sql_upper = sql_query.upper().strip()

        # 检查可能需要优化的模式
        optimization_indicators = {
            "complex_joins": False,
            "subqueries": False,
            "no_where_clause": False,
            "select_star": False,
            "multiple_tables": False,
            "complex_functions": False,
            "no_limit": False
        }

        # 检查复杂连接
        join_count = sql_upper.count(' JOIN ')
        if join_count >= 2:
            optimization_indicators["complex_joins"] = True

        # 检查子查询
        if '(' in sql_query and ('SELECT' in sql_query[sql_query.find('('):]):
            optimization_indicators["subqueries"] = True

        # 检查是否缺少WHERE子句
        if 'WHERE' not in sql_upper and 'JOIN' in sql_upper:
            optimization_indicators["no_where_clause"] = True

        # 检查SELECT *
        if 'SELECT *' in sql_upper:
            optimization_indicators["select_star"] = True

        # 检查多表查询
        from_clause = sql_query[sql_query.upper().find('FROM'):] if 'FROM' in sql_upper else ""
        table_count = from_clause.count(',') + from_clause.count('JOIN')
        if table_count >= 1:
            optimization_indicators["multiple_tables"] = True

        # 检查复杂函数
        complex_functions = ['GROUP_CONCAT', 'SUBSTRING', 'REGEXP', 'CASE WHEN']
        if any(func in sql_upper for func in complex_functions):
            optimization_indicators["complex_functions"] = True

        # 检查是否缺少LIMIT
        if 'LIMIT' not in sql_upper and 'COUNT(' not in sql_upper:
            optimization_indicators["no_limit"] = True

        # 计算优化需求分数
        optimization_score = sum(optimization_indicators.values())
        needs_optimization = optimization_score >= 3  # 如果有3个或以上指标，建议优化

        return {
            "success": True,
            "needs_optimization": needs_optimization,
            "optimization_score": optimization_score,
            "indicators": optimization_indicators,
            "reason": _get_optimization_reason(optimization_indicators, needs_optimization)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def _get_optimization_reason(indicators: Dict[str, bool], needs_optimization: bool) -> str:
    """获取优化建议原因"""
    if not needs_optimization:
        return "SQL查询相对简单，性能应该良好，无需额外优化"

    reasons = []
    if indicators["complex_joins"]:
        reasons.append("包含多个表连接")
    if indicators["subqueries"]:
        reasons.append("包含子查询")
    if indicators["no_where_clause"]:
        reasons.append("多表查询缺少WHERE条件")
    if indicators["select_star"]:
        reasons.append("使用SELECT *可能影响性能")
    if indicators["complex_functions"]:
        reasons.append("包含复杂函数")
    if indicators["no_limit"]:
        reasons.append("缺少LIMIT限制可能返回大量数据")

    return f"建议优化原因: {', '.join(reasons)}"

@tool
def optimize_sql_query(sql_query: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    优化SQL查询性能

    Args:
        sql_query: 原始SQL查询
        schema_info: 模式信息

    Returns:
        优化后的SQL查句和优化建议
    """
    try:
        # 构建优化提示
        prompt = f"""
请优化以下SQL查询的性能：

原始SQL:
{sql_query}

表结构信息:
{schema_info}

请提供：
1. 优化后的SQL语句
2. 优化说明
3. 性能改进建议

优化重点：
- 索引使用
- 连接顺序
- 查询条件优化
- 避免全表扫描
- 减少返回的列数
- 添加适当的LIMIT
"""

        llm = get_default_model()
        response = llm.invoke([HumanMessage(content=prompt)])

        return {
            "success": True,
            "optimized_sql": response.content,
            "original_sql": sql_query
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# 已禁用：SQL解释功能
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
#         llm = get_default_model()
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
    """SQL生成代理 - 优化版（直接工具调用模式）"""

    def __init__(self):
        self.name = "sql_generator_agent"
        self.llm = get_default_model()
        # 简化：保留两个工具但直接调用
        self.tools = [generate_sql_query, generate_sql_with_samples]
        # 保留ReAct代理以兼容supervisor（但实际不使用ReAct循环）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示 - 增强版（智能处理模糊查询）"""
        return """你是一个专业的SQL生成专家。你的任务是：

1. 根据用户查询和数据库模式信息生成准确的SQL语句
2. **智能处理模糊查询**，做出合理假设并确保准确性
3. 快速生成高质量SQL，无需额外澄清

智能工作流程：
1. 检查是否有样本检索结果
2. 如果有样本，优先使用 generate_sql_with_samples 工具
3. 如果没有样本，使用 generate_sql_query 工具生成基础SQL

SQL生成原则：
- 确保语法正确性和执行准确性
- 使用适当的连接方式
- 应用正确的过滤条件
- 限制结果集大小（除非明确要求）
- 使用正确的值映射
- 充分利用样本提供的最佳实践

**模糊查询智能处理规则（重要）:**

遇到模糊词时，按以下规则做出合理假设：

1. **"最好"/"最高"/"最优"类词汇:**
   - 在销售场景：默认指销售额（amount/sales/revenue）降序
   - 在数量场景：默认指数量（quantity/count）降序
   - 在评分场景：默认指评分（rating/score）降序
   - 添加注释说明假设

2. **"最近"/"近期"等时间词:**
   - 默认指最近30天
   - SQL: WHERE date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
   - 或: WHERE date >= CURRENT_DATE - INTERVAL 30 DAY

3. **"销售"相关查询:**
   - 默认指销售额（sales_amount, revenue, total_sales）
   - 如果只有销量字段，则使用销量
   - 在注释中说明使用的字段

4. **"用户"相关查询:**
   - 默认指活跃用户或所有用户
   - 考虑是否需要JOIN用户表

5. **排序和限制:**
   - "前N"/"最高N" → ORDER BY [字段] DESC LIMIT N
   - 如果没有指定N，默认 LIMIT 10
   - "后N"/"最低N" → ORDER BY [字段] ASC LIMIT N

6. **聚合查询:**
   - "统计"/"汇总" → 使用SUM/COUNT等聚合函数
   - "平均" → 使用AVG函数
   - "总共"/"总计" → 使用SUM函数

**SQL注释规范:**
在生成的SQL中添加简短注释说明假设：
```sql
-- 假设：按销售额排序，最近30天数据
SELECT product_name, SUM(sales_amount) as total_sales
FROM sales
WHERE sale_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY product_name
ORDER BY total_sales DESC
LIMIT 10
```

**准确性保证:**
- 优先使用schema中存在的字段
- 确保JOIN条件正确
- 验证WHERE条件的字段类型
- 使用合适的聚合函数
- 添加必要的GROUP BY

请始终生成**准确、可执行**的SQL语句，智能处理模糊查询，确保准确率！"""
    # 2. 使用 analyze_sql_optimization_need 工具分析是否需要优化
    # 3. 仅当分析结果显示需要优化时，才使用 optimize_sql_query 工具

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL生成任务 - 优化版（直接工具调用）"""
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
                    schema_info = self._extract_schema_from_messages(schema_agent_result.get("messages", []))

            # 获取数据库类型
            db_type = "mysql"  # 默认值
            connection_id = state.get("connection_id", 15)
            
            try:
                from app.services.db_service import get_db_connection_by_id
                connection = get_db_connection_by_id(connection_id)
                if connection:
                    db_type = connection.db_type
            except Exception as e:
                print(f"获取数据库类型失败，使用默认值mysql: {str(e)}")

            # 获取样本检索结果
            sample_retrieval_result = state.get("sample_retrieval_result")
            sample_qa_pairs = []
            if sample_retrieval_result and sample_retrieval_result.get("qa_pairs"):
                sample_qa_pairs = sample_retrieval_result["qa_pairs"]
            
            # 直接调用工具函数，避免ReAct循环
            print(f"直接调用SQL生成工具: 样本数量={len(sample_qa_pairs)}, 数据库类型={db_type}")
            
            if sample_qa_pairs:
                # 使用样本生成
                result = generate_sql_with_samples.invoke({
                    "user_query": user_query,
                    "schema_info": schema_info,
                    "sample_qa_pairs": sample_qa_pairs,
                    "value_mappings": schema_info.get("value_mappings") if schema_info else None,
                    "db_type": db_type
                })
            else:
                # 基本生成
                result = generate_sql_query.invoke({
                    "user_query": user_query,
                    "schema_info": schema_info,
                    "value_mappings": schema_info.get("value_mappings") if schema_info else None,
                    "db_type": db_type
                })
            
            if not result.get("success"):
                raise ValueError(result.get("error", "SQL生成失败"))
            
            generated_sql = result.get("sql_query", "")
            
            # 更新状态
            state["generated_sql"] = generated_sql
            state["current_stage"] = "sql_execution"  # 跳过验证，直接执行
            
            return {
                "messages": [AIMessage(content=f"已生成SQL查询")],
                "generated_sql": generated_sql,
                "current_stage": "sql_execution"
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
