"""
Schema 服务模块
提供数据库 Schema 发现和持久化功能

模块结构:
- discovery/: Schema 发现（通用、MySQL、PostgreSQL、SQLite）
- persistence/: Schema 持久化（保存、Neo4j同步）
"""

# Discovery 模块
from .discovery import (
    discover_schema,
    discover_generic_schema,
    discover_mysql_schema,
    discover_postgresql_schema,
    discover_sqlite_schema,
)

# Persistence 模块
from .persistence import (
    save_discovered_schema,
    sync_schema_to_graph_db,
)

__all__ = [
    # Discovery
    "discover_schema",
    "discover_generic_schema",
    "discover_mysql_schema",
    "discover_postgresql_schema",
    "discover_sqlite_schema",
    # Persistence
    "save_discovered_schema",
    "sync_schema_to_graph_db",
]
