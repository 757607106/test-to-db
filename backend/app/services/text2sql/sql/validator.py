"""
SQL 验证工具
提供 SQL 语法验证和安全性检查
"""

import sqlparse


def validate_sql(sql: str) -> bool:
    """
    验证SQL语法
    """
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False

        # 检查是否是SELECT语句（为了安全）
        stmt = parsed[0]
        return stmt.get_type().upper() == 'SELECT'
    except Exception:
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
