"""
SQL 辅助函数模块 (轻量级)

此模块包含纯工具函数，不依赖任何数据库或 ORM 模块，
可以安全地在任何地方导入而不触发重型依赖链。

用于 dashboard_insight_graph、sql_generator_agent 等模块复用。

Phase 1 优化:
- 添加 Schema 格式验证工具函数
"""
from typing import Any
import re


def get_sql_syntax_guide(db_type: str) -> str:
    """
    获取数据库特定的 SQL 语法指南
    
    Args:
        db_type: 数据库类型 (MYSQL, POSTGRESQL, SQLITE, SQLSERVER, ORACLE)
        
    Returns:
        str: SQL 语法指南字符串
    """
    guides = {
        "MYSQL": "MySQL: 使用LIMIT, 反引号`, DATE_FORMAT(), 不支持FULL OUTER JOIN",
        "MARIADB": "MariaDB: 使用LIMIT, 反引号`, DATE_FORMAT(), 不支持FULL OUTER JOIN",
        "POSTGRESQL": "PostgreSQL: 使用LIMIT, 双引号\", TO_CHAR(), 支持FULL OUTER JOIN",
        "SQLITE": "SQLite: 使用LIMIT, strftime(), 不支持RIGHT JOIN/FULL OUTER JOIN",
        "SQLSERVER": "SQL Server: 使用TOP N, 方括号[], FORMAT(), 支持FULL OUTER JOIN",
        "ORACLE": "Oracle: 使用ROWNUM, 双引号\", TO_CHAR(), 需要FROM DUAL",
    }
    return guides.get(db_type.upper(), f"使用标准ANSI SQL语法 ({db_type})")


def infer_semantic_type(column_name: str, data_type: str) -> str:
    """
    推断列的语义类型
    
    Args:
        column_name: 列名
        data_type: 数据类型
        
    Returns:
        str: 语义类型 (datetime, currency, quantity, identifier, name, category, general)
    """
    name_lower = column_name.lower()
    
    if any(kw in name_lower for kw in ["date", "time", "created", "updated", "timestamp"]):
        return "datetime"
    if any(kw in name_lower for kw in ["price", "amount", "cost", "fee", "total", "money"]):
        return "currency"
    if any(kw in name_lower for kw in ["count", "quantity", "qty", "num", "number"]):
        return "quantity"
    if name_lower.endswith("_id") or name_lower == "id":
        return "identifier"
    if any(kw in name_lower for kw in ["name", "title", "label"]):
        return "name"
    if any(kw in name_lower for kw in ["status", "state", "type", "category"]):
        return "category"
    
    return "general"


def is_aggregatable_type(data_type: str) -> bool:
    """
    判断数据类型是否可聚合 (SUM, AVG, etc.)
    
    Args:
        data_type: 数据类型字符串
        
    Returns:
        bool: 是否可聚合
    """
    numeric_types = ["int", "float", "double", "decimal", "numeric", "number", "bigint", "smallint", "tinyint"]
    return any(t in data_type.lower() for t in numeric_types)


def is_groupable_type(data_type: str, column_name: str) -> bool:
    """
    判断列是否适合 GROUP BY
    
    Args:
        data_type: 数据类型字符串
        column_name: 列名
        
    Returns:
        bool: 是否适合分组
    """
    string_types = ["varchar", "char", "text", "string", "enum", "nvarchar", "nchar"]
    date_types = ["date", "datetime", "timestamp"]
    
    if any(t in data_type.lower() for t in string_types + date_types):
        return True
    if "_id" in column_name.lower() and column_name.lower() != "id":
        return True
    
    return False


def validate_sql_safety(sql: str) -> dict:
    """
    验证 SQL 安全性
    
    Args:
        sql: SQL 语句
        
    Returns:
        dict: {"valid": bool, "error": str or None, "warnings": list}
    """
    result = {"valid": True, "error": None, "warnings": []}
    sql_upper = sql.upper().strip()
    
    # 安全检查 - 危险关键字
    dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    for kw in dangerous_keywords:
        if kw in sql_upper and not sql_upper.startswith("SELECT"):
            result["valid"] = False
            result["error"] = f"检测到危险操作: {kw}"
            return result
    
    # 必须是 SELECT 语句
    if not sql_upper.startswith("SELECT"):
        result["valid"] = False
        result["error"] = "必须是 SELECT 语句"
        return result
    
    return result


