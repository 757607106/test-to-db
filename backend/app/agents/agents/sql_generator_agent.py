"""
SQL 生成代理

基于用户查询和数据库模式信息生成 SQL 语句。
支持多数据库类型、样本检索、错误恢复上下文。

Phase 1 优化:
- 使用统一的 SchemaContext 格式解析 schema_info
- 消除格式不一致导致的表名提取失败问题
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
from app.agents.utils.retry_utils import retry_with_backoff_sync, RetryConfigs
from app.schemas.schema_context import SchemaContext, normalize_schema_info, extract_table_names
from app.services.schema_prompt_builder import build_schema_prompt, build_column_whitelist, validate_sql_columns

logger = logging.getLogger(__name__)


# ============================================================================
# 数据库特定语法规则配置
# ============================================================================

DATABASE_SYNTAX_RULES = {
    "mysql": {
        "name": "MySQL",
        "rules": [
            "LIMIT 和 OFFSET 子句只能使用常量或变量，不支持子查询作为参数",
            "【重要】IN/ALL/ANY/SOME 子查询中禁止使用 LIMIT，这是 MySQL 的硬性限制",
            "【重要】如需在子查询中限制结果数量，必须使用 JOIN + 派生表的方式替代 IN + LIMIT",
            "计算中位数时必须使用用户变量或分步查询，不能在 LIMIT/OFFSET 中嵌套 SELECT",
            "字符串使用单引号，标识符使用反引号 (`table_name`)",
            "日期函数使用 DATE_FORMAT(), CURDATE(), NOW() 等",
            "分页语法: LIMIT offset, count 或 LIMIT count OFFSET offset",
            "不支持 FULL OUTER JOIN，需要用 UNION 模拟",
            "GROUP BY 必须包含所有非聚合列（除非启用 ONLY_FULL_GROUP_BY 模式被禁用）",
            "表别名引用格式: alias.column_name，禁止使用 database.alias.column_name",
        ],
        "median_hint": "MySQL 计算中位数建议使用变量方式：SET @row := 0; SELECT AVG(val) FROM (SELECT @row := @row + 1 AS row_num, column_name AS val FROM table ORDER BY column_name) t WHERE row_num IN (FLOOR((@row+1)/2), CEIL((@row+1)/2))",
        "top_n_hint": "MySQL 获取 Top N 记录并关联其他表时，禁止使用 WHERE id IN (SELECT id ... LIMIT N)，必须改用 JOIN 派生表：SELECT * FROM main_table m JOIN (SELECT id FROM sub_table ORDER BY col DESC LIMIT N) top ON m.id = top.id",
    },
    "postgresql": {
        "name": "PostgreSQL",
        "rules": [
            "支持在 LIMIT/OFFSET 中使用子查询",
            "字符串使用单引号，标识符使用双引号 (\"table_name\")",
            "支持 PERCENTILE_CONT() 和 PERCENTILE_DISC() 计算中位数",
            "日期函数使用 TO_CHAR(), CURRENT_DATE, NOW() 等",
            "支持 FULL OUTER JOIN",
            "支持窗口函数 OVER(PARTITION BY ... ORDER BY ...)",
            "布尔值使用 TRUE/FALSE 而非 1/0",
            "支持 RETURNING 子句返回修改的行",
        ],
        "median_hint": "PostgreSQL 计算中位数：SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY column_name) FROM table",
    },
    "sqlite": {
        "name": "SQLite",
        "rules": [
            "LIMIT 和 OFFSET 只支持常量表达式，不支持子查询",
            "不支持 RIGHT JOIN 和 FULL OUTER JOIN",
            "日期函数使用 DATE(), TIME(), DATETIME(), STRFTIME()",
            "字符串连接使用 || 运算符",
            "不支持存储过程和用户变量",
            "ALTER TABLE 功能有限，不支持修改列或删除列",
            "GROUP BY 对非聚合列较宽松，但建议明确列出",
        ],
        "median_hint": "SQLite 计算中位数：SELECT column_name FROM table ORDER BY column_name LIMIT 1 OFFSET (SELECT COUNT(*) FROM table) / 2",
    },
    "sqlserver": {
        "name": "SQL Server",
        "rules": [
            "使用 TOP N 而非 LIMIT（SQL Server 2012+ 支持 OFFSET-FETCH）",
            "分页语法: OFFSET n ROWS FETCH NEXT m ROWS ONLY（必须配合 ORDER BY）",
            "字符串使用单引号，标识符使用方括号 [table_name]",
            "日期函数使用 GETDATE(), DATEADD(), DATEDIFF(), FORMAT()",
            "字符串连接使用 + 运算符",
            "支持 PERCENTILE_CONT() 计算中位数（需要 OVER 子句）",
            "CTE 使用 WITH ... AS 语法",
        ],
        "median_hint": "SQL Server 计算中位数：SELECT DISTINCT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY column_name) OVER() FROM table",
    },
    "oracle": {
        "name": "Oracle",
        "rules": [
            "使用 ROWNUM 或 FETCH FIRST N ROWS ONLY（12c+）分页",
            "字符串使用单引号，标识符使用双引号",
            "日期函数使用 SYSDATE, TO_DATE(), TO_CHAR()",
            "字符串连接使用 || 运算符",
            "空字符串等于 NULL",
            "SELECT 必须有 FROM 子句（可用 FROM DUAL）",
            "支持 PERCENTILE_CONT() 计算中位数",
        ],
        "median_hint": "Oracle 计算中位数：SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY column_name) FROM table",
    },
}

# 默认规则（当数据库类型未知时使用）
DEFAULT_SYNTAX_RULES = {
    "name": "通用 SQL",
    "rules": [
        "LIMIT/OFFSET 中避免使用子查询（部分数据库不支持）",
        "使用标准 SQL 语法，避免数据库特定扩展",
        "日期和时间处理使用 ANSI SQL 标准函数",
        "字符串使用单引号",
        "避免使用数据库特定的分页语法",
    ],
    "median_hint": "计算中位数时建议使用简单的子查询或 CTE 方式，避免在 LIMIT/OFFSET 中嵌套复杂表达式",
}


def get_database_rules(db_type: str) -> Dict[str, Any]:
    """获取指定数据库类型的语法规则"""
    db_type_lower = db_type.lower().strip()
    return DATABASE_SYNTAX_RULES.get(db_type_lower, DEFAULT_SYNTAX_RULES)


def _get_specific_fix_hints(error_message: str, db_type: str) -> str:
    """
    根据错误消息生成针对性的修复建议
    
    这是智能错误修复的核心函数，能够识别具体的数据库错误并提供精确的修复方案。
    
    Args:
        error_message: 错误消息
        db_type: 数据库类型
        
    Returns:
        str: 针对性的修复建议
    """
    error_lower = error_message.lower()
    hints = []
    
    # MySQL 特定错误
    if db_type.lower() == "mysql":
        # LIMIT & IN/ALL/ANY/SOME subquery 错误 - 最常见的复杂查询错误
        if ("limit" in error_lower and ("in" in error_lower or "subquery" in error_lower)) or \
           "1235" in error_lower or \
           "doesn't yet support" in error_lower:
            hints.append("【关键错误】MySQL 不支持在 IN/ALL/ANY/SOME 子查询中使用 LIMIT")
            hints.append("【必须修复】将 WHERE id IN (SELECT ... LIMIT N) 改写为 JOIN 派生表方式")
            hints.append("")
            hints.append("【错误写法示例】:")
            hints.append("  WHERE product_id IN (SELECT id FROM products ORDER BY sales LIMIT 10)")
            hints.append("")
            hints.append("【正确写法示例】:")
            hints.append("  JOIN (SELECT id FROM products ORDER BY sales LIMIT 10) AS top_products")
            hints.append("    ON main.product_id = top_products.id")
            hints.append("")
            hints.append("【重要提醒】:")
            hints.append("  1. 派生表必须有别名，如 ) AS top_products")
            hints.append("  2. 使用 INNER JOIN 或 LEFT JOIN 连接派生表")
            hints.append("  3. 确保 JOIN 条件正确匹配主键/外键")
        
        # Unknown column 错误
        elif "unknown column" in error_lower or "1054" in error_lower:
            hints.append("【关键错误】SQL 中引用了不存在的列名")
            hints.append("【检查要点】:")
            hints.append("  1. 确保所有列名都在 schema 中存在")
            hints.append("  2. 检查表别名是否正确使用（如 t.column_name）")
            hints.append("  3. 多表查询时确保列名有表前缀避免歧义")
            # 尝试从错误消息中提取列名
            import re
            col_match = re.search(r"unknown column ['\"]?([^'\"]+)['\"]?", error_lower)
            if col_match:
                bad_col = col_match.group(1)
                hints.append(f"  4. 问题列名: {bad_col} - 请检查正确的列名")
        
        # Table doesn't exist 错误
        elif ("table" in error_lower and ("doesn't exist" in error_lower or "not found" in error_lower)) or \
             "1146" in error_lower:
            hints.append("【关键错误】SQL 中引用了不存在的表名")
            hints.append("【检查要点】:")
            hints.append("  1. 确保所有表名都在提供的 schema 中")
            hints.append("  2. 检查表名拼写是否正确")
            hints.append("  3. 注意表名大小写（MySQL 在某些系统上区分大小写）")
        
        # GROUP BY 错误
        elif "group by" in error_lower or "1055" in error_lower or "only_full_group_by" in error_lower:
            hints.append("【关键错误】GROUP BY 子句不完整")
            hints.append("【修复方法】:")
            hints.append("  1. SELECT 中的非聚合列必须出现在 GROUP BY 中")
            hints.append("  2. 或者对非聚合列使用聚合函数（如 MAX, MIN, ANY_VALUE）")
            hints.append("  3. 示例: SELECT name, SUM(amount) FROM t GROUP BY name")
        
        # Subquery returns more than 1 row
        elif "subquery returns more than 1 row" in error_lower or "1242" in error_lower:
            hints.append("【关键错误】子查询返回了多行，但上下文期望单值")
            hints.append("【修复方法】:")
            hints.append("  1. 使用 IN 替代 = 运算符")
            hints.append("  2. 或添加 LIMIT 1 限制子查询结果")
            hints.append("  3. 或使用聚合函数（如 MAX, MIN）确保单值")
        
        # Ambiguous column 错误
        elif "ambiguous" in error_lower:
            hints.append("【关键错误】列名歧义，多个表中存在同名列")
            hints.append("【修复方法】:")
            hints.append("  1. 为所有列添加表别名前缀")
            hints.append("  2. 示例: SELECT t1.id, t2.name FROM table1 t1 JOIN table2 t2")
    
    # PostgreSQL 特定错误
    elif db_type.lower() == "postgresql":
        if "column" in error_lower and "does not exist" in error_lower:
            hints.append("【关键错误】PostgreSQL 列名区分大小写（除非用双引号）")
            hints.append("【检查要点】:")
            hints.append("  1. 确保列名大小写与 schema 一致")
            hints.append("  2. 如需保留大小写，使用双引号: \"ColumnName\"")
    
    # 通用错误处理
    if not hints:
        if "syntax" in error_lower:
            hints.append("【SQL 语法错误】请检查 SQL 结构")
            hints.append("【建议】:")
            hints.append("  1. 简化 SQL 结构，避免复杂嵌套")
            hints.append("  2. 检查括号、引号是否匹配")
            hints.append("  3. 检查关键字拼写是否正确")
        elif "timeout" in error_lower or "timed out" in error_lower:
            hints.append("【查询超时】请优化 SQL")
            hints.append("【建议】:")
            hints.append("  1. 添加 LIMIT 限制结果数量")
            hints.append("  2. 优化 JOIN 条件，确保使用索引")
            hints.append("  3. 减少查询的数据范围")
        else:
            hints.append("【建议】简化 SQL 结构，使用更直接的查询方式")
    
    return "\n".join(f"  {hint}" if not hint.startswith("【") else hint for hint in hints)

def format_database_rules_prompt(db_type: str) -> str:
    """格式化数据库特定规则为提示词"""
    rules = get_database_rules(db_type)
    db_name = rules.get("name", db_type)
    rule_list = rules.get("rules", [])
    median_hint = rules.get("median_hint", "")
    top_n_hint = rules.get("top_n_hint", "")
    
    prompt = f"""
