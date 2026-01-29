"""
Schema 发现模块
提供各种数据库类型的 Schema 发现功能
"""

from .generic import discover_generic_schema
from .mysql import discover_mysql_schema
from .postgresql import discover_postgresql_schema
from .sqlite import discover_sqlite_schema
from .main import discover_schema

__all__ = [
    "discover_schema",
    "discover_generic_schema",
    "discover_mysql_schema",
    "discover_postgresql_schema",
    "discover_sqlite_schema",
]
