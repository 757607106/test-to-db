"""
Text2SQL工具模块 - 向后兼容层
提供查询分析、表结构检索、SQL处理等工具函数

注意: 此文件为向后兼容层，实际实现已拆分到 text2sql/ 子模块
新代码请直接导入: from app.services.text2sql import ...

优化历史:
- 2026-01: 合并LLM调用，减少延迟
- 2026-01: 添加缓存优化
- 2026-01: 模块化拆分重构
"""

# 从新模块结构重新导出所有公共 API，保持向后兼容

# ============================================================================
# 缓存配置和状态（从 cache 模块导入）
# ============================================================================
from app.services.text2sql.cache import (
    QUERY_ANALYSIS_CACHE_TTL,
    QUERY_ANALYSIS_CACHE_MAX_SIZE,
    SCHEMA_CACHE_TTL,
    FULL_SCHEMA_CONTEXT_CACHE_TTL,
    query_analysis_cache,
    query_analysis_cache_timestamps,
    schema_cache as _schema_cache,
    schema_cache_timestamps as _schema_cache_timestamps,
    full_schema_context_cache as _full_schema_context_cache,
    full_schema_context_timestamps as _full_schema_context_timestamps,
    is_query_cache_valid as _is_query_cache_valid,
    cleanup_query_cache as _cleanup_query_cache,
    is_schema_cache_valid as _is_schema_cache_valid,
    get_cached_all_tables,
    clear_schema_cache,
)

# ============================================================================
# 查询分析函数（从 analysis 模块导入）
# ============================================================================
from app.services.text2sql.analysis import (
    analyze_query_with_llm,
    analyze_query_and_find_tables_unified,
    create_fallback_analysis as _create_fallback_analysis,
    extract_keywords,
    find_relevant_tables_semantic,
    basic_table_matching,
    filter_expanded_tables_with_llm,
)

# ============================================================================
# Schema 检索函数（从 schema 模块导入）
# ============================================================================
from app.services.text2sql.schema import (
    retrieve_relevant_schema,
    retrieve_relevant_schema_async,
    fetch_columns_batch_sync,
    fetch_relationships_sync,
)

# ============================================================================
# SQL 处理函数（从 sql 模块导入）
# ============================================================================
from app.services.text2sql.sql import (
    format_schema_for_prompt,
    get_value_mappings,
    process_sql_with_value_mappings,
    validate_sql,
    validate_sql_safety,
    extract_sql_from_llm_response,
    clean_sql_from_llm_response,
)

# ============================================================================
# 工具函数（从 utils 模块导入）
# ============================================================================
from app.services.text2sql.utils import (
    get_sql_syntax_guide,
    infer_semantic_type,
    is_aggregatable_type,
    is_groupable_type,
)


# ============================================================================
# 公共 API 导出
# ============================================================================
__all__ = [
    # 缓存配置
    "QUERY_ANALYSIS_CACHE_TTL",
    "QUERY_ANALYSIS_CACHE_MAX_SIZE",
    "SCHEMA_CACHE_TTL",
    "FULL_SCHEMA_CONTEXT_CACHE_TTL",
    # 缓存状态
    "query_analysis_cache",
    "query_analysis_cache_timestamps",
    # 缓存函数
    "get_cached_all_tables",
    "clear_schema_cache",
    # 查询分析
    "analyze_query_with_llm",
    "analyze_query_and_find_tables_unified",
    "extract_keywords",
    "find_relevant_tables_semantic",
    "basic_table_matching",
    "filter_expanded_tables_with_llm",
    # Schema 检索
    "retrieve_relevant_schema",
    "retrieve_relevant_schema_async",
    "fetch_columns_batch_sync",
    "fetch_relationships_sync",
    # SQL 处理
    "format_schema_for_prompt",
    "get_value_mappings",
    "process_sql_with_value_mappings",
    "validate_sql",
    "validate_sql_safety",
    "extract_sql_from_llm_response",
    "clean_sql_from_llm_response",
    # 工具函数
    "get_sql_syntax_guide",
    "infer_semantic_type",
    "is_aggregatable_type",
    "is_groupable_type",
]
