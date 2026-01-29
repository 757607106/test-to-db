"""
Schema 发现主入口
根据数据库类型选择合适的发现方法
"""

from typing import List, Dict, Any

from app.models.db_connection import DBConnection
from app.services.db_service import get_db_engine
from sqlalchemy import inspect

from .generic import discover_generic_schema
from .mysql import discover_mysql_schema
from .postgresql import discover_postgresql_schema
from .sqlite import discover_sqlite_schema


def discover_schema(connection: DBConnection) -> List[Dict[str, Any]]:
    """
    Discover schema from a database connection.
    """
    try:
        print(f"Discovering schema for {connection.name} ({connection.db_type} at {connection.host}:{connection.port}/{connection.database_name})")
        engine = get_db_engine(connection)
        inspector = inspect(engine)

        # Choose the appropriate discovery method based on database type
        if connection.db_type.lower() == "mysql":
            return discover_mysql_schema(inspector)
        elif connection.db_type.lower() == "postgresql":
            return discover_postgresql_schema(inspector)
        elif connection.db_type.lower() == "sqlite":
            return discover_sqlite_schema(inspector)
        else:
            # Default discovery method
            return discover_generic_schema(inspector)
    except Exception as e:
        error_msg = f"Schema discovery failed: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        raise Exception(error_msg)
