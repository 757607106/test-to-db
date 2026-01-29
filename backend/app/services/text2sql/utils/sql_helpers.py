"""
SQL 辅助工具
提供数据库特定的 SQL 语法指南
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
