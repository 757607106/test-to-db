"""
Text2SQL 工具模块
提供查询分析、表结构检索、SQL处理等工具函数

模块结构:
- cache/: 缓存管理（查询分析缓存、Schema缓存）
- analysis/: 查询分析（LLM分析、表匹配）
- schema/: Schema检索（同步/异步）
- sql/: SQL处理（格式化、验证、值映射）
- utils/: 工具函数（类型推断、SQL语法指南）

优化历史:
- 2026-01: 合并LLM调用，减少延迟
- 2026-01: 添加缓存优化
- 2026-01: 模块化拆分重构
"""

# Cache 模块
from .cache import (
    QUERY_ANALYSIS_CACHE_TTL,
    QUERY_ANALYSIS_CACHE_MAX_SIZE,
    SCHEMA_CACHE_TTL,
    FULL_SCHEMA_CONTEXT_CACHE_TTL,
    query_analysis_cache,
    query_analysis_cache_timestamps,
    is_query_cache_valid,
    cleanup_query_cache,
    schema_cache,
    schema_cache_timestamps,
    full_schema_context_cache,
    full_schema_context_timestamps,
    is_schema_cache_valid,
    get_cached_all_tables,
    clear_schema_cache,
)

# Analysis 模块
from .analysis import (
    analyze_query_with_llm,
    analyze_query_and_find_tables_unified,
    create_fallback_analysis,
    extract_keywords,
    find_relevant_tables_semantic,
    basic_table_matching,
    filter_expanded_tables_with_llm,
)

# Schema 模块
from .schema import (
    retrieve_relevant_schema,
    retrieve_relevant_schema_async,
    fetch_columns_batch_sync,
    fetch_relationships_sync,
)

# SQL 模块
from .sql import (
    format_schema_for_prompt,
    get_value_mappings,
    process_sql_with_value_mappings,
    validate_sql,
    validate_sql_safety,
    extract_sql_from_llm_response,
    clean_sql_from_llm_response,
)

# Utils 模块
from .utils import (
    get_sql_syntax_guide,
    infer_semantic_type,
    is_aggregatable_type,
    is_groupable_type,
)

__all__ = [
    # Cache
    "QUERY_ANALYSIS_CACHE_TTL",
    "QUERY_ANALYSIS_CACHE_MAX_SIZE",
    "SCHEMA_CACHE_TTL",
    "FULL_SCHEMA_CONTEXT_CACHE_TTL",
    "query_analysis_cache",
    "query_analysis_cache_timestamps",
    "is_query_cache_valid",
    "cleanup_query_cache",
    "schema_cache",
    "schema_cache_timestamps",
    "full_schema_context_cache",
    "full_schema_context_timestamps",
    "is_schema_cache_valid",
    "get_cached_all_tables",
    "clear_schema_cache",
    # Analysis
    "analyze_query_with_llm",
    "analyze_query_and_find_tables_unified",
    "create_fallback_analysis",
    "extract_keywords",
    "find_relevant_tables_semantic",
    "basic_table_matching",
    "filter_expanded_tables_with_llm",
    # Schema
    "retrieve_relevant_schema",
    "retrieve_relevant_schema_async",
    "fetch_columns_batch_sync",
    "fetch_relationships_sync",
    # SQL
    "format_schema_for_prompt",
    "get_value_mappings",
    "process_sql_with_value_mappings",
    "validate_sql",
    "validate_sql_safety",
    "extract_sql_from_llm_response",
    "clean_sql_from_llm_response",
    # Utils
    "get_sql_syntax_guide",
    "infer_semantic_type",
    "is_aggregatable_type",
    "is_groupable_type",
]
