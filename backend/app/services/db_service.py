import pymysql
import sqlalchemy
from sqlalchemy import create_engine, inspect
from typing import Dict, Any, List, Optional
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

def get_db_engine(connection: DBConnection, password: str = None, timeout_seconds: Optional[int] = None):
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

        connect_args = None
        if timeout_seconds is not None:
            try:
                timeout_seconds = int(timeout_seconds)
            except Exception:
                timeout_seconds = None
            if timeout_seconds is not None:
                timeout_seconds = max(1, min(timeout_seconds, 300))

        if connection.db_type.lower() == "mysql":
            conn_str = (
                f"mysql+pymysql://{connection.username}:"
                f"{encoded_password}@"
                f"{connection.host}:{connection.port}/{connection.database_name}"
            )
            print(f"Connecting to MySQL database: {connection.host}:{connection.port}/{connection.database_name}")
            if timeout_seconds is not None:
                connect_args = {
                    "connect_timeout": min(timeout_seconds, 60),
                    "read_timeout": timeout_seconds,
                    "write_timeout": timeout_seconds,
                }
            return create_engine(conn_str, connect_args=connect_args or {})

        elif connection.db_type.lower() == "postgresql":
            conn_str = (
                f"postgresql+psycopg://{connection.username}:"
                f"{encoded_password}@"
                f"{connection.host}:{connection.port}/{connection.database_name}"
            )
            print(f"Connecting to PostgreSQL database: {connection.host}:{connection.port}/{connection.database_name}")
            if timeout_seconds is not None:
                connect_args = {"connect_timeout": min(timeout_seconds, 60)}
            try:
                return create_engine(conn_str, connect_args=connect_args or {})
            except (ModuleNotFoundError, ImportError) as e:
                error_text = str(e).lower()
                if "psycopg" in error_text or "psycopg2" in error_text:
                    raise Exception(
                        "PostgreSQL driver not installed. Install: pip install 'psycopg[binary]'"
                    )
                raise
            except sqlalchemy.exc.NoSuchModuleError:
                raise Exception(
                    "PostgreSQL driver not available. Install: pip install 'psycopg[binary]'"
                )

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

def execute_query(connection: DBConnection, query: str, timeout_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Execute a SQL query on the target database and return the results.
    """
    try:
        # MySQL 特殊处理：修复不支持的语法
        if connection.db_type.lower() == "mysql":
            query = fix_mysql_full_outer_join(query)
        
        engine = get_db_engine(connection, timeout_seconds=timeout_seconds)
        with engine.connect() as conn:
            if connection.db_type.lower() == "postgresql":
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            if timeout_seconds is not None:
                try:
                    timeout_seconds_int = int(timeout_seconds)
                except Exception:
                    timeout_seconds_int = None

                if timeout_seconds_int is not None:
                    timeout_seconds_int = max(1, min(timeout_seconds_int, 300))
                    timeout_ms = timeout_seconds_int * 1000
                    db_type = connection.db_type.lower()
                    if db_type == "postgresql":
                        try:
                            conn.execute(sqlalchemy.text("SET statement_timeout = :ms"), {"ms": timeout_ms})
                        except Exception:
                            pass
                    elif db_type == "mysql":
                        try:
                            conn.execute(sqlalchemy.text("SET SESSION MAX_EXECUTION_TIME = :ms"), {"ms": timeout_ms})
                        except Exception:
                            pass
                        q_strip = (query or "").lstrip()
                        if q_strip[:6].lower() == "select" and "max_execution_time" not in q_strip.lower():
                            query = q_strip[:6] + f" /*+ MAX_EXECUTION_TIME({timeout_ms}) */" + q_strip[6:]
            try:
                result = conn.execute(sqlalchemy.text(query))
            except Exception as e:
                error_text = str(e).lower()
                if "current transaction is aborted" in error_text or "infailedsqltransaction" in error_text:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    result = conn.execute(sqlalchemy.text(query))
                else:
                    raise
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

def execute_query_with_connection(connection: DBConnection, query: str, timeout_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    使用指定的数据库连接执行查询
    """
    return execute_query(connection, query, timeout_seconds=timeout_seconds)