【{db_name} 数据库语法规则 - 必须严格遵守】
"""
    for i, rule in enumerate(rule_list, 1):
        prompt += f"{i}. {rule}\n"
    
    if top_n_hint:
        prompt += f"\n【Top N 查询参考 - 重要】\n{top_n_hint}\n"
    
    if median_hint:
        prompt += f"\n【中位数计算参考】\n{median_hint}\n"
    
    return prompt


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
    异步获取 QA 样本
    
    长期方案优化：
    - 从数据库配置读取是否启用
    - 提高相似度阈值
    - 只使用验证过的样本
    """
    try:
        from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
        from app.api.api_v1.endpoints.system_config import get_sql_enhancement_settings
        
        # 从数据库获取配置
        settings = get_sql_enhancement_settings()
        
        if not settings.qa_sample_enabled:
            logger.info("QA 样本召回已禁用（数据库配置）")
            return []
        
        logger.info(f"开始 QA 样本召回 - top_k={settings.qa_sample_top_k}, min_similarity={settings.qa_sample_min_similarity}")
        
        samples = await HybridRetrievalEnginePool.quick_retrieve(
            user_query=user_query,
            schema_context=schema_info,
            connection_id=connection_id,
            top_k=settings.qa_sample_top_k,
            min_similarity=settings.qa_sample_min_similarity
        )
        
        # 根据配置过滤样本
        filtered_samples = _filter_qa_samples(samples, settings)
        logger.info(f"QA 样本召回成功: 原始 {len(samples)} 个, 过滤后 {len(filtered_samples)} 个")
        return filtered_samples
        
    except Exception as e:
        logger.warning(f"QA 样本召回失败: {e}")
        return []


