"""
Schema 服务模块 - 向后兼容层
提供数据库 Schema 发现和持久化功能

注意: 此文件为向后兼容层，实际实现已拆分到 schema/ 子模块
新代码请直接导入: from app.services.schema import ...
"""

# 从新模块结构重新导出所有公共 API，保持向后兼容

# ============================================================================
# Discovery 模块（Schema 发现）
# ============================================================================
from app.services.schema.discovery import (
    discover_schema,
    discover_generic_schema,
    discover_mysql_schema,
    discover_postgresql_schema,
    discover_sqlite_schema,
)

# ============================================================================
# Persistence 模块（Schema 持久化）
# ============================================================================
from app.services.schema.persistence import (
    save_discovered_schema,
    sync_schema_to_graph_db,
)


# ============================================================================
# 公共 API 导出
# ============================================================================
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
