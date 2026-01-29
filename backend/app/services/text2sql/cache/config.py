"""
缓存配置常量
"""

# 缓存TTL配置
QUERY_ANALYSIS_CACHE_TTL = 600  # 查询分析缓存: 10分钟
QUERY_ANALYSIS_CACHE_MAX_SIZE = 100  # 最大缓存条目数
SCHEMA_CACHE_TTL = 1800  # Schema缓存: 30分钟（表结构不常变）
FULL_SCHEMA_CONTEXT_CACHE_TTL = 600  # 完整 Schema 上下文缓存: 10分钟
