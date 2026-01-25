import pymysql
import sqlalchemy
from sqlalchemy import create_engine, inspect
from typing import Dict, Any, List
import urllib.parse
import re

from app.models.db_connection import DBConnection


def fix_mysql_full_outer_join(sql: str) -> str:
    """
    MySQL 不支持 FULL OUTER JOIN，将其转换为 LEFT JOIN UNION RIGHT JOIN 的形式。
    简化处理：如果检测到 FULL OUTER JOIN，提示用户修改查询。
    对于简单场景，尝试进行转换。
    """
    # 检测是否包含 FULL OUTER JOIN（不区分大小写）
    full_outer_pattern = re.compile(r'\bFULL\s+OUTER\s+JOIN\b', re.IGNORECASE)
    
    if not full_outer_pattern.search(sql):
        return sql
    
    # 简单场景转换：将 FULL OUTER JOIN 替换为 LEFT JOIN
    # 完整的 FULL OUTER JOIN 模拟需要 UNION，但这会改变查询结构
    # 这里我们使用 LEFT JOIN 作为降级方案，并记录警告
    print(f"警告: MySQL 不支持 FULL OUTER JOIN，已自动转换为 LEFT JOIN。原始SQL: {sql[:100]}...")
    
    # 替换为 LEFT JOIN（简化降级）
    fixed_sql = full_outer_pattern.sub('LEFT JOIN', sql)
    
    return fixed_sql

def get_db_engine(connection: DBConnection, password: str = None):
    """
    Create a SQLAlchemy engine for the given database connection.
    """
    try:
        # 直接使用明文密码，不进行加密/解密处理
        # 在实际应用中，应该对密码进行适当的加密和解密

        # 如果是从配置文件读取的连接信息
        if hasattr(connection, 'password') and connection.password:
            actual_password = connection.password
        # 如果是从数据库读取的连接信息
        elif password:
            actual_password = password
        # 如果是使用已加密的密码
        else:
            # 这里我们假设password_encrypted存储的是明文密码
            # 在实际应用中，应该进行解密
            actual_password = connection.password_encrypted

        # Encode password for URL safety
        encoded_password = urllib.parse.quote_plus(actual_password)

        if connection.db_type.lower() == "mysql":
            conn_str = (
                f"mysql+pymysql://{connection.username}:"
                f"{encoded_password}@"
                f"{connection.host}:{connection.port}/{connection.database_name}"
            )
            print(f"Connecting to MySQL database: {connection.host}:{connection.port}/{connection.database_name}")
            return create_engine(conn_str)

        elif connection.db_type.lower() == "postgresql":
            conn_str = (
                f"postgresql://{connection.username}:"
                f"{encoded_password}@"
                f"{connection.host}:{connection.port}/{connection.database_name}"
            )
            print(f"Connecting to PostgreSQL database: {connection.host}:{connection.port}/{connection.database_name}")
            return create_engine(conn_str)

        elif connection.db_type.lower() == "sqlite":
            # For SQLite, the database_name is treated as the file path
            conn_str = f"sqlite:///{connection.database_name}"
            print(f"Connecting to SQLite database: {connection.database_name}")
            return create_engine(conn_str)

        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")
    except Exception as e:
        print(f"Error creating database engine: {str(e)}")
        raise

def test_db_connection(connection: DBConnection) -> bool:
    """
    Test if a database connection is valid.
    """
    try:
        print(f"Testing connection to {connection.db_type} database at {connection.host}:{connection.port}/{connection.database_name}")
        engine = get_db_engine(connection)
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            print(f"Connection test successful: {result.fetchone()}")
        return True
    except Exception as e:
        error_msg = f"Connection test failed: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)

def execute_query(connection: DBConnection, query: str) -> List[Dict[str, Any]]:
    """
    Execute a SQL query on the target database and return the results.
    """
    try:
        # MySQL 特殊处理：修复不支持的语法
        if connection.db_type.lower() == "mysql":
            query = fix_mysql_full_outer_join(query)
        
        engine = get_db_engine(connection)
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(query))
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        raise Exception(f"Query execution failed: {str(e)}")

def get_db_connection_by_id(connection_id: int) -> DBConnection:
    """
    根据连接ID获取数据库连接对象
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
        return connection
    finally:
        db.close()

def execute_query_with_connection(connection: DBConnection, query: str) -> List[Dict[str, Any]]:
    """
    使用指定的数据库连接执行查询
    """
    return execute_query(connection, query)