def _filter_qa_samples(samples: List[Dict[str, Any]], settings=None) -> List[Dict[str, Any]]:
    """根据配置过滤 QA 样本"""
    if settings is None:
        from app.api.api_v1.endpoints.system_config import get_sql_enhancement_settings
        settings = get_sql_enhancement_settings()
    
    if not samples:
        return []
    
    filtered = samples
    
    # 只使用验证过的样本
    if settings.qa_sample_verified_only:
        filtered = [s for s in filtered if s.get('verified', False)]
    
    # 过滤低成功率样本
    filtered = [s for s in filtered if s.get('success_rate', 0) >= 0.7]
    
    return filtered


def _format_qa_samples_for_prompt(samples: List[Dict[str, Any]]) -> str:
    """
    格式化 QA 样本为 prompt 内容
    
    长期方案：明确告诉 LLM 如何使用这些样本
    """
    if not samples:
        return ""
    
    prompt = """
【参考样本 - 仅供结构参考，不要照搬】
以下是与当前查询相似的历史查询及其 SQL，请参考其 JOIN 方式和字段选择，但要根据当前查询的具体需求调整：
"""
    
    for i, sample in enumerate(samples[:3], 1):
        similarity = sample.get('final_score', sample.get('similarity', 0))
        prompt += f"""
样本{i} (相似度: {similarity:.0%}):
- 历史问题: {sample.get('question', '')}
- 参考SQL: {sample.get('sql', '')}
- 注意: 仅参考 SQL 结构，根据当前查询调整 WHERE 条件和字段
"""
    
    prompt += """
【重要提醒】
- 不要直接复制样本 SQL
- 根据当前用户查询的具体需求调整
- 如果样本不适用，忽略样本自行生成
"""
    
    return prompt


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
    """根据用户查询和模式信息生成 SQL 语句"""
    try:
        # 从状态获取配置
        connection_id = state.get("connection_id")
        
        # 解析输入
        schema_data = json.loads(schema_info) if isinstance(schema_info, str) else schema_info
        mappings_data = json.loads(value_mappings) if value_mappings and isinstance(value_mappings, str) else value_mappings
        samples = json.loads(sample_qa_pairs) if sample_qa_pairs and isinstance(sample_qa_pairs, str) else (sample_qa_pairs or [])
        
        # 获取 SQL 增强配置
        from app.api.api_v1.endpoints.system_config import get_sql_enhancement_settings
        enhancement_settings = get_sql_enhancement_settings()
        
        # ✅ 关键修复：使用 schema_prompt_builder 构建防幻觉的 Schema 提示词
        tables_data = schema_data.get('tables', [])
        columns_data = schema_data.get('columns', [])
        relationships_data = schema_data.get('relationships', [])
        
        # 使用专门的防幻觉 Schema 提示词构建器
        schema_prompt = build_schema_prompt(
            tables=tables_data,
            columns=columns_data,
            relationships=relationships_data,
            db_type=db_type
        )
        
        # 构建列名白名单（用于后续验证）
        column_whitelist = build_column_whitelist(columns_data)
        
        # 构建基础上下文
        context = f"""
数据库类型: {db_type}

{schema_prompt}
"""
        
        # ==========================================
        # 长期方案：正确使用指标库
        # ==========================================
        metrics_prompt = ""
        if enhancement_settings.metrics_enabled:
            semantic_layer = schema_data.get("semantic_layer", {})
            metrics = semantic_layer.get("metrics", [])
            
            if metrics:
                # 只使用最相关的几个指标
                relevant_metrics = metrics[:enhancement_settings.metrics_max_count]
                
                metrics_prompt = """
【业务指标定义 - 必须使用以下公式】
以下是预定义的业务指标，当用户查询涉及这些指标时，必须使用对应的公式：
"""
                for m in relevant_metrics:
                    metrics_prompt += f"""
- {m.get('business_name', m.get('name', ''))}: 
  公式: {m.get('formula', '')}
  来源表: {m.get('source_table', '')}
  说明: {m.get('description', '')}
"""
                metrics_prompt += """
【重要】如果用户查询的指标在上述列表中，必须使用预定义的公式，确保口径一致。
"""
                logger.info(f"注入 {len(relevant_metrics)} 个业务指标到 prompt")
        
        # ==========================================
        # 长期方案：正确使用枚举值提示
        # ==========================================
        enum_prompt = ""
        if enhancement_settings.enum_hints_enabled:
            semantic_layer = schema_data.get("semantic_layer", {})
            enum_columns = semantic_layer.get("enum_columns", [])
            
            if enum_columns:
                enum_prompt = """
【字段可选值参考】
以下字段有预定义的可选值，生成 WHERE 条件时请使用正确的值：
"""
                for enum_col in enum_columns[:10]:  # 最多 10 个字段
                    col_name = enum_col.get('column_name', '')
                    table_name = enum_col.get('table_name', '')
                    values = enum_col.get('values', [])
                    
                    # 限制每个字段的枚举值数量
                    if len(values) > enhancement_settings.enum_max_values:
                        values = values[:enhancement_settings.enum_max_values]
                        values.append("...")
                    
                    enum_prompt += f"- {table_name}.{col_name}: {', '.join(str(v) for v in values)}\n"
                
                logger.info(f"注入 {len(enum_columns)} 个枚举字段提示到 prompt")
        
        # ==========================================
        # 值映射信息
        # ==========================================
        if mappings_data:
            context += f"""
值映射信息（用于字段值转换）:
{json.dumps(mappings_data, ensure_ascii=False, indent=2)}
"""
        
        # ==========================================
        # 长期方案：正确使用 QA 样本
        # ==========================================
        sample_context = ""
        if samples and enhancement_settings.qa_sample_enabled:
            sample_context = _format_qa_samples_for_prompt(samples)
        
        # 检查是否有错误恢复上下文
        error_recovery_hint = ""
        if state.get("error_recovery_context"):
            error_ctx = state.get("error_recovery_context", {})
            failed_sql = error_ctx.get("failed_sql", "")
            error_message = error_ctx.get("error_message", "")
            error_type = error_ctx.get("error_type", "")
            recovery_steps = error_ctx.get("recovery_steps", [])
            fix_prompt = error_ctx.get("fix_prompt", "")
            
            # ✅ 关键修复：检查是否有列名验证失败的详细信息
            available_columns_hint = error_ctx.get("available_columns_hint", "")
            
            if failed_sql or error_message:
                # 优先使用预构建的 fix_prompt（包含详细的列名信息）
                if fix_prompt:
                    specific_fix_hints = fix_prompt
                elif available_columns_hint:
                    # 如果有可用列信息，构建详细的修复提示
                    specific_fix_hints = f"""
【严重错误】上一次生成的 SQL 使用了不存在的列名！

错误信息: {error_message}

【正确的列名信息 - 请严格使用以下列名】
{available_columns_hint}

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
4. 如果需要计算某个指标（如库存总量），请使用实际存在的列进行计算
"""
                else:
                    from app.services.sql_helpers import build_targeted_fix_prompt
                    specific_fix_hints = build_targeted_fix_prompt(error_message, failed_sql, db_type)
                
                error_recovery_hint = f"""
⚠️ 【严重警告】上一次生成的 SQL 验证/执行失败，必须避免相同错误！

失败的 SQL:
```sql
{failed_sql}
```

错误信息: {error_message}
错误类型: {error_type}

{specific_fix_hints}

【额外修复建议】:
{chr(10).join(f"- {step}" for step in recovery_steps) if recovery_steps else "- 检查列名和表名是否正确"}

【重要】请生成一个完全不同结构的 SQL 查询，确保不再出现相同错误。
"""
        
        # ==========================================
        # P3: Skills-SQL-Assistant 业务规则注入
        # ==========================================
        skill_rules_prompt = ""
        if state.get("skill_mode_enabled"):
            skill_name = state.get("selected_skill_name", "")
            business_rules = state.get("skill_business_rules", "")
            loaded_content = state.get("loaded_skill_content", {})
            
            if business_rules:
                skill_rules_prompt = f"""
【业务领域规则 - {skill_name}】
{business_rules}

请在生成 SQL 时严格遵守以上业务规则。
"""
            
            common_patterns = loaded_content.get("common_patterns", []) if loaded_content else []
            if common_patterns:
                patterns_str = "\n".join([
                    f"- {p.get('pattern', '')}: {p.get('hint', '')}"
                    for p in common_patterns[:3]
                ])
                skill_rules_prompt += f"""
【常用查询模式参考】
{patterns_str}
"""
        
        # 获取数据库特定语法规则
        db_rules_prompt = format_database_rules_prompt(db_type)
        
        # 提取表名列表用于强约束
        available_tables = []
        if isinstance(schema_data, dict):
            if "tables" in schema_data:
                available_tables = [t.get("table_name", "") for t in schema_data.get("tables", [])]
            else:
                available_tables = list(schema_data.keys())
        
        # ✅ 关键修复：如果错误恢复上下文中有完整表列表，优先使用
        error_ctx = state.get("error_recovery_context", {})
        if error_ctx and error_ctx.get("full_table_list"):
            full_table_list = error_ctx.get("full_table_list", [])
            if full_table_list:
                logger.info(f"[错误恢复] 使用完整表列表: {len(full_table_list)} 个表")
                available_tables = full_table_list
        
        available_tables_str = ", ".join(available_tables) if available_tables else "未知"
        
        # 构建 SQL 生成提示
        prompt = f"""
基于以下信息生成 SQL 查询：

用户查询: {user_query}

{context}
{metrics_prompt}
{enum_prompt}
{sample_context}
{skill_rules_prompt}
{db_rules_prompt}
{error_recovery_hint}

【严格约束 - 必须遵守】
⚠️ 只能使用以下表: {available_tables_str}
⚠️ 禁止使用任何未在上述列表中的表名
⚠️ 如果用户需要的数据在提供的表中不存在，请使用最接近的可用表

请生成一个准确、高效的 SQL 查询语句。要求：
1. 只返回 SQL 语句，不要其他解释
2. 【最重要】只能使用上面提供的表和字段，禁止虚构表名
3. 【最重要】必须严格遵守上述 {db_type.upper()} 数据库的语法规则
4. 如果有预定义的业务指标，必须使用指标公式
5. 使用适当的连接和过滤条件
6. 限制结果数量（除非用户明确要求全部数据）
7. 使用正确的值映射和枚举值

【禁止假设 - 严格遵守】
- 禁止在 SQL 中添加任何注释（如 "-- 假设..."、"-- 替换为..."）
- 禁止使用占位符值（如 "1, 2, 3, 4, 5" 代替实际ID）
- 禁止假设字段的业务含义（如假设 status=1 表示某种状态）
- 禁止生成需要用户手动修改的 SQL

如果信息不足以生成完整 SQL：
- 对于缺少具体值的情况（如"前5个产品"但未指定哪5个），使用子查询动态获取
- 对于状态字段，如果不知道具体值含义，不要添加状态过滤条件
- 生成可直接执行的 SQL，不需要任何人工修改
"""
        
        # 使用指数退避重试调用 LLM
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        retry_config = RetryConfigs.LLM_CALL
        response = retry_with_backoff_sync(
            llm.invoke,
            [HumanMessage(content=prompt)],
            **retry_config.to_dict()
        )
        
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
        
        # ✅ 新增：移除 SQL 中的注释（防止 LLM 添加假设性注释）
        import re
        # 移除单行注释 (-- 开头)
        sql_query = re.sub(r'--.*?$', '', sql_query, flags=re.MULTILINE)
        # 移除多行注释 (/* ... */)
        sql_query = re.sub(r'/\*.*?\*/', '', sql_query, flags=re.DOTALL)
        # 清理多余空行
        sql_query = re.sub(r'\n\s*\n', '\n', sql_query).strip()
        
        # ✅ 新增：列名验证（防幻觉关键步骤）
        # 修复：列名验证失败时直接返回失败，触发重试
        column_validation_errors = []
        if column_whitelist:
            validation_result = validate_sql_columns(sql_query, column_whitelist)
            if not validation_result["valid"]:
                column_validation_errors = validation_result["errors"]
                logger.warning(f"[列名验证] 发现问题: {column_validation_errors}")
                
                # ✅ 关键修复：构建详细的列名白名单信息，帮助 LLM 修正
                # 提取所有可用的列名，按表分组
                available_columns_info = []
                for table_name, cols in column_whitelist.items():
                    available_columns_info.append(f"表 `{table_name}` 的可用列: {', '.join(cols)}")
                available_columns_str = "\n".join(available_columns_info)
                
                # ✅ 修复：列名验证失败时返回失败状态，触发错误恢复
                # 包含详细的正确列名信息
                return json.dumps({
                    "success": False,  # 标记为失败，触发重试
                    "error": f"列名验证失败: {'; '.join(column_validation_errors)}",
                    "sql_query": sql_query,
                    "samples_used": len(samples) if samples else 0,
                    "column_validation_errors": column_validation_errors,
                    "validation_passed": False,
                    # ✅ 新增：传递正确的列名信息
                    "available_columns": available_columns_str,
                    "column_whitelist": column_whitelist
                }, ensure_ascii=False)
        
        return json.dumps({
            "success": True,
            "sql_query": sql_query,
            "samples_used": len(samples) if samples else 0,
            "metrics_used": len(schema_data.get("semantic_layer", {}).get("metrics", [])) if enhancement_settings.metrics_enabled else 0,
            "context_used": len(context),
            "validation_passed": True
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"SQL 生成失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# 注意: _format_qa_samples_for_prompt 函数已在上方定义（第 296 行）


@tool
def generate_sql_with_samples(
    user_query: str,
    schema_info: str,
    sample_qa_pairs: str,
    value_mappings: Optional[str] = None
) -> str:
    """基于样本生成高质量 SQL 查询"""
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
        
        # 使用指数退避重试调用 LLM
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        retry_config = RetryConfigs.LLM_CALL
        response = retry_with_backoff_sync(
            llm.invoke,
            [HumanMessage(content=prompt)],
            **retry_config.to_dict()
        )
        
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
    """SQL 生成代理"""
    
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
2. 只返回 SQL 语句，不解释，不总结

**关键约束**:
1. 只能使用 schema_info 中提供的表名和列名
2. 禁止虚构任何表名或列名
3. 禁止在 SQL 中添加注释或假设
4. 禁止使用占位符值，必须生成可直接执行的 SQL

**错误恢复模式**:
- 如果 error_recovery_context 存在，说明上一次生成失败
- 必须仔细阅读 available_columns_hint 中的正确列名
- 生成完全不同结构的 SQL 避免相同错误

**生成原则**:
- 确保语法绝对正确
- 使用适当的连接方式
- 限制结果集大小（除非明确要求全部）
- 使用正确的值映射
- 避免危险操作（DROP, DELETE, UPDATE 等）

**禁止的行为**:
- 不要生成查询结果的预测或解读
- 不要添加 SQL 以外的内容
- 不要重复调用工具"""
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理 SQL 生成任务"""
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
            for msg in reversed(messages):
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
            
            # ✅ 获取数据库类型（根据实际连接动态获取）
            db_type = "mysql"  # 默认值
            if connection_id:
                try:
                    from app.services.db_service import get_db_connection_by_id
                    connection = get_db_connection_by_id(connection_id)
                    if connection and connection.db_type:
                        db_type = connection.db_type.lower()
                        logger.info(f"✓ 检测到数据库类型: {db_type}")
                except Exception as e:
                    logger.warning(f"获取数据库类型失败，使用默认值 mysql: {e}")
            
            # ✅ 关键修复：如果 schema_info 为 None 且处于错误恢复状态，重新获取 schema
            if not schema_info:
                if error_recovery_context and connection_id:
                    logger.warning("错误恢复时 schema_info 为 None，尝试重新获取...")
                    try:
                        from app.db.session import get_db_session
                        from app import crud
                        
                        with get_db_session() as db:
                            all_tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
                            tables_list = []
                            columns_list = []
                            
                            for table in all_tables:
                                table_columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                                tables_list.append({
                                    "table_name": table.table_name,
                                    "description": table.description or "",
                                    "id": table.id
                                })
                                columns_list.extend([
                                    {
                                        "column_name": col.column_name,
                                        "table_name": table.table_name,
                                        "data_type": col.data_type,
                                        "description": col.description or "",
                                        "is_primary_key": col.is_primary_key,
                                        "is_foreign_key": col.is_foreign_key
                                    }
                                    for col in table_columns
                                ])
                            
                            # 获取关系信息
                            relationships = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)
                            relationships_list = [
                                {
                                    "source_table": rel.source_table,
                                    "source_column": rel.source_column,
                                    "target_table": rel.target_table,
                                    "target_column": rel.target_column,
                                    "relationship_type": rel.relationship_type
                                }
                                for rel in relationships
                            ]
                            
                            schema_info = {
                                "tables": tables_list,
                                "columns": columns_list,
                                "relationships": relationships_list,
                                "connection_id": connection_id,
                                "db_type": db_type
                            }
                            
                            logger.info(f"✓ 错误恢复时重新获取 schema 成功: {len(tables_list)} 个表, {len(columns_list)} 个列")
                            
                    except Exception as e:
                        logger.error(f"错误恢复时重新获取 schema 失败: {e}")
                        raise ValueError(f"缺少 schema 信息且无法重新获取: {e}")
                else:
                    raise ValueError("缺少 schema 信息，请先执行 schema_agent")
            
            # ✅ 添加调试日志：检查 schema_info 的结构
            if isinstance(schema_info, dict):
                schema_tables = schema_info.get("tables", [])
                schema_columns = schema_info.get("columns", [])
                logger.info(f"[调试] schema_info 类型: dict")
                logger.info(f"[调试] schema_info keys: {list(schema_info.keys())}")
                logger.info(f"[调试] tables 类型: {type(schema_tables)}, 数量: {len(schema_tables) if isinstance(schema_tables, list) else 'N/A'}")
                logger.info(f"[调试] columns 类型: {type(schema_columns)}, 数量: {len(schema_columns) if isinstance(schema_columns, list) else 'N/A'}")
                if isinstance(schema_tables, list) and schema_tables:
                    first_table = schema_tables[0]
                    logger.info(f"[调试] 第一个表: {first_table}")
                    if len(schema_tables) > 1:
                        logger.info(f"[调试] 第二个表: {schema_tables[1]}")
            else:
                logger.info(f"[调试] schema_info 类型: {type(schema_info)}")
                if hasattr(schema_info, '__dict__'):
                    logger.info(f"[调试] schema_info.__dict__: {schema_info.__dict__}")
            
            # ✅ Phase 1: 使用统一的 SchemaContext 格式解析 schema_info
            schema_context = normalize_schema_info(schema_info, connection_id, db_type)
            table_names = schema_context.table_names
            logger.info(f"[调试] normalize 后的表数量: {len(table_names)}, 表名: {table_names}")
            logger.info(f"使用 schema 信息生成 SQL, tables={table_names[:5]}{'...' if len(table_names) > 5 else ''}")
            
            # ✅ 关键修复: 如果是错误恢复且错误类型是表名不存在，获取完整表列表
            if error_recovery_context:
                error_type = error_recovery_context.get("error_type", "")
                error_msg = error_recovery_context.get("error_message", "").lower()
                
                # 检测是否是表名/列名不存在的错误
                is_schema_mismatch = (
                    "unknown column" in error_msg or 
                    "doesn't exist" in error_msg or
                    "not found" in error_msg or
                    "prevalidation_failed" in error_type or
                    "未知表" in error_msg or
                    "unknown table" in error_msg
                )
                
                if is_schema_mismatch:
                    logger.warning("检测到 Schema 不匹配错误，尝试获取完整表列表...")
                    try:
                        from app.db.session import get_db_session
                        from app import crud
                        
                        with get_db_session() as db:
                            all_tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
                            all_columns = []
                            
                            full_tables_list = []
                            for table in all_tables:
                                table_columns = crud.schema_column.get_by_table(db=db, table_id=table.id)
                                full_tables_list.append({
                                    "table_name": table.table_name,
                                    "description": table.description or "",
                                    "columns": [
                                        {
                                            "column_name": col.column_name,
                                            "data_type": col.data_type,
                                            "description": col.description or "",
                                            "is_primary_key": col.is_primary_key,
                                            "is_foreign_key": col.is_foreign_key
                                        }
                                        for col in table_columns
                                    ]
                                })
                                all_columns.extend([
                                    {
                                        "column_name": col.column_name,
                                        "table_name": table.table_name,
                                        "data_type": col.data_type
                                    }
                                    for col in table_columns
                                ])
                            
                            # 更新 schema_context 为完整表列表
                            schema_context = normalize_schema_info({
                                "tables": full_tables_list,
                                "columns": all_columns,
                                "relationships": schema_info.get("relationships", [])
                            }, connection_id, db_type)
                            
                            table_names = schema_context.table_names
                            logger.info(f"✓ 已获取完整表列表: {len(table_names)} 个表")
                            logger.info(f"完整表名: {table_names}")
                            
                    except Exception as e:
                        logger.error(f"获取完整表列表失败: {e}")
            
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
            
            # 准备工具参数 - 使用统一的 SchemaContext 格式
            schema_info_json = json.dumps(schema_context.to_dict(), ensure_ascii=False)
            value_mappings_json = json.dumps(schema_context.value_mappings, ensure_ascii=False) if schema_context.value_mappings else None
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
                    schema_info=schema_context.to_dict(),
                    value_mappings=schema_context.value_mappings,
                    sample_qa_pairs=sample_qa_pairs,
                    db_type=db_type
                )
            else:
                # 调用同步工具生成 SQL
                result_json = generate_sql_query.invoke({
                    "user_query": user_query,
                    "schema_info": schema_info_json,
                    "state": {
                        "connection_id": connection_id,
                        "skip_sample_retrieval": skip_sample,
                        "error_recovery_context": error_recovery_context
                    },
                    "value_mappings": value_mappings_json,
                    "sample_qa_pairs": sample_qa_pairs_json,
                    "db_type": db_type
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
                # ✅ 关键修复：检查是否是列名验证失败
                if result.get("column_validation_errors"):
                    column_errors = result.get("column_validation_errors", [])
                    available_columns = result.get("available_columns", "")
                    failed_sql = result.get("sql_query", "")
                    
                    logger.warning(f"[列名验证失败] 错误: {column_errors}")
                    logger.info(f"[列名验证失败] 可用列信息已准备，将传递给重试")
                    
                    # 构建详细的错误恢复上下文，包含正确的列名信息
                    error_recovery_ctx = {
                        "error_type": "column_validation_failed",
                        "error_message": f"列名验证失败: {'; '.join(column_errors)}",
                        "failed_sql": failed_sql,
                        "recovery_action": "regenerate_sql",
                        "recovery_steps": [
                            "检查 SQL 中使用的列名",
                            "只使用下面列出的可用列名",
                            "不要猜测或虚构列名"
                        ],
                        # ✅ 关键：传递正确的列名信息给 LLM
                        "available_columns_hint": available_columns,
                        "column_whitelist": result.get("column_whitelist", {}),
                        "fix_prompt": f"""
【严重错误】上一次生成的 SQL 使用了不存在的列名！

错误详情:
{chr(10).join(f"  - {err}" for err in column_errors)}

【正确的列名信息】
{available_columns}

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
4. 如果需要的数据不存在，使用最接近的可用列

请重新生成 SQL，确保所有列名都在可用列表中。
"""
                    }
                    
                    return {
                        "messages": [],
                        "current_stage": "error_recovery",
                        "error_recovery_context": error_recovery_ctx,
                        "generated_sql": None,
                        "retry_count": state.get("retry_count", 0) + 1,
                        "error_history": state.get("error_history", []) + [{
                            "stage": "sql_generation_column_validation",
                            "error": f"列名验证失败: {'; '.join(column_errors)}",
                            "failed_sql": failed_sql,
                            "column_errors": column_errors,
                            # ✅ 关键修复：在 error_history 中也保存列名白名单
                            # 这样 error_recovery_agent 可以从 error_history 中提取
                            "column_whitelist": result.get("column_whitelist", {}),
                            "available_columns": available_columns
                        }]
                    }
                else:
                    raise ValueError(f"SQL 生成失败: {result.get('error')}")
            
            generated_sql = result.get("sql_query", "")
            
            if not generated_sql:
                raise ValueError("生成的 SQL 为空")
            
            logger.info(f"SQL 生成成功: {generated_sql[:100]}...")
            
            # ✅ SQL 修正步骤 - 使用 SchemaContext 的表名列表
            sql_fix_start = time.time()
            if writer:
                writer(create_sql_step_event(
                    step="sql_fix",
                    status="running",
                    result="验证 SQL 表名...",
                    time_ms=0
                ))
            
            # Phase 1: 直接使用 schema_context.table_names
            allowed_tables = schema_context.table_names
            
            # Phase 2: 使用 prevalidate_sql 进行全面验证
            from app.services.sql_helpers import prevalidate_sql, build_targeted_fix_prompt
            validation_result = prevalidate_sql(generated_sql, allowed_tables, db_type)
            
            sql_fix_elapsed = int((time.time() - sql_fix_start) * 1000)
            
            if not validation_result["can_execute"]:
                # Phase 2: 验证失败时阻止执行，触发重新生成
                error_msgs = validation_result["errors"]
                suggestions = validation_result["suggestions"]
                
                error_summary = "; ".join(error_msgs)
                logger.warning(f"[SQL预验证] 验证失败，需要重新生成: {error_summary}")
                
                if writer:
                    writer(create_sql_step_event(
                        step="sql_fix",
                        status="error",
                        result=f"❌ {error_summary}",
                        time_ms=sql_fix_elapsed
                    ))
                
                # 构建错误恢复上下文，触发重新生成
                # ✅ 关键修复：在错误恢复上下文中提供完整表列表
                full_table_list = []
                try:
                    from app.db.session import get_db_session
                    from app import crud
                    
                    with get_db_session() as db:
                        all_tables = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
                        full_table_list = [t.table_name for t in all_tables]
                        logger.info(f"[错误恢复] 获取完整表列表: {len(full_table_list)} 个表")
                except Exception as e:
                    logger.warning(f"获取完整表列表失败: {e}")
                    full_table_list = allowed_tables  # 回退到当前表列表
                
                error_recovery_context = {
                    "failed_sql": generated_sql,
                    "error_message": error_summary,
                    "error_type": "prevalidation_failed",
                    "recovery_steps": suggestions,
                    "fix_prompt": build_targeted_fix_prompt(error_summary, generated_sql, db_type),
                    "full_table_list": full_table_list  # 提供完整表列表供重试使用
                }
                
                return {
                    "messages": [],
                    "current_stage": "error_recovery",
                    "generated_sql": None,  # ✅ 显式清除失败的 SQL，防止被执行
                    "error_recovery_context": error_recovery_context,
                    "retry_count": state.get("retry_count", 0) + 1,
                    "error_history": state.get("error_history", []) + [{
                        "stage": "sql_prevalidation",
                        "error": error_summary,
                        "failed_sql": generated_sql,
                        "suggestions": suggestions
                    }]
                }
            
            # 验证通过，但可能有警告
            if validation_result["warnings"]:
                warning_msg = "; ".join(validation_result["warnings"])
                logger.info(f"[SQL预验证] 警告: {warning_msg}")
                
                if writer:
                    writer(create_sql_step_event(
                        step="sql_fix",
                        status="completed",
                        result=f"⚠️ 验证通过，但有警告: {warning_msg[:100]}",
                        time_ms=sql_fix_elapsed
                    ))
            else:
                if writer:
                    writer(create_sql_step_event(
                        step="sql_fix",
                        status="completed",
                        result=f"✓ SQL 验证通过",
                        time_ms=sql_fix_elapsed
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
                        "db_type": db_type
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
                    "connection_id": connection_id,
                    "validation_warnings": validation_result["warnings"]
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
            
            # ✅ 修复：设置 error_recovery_context，避免路由时 NoneType 错误
            error_msg = str(e)
            error_recovery_ctx = {
                "error_type": "sql_generation_failed",
                "error_message": error_msg,
                "failed_sql": "",
                "recovery_action": "regenerate_sql",
                "recovery_steps": ["检查错误信息", "简化查询", "重新生成 SQL"],
                "retry_count": state.get("retry_count", 0) + 1
            }
            
            return {
                "messages": [ai_message, tool_message],
                "current_stage": "error_recovery",
                "error_recovery_context": error_recovery_ctx,
                "generated_sql": None,  # 清除失败的 SQL
                "error_history": state.get("error_history", []) + [{
                    "stage": "sql_generation",
                    "error": error_msg,
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
        sample_qa_pairs: List[Dict[str, Any]],
        db_type: str = "mysql"
    ) -> str:
        """基于缓存 SQL 模板生成新 SQL"""
        try:
            # 获取数据库特定语法规则
            db_rules_prompt = format_database_rules_prompt(db_type)
            
            # 构建模板增强的生成提示
            prompt = f"""作为 SQL 专家，请基于以下信息修改 SQL 查询：

**数据库类型**: {db_type}

**用户需求**: {user_query}

**参考SQL模板** (来自相似查询):
```sql
{cached_sql_template}
```

**数据库模式**:
{json.dumps(schema_info, ensure_ascii=False, indent=2)}

**值映射信息**:
{json.dumps(value_mappings, ensure_ascii=False, indent=2) if value_mappings else '无'}

{db_rules_prompt}

**任务**: 
1. 分析用户需求与参考SQL的差异
2. 基于参考SQL的结构，修改WHERE条件、字段选择等以满足用户需求
3. 【最重要】确保生成的SQL完全符合 {db_type.upper()} 的语法规则
4. 确保SQL语法正确，字段名与模式一致

**要求**: 只返回修改后的SQL语句，不要其他内容。
"""
            
            # 使用指数退避重试调用 LLM
            llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
            retry_config = RetryConfigs.LLM_CALL
            response = retry_with_backoff_sync(
                llm.invoke,
                [HumanMessage(content=prompt)],
                **retry_config.to_dict()
            )
            
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
                "db_type": db_type
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
