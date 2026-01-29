"""
缓存模块
提供查询分析缓存和 Schema 缓存管理
"""

from .config import (
    QUERY_ANALYSIS_CACHE_TTL,
    QUERY_ANALYSIS_CACHE_MAX_SIZE,
    SCHEMA_CACHE_TTL,
    FULL_SCHEMA_CONTEXT_CACHE_TTL,
)
from .query_cache import (
    query_analysis_cache,
    query_analysis_cache_timestamps,
    is_query_cache_valid,
    cleanup_query_cache,
)
from .schema_cache import (
    schema_cache,
    schema_cache_timestamps,
    full_schema_context_cache,
    full_schema_context_timestamps,
    is_schema_cache_valid,
    get_cached_all_tables,
    clear_schema_cache,
)

__all__ = [
    # 配置常量
    "QUERY_ANALYSIS_CACHE_TTL",
    "QUERY_ANALYSIS_CACHE_MAX_SIZE",
    "SCHEMA_CACHE_TTL",
    "FULL_SCHEMA_CONTEXT_CACHE_TTL",
    # 查询缓存
    "query_analysis_cache",
    "query_analysis_cache_timestamps",
    "is_query_cache_valid",
    "cleanup_query_cache",
    # Schema 缓存
    "schema_cache",
    "schema_cache_timestamps",
    "full_schema_context_cache",
    "full_schema_context_timestamps",
    "is_schema_cache_valid",
    "get_cached_all_tables",
    "clear_schema_cache",
]
