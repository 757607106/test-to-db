"""
SQL 辅助函数模块 (轻量级)

此模块包含纯工具函数，不依赖任何数据库或 ORM 模块，
可以安全地在任何地方导入而不触发重型依赖链。

用于 dashboard_insight_graph、sql_generator_agent 等模块复用。
"""


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
