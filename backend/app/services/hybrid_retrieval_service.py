"""
混合检索服务 - 向后兼容层

此文件保留用于向后兼容，所有类和函数已迁移到 hybrid_retrieval 模块。
请在新代码中直接使用:
    from app.services.hybrid_retrieval import HybridRetrievalEngine, ...

迁移指南:
- QAPairWithContext, RetrievalResult -> from app.services.hybrid_retrieval.models
- VectorService, VectorServiceFactory, VectorServiceMonitor -> from app.services.hybrid_retrieval.vector
- MilvusService -> from app.services.hybrid_retrieval.storage.milvus_service
- EnhancedNeo4jService -> from app.services.hybrid_retrieval.storage.neo4j_enhanced
- FusionRanker -> from app.services.hybrid_retrieval.ranking
- HybridRetrievalEngine, HybridRetrievalEnginePool -> from app.services.hybrid_retrieval.engine
"""

# 向后兼容导出 - 保持原有导入路径可用
from app.services.hybrid_retrieval import (
    # 数据模型
    QAPairWithContext,
    RetrievalResult,
    # 工具函数
    get_database_name_by_connection_id,
    extract_tables_from_sql,
    extract_entities_from_question,
    clean_sql,
    generate_qa_id,
    # 向量化服务
    VectorService,
    VectorServiceFactory,
    VectorServiceMonitor,
    # 存储服务
    MilvusService,
    EnhancedNeo4jService,
    # 排序服务
    FusionRanker,
    # 检索引擎
    HybridRetrievalEngine,
    HybridRetrievalEnginePool,
)

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