def clean_sql_from_llm_response(sql: str) -> str:
    """
    清理 LLM 响应中的 SQL (去除 markdown 包裹)
    
    Args:
        sql: 原始 SQL 字符串
        
    Returns:
        str: 清理后的 SQL
    """
    sql = sql.strip()
    
    # 去除 markdown 代码块
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    
    if sql.endswith("```"):
        sql = sql[:-3]
    
    return sql.strip()


def extract_table_names_from_sql(sql: str) -> list:
    """
    从 SQL 语句中提取表名
    
    支持的语法:
    - FROM table_name
    - JOIN table_name
    - FROM schema.table_name
    - 带别名: FROM table_name AS alias, FROM table_name alias
    
    Args:
        sql: SQL 语句
        
    Returns:
        list: 提取的表名列表（不含 schema 前缀和别名）
    """
    import re
    
    tables = set()
    sql_upper = sql.upper()
    
    # 移除字符串字面量（避免误匹配）
    sql_clean = re.sub(r"'[^']*'", "''", sql)
    sql_clean = re.sub(r'"[^"]*"', '""', sql_clean)
    
    # 匹配 FROM 子句中的表名
    # 支持: FROM table, FROM schema.table, FROM table AS alias, FROM table alias
    from_pattern = r'\bFROM\s+([`"\[\]]?[\w]+[`"\]\]]?(?:\s*\.\s*[`"\[\]]?[\w]+[`"\]\]]?)?)'
    for match in re.finditer(from_pattern, sql_clean, re.IGNORECASE):
        table_ref = match.group(1).strip()
        # 提取表名（去除 schema 前缀和引号）
        table_name = _extract_table_name(table_ref)
        if table_name:
            tables.add(table_name.lower())
    
    # 匹配 JOIN 子句中的表名
    join_pattern = r'\bJOIN\s+([`"\[\]]?[\w]+[`"\]\]]?(?:\s*\.\s*[`"\[\]]?[\w]+[`"\]\]]?)?)'
    for match in re.finditer(join_pattern, sql_clean, re.IGNORECASE):
        table_ref = match.group(1).strip()
        table_name = _extract_table_name(table_ref)
        if table_name:
            tables.add(table_name.lower())
    
    return list(tables)


def _extract_table_name(table_ref: str) -> str:
    """
    从表引用中提取纯表名
    
    处理:
    - schema.table -> table
    - `table` -> table
    - [table] -> table
    - "table" -> table
    
    Args:
        table_ref: 表引用字符串
        
    Returns:
        str: 纯表名
    """
    import re
    
    # 去除引号
    table_ref = re.sub(r'[`"\[\]]', '', table_ref)
    
    # 如果有 schema 前缀，取最后一部分
    if '.' in table_ref:
        table_ref = table_ref.split('.')[-1]
    
    return table_ref.strip()


def validate_sql_tables(sql: str, allowed_tables: list) -> dict:
    """
    验证 SQL 中使用的表是否在允许列表中
    
    用于防止 LLM 生成使用不存在表的 SQL（幻觉问题）
    
    Args:
        sql: SQL 语句
        allowed_tables: 允许使用的表名列表
        
    Returns:
        dict: {
            "valid": bool,
            "used_tables": list,  # SQL 中使用的表
            "invalid_tables": list,  # 不在允许列表中的表
            "error": str or None
        }
    """
    result = {
        "valid": True,
        "used_tables": [],
        "invalid_tables": [],
        "error": None
    }
    
    # 提取 SQL 中的表名
    used_tables = extract_table_names_from_sql(sql)
    result["used_tables"] = used_tables
    
    # 规范化允许的表名（小写）
    allowed_tables_lower = [t.lower() for t in allowed_tables]
    
    # 检查每个使用的表是否在允许列表中
    for table in used_tables:
        if table.lower() not in allowed_tables_lower:
            result["invalid_tables"].append(table)
    
    if result["invalid_tables"]:
        result["valid"] = False
        result["error"] = f"SQL 使用了未知表: {', '.join(result['invalid_tables'])}"
    
    return result


