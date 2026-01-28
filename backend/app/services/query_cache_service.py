"""
查询缓存服务 - 实现全局查询结果缓存

功能:
1. 精确匹配缓存（L1）：完全相同的查询直接返回缓存结果
2. 语义匹配缓存（L2）：利用 Milvus 向量检索，相似度 >= 0.95 时命中

优化历史:
- 2026-01-19: 初始实现，解决重复查询需要重新走完整流程的问题
"""

import hashlib
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    query: str                          # 原始查询
    connection_id: int                  # 数据库连接ID
    tenant_id: Optional[int]            # 租户ID（多租户隔离）
    sql: str                            # 生成的SQL
    result: Any                         # 执行结果
    created_at: float                   # 创建时间戳
    hit_count: int = 0                  # 命中次数
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > ttl_seconds


@dataclass
class CacheHit:
    """缓存命中结果"""
    hit_type: str                       # "exact" 或 "semantic"
    query: str                          # 原始/匹配的查询
    sql: str                            # SQL 语句
    result: Any                         # 执行结果
    similarity: float = 1.0             # 相似度（精确匹配为1.0）
    

class QueryCacheService:
    """
    全局查询缓存服务
    
    特性:
    - 双层缓存：精确匹配 + 语义匹配
    - LRU 淘汰策略
    - TTL 过期机制
    - 线程安全
    - 单例模式
    """
    
    _instance = None
    _lock = Lock()
    
    # 配置
    MAX_CACHE_SIZE = 1000               # 最大缓存条目数
    EXACT_CACHE_TTL = 3600              # 精确缓存 TTL（1小时）
    SEMANTIC_SIMILARITY_THRESHOLD = 0.95  # 语义匹配阈值
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 使用 OrderedDict 实现 LRU
        self._exact_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = Lock()
        self._stats = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "stores": 0
        }
        self._initialized = True
        logger.info("QueryCacheService initialized")
    
    @classmethod
    def get_instance(cls) -> "QueryCacheService":
        """获取单例实例"""
        return cls()
    
    def _normalize_query(self, query: Any) -> str:
        """
        规范化查询内容，确保缓存键一致
        """
        if query is None:
            return ""
        if isinstance(query, str):
            return query
        if isinstance(query, list):
            parts = []
            for item in query:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(p for p in parts if p).strip()
        if isinstance(query, dict):
            if query.get("type") == "text" and query.get("text"):
                return str(query.get("text"))
        return str(query)

    def _make_cache_key(self, query: str, connection_id: int, tenant_id: Optional[int] = None) -> str:
        """
        生成缓存键（支持多租户隔离）
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID
            tenant_id: 租户ID（可选，用于多租户隔离）
        """
        normalized_query = self._normalize_query(query).lower().strip()
        # 租户隔离：不同租户的缓存键不同
        tenant_prefix = f"t{tenant_id}:" if tenant_id else ""
        key_str = f"{tenant_prefix}{normalized_query}:{connection_id}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _evict_if_needed(self):
        """LRU 淘汰"""
        while len(self._exact_cache) >= self.MAX_CACHE_SIZE:
            # 移除最老的条目
            self._exact_cache.popitem(last=False)
            logger.debug("Cache eviction: removed oldest entry")
    
    def _clean_expired(self):
        """清理过期条目"""
        now = time.time()
        expired_keys = [
            key for key, entry in self._exact_cache.items()
            if entry.is_expired(self.EXACT_CACHE_TTL)
        ]
        for key in expired_keys:
            del self._exact_cache[key]
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
    
    async def check_cache(self, query: str, connection_id: int, tenant_id: Optional[int] = None) -> Optional[CacheHit]:
        """
        检查缓存（支持多租户隔离）
        
        Phase 6 优化: 支持简化模式（只使用精确缓存）
        
        缓存模式：
        - simple: 只检查精确缓存（快速，跳过 Milvus）
        - full: 并行检查精确缓存 + 语义缓存（完整功能）
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID
            tenant_id: 租户ID（可选，用于多租户隔离）
            
        Returns:
            CacheHit 如果命中，否则 None
        """
        import asyncio
        from app.core.config import settings
        
        # Phase 6: 检查缓存模式
        cache_mode = getattr(settings, 'CACHE_MODE', 'simple')
        
        if cache_mode == "simple":
            # ==========================================
            # 简化模式：只检查精确缓存
            # ==========================================
            start_time = time.time()
            result = self._check_exact_cache(query, connection_id, tenant_id)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result:
                self._stats["exact_hits"] += 1
                logger.info(f"Cache HIT (exact, simple mode): query='{query[:50]}...', connection_id={connection_id}, tenant_id={tenant_id} [{elapsed_ms}ms]")
                return result
            
            self._stats["misses"] += 1
            logger.debug(f"Cache MISS (simple mode): query='{query[:50]}...' [{elapsed_ms}ms]")
            return None
        
        # ==========================================
        # 完整模式：并行查询 L1 和 L2 缓存
        # ==========================================
        # 将同步的_check_exact_cache包装为async
        async def check_exact_async():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self._check_exact_cache, 
                query, 
                connection_id,
                tenant_id
            )
        
        # 创建并发任务
        l1_task = asyncio.create_task(check_exact_async())
        l2_task = asyncio.create_task(self._check_semantic_cache(query, connection_id, tenant_id))
        
        try:
            # 等待第一个完成的缓存查询
            done, pending = await asyncio.wait(
                {l1_task, l2_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=2.0  # 2秒超时保护
            )
            
            # 处理第一个完成的结果
            for task in done:
                result = task.result()
                if result:  # 缓存命中
                    # 取消未完成的任务
                    for pending_task in pending:
                        pending_task.cancel()
                    
                    # 更新统计
                    if result.hit_type == "exact":
                        self._stats["exact_hits"] += 1
                        logger.info(f"Cache HIT (exact): query='{query[:50]}...', connection_id={connection_id}, tenant_id={tenant_id}")
                    else:
                        self._stats["semantic_hits"] += 1
                        logger.info(f"Cache HIT (semantic): query='{query[:50]}...', similarity={result.similarity:.3f}")
                    
                    return result
            
            # 第一个完成的没有命中，等待剩余任务
            if pending:
                remaining_results = await asyncio.gather(*pending, return_exceptions=True)
                for result in remaining_results:
                    if isinstance(result, CacheHit):
                        if result.hit_type == "exact":
                            self._stats["exact_hits"] += 1
                        else:
                            self._stats["semantic_hits"] += 1
                        return result
        
        except asyncio.TimeoutError:
            logger.warning("缓存查询超时(2s)，跳过缓存")
        except Exception as e:
            logger.error(f"缓存查询异常: {e}")
        
        # 未命中
        self._stats["misses"] += 1
        logger.debug(f"Cache MISS: query='{query[:50]}...', connection_id={connection_id}")
        return None
    
    def _check_exact_cache(self, query: str, connection_id: int, tenant_id: Optional[int] = None) -> Optional[CacheHit]:
        """检查精确匹配缓存（支持多租户隔离）"""
        cache_key = self._make_cache_key(query, connection_id, tenant_id)
        
        with self._cache_lock:
            # 定期清理过期条目
            if len(self._exact_cache) > 100:
                self._clean_expired()
            
            if cache_key in self._exact_cache:
                entry = self._exact_cache[cache_key]
                
                # 检查是否过期
                if entry.is_expired(self.EXACT_CACHE_TTL):
                    del self._exact_cache[cache_key]
                    return None
                
                # 更新 LRU 顺序
                self._exact_cache.move_to_end(cache_key)
                entry.hit_count += 1
                
                return CacheHit(
                    hit_type="exact",
                    query=entry.query,
                    sql=entry.sql,
                    result=entry.result,
                    similarity=1.0
                )
        
        return None
    
    async def _check_semantic_cache(self, query: str, connection_id: int) -> Optional[CacheHit]:
        """
        检查语义匹配缓存
        
        利用现有的 Milvus QA 样本系统进行语义检索
        """
        try:
            from app.services.hybrid_retrieval_service import HybridRetrievalEnginePool
            
            # 检查是否有 QA 样本
            has_samples = await HybridRetrievalEnginePool.has_qa_samples(connection_id)
            if not has_samples:
                return None
            
            # 获取检索引擎
            engine = await HybridRetrievalEnginePool.get_engine(connection_id)
            
            # 只进行语义检索（不需要 schema_context，因为这里只是缓存检查）
            results = await engine.hybrid_retrieve(
                query=query,
                schema_context={},
                connection_id=connection_id,
                top_k=1
            )
            
            if results and len(results) > 0:
                top_result = results[0]
                qa_pair = top_result.qa_pair
                
                # ✅ 先检查是否精确文本匹配（忽略大小写和首尾空格）
                query_normalized = query.strip().lower()
                qa_question_normalized = qa_pair.question.strip().lower() if qa_pair.question else ""
                is_exact_text_match = (query_normalized == qa_question_normalized)
                
                # 检查相似度是否达到阈值 或 精确文本匹配
                if is_exact_text_match or top_result.final_score >= self.SEMANTIC_SIMILARITY_THRESHOLD:
                    effective_score = 1.0 if is_exact_text_match else top_result.final_score
                    
                    # 从精确缓存中查找对应的执行结果
                    # 语义匹配只能返回 SQL，执行结果需要重新执行
                    # 但如果精确缓存中有这个 QA 对的结果，可以直接返回
                    matched_key = self._make_cache_key(qa_pair.question, connection_id)
                    
                    with self._cache_lock:
                        if matched_key in self._exact_cache:
                            entry = self._exact_cache[matched_key]
                            if not entry.is_expired(self.EXACT_CACHE_TTL):
                                return CacheHit(
                                    hit_type="semantic" if not is_exact_text_match else "exact_text",
                                    query=qa_pair.question,
                                    sql=qa_pair.sql,
                                    result=entry.result,
                                    similarity=effective_score  # ✅ 使用有效分数
                                )
                    
                    # 如果没有执行结果缓存，仍然返回 SQL（可以跳过 SQL 生成步骤）
                    return CacheHit(
                        hit_type="semantic" if not is_exact_text_match else "exact_text",
                        query=qa_pair.question,
                        sql=qa_pair.sql,
                        result=None,  # 没有缓存的执行结果，需要重新执行
                        similarity=effective_score  # ✅ 使用有效分数
                    )
            
            return None
            
        except Exception as e:
            logger.warning(f"Semantic cache check failed: {e}")
            return None
    
    def store_result(self, query: str, connection_id: int, sql: str, result: Any) -> None:
        """
        存储查询结果到缓存
        
        Args:
            query: 用户查询
            connection_id: 数据库连接ID
            sql: 生成的SQL
            result: 执行结果
        """
        cache_key = self._make_cache_key(query, connection_id)
        
        with self._cache_lock:
            # 检查是否需要淘汰
            self._evict_if_needed()
            
            # 存储新条目
            self._exact_cache[cache_key] = CacheEntry(
                query=self._normalize_query(query),
                connection_id=connection_id,
                sql=sql,
                result=result,
                created_at=time.time()
            )
            
            # 移动到末尾（最新）
            self._exact_cache.move_to_end(cache_key)
            self._stats["stores"] += 1
        
        logger.info(f"Cache STORE: query='{query[:50]}...', connection_id={connection_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._cache_lock:
            total_hits = self._stats["exact_hits"] + self._stats["semantic_hits"]
            total_requests = total_hits + self._stats["misses"]
            hit_rate = total_hits / total_requests if total_requests > 0 else 0
            
            return {
                "cache_size": len(self._exact_cache),
                "max_size": self.MAX_CACHE_SIZE,
                "exact_hits": self._stats["exact_hits"],
                "semantic_hits": self._stats["semantic_hits"],
                "misses": self._stats["misses"],
                "stores": self._stats["stores"],
                "hit_rate": f"{hit_rate:.2%}",
                "ttl_seconds": self.EXACT_CACHE_TTL
            }
    
    def clear(self) -> None:
        """清空缓存"""
        with self._cache_lock:
            self._exact_cache.clear()
            self._stats = {
                "exact_hits": 0,
                "semantic_hits": 0,
                "misses": 0,
                "stores": 0
            }
        logger.info("Cache cleared")
    
    def invalidate(self, connection_id: int) -> int:
        """
        使指定连接的缓存失效
        
        Args:
            connection_id: 数据库连接ID
            
        Returns:
            被清除的条目数
        """
        with self._cache_lock:
            keys_to_remove = [
                key for key, entry in self._exact_cache.items()
                if entry.connection_id == connection_id
            ]
            for key in keys_to_remove:
                del self._exact_cache[key]
            
            if keys_to_remove:
                logger.info(f"Invalidated {len(keys_to_remove)} cache entries for connection_id={connection_id}")
            
            return len(keys_to_remove)


# 便捷函数
def get_cache_service() -> QueryCacheService:
    """获取缓存服务实例"""
    return QueryCacheService.get_instance()
