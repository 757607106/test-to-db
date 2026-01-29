"""
混合检索引擎池
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional

from pymilvus import MilvusClient

from app.core.config import settings
from ..utils import get_database_name_by_connection_id
from ..vector import VectorServiceFactory
from .retrieval_engine import HybridRetrievalEngine

logger = logging.getLogger(__name__)


class HybridRetrievalEnginePool:
    """
    混合检索引擎池 - 复用服务实例，避免重复初始化
    
    特性：
    - 单例模式管理默认引擎
    - 按connection_id缓存引擎实例
    - 自动初始化和健康检查
    - 线程安全
    """
    
    _default_engine: Optional[HybridRetrievalEngine] = None
    _instances: Dict[int, HybridRetrievalEngine] = {}
    _lock = asyncio.Lock()
    _initialized = False
    
    @classmethod
    async def get_engine(cls, connection_id: Optional[int] = None) -> HybridRetrievalEngine:
        """
        获取或创建检索引擎实例
        
        Args:
            connection_id: 数据库连接ID，如果为None则返回默认引擎
            
        Returns:
            HybridRetrievalEngine: 检索引擎实例
        """
        async with cls._lock:
            if connection_id is None:
                # 返回默认引擎
                if cls._default_engine is None:
                    logger.info("创建默认混合检索引擎实例...")
                    cls._default_engine = await cls._create_engine()
                    logger.info("默认混合检索引擎实例创建成功")
                return cls._default_engine
            else:
                # 按connection_id缓存
                if connection_id not in cls._instances:
                    logger.info(f"为connection_id={connection_id}创建混合检索引擎实例...")
                    cls._instances[connection_id] = await cls._create_engine(connection_id)
                    logger.info(f"connection_id={connection_id}的检索引擎实例创建成功")
                return cls._instances[connection_id]
    
    @classmethod
    async def _create_engine(cls, connection_id: Optional[int] = None) -> HybridRetrievalEngine:
        """
        创建并初始化检索引擎实例
        
        Args:
            connection_id: 数据库连接ID
            
        Returns:
            HybridRetrievalEngine: 初始化完成的检索引擎
        """
        try:
            # 获取向量服务（复用全局实例）
            vector_service = await VectorServiceFactory.get_default_service()
            
            # 创建检索引擎
            engine = HybridRetrievalEngine(
                vector_service=vector_service,
                connection_id=connection_id
            )
            
            # 初始化引擎
            await engine.initialize()
            
            logger.info(f"检索引擎初始化成功 - connection_id: {connection_id}")
            return engine
            
        except Exception as e:
            logger.error(f"创建检索引擎失败 - connection_id: {connection_id}, error: {str(e)}")
            raise
    
    @classmethod
    async def warmup(cls, connection_ids: List[int] = None):
        """
        预热初始化检索引擎
        
        Args:
            connection_ids: 需要预热的连接ID列表，如果为None则只初始化默认引擎
        """
        logger.info("开始预热混合检索引擎...")
        
        try:
            # 初始化默认引擎
            await cls.get_engine(None)
            logger.info("默认引擎预热完成")
            
            # 如果提供了连接ID列表，预热这些连接的引擎
            if connection_ids:
                for conn_id in connection_ids:
                    try:
                        await cls.get_engine(conn_id)
                        logger.info(f"连接 {conn_id} 的引擎预热完成")
                    except Exception as e:
                        logger.warning(f"连接 {conn_id} 的引擎预热失败: {str(e)}")
            
            cls._initialized = True
            logger.info("混合检索引擎预热完成")
            
        except Exception as e:
            logger.error(f"混合检索引擎预热失败: {str(e)}")
            raise
    
    @classmethod
    async def health_check(cls) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            Dict: 健康状态信息
        """
        status = {
            "initialized": cls._initialized,
            "default_engine": cls._default_engine is not None,
            "cached_engines": len(cls._instances),
            "connection_ids": list(cls._instances.keys()),
            "healthy": True,
            "errors": []
        }
        
        # 检查默认引擎
        if cls._default_engine:
            try:
                if not cls._default_engine._initialized:
                    status["healthy"] = False
                    status["errors"].append("默认引擎未初始化")
            except Exception as e:
                status["healthy"] = False
                status["errors"].append(f"默认引擎检查失败: {str(e)}")
        
        return status
    
    @classmethod
    async def has_qa_samples(cls, connection_id: int) -> bool:
        """
        快速检查指定连接是否有 QA 样本数据
        
        Args:
            connection_id: 数据库连接ID
            
        Returns:
            bool: 是否有样本数据
        """
        try:
            # 获取数据库名称并生成集合名
            database_name = get_database_name_by_connection_id(connection_id)
            if database_name:
                clean_name = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in database_name.lower())
                if clean_name and not (clean_name[0].isalpha() or clean_name[0] == "_"):
                    clean_name = "db_" + clean_name
                if not clean_name or clean_name.replace("_", "") == "":
                    clean_name = "db_unknown"
                clean_name = clean_name[:50]
                collection_name = f"{clean_name}_qa_pairs"
            else:
                collection_name = "default_qa_pairs"
            
            # 快速连接 Milvus 检查
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            client = MilvusClient(uri=uri)
            
            # 检查集合是否存在
            if not client.has_collection(collection_name=collection_name):
                logger.debug(f"Collection {collection_name} does not exist, no QA samples")
                return False
            
            # 检查是否有数据（使用 query 统计）
            results = client.query(
                collection_name=collection_name,
                filter=f"connection_id == {connection_id}",
                output_fields=["id"],
                limit=1  # 只需要知道是否有数据
            )
            
            has_data = len(results) > 0
            logger.debug(f"QA samples check for connection_id={connection_id}: {has_data}")
            return has_data
            
        except Exception as e:
            logger.warning(f"Failed to check QA samples for connection_id={connection_id}: {e}")
            return False
    
    @classmethod
    async def quick_retrieve(cls, user_query: str, schema_context: Dict[str, Any], 
                            connection_id: int, top_k: int = 3, 
                            min_similarity: float = 0.6) -> List[Dict[str, Any]]:
        """
        轻量级快速检索 QA 样本
        
        专为集成到 sql_generator_agent 设计，特点：
        - 先检查是否有样本，没有则立即返回
        - 只返回格式化后的结果，不返回复杂对象
        - 自动过滤低质量样本
        
        Args:
            user_query: 用户查询
            schema_context: 模式上下文
            connection_id: 数据库连接ID
            top_k: 返回数量
            min_similarity: 最低相似度阈值
            
        Returns:
            List[Dict]: 格式化的样本列表，如果没有样本则返回空列表
        """
        start_time = time.time()
        
        try:
            logger.info(f"[QuickRetrieve] 开始检索QA样本 - "
                       f"连接ID: {connection_id}, "
                       f"查询: '{user_query[:50]}...', "
                       f"top_k: {top_k}, "
                       f"min_similarity: {min_similarity}")
            
            # 先快速检查是否有样本
            check_start = time.time()
            has_samples = await cls.has_qa_samples(connection_id)
            check_time = time.time() - check_start
            
            if not has_samples:
                logger.info(f"[QuickRetrieve] 未找到样本 - "
                          f"连接ID: {connection_id}, "
                          f"检查耗时: {check_time:.3f}s")
                return []
            
            logger.debug(f"[QuickRetrieve] 样本存在检查通过，耗时: {check_time:.3f}s")
            
            # 有样本，执行检索
            retrieve_start = time.time()
            engine = await cls.get_engine(connection_id)
            results = await engine.hybrid_retrieve(
                query=user_query,
                schema_context=schema_context,
                connection_id=connection_id,
                top_k=top_k
            )
            retrieve_time = time.time() - retrieve_start
            
            logger.debug(f"[QuickRetrieve] 混合检索完成 - "
                        f"原始结果: {len(results)}个, "
                        f"耗时: {retrieve_time:.3f}s")
            
            # 格式化并过滤结果
            formatted = []
            for i, result in enumerate(results):
                if result.final_score >= min_similarity:
                    qa = result.qa_pair
                    formatted.append({
                        "question": qa.question,
                        "sql": qa.sql,
                        "query_type": qa.query_type,
                        "success_rate": qa.success_rate,
                        "similarity": result.final_score,
                        "verified": qa.verified
                    })
                    logger.debug(f"[QuickRetrieve] 样本{i+1}: "
                               f"相似度={result.final_score:.3f}, "
                               f"成功率={qa.success_rate:.2f}, "
                               f"已验证={qa.verified}, "
                               f"问题='{qa.question[:40]}...'")
                else:
                    logger.debug(f"[QuickRetrieve] 样本{i+1}被过滤: "
                               f"相似度={result.final_score:.3f} < {min_similarity}")
            
            total_time = time.time() - start_time
            logger.info(f"[QuickRetrieve] ✓ 检索完成 - "
                       f"连接ID: {connection_id}, "
                       f"找到: {len(formatted)}/{len(results)}个高质量样本, "
                       f"总耗时: {total_time:.3f}s "
                       f"(检查: {check_time:.3f}s, 检索: {retrieve_time:.3f}s)")
            
            return formatted
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[QuickRetrieve] ✗ 检索失败 - "
                        f"连接ID: {connection_id}, "
                        f"错误: {str(e)}, "
                        f"耗时: {total_time:.3f}s", 
                        exc_info=True)
            return []
    
    @classmethod
    def clear_cache(cls):
        """清理所有缓存的引擎实例"""
        logger.info("清理混合检索引擎缓存...")
        cls._default_engine = None
        cls._instances.clear()
        cls._initialized = False
        logger.info("混合检索引擎缓存已清理")
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            "initialized": cls._initialized,
            "has_default_engine": cls._default_engine is not None,
            "cached_engines_count": len(cls._instances),
            "cached_connection_ids": list(cls._instances.keys())
        }