def suggest_similar_table(table_name: str, allowed_tables: list) -> str:
    """
    为无效表名建议相似的有效表名
    
    使用简单的字符串相似度匹配
    
    Args:
        table_name: 无效的表名
        allowed_tables: 允许的表名列表
        
    Returns:
        str: 最相似的表名，如果没有找到则返回空字符串
    """
    if not allowed_tables:
        return ""
    
    table_lower = table_name.lower()
    best_match = ""
    best_score = 0
    
    for allowed in allowed_tables:
        allowed_lower = allowed.lower()
        
        # 计算简单相似度
        score = 0
        
        # 完全包含
        if table_lower in allowed_lower or allowed_lower in table_lower:
            score = 0.8
        
        # 前缀匹配
        elif table_lower.startswith(allowed_lower[:3]) or allowed_lower.startswith(table_lower[:3]):
            score = 0.5
        
        # 共同字符比例
        else:
            common = set(table_lower) & set(allowed_lower)
            score = len(common) / max(len(table_lower), len(allowed_lower))
        
        if score > best_score:
            best_score = score
            best_match = allowed
    
    return best_match if best_score > 0.3 else ""


# ============================================================================
# Phase 1: Schema 格式验证工具
# ============================================================================

def validate_schema_format(schema_info: Any) -> dict:
    """
    验证 Schema 信息的格式完整性
    
    用于调试和确保 Schema 在各模块间传递时格式正确。
    
    Args:
        schema_info: 任意格式的 schema 信息
        
    Returns:
        dict: {
            "valid": bool,
            "format_type": str,  # "SchemaContext", "dict_standard", "dict_nested", "unknown"
            "table_count": int,
            "column_count": int,
            "issues": list,  # 发现的问题列表
        }
    """
    result = {
        "valid": True,
        "format_type": "unknown",
        "table_count": 0,
        "column_count": 0,
        "issues": []
    }
    
    if schema_info is None:
        result["valid"] = False
        result["issues"].append("schema_info 为 None")
        return result
    
    # 检测格式类型
    try:
        from app.schemas.schema_context import SchemaContext
        if isinstance(schema_info, SchemaContext):
            result["format_type"] = "SchemaContext"
            result["table_count"] = schema_info.table_count
            result["column_count"] = schema_info.column_count
            return result
    except ImportError:
        pass
    
    if isinstance(schema_info, dict):
        # 检查是否是标准格式
        if "tables" in schema_info:
            tables = schema_info["tables"]
            
            # 检查是否是嵌套格式
            if isinstance(tables, dict) and "tables" in tables:
                result["format_type"] = "dict_nested"
                result["issues"].append("检测到嵌套格式 (schema_info.tables.tables)，建议使用 normalize_schema_info 转换")
                inner_tables = tables.get("tables", [])
                result["table_count"] = len(inner_tables) if isinstance(inner_tables, list) else 0
                inner_columns = tables.get("columns", [])
                result["column_count"] = len(inner_columns) if isinstance(inner_columns, list) else 0
            elif isinstance(tables, list):
                result["format_type"] = "dict_standard"
                result["table_count"] = len(tables)
                
                # 检查表信息格式
                for i, t in enumerate(tables[:3]):  # 只检查前3个
                    if isinstance(t, dict):
                        if "table_name" not in t and "name" not in t:
                            result["issues"].append(f"表 {i} 缺少 table_name 或 name 字段")
                
                columns = schema_info.get("columns", [])
                result["column_count"] = len(columns) if isinstance(columns, list) else 0
            else:
                result["format_type"] = "dict_unknown"
                result["issues"].append(f"tables 字段类型异常: {type(tables)}")
        else:
            result["format_type"] = "dict_no_tables"
            result["issues"].append("缺少 tables 字段")
    else:
        result["format_type"] = "unknown"
        result["issues"].append(f"未知类型: {type(schema_info)}")
    
    if result["issues"]:
        result["valid"] = False
    
    return result


def get_schema_summary(schema_info: Any) -> str:
    """
    获取 Schema 信息的简要摘要（用于日志）
    
    Args:
        schema_info: 任意格式的 schema 信息
        
    Returns:
        str: 摘要字符串，如 "16 表, 120 列, 格式: SchemaContext"
    """
    validation = validate_schema_format(schema_info)
    
    summary = f"{validation['table_count']} 表, {validation['column_count']} 列"
    summary += f", 格式: {validation['format_type']}"
    
    if not validation["valid"]:
        summary += f" [问题: {len(validation['issues'])}]"
    
    return summary


# ============================================================================
# Phase 2: SQL 生成准确性增强
# ============================================================================

from typing import Tuple, List, Dict, Optional
import re


