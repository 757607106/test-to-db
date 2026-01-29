"""
查询分析缓存
带 TTL 和大小限制的查询缓存管理
"""

import time
from typing import Dict, Any

from .config import QUERY_ANALYSIS_CACHE_TTL, QUERY_ANALYSIS_CACHE_MAX_SIZE


# 查询分析缓存（带TTL和大小限制）
query_analysis_cache: Dict[str, Dict[str, Any]] = {}
query_analysis_cache_timestamps: Dict[str, float] = {}


def is_query_cache_valid(query: str) -> bool:
    """检查查询缓存是否有效"""
    if query not in query_analysis_cache:
        return False
    cache_time = query_analysis_cache_timestamps.get(query, 0)
    return (time.time() - cache_time) < QUERY_ANALYSIS_CACHE_TTL


def cleanup_query_cache():
    """清理过期和超出大小的缓存"""
    global query_analysis_cache, query_analysis_cache_timestamps
    
    current_time = time.time()
    
    # 移除过期条目
    expired_keys = [
        k for k, t in query_analysis_cache_timestamps.items()
        if (current_time - t) >= QUERY_ANALYSIS_CACHE_TTL
    ]
    for k in expired_keys:
        query_analysis_cache.pop(k, None)
        query_analysis_cache_timestamps.pop(k, None)
    
    # 如果仍超过大小限制，移除最旧的条目
    if len(query_analysis_cache) > QUERY_ANALYSIS_CACHE_MAX_SIZE:
        sorted_items = sorted(query_analysis_cache_timestamps.items(), key=lambda x: x[1])
        items_to_remove = len(query_analysis_cache) - QUERY_ANALYSIS_CACHE_MAX_SIZE
        for k, _ in sorted_items[:items_to_remove]:
            query_analysis_cache.pop(k, None)
            query_analysis_cache_timestamps.pop(k, None)
