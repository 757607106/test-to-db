"""
Schema 检索模块
提供基于自然语言查询检索相关表结构信息的功能
"""

from .retriever import retrieve_relevant_schema
from .retriever_async import retrieve_relevant_schema_async
from .db_helpers import (
    fetch_columns_batch_sync,
    fetch_relationships_sync,
)

__all__ = [
    # 同步检索
    "retrieve_relevant_schema",
    # 异步检索
    "retrieve_relevant_schema_async",
    # 数据库辅助
    "fetch_columns_batch_sync",
    "fetch_relationships_sync",
]