def validate_sql_syntax(sql: str) -> Tuple[bool, str]:
    """
    验证 SQL 基本语法
    
    使用简单的规则检查，不依赖外部库。
    
    Args:
        sql: SQL 语句
        
    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if not sql or not sql.strip():
        return False, "SQL 语句为空"
    
    sql_clean = sql.strip()
    sql_upper = sql_clean.upper()
    
    # 必须以 SELECT 开头
    if not sql_upper.startswith("SELECT"):
        return False, "SQL 必须以 SELECT 开头"
    
    # 检查括号匹配
    open_parens = sql_clean.count('(')
    close_parens = sql_clean.count(')')
    if open_parens != close_parens:
        return False, f"括号不匹配: 左括号 {open_parens} 个, 右括号 {close_parens} 个"
    
    # 检查引号匹配（单引号）
    single_quotes = sql_clean.count("'")
    if single_quotes % 2 != 0:
        return False, "单引号不匹配"
    
    # 检查是否有 FROM 子句（除非是简单的 SELECT 1 类型）
    if not re.search(r'\bFROM\b', sql_upper) and not re.search(r'SELECT\s+[\d\w\(\)]+\s*$', sql_upper):
        return False, "缺少 FROM 子句"
    
    # 检查常见语法错误
    # 1. SELECT 后直接跟 FROM（没有列）
    if re.search(r'\bSELECT\s+FROM\b', sql_upper):
        return False, "SELECT 和 FROM 之间缺少列名"
    
    # 2. 连续的逗号
    if ',,' in sql_clean or ', ,' in sql_clean:
        return False, "检测到连续的逗号"
    
    # 3. WHERE 后直接跟 AND/OR
    if re.search(r'\bWHERE\s+(AND|OR)\b', sql_upper):
        return False, "WHERE 后不能直接跟 AND/OR"
    
    # 4. GROUP BY 后没有列名
    if re.search(r'\bGROUP\s+BY\s*(ORDER|HAVING|LIMIT|$)', sql_upper):
        return False, "GROUP BY 后缺少列名"
    
    # 5. ORDER BY 后没有列名
    if re.search(r'\bORDER\s+BY\s*(LIMIT|$)', sql_upper):
        return False, "ORDER BY 后缺少列名"
    
    return True, ""


def check_mysql_antipatterns(sql: str) -> List[Dict[str, str]]:
    """
    检测 MySQL 已知的反模式和问题
    
    这些模式在 MySQL 中会导致错误或性能问题。
    
    Args:
        sql: SQL 语句
        
    Returns:
        List[Dict]: 检测到的问题列表，每个包含 {pattern, description, severity, suggestion}
    """
    issues = []
    sql_upper = sql.upper()
    
    # 1. IN 子查询中使用 LIMIT（MySQL 硬性限制）
    # 匹配: WHERE xxx IN (SELECT ... LIMIT ...)
    # 匹配: WHERE xxx IN (SELECT ... ORDER BY ... LIMIT ...)
    in_limit_pattern = r'\bIN\s*\(\s*SELECT\b[^)]*\bLIMIT\b'
    if re.search(in_limit_pattern, sql_upper):
        issues.append({
            "pattern": "IN_SUBQUERY_LIMIT",
            "description": "MySQL 不支持在 IN/ALL/ANY/SOME 子查询中使用 LIMIT",
            "severity": "error",
            "suggestion": "将 WHERE id IN (SELECT ... LIMIT N) 改写为 JOIN 派生表方式: JOIN (SELECT ... LIMIT N) t ON ..."
        })
    
    # 2. ALL/ANY/SOME 子查询中使用 LIMIT
    all_any_limit_pattern = r'\b(ALL|ANY|SOME)\s*\(\s*SELECT\b[^)]*\bLIMIT\b'
    if re.search(all_any_limit_pattern, sql_upper):
        issues.append({
            "pattern": "ALL_ANY_SUBQUERY_LIMIT",
            "description": "MySQL 不支持在 ALL/ANY/SOME 子查询中使用 LIMIT",
            "severity": "error",
            "suggestion": "使用 JOIN 派生表方式替代"
        })
    
    # 3. FULL OUTER JOIN（MySQL 不支持）
    if "FULL OUTER JOIN" in sql_upper or "FULL JOIN" in sql_upper:
        issues.append({
            "pattern": "FULL_OUTER_JOIN",
            "description": "MySQL 不支持 FULL OUTER JOIN",
            "severity": "error",
            "suggestion": "使用 LEFT JOIN UNION RIGHT JOIN 模拟 FULL OUTER JOIN"
        })
    
    # 4. LIMIT 中使用子查询（MySQL 不支持）
    # 匹配: LIMIT (SELECT ...)
    limit_subquery_pattern = r'\bLIMIT\s*\(\s*SELECT\b'
    if re.search(limit_subquery_pattern, sql_upper):
        issues.append({
            "pattern": "LIMIT_SUBQUERY",
            "description": "MySQL 的 LIMIT 子句不支持子查询",
            "severity": "error",
            "suggestion": "将 LIMIT 值计算移到应用层，或使用变量"
        })
    
    # 5. OFFSET 中使用子查询
    offset_subquery_pattern = r'\bOFFSET\s*\(\s*SELECT\b'
    if re.search(offset_subquery_pattern, sql_upper):
        issues.append({
            "pattern": "OFFSET_SUBQUERY",
            "description": "MySQL 的 OFFSET 子句不支持子查询",
            "severity": "error",
            "suggestion": "将 OFFSET 值计算移到应用层，或使用变量"
        })
    
    # 6. 在 SELECT 列表中使用未聚合的列（GROUP BY 问题）
    # 这个检测比较复杂，只做简单提示
    if "GROUP BY" in sql_upper:
        # 检查是否有 SELECT * 与 GROUP BY 一起使用
        if re.search(r'\bSELECT\s+\*\s+.*\bGROUP\s+BY\b', sql_upper):
            issues.append({
                "pattern": "SELECT_STAR_GROUP_BY",
                "description": "SELECT * 与 GROUP BY 一起使用可能导致错误",
                "severity": "warning",
                "suggestion": "明确列出需要的列，确保非聚合列都在 GROUP BY 中"
            })
    
    # 7. 使用保留字作为标识符但未加引号（更精确的检测）
    # 只检测明显作为列名或表别名使用的情况
    mysql_reserved_as_identifier = ["ORDER", "GROUP", "KEY", "INDEX", "TABLE", "SELECT", "WHERE", "LIMIT"]
    for word in mysql_reserved_as_identifier:
        # 检查是否作为列名使用（在 SELECT 后、逗号后、或 AS 后）
        # 排除作为关键字的正常使用
        patterns = [
            rf'\bSELECT\s+{word}\s*[,\s]',  # SELECT ORDER, ...
            rf',\s*{word}\s*[,\s]',  # ..., ORDER, ...
            rf'\bAS\s+{word}\b',  # AS ORDER
            rf'\.{word}\b',  # table.ORDER
        ]
        for pattern in patterns:
            if re.search(pattern, sql_upper):
                # 检查是否已经用反引号包裹
                if f'`{word.lower()}`' not in sql.lower() and f'`{word}`' not in sql:
                    issues.append({
                        "pattern": "RESERVED_WORD_UNQUOTED",
                        "description": f"'{word}' 是 MySQL 保留字，作为标识符使用时需要用反引号包裹",
                        "severity": "warning",
                        "suggestion": f"将 {word} 改为 `{word}`"
                    })
                    break
        else:
            continue
        break  # 只报告一次
    
    return issues


def check_postgresql_antipatterns(sql: str) -> List[Dict[str, str]]:
    """
    检测 PostgreSQL 特定的问题
    
    Args:
        sql: SQL 语句
        
    Returns:
        List[Dict]: 检测到的问题列表
    """
    issues = []
    sql_upper = sql.upper()
    
    # 1. 使用反引号（PostgreSQL 使用双引号）
    if '`' in sql:
        issues.append({
            "pattern": "BACKTICK_IDENTIFIER",
            "description": "PostgreSQL 使用双引号而非反引号包裹标识符",
            "severity": "error",
            "suggestion": "将 `table_name` 改为 \"table_name\""
        })
    
    # 2. 使用 LIMIT 和 OFFSET 的 MySQL 语法
    if re.search(r'\bLIMIT\s+\d+\s*,\s*\d+', sql_upper):
        issues.append({
            "pattern": "MYSQL_LIMIT_SYNTAX",
            "description": "PostgreSQL 不支持 LIMIT offset, count 语法",
            "severity": "error",
            "suggestion": "使用 LIMIT count OFFSET offset 语法"
        })
    
    return issues


def check_sql_antipatterns(sql: str, db_type: str = "mysql") -> List[Dict[str, str]]:
    """
    根据数据库类型检测 SQL 反模式
    
    Args:
        sql: SQL 语句
        db_type: 数据库类型
        
    Returns:
        List[Dict]: 检测到的问题列表
    """
    db_type_lower = db_type.lower()
    
    if db_type_lower in ["mysql", "mariadb"]:
        return check_mysql_antipatterns(sql)
    elif db_type_lower in ["postgresql", "postgres"]:
        return check_postgresql_antipatterns(sql)
    else:
        # 通用检查
        return []


def build_targeted_fix_prompt(error_message: str, failed_sql: str, db_type: str = "mysql") -> str:
    """
    根据错误类型生成针对性的修复提示
    
    用于错误恢复时，给 LLM 提供具体的修复指导。
    
    Args:
        error_message: 数据库返回的错误信息
        failed_sql: 失败的 SQL 语句
        db_type: 数据库类型
        
    Returns:
        str: 针对性的修复提示
    """
    error_lower = error_message.lower()
    hints = []
    
    # MySQL 特定错误
    if db_type.lower() in ["mysql", "mariadb"]:
        # LIMIT in IN subquery
        if "limit" in error_lower and ("in" in error_lower or "subquery" in error_lower or "1235" in error_lower):
            hints.append("【关键错误】MySQL 不支持在 IN/ALL/ANY/SOME 子查询中使用 LIMIT")
            hints.append("【必须修复】将 WHERE id IN (SELECT ... LIMIT N) 改写为:")
            hints.append("  JOIN (SELECT ... LIMIT N) AS subq ON main.id = subq.id")
            hints.append("【示例】:")
            hints.append("  错误: SELECT * FROM orders WHERE product_id IN (SELECT id FROM products ORDER BY sales DESC LIMIT 10)")
            hints.append("  正确: SELECT o.* FROM orders o JOIN (SELECT id FROM products ORDER BY sales DESC LIMIT 10) top ON o.product_id = top.id")
        
        # Unknown column
        elif "unknown column" in error_lower:
            # 尝试提取列名
            col_match = re.search(r"unknown column '([^']+)'", error_lower)
            col_name = col_match.group(1) if col_match else "未知"
            hints.append(f"【关键错误】列 '{col_name}' 不存在")
            hints.append("【检查】确保列名拼写正确，且在正确的表中")
            hints.append("【注意】如果使用了表别名，确保引用格式为 alias.column_name")
        
        # Table doesn't exist
        elif "table" in error_lower and ("doesn't exist" in error_lower or "not found" in error_lower):
            table_match = re.search(r"table '([^']+)'", error_lower)
            table_name = table_match.group(1) if table_match else "未知"
            hints.append(f"【关键错误】表 '{table_name}' 不存在")
            hints.append("【检查】确保表名拼写正确，只使用 Schema 中提供的表")
        
        # GROUP BY error (1055)
        elif "group by" in error_lower or "1055" in error_lower or "only_full_group_by" in error_lower:
            hints.append("【关键错误】GROUP BY 子句不完整")
            hints.append("【修复】SELECT 中的非聚合列必须出现在 GROUP BY 中")
            hints.append("【或者】对非分组列使用聚合函数如 MAX(), MIN(), ANY_VALUE()")
        
        # Subquery returns more than 1 row
        elif "subquery returns more than 1 row" in error_lower:
            hints.append("【关键错误】子查询返回了多行，但上下文期望单值")
            hints.append("【修复方案】:")
            hints.append("  1. 使用 IN 替代 = (如果是比较操作)")
            hints.append("  2. 添加 LIMIT 1 (如果只需要一个值)")
            hints.append("  3. 使用聚合函数 MAX/MIN/AVG (如果需要汇总)")
        
        # Syntax error
        elif "syntax" in error_lower or "1064" in error_lower:
            hints.append("【关键错误】SQL 语法错误")
            hints.append("【检查】:")
            hints.append("  1. 括号是否匹配")
            hints.append("  2. 关键字拼写是否正确")
            hints.append("  3. 逗号使用是否正确")
            hints.append("  4. 字符串是否用单引号包裹")
    
    # PostgreSQL 特定错误
    elif db_type.lower() in ["postgresql", "postgres"]:
        if "column" in error_lower and "does not exist" in error_lower:
            hints.append("【关键错误】列不存在")
            hints.append("【注意】PostgreSQL 列名区分大小写（除非用双引号）")
            hints.append("【检查】确保列名大小写与 Schema 一致")
        
        elif "relation" in error_lower and "does not exist" in error_lower:
            hints.append("【关键错误】表不存在")
            hints.append("【注意】PostgreSQL 表名区分大小写")
    
    # 通用错误处理
    if not hints:
        hints.append("【错误】SQL 执行失败")
        hints.append(f"【错误信息】{error_message[:200]}")
        hints.append("【建议】简化 SQL 结构，检查表名和列名是否正确")
    
    return "\n".join(hints)

