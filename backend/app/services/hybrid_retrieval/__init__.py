"""
混合检索服务模块

提供向量检索、图检索和融合排序功能的完整实现。

包含:
- models: 数据模型 (QAPairWithContext, RetrievalResult)
- utils: 工具函数
- vector: 向量化服务 (VectorService, VectorServiceFactory, VectorServiceMonitor)
- storage: 存储服务 (MilvusService, EnhancedNeo4jService)
- ranking: 排序服务 (FusionRanker)
- engine: 检索引擎 (HybridRetrievalEngine, HybridRetrievalEnginePool)
"""

# 数据模型
from .models import QAPairWithContext, RetrievalResult

# 工具函数
from .utils import (
    get_database_name_by_connection_id,
    extract_tables_from_sql,
    extract_entities_from_question,
    clean_sql,
    generate_qa_id,
)

# 向量化服务
from .vector import VectorService, VectorServiceFactory, VectorServiceMonitor

# 存储服务
from .storage import MilvusService, EnhancedNeo4jService

# 排序服务
from .ranking import FusionRanker

# 检索引擎
from .engine import HybridRetrievalEngine, HybridRetrievalEnginePool

__all__ = [
    # 数据模型
    "QAPairWithContext",
    "RetrievalResult",
    # 工具函数
    "get_database_name_by_connection_id",
    "extract_tables_from_sql",
    "extract_entities_from_question",
    "clean_sql",
    "generate_qa_id",
    # 向量化服务
    "VectorService",
    "VectorServiceFactory",
    "VectorServiceMonitor",
    # 存储服务
    "MilvusService",
    "EnhancedNeo4jService",
    # 排序服务
    "FusionRanker",
    # 检索引擎
    "HybridRetrievalEngine",
    "HybridRetrievalEnginePool",
]
