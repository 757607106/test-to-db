"""
Schema 缓存
按 connection_id 缓存表结构信息
"""

import time
import logging
from typing import Dict, Any, List, Optional

from .config import SCHEMA_CACHE_TTL


logger = logging.getLogger(__name__)


# Schema缓存（按 cache_key 缓存表结构信息）
schema_cache: Dict[str, Any] = {}
schema_cache_timestamps: Dict[int, float] = {}

# 完整 Schema 上下文缓存（按 connection_id + query_hash 缓存）
full_schema_context_cache: Dict[str, Dict[str, Any]] = {}
full_schema_context_timestamps: Dict[str, float] = {}


def is_schema_cache_valid(connection_id: int) -> bool:
    """检查Schema缓存是否有效"""
    if connection_id not in schema_cache_timestamps:
        return False
    cache_time = schema_cache_timestamps.get(connection_id, 0)
    return (time.time() - cache_time) < SCHEMA_CACHE_TTL


def get_cached_all_tables(connection_id: int, neo4j_session) -> List[Dict[str, Any]]:
    """
    获取缓存的所有表信息（优化Neo4j查询）
    
    Args:
        connection_id: 数据库连接ID
        neo4j_session: Neo4j会话
        
    Returns:
        表信息列表
    """
    cache_key = f"tables:{connection_id}"
    
    # 检查缓存
    if is_schema_cache_valid(connection_id) and cache_key in schema_cache:
        logger.debug(f"Using cached schema for connection {connection_id}")
        return schema_cache[cache_key]
    
    # 从Neo4j查询
    all_tables = neo4j_session.run(
        """
        MATCH (t:Table {connection_id: $connection_id})
        RETURN t.id AS id, t.name AS name, t.description AS description
        """,
        connection_id=connection_id
    ).data()
    
    # 缓存结果
    schema_cache[cache_key] = all_tables
    schema_cache_timestamps[connection_id] = time.time()
    
    logger.debug(f"Cached {len(all_tables)} tables for connection {connection_id}")
    return all_tables


def clear_schema_cache(connection_id: Optional[int] = None):
    """
    清除Schema缓存
    
    Args:
        connection_id: 指定连接ID，如果为None则清除所有缓存
    """
    global schema_cache, schema_cache_timestamps
    
    if connection_id is not None:
        cache_key = f"tables:{connection_id}"
        schema_cache.pop(cache_key, None)
        schema_cache_timestamps.pop(connection_id, None)
        logger.info(f"Cleared schema cache for connection {connection_id}")
    else:
        schema_cache.clear()
        schema_cache_timestamps.clear()
        logger.info("Cleared all schema cache")
