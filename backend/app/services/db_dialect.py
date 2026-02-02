"""
数据库方言管理模块

集中管理不同数据库的语法差异，为 SQL 生成和验证提供支持。

设计原则：
1. 简洁清晰：每种数据库一个配置，规则明确
2. 易于扩展：添加新数据库只需添加配置
3. 不过度设计：只包含实际需要的差异
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class DialectConfig:
    """数据库方言配置"""
    
    name: str                          # 数据库名称
    
    # 标识符引用
    identifier_quote: str = "`"        # 标识符引号：MySQL 用 `，PostgreSQL 用 "，SQL Server 用 []
    
    # 结果限制语法
    limit_syntax: str = "LIMIT"        # LIMIT, TOP, FETCH FIRST
    limit_position: str = "end"        # end（末尾）, after_select（SELECT 后）
    
    # 字符串函数
    concat_operator: str = "CONCAT"    # 字符串连接：CONCAT()，||，+
    date_format_func: str = "DATE_FORMAT"  # 日期格式化函数
    
    # 布尔值
    true_value: str = "TRUE"           # TRUE, 1
    false_value: str = "FALSE"         # FALSE, 0
    
    # JOIN 支持
    supports_full_outer_join: bool = True
    supports_right_join: bool = True
    
    # 其他特性
    supports_limit_in_subquery: bool = True  # IN 子查询中是否支持 LIMIT
    case_sensitive_identifiers: bool = False  # 标识符是否大小写敏感
    
    # 保留字（需要用引号包裹）
    reserved_words: List[str] = field(default_factory=list)


# ============================================================================
# 预定义方言配置
# ============================================================================

MYSQL_DIALECT = DialectConfig(
    name="MySQL",
    identifier_quote="`",
    limit_syntax="LIMIT",
    limit_position="end",
    concat_operator="CONCAT",
    date_format_func="DATE_FORMAT",
    true_value="TRUE",
    false_value="FALSE",
    supports_full_outer_join=False,
    supports_right_join=True,
    supports_limit_in_subquery=False,  # MySQL 不支持 IN 子查询中的 LIMIT
    case_sensitive_identifiers=False,
    reserved_words=["ORDER", "GROUP", "KEY", "INDEX", "TABLE", "LIMIT", "RANGE", "READ", "WRITE"]
)

POSTGRESQL_DIALECT = DialectConfig(
    name="PostgreSQL",
    identifier_quote='"',
    limit_syntax="LIMIT",
    limit_position="end",
    concat_operator="||",
    date_format_func="TO_CHAR",
    true_value="TRUE",
    false_value="FALSE",
    supports_full_outer_join=True,
    supports_right_join=True,
    supports_limit_in_subquery=True,
    case_sensitive_identifiers=True,  # PostgreSQL 默认转小写，但引号内区分大小写
    reserved_words=["USER", "ORDER", "GROUP", "LIMIT", "TABLE", "COLUMN", "ALL", "ARRAY"]
)

SQLITE_DIALECT = DialectConfig(
    name="SQLite",
    identifier_quote='"',
    limit_syntax="LIMIT",
    limit_position="end",
    concat_operator="||",
    date_format_func="strftime",
    true_value="1",
    false_value="0",
    supports_full_outer_join=False,
    supports_right_join=False,  # SQLite 不支持 RIGHT JOIN
    supports_limit_in_subquery=True,
    case_sensitive_identifiers=False,
    reserved_words=["ORDER", "GROUP", "TABLE", "INDEX", "LIMIT"]
)

SQLSERVER_DIALECT = DialectConfig(
    name="SQL Server",
    identifier_quote="[",  # SQL Server 使用 [name]
    limit_syntax="TOP",
    limit_position="after_select",  # SELECT TOP N ...
    concat_operator="+",
    date_format_func="FORMAT",
    true_value="1",
    false_value="0",
    supports_full_outer_join=True,
    supports_right_join=True,
    supports_limit_in_subquery=True,
    case_sensitive_identifiers=False,
    reserved_words=["USER", "ORDER", "GROUP", "TABLE", "INDEX", "KEY", "COLUMN"]
)

ORACLE_DIALECT = DialectConfig(
    name="Oracle",
    identifier_quote='"',
    limit_syntax="FETCH FIRST",
    limit_position="end",
    concat_operator="||",
    date_format_func="TO_CHAR",
    true_value="1",
    false_value="0",
    supports_full_outer_join=True,
    supports_right_join=True,
    supports_limit_in_subquery=True,
    case_sensitive_identifiers=True,
    reserved_words=["USER", "ORDER", "GROUP", "TABLE", "INDEX", "COLUMN", "DATE", "NUMBER", "LEVEL"]
)

# 方言映射表
_DIALECT_MAP: Dict[str, DialectConfig] = {
    "mysql": MYSQL_DIALECT,
    "mariadb": MYSQL_DIALECT,
    "postgresql": POSTGRESQL_DIALECT,
    "postgres": POSTGRESQL_DIALECT,
    "sqlite": SQLITE_DIALECT,
    "sqlserver": SQLSERVER_DIALECT,
    "mssql": SQLSERVER_DIALECT,
    "oracle": ORACLE_DIALECT,
}


def get_dialect(db_type: str) -> DialectConfig:
    """
    获取数据库方言配置
    
    Args:
        db_type: 数据库类型
        
    Returns:
        DialectConfig: 方言配置，未知类型返回 MySQL 配置
    """
    return _DIALECT_MAP.get(db_type.lower(), MYSQL_DIALECT)


def get_syntax_guide_for_prompt(db_type: str) -> str:
    """
    获取用于 LLM prompt 的详细语法指南
    
    这是给 SQL 生成 Agent 使用的，提供清晰的语法约束。
    
    Args:
        db_type: 数据库类型
        
    Returns:
        str: 详细的语法指南文本
    """
    dialect = get_dialect(db_type)
    
    lines = [
        f"## 数据库语法规则（{dialect.name}）",
        "",
        "【必须遵循】以下是该数据库的语法规则：",
        "",
    ]
    
    # 1. 标识符引用
    if dialect.identifier_quote == "`":
        lines.append(f"1. 标识符引用：使用反引号 ` 包裹（如 `order`, `table`）")
    elif dialect.identifier_quote == '"':
        lines.append(f'1. 标识符引用：使用双引号 " 包裹（如 "order", "table"）')
    else:
        lines.append(f"1. 标识符引用：使用方括号 [] 包裹（如 [order], [table]）")
    
    # 2. 结果限制
    if dialect.limit_syntax == "LIMIT":
        lines.append("2. 限制结果数量：在语句末尾使用 LIMIT N（如 SELECT * FROM t LIMIT 100）")
    elif dialect.limit_syntax == "TOP":
        lines.append("2. 限制结果数量：在 SELECT 后使用 TOP N（如 SELECT TOP 100 * FROM t）")
    else:
        lines.append("2. 限制结果数量：在语句末尾使用 FETCH FIRST N ROWS ONLY")
    
    # 3. JOIN 限制
    join_notes = []
    if not dialect.supports_full_outer_join:
        join_notes.append("不支持 FULL OUTER JOIN")
    if not dialect.supports_right_join:
        join_notes.append("不支持 RIGHT JOIN")
    if join_notes:
        lines.append(f"3. JOIN 限制：{', '.join(join_notes)}")
    else:
        lines.append("3. JOIN 支持：支持所有 JOIN 类型")
    
    # 4. 子查询限制（重要！）
    if not dialect.supports_limit_in_subquery:
        lines.append("4. 【重要】子查询限制：IN/ANY/ALL 子查询中禁止使用 LIMIT！")
        lines.append("   错误示例：WHERE id IN (SELECT id FROM t LIMIT 10)")
        lines.append("   正确写法：JOIN (SELECT id FROM t LIMIT 10) sub ON main.id = sub.id")
    else:
        lines.append("4. 子查询：支持在子查询中使用 LIMIT")
    
    # 5. 字符串连接
    if dialect.concat_operator == "CONCAT":
        lines.append("5. 字符串连接：使用 CONCAT(a, b) 函数")
    elif dialect.concat_operator == "||":
        lines.append("5. 字符串连接：使用 || 运算符（如 a || b）")
    else:
        lines.append("5. 字符串连接：使用 + 运算符（如 a + b）")
    
    # 6. 日期函数
    lines.append(f"6. 日期格式化：使用 {dialect.date_format_func}() 函数")
    
    # 7. PostgreSQL 特有的日期运算规则
    if db_type.lower() in ["postgresql", "postgres"]:
        lines.append("7. 【重要】日期运算：date - date 直接返回整数（天数），不需要 EXTRACT")
        lines.append("   错误示例：EXTRACT(DAY FROM (date1 - date2))")
        lines.append("   正确写法：date1 - date2（直接返回天数差值）")
        lines.append("   计算平均天数：AVG(date1 - date2)")
    
    # 8. 保留字提醒
    if dialect.reserved_words:
        words = ", ".join(dialect.reserved_words[:5])
        next_num = 8 if db_type.lower() in ["postgresql", "postgres"] else 7
        lines.append(f"{next_num}. 保留字：{words} 等作为列名时需要用引号包裹")
    
    return "\n".join(lines)


def convert_limit_syntax(sql: str, source_db: str, target_db: str) -> str:
    """
    转换 SQL 的 LIMIT 语法到目标数据库格式
    
    Args:
        sql: 原始 SQL
        source_db: 源数据库类型
        target_db: 目标数据库类型
        
    Returns:
        str: 转换后的 SQL
    """
    target_dialect = get_dialect(target_db)
    
    # 提取现有的 LIMIT 值
    limit_match = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
    top_match = re.search(r'\bTOP\s+(\d+)', sql, re.IGNORECASE)
    fetch_match = re.search(r'\bFETCH\s+FIRST\s+(\d+)', sql, re.IGNORECASE)
    
    limit_value = None
    if limit_match:
        limit_value = int(limit_match.group(1))
        sql = re.sub(r'\s*\bLIMIT\s+\d+\s*', ' ', sql, flags=re.IGNORECASE)
    elif top_match:
        limit_value = int(top_match.group(1))
        sql = re.sub(r'\bTOP\s+\d+\s*', '', sql, flags=re.IGNORECASE)
    elif fetch_match:
        limit_value = int(fetch_match.group(1))
        sql = re.sub(r'\s*\bFETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\s*', ' ', sql, flags=re.IGNORECASE)
    
    if limit_value is None:
        return sql.strip()
    
    sql = sql.strip().rstrip(';')
    
    # 添加目标格式的限制
    if target_dialect.limit_syntax == "LIMIT":
        sql = f"{sql} LIMIT {limit_value}"
    elif target_dialect.limit_syntax == "TOP":
        sql = re.sub(r'\bSELECT\b', f'SELECT TOP {limit_value}', sql, count=1, flags=re.IGNORECASE)
    else:  # FETCH FIRST
        sql = f"{sql} FETCH FIRST {limit_value} ROWS ONLY"
    
    return sql


def validate_dialect_compatibility(sql: str, db_type: str) -> Dict[str, any]:
    """
    验证 SQL 是否符合目标数据库方言
    
    Args:
        sql: SQL 语句
        db_type: 数据库类型
        
    Returns:
        dict: {
            "valid": bool,
            "errors": List[str],
            "warnings": List[str],
            "fixed_sql": Optional[str]  # 自动修复后的 SQL（如果可修复）
        }
    """
    dialect = get_dialect(db_type)
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "fixed_sql": None
    }
    
    sql_upper = sql.upper()
    
    # 1. 检查 FULL OUTER JOIN
    if not dialect.supports_full_outer_join:
        if "FULL OUTER JOIN" in sql_upper or "FULL JOIN" in sql_upper:
            result["errors"].append(f"{dialect.name} 不支持 FULL OUTER JOIN，请使用 LEFT JOIN UNION RIGHT JOIN")
            result["valid"] = False
    
    # 2. 检查 RIGHT JOIN
    if not dialect.supports_right_join:
        if "RIGHT JOIN" in sql_upper or "RIGHT OUTER JOIN" in sql_upper:
            result["errors"].append(f"{dialect.name} 不支持 RIGHT JOIN，请改用 LEFT JOIN（交换表的位置）")
            result["valid"] = False
    
    # 3. 检查 IN 子查询中的 LIMIT（MySQL 特有问题）
    if not dialect.supports_limit_in_subquery:
        in_limit_pattern = r'\bIN\s*\(\s*SELECT\b[^)]*\bLIMIT\b'
        if re.search(in_limit_pattern, sql_upper):
            result["errors"].append(
                f"{dialect.name} 不支持在 IN 子查询中使用 LIMIT，"
                "请改用 JOIN 派生表方式"
            )
            result["valid"] = False
    
    # 4. 检查标识符引号使用
    if dialect.identifier_quote == "`":
        # MySQL：不应该使用双引号作为标识符
        if re.search(r'"[a-zA-Z_][a-zA-Z0-9_]*"', sql):
            result["warnings"].append("MySQL 使用反引号 ` 而非双引号 \" 包裹标识符")
    elif dialect.identifier_quote == '"':
        # PostgreSQL/Oracle：不应该使用反引号
        if '`' in sql:
            result["warnings"].append(f"{dialect.name} 使用双引号 \" 而非反引号 ` 包裹标识符")
    
    # 5. 检查 LIMIT 语法是否正确
    if dialect.limit_syntax == "TOP":
        if re.search(r'\bLIMIT\s+\d+', sql_upper):
            result["warnings"].append(f"{dialect.name} 应使用 SELECT TOP N 而非 LIMIT")
    elif dialect.limit_syntax == "FETCH FIRST":
        if re.search(r'\bLIMIT\s+\d+', sql_upper):
            result["warnings"].append(f"{dialect.name} 应使用 FETCH FIRST N ROWS ONLY 而非 LIMIT")
    
    return result


# ============================================================================
# 便捷函数
# ============================================================================

def get_supported_databases() -> List[str]:
    """获取支持的数据库类型列表"""
    return ["mysql", "postgresql", "sqlite", "sqlserver", "oracle"]


def quote_identifier(name: str, db_type: str) -> str:
    """
    为标识符添加正确的引号
    
    Args:
        name: 标识符名称
        db_type: 数据库类型
        
    Returns:
        str: 带引号的标识符
    """
    dialect = get_dialect(db_type)
    quote = dialect.identifier_quote
    
    if quote == "[":
        return f"[{name}]"
    else:
        return f"{quote}{name}{quote}"
