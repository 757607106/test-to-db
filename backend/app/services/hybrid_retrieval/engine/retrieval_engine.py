"""
混合检索引擎
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings
from ..models import QAPairWithContext, RetrievalResult
from ..vector import VectorService, VectorServiceFactory, VectorServiceMonitor
from ..storage import MilvusService, EnhancedNeo4jService
from ..ranking import FusionRanker

logger = logging.getLogger(__name__)


class HybridRetrievalEngine:
    """混合检索引擎，结合向量检索和图检索"""

    def __init__(self, vector_service: VectorService = None, connection_id: int = None):
        self.vector_service = vector_service
        self.connection_id = connection_id
        self.milvus_service = MilvusService(connection_id=connection_id)
        self.neo4j_service = EnhancedNeo4jService()
        self.fusion_ranker = FusionRanker()
        self.monitor = None
        self._initialized = False
        self._milvus_services = {}  # 缓存不同连接的MilvusService实例

    async def initialize(self):
        """初始化所有服务"""
        if not self._initialized:
            try:
                # 初始化向量服务（如果没有提供则创建默认服务）
                if self.vector_service is None:
                    self.vector_service = await VectorServiceFactory.get_default_service()
                elif not self.vector_service._initialized:
                    await self.vector_service.initialize()

                # 初始化监控
                self.monitor = VectorServiceMonitor(self.vector_service)

                # 初始化Milvus服务
                await self.milvus_service.initialize(self.vector_service.dimension)

                # 初始化Neo4j服务
                await self.neo4j_service.initialize()

                self._initialized = True
                logger.info("Hybrid retrieval engine initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize hybrid retrieval engine: {str(e)}")
                raise

    async def get_milvus_service_for_connection(self, connection_id: int) -> MilvusService:
        """根据连接ID获取或创建对应的MilvusService实例"""
        if connection_id not in self._milvus_services:
            # 创建新的MilvusService实例
            milvus_service = MilvusService(connection_id=connection_id)
            await milvus_service.initialize(self.vector_service.dimension)
            self._milvus_services[connection_id] = milvus_service
            logger.info(f"Created MilvusService for connection {connection_id}")

        return self._milvus_services[connection_id]

    async def hybrid_retrieve(self, query: str, schema_context: Dict[str, Any],
                            connection_id: int, top_k: int = 5) -> List[RetrievalResult]:
        """混合检索主函数"""
        if not self._initialized:
            await self.initialize()

        try:
            # 并行执行多种检索
            if settings.PARALLEL_RETRIEVAL:
                semantic_task = self._semantic_search(query, connection_id)
                structural_task = self._structural_search(schema_context, connection_id)
                pattern_task = self._pattern_search(query, connection_id)

                # 等待所有检索完成
                semantic_results, structural_results, pattern_results = await asyncio.gather(
                    semantic_task, structural_task, pattern_task, return_exceptions=True
                )

                # 处理异常结果
                semantic_results = semantic_results if not isinstance(semantic_results, Exception) else []
                structural_results = structural_results if not isinstance(structural_results, Exception) else []
                pattern_results = pattern_results if not isinstance(pattern_results, Exception) else []
            else:
                # 串行执行
                # 从向量数据库检索样本案例数据
                semantic_results = await self._semantic_search(query, connection_id)
                structural_results = await self._structural_search(schema_context, connection_id)
                pattern_results = await self._pattern_search(query, connection_id)

            # 融合排序
            final_results = self.fusion_ranker.fuse_and_rank(
                semantic_results, structural_results, pattern_results
            )

            return final_results[:top_k]

        except Exception as e:
            logger.error(f"Error in hybrid retrieval: {str(e)}")
            return []

    async def _semantic_search(self, query: str, connection_id: int) -> List[RetrievalResult]:
        """语义检索"""
        try:
            # 使用监控的向量化查询
            if self.monitor:
                query_vector = await self.monitor.embed_with_monitoring(query)
            else:
                query_vector = await self.vector_service.embed_question(query)

            # 获取对应连接的Milvus服务
            milvus_service = await self.get_milvus_service_for_connection(connection_id)

            # Milvus检索
            milvus_results = await milvus_service.search_similar(
                query_vector, top_k=5, connection_id=connection_id
            )

            # 转换为RetrievalResult
            results = []
            for result in milvus_results:
                qa_pair = self._build_qa_pair_from_milvus_result(result)
                results.append(RetrievalResult(
                    qa_pair=qa_pair,
                    semantic_score=result['similarity_score'],
                    explanation=f"语义相似度: {result['similarity_score']:.3f}"
                ))

            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []

    def _build_qa_pair_from_milvus_result(self, result: Dict) -> QAPairWithContext:
        """从Milvus结果构建QAPair对象"""
        return QAPairWithContext(
            id=result["id"],
            question=result["question"],
            sql=result["sql"],
            connection_id=result["connection_id"],
            difficulty_level=result["difficulty_level"],
            query_type=result["query_type"],
            success_rate=result["success_rate"],
            verified=result["verified"],
            created_at=datetime.now(),  # 需要从存储中获取实际时间
            used_tables=[],
            used_columns=[],
            query_pattern=result["query_type"],
            mentioned_entities=[]
        )

    async def _structural_search(self, schema_context: Dict[str, Any],
                               connection_id: int) -> List[RetrievalResult]:
        """结构检索"""
        try:
            return await self.neo4j_service.structural_search(
                schema_context, connection_id, top_k=20
            )
        except Exception as e:
            logger.error(f"Error in structural search: {str(e)}")
            return []

    async def _pattern_search(self, query: str, connection_id: int) -> List[RetrievalResult]:
        """模式检索"""
        try:
            # 简单的查询类型识别
            query_type = self._classify_query_type(query)
            difficulty_level = self._estimate_difficulty(query)

            return await self.neo4j_service.pattern_search(
                query_type, difficulty_level, connection_id, top_k=20
            )
        except Exception as e:
            logger.error(f"Error in pattern search: {str(e)}")
            return []

    def _classify_query_type(self, query: str) -> str:
        """分类查询类型"""
        query_lower = query.lower()

        if any(word in query_lower for word in ['count', 'sum', 'avg', 'max', 'min', '统计', '计算', '总数']):
            return "AGGREGATE"
        elif any(word in query_lower for word in ['join', '连接', '关联', '联合']):
            return "JOIN"
        elif any(word in query_lower for word in ['group', '分组', '按照', '分类']):
            return "GROUP_BY"
        elif any(word in query_lower for word in ['order', '排序', '排列']):
            return "ORDER_BY"
        else:
            return "SELECT"

    def _estimate_difficulty(self, query: str) -> int:
        """估算查询难度"""
        difficulty = 1
        query_lower = query.lower()

        if any(word in query_lower for word in ['join', '连接', '关联']):
            difficulty += 1
        if any(word in query_lower for word in ['group', '分组']):
            difficulty += 1
        if any(word in query_lower for word in ['having', '子查询', 'subquery']):
            difficulty += 1
        if any(word in query_lower for word in ['union', '联合']):
            difficulty += 1

        return min(5, difficulty)

    async def store_qa_pair(self, qa_pair: QAPairWithContext, schema_context: Dict[str, Any]):
        """存储问答对到Neo4j和Milvus"""
        if not self._initialized:
            await self.initialize()

        try:
            # 向量化问题
            if not qa_pair.embedding_vector:
                qa_pair.embedding_vector = await self.vector_service.embed_question(qa_pair.question)

            # 存储到Neo4j
            await self.neo4j_service.store_qa_pair_with_context(qa_pair, schema_context)

            # 获取对应连接的Milvus服务并存储
            milvus_service = await self.get_milvus_service_for_connection(qa_pair.connection_id)
            await milvus_service.insert_qa_pair(qa_pair)

            logger.info(f"Successfully stored QA pair: {qa_pair.id}")

        except Exception as e:
            logger.error(f"Failed to store QA pair: {str(e)}")
            raise

    async def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        status = {
            "initialized": self._initialized,
            "vector_service": None,
            "milvus_service": {"initialized": self.milvus_service._initialized},
            "neo4j_service": {"initialized": self.neo4j_service._initialized}
        }

        if self.vector_service:
            status["vector_service"] = await self.vector_service.health_check()

        if self.monitor:
            status["monitoring_metrics"] = self.monitor.get_metrics()

        return status

    async def get_stats(self, connection_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取问答对统计信息
        
        Args:
            connection_id: 数据库连接ID（可选）
                - 如果提供，只统计该连接的QA对
                - 如果为None，统计所有连接的QA对
                
        Returns:
            统计信息字典
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 如果指定了connection_id，只统计该连接的QA对
            if connection_id:
                milvus_service = await self.get_milvus_service_for_connection(connection_id)
                return await milvus_service.get_stats(connection_id)
            
            # 如果没有指定connection_id，统计所有collections的QA对
            else:
                logger.info("统计所有collections的QA对...")
                total_count = 0
                verified_count = 0
                all_query_types = {}
                all_difficulty_dist = {}
                all_success_rates = []
                
                try:
                    # 获取所有collections
                    collections = self.milvus_service.client.list_collections()
                    logger.info(f"找到 {len(collections)} 个collections进行统计")
                    
                    # 遍历每个collection
                    for collection_name in collections:
                        # 只统计qa_pairs结尾的collection
                        if not collection_name.endswith('_qa_pairs'):
                            continue
                        
                        try:
                            logger.debug(f"统计collection: {collection_name}")
                            # 查询该collection中的所有QA对
                            results = self.milvus_service.client.query(
                                collection_name=collection_name,
                                filter="id != ''",
                                output_fields=["id", "query_type", "difficulty_level", "verified", "success_rate"],
                                limit=10000
                            )
                            
                            if results:
                                logger.debug(f"从 {collection_name} 统计到 {len(results)} 条QA对")
                                total_count += len(results)
                                verified_count += sum(1 for r in results if r.get("verified", False))
                                
                                # 查询类型统计
                                for r in results:
                                    qt = r.get("query_type", "UNKNOWN")
                                    all_query_types[qt] = all_query_types.get(qt, 0) + 1
                                
                                # 难度分布
                                for r in results:
                                    dl = str(r.get("difficulty_level", 3))
                                    all_difficulty_dist[dl] = all_difficulty_dist.get(dl, 0) + 1
                                
                                # 成功率
                                all_success_rates.extend([r.get("success_rate", 0) for r in results])
                                
                        except Exception as coll_error:
                            logger.warning(f"统计collection {collection_name} 失败: {coll_error}")
                            continue
                    
                    # 计算平均成功率
                    avg_success_rate = sum(all_success_rates) / len(all_success_rates) if all_success_rates else 0.0
                    
                    logger.info(f"总统计: {total_count} 条QA对, {verified_count} 条已验证")
                    
                    return {
                        "total_qa_pairs": total_count,
                        "verified_qa_pairs": verified_count,
                        "query_types": all_query_types,
                        "difficulty_distribution": all_difficulty_dist,
                        "average_success_rate": round(avg_success_rate * 100, 2),  # 转换为百分比
                        "collection_name": "all_collections"
                    }
                    
                except Exception as e:
                    logger.error(f"统计所有collections失败: {str(e)}")
                    # Fallback到默认collection
                    return await self.milvus_service.get_stats(None)
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {
                "total_qa_pairs": 0,
                "verified_qa_pairs": 0,
                "query_types": {},
                "difficulty_distribution": {},
                "average_success_rate": 0.0,
                "error": str(e)
            }

    async def get_all_qa_pairs(self, connection_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        获取所有问答对
        
        Args:
            connection_id: 数据库连接ID（可选）
                - 如果提供，只返回该连接的QA对
                - 如果为None，返回所有连接的QA对
            limit: 返回数量限制
            
        Returns:
            QA对列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 如果指定了connection_id，只查询该连接的QA对
            if connection_id:
                milvus_service = await self.get_milvus_service_for_connection(connection_id)
                return await milvus_service.get_all_qa_pairs(connection_id, limit)
            
            # 如果没有指定connection_id，查询所有collections的QA对
            else:
                logger.info("查询所有collections的QA对...")
                all_qa_pairs = []
                
                try:
                    # 获取所有collections
                    collections = self.milvus_service.client.list_collections()
                    logger.info(f"找到 {len(collections)} 个collections")
                    
                    # 遍历每个collection
                    for collection_name in collections:
                        # 只查询qa_pairs结尾的collection
                        if not collection_name.endswith('_qa_pairs'):
                            continue
                        
                        try:
                            logger.debug(f"查询collection: {collection_name}")
                            # 查询该collection中的所有QA对
                            results = self.milvus_service.client.query(
                                collection_name=collection_name,
                                filter="id != ''",  # 查询所有记录
                                output_fields=["id", "question", "sql", "connection_id", 
                                              "difficulty_level", "query_type", "success_rate", "verified"],
                                limit=limit
                            )
                            
                            if results:
                                logger.info(f"从 {collection_name} 获取到 {len(results)} 条QA对")
                                all_qa_pairs.extend(results)
                        except Exception as coll_error:
                            logger.warning(f"查询collection {collection_name} 失败: {coll_error}")
                            continue
                    
                    # 按id去重（避免重复）
                    seen_ids = set()
                    unique_qa_pairs = []
                    for qa in all_qa_pairs:
                        if qa.get('id') not in seen_ids:
                            seen_ids.add(qa.get('id'))
                            unique_qa_pairs.append(qa)
                    
                    logger.info(f"总共获取到 {len(unique_qa_pairs)} 条唯一QA对")
                    return unique_qa_pairs[:limit]  # 限制返回数量
                    
                except Exception as e:
                    logger.error(f"查询所有collections失败: {str(e)}")
                    # Fallback到默认collection
                    return await self.milvus_service.get_all_qa_pairs(None, limit)
            
        except Exception as e:
            logger.error(f"Failed to get all QA pairs: {str(e)}")
            return []

    async def update_qa_pair(self, qa_id: str, update_data: Dict) -> bool:
        """更新问答对"""
        if not self._initialized:
            await self.initialize()

        try:
            # 如果问题被更新，需要重新生成向量
            new_vector = None
            if "question" in update_data:
                new_vector = await self.vector_service.embed_question(update_data["question"])
            
            # 策略：从 Milvus 获取所有 collections，然后在每个 collection 中查找
            try:
                collections = self.milvus_service.client.list_collections()
                logger.info(f"Searching for QA pair {qa_id} in {len(collections)} collections")
                
                for collection_name in collections:
                    try:
                        # 尝试在这个 collection 中查询
                        results = self.milvus_service.client.query(
                            collection_name=collection_name,
                            filter=f'id == "{qa_id}"',
                            output_fields=["id", "connection_id"],
                            limit=1
                        )
                        
                        if results and len(results) > 0:
                            # 找到了！获取 connection_id
                            connection_id = results[0].get("connection_id")
                            logger.info(f"Found QA pair {qa_id} in collection {collection_name}, connection_id={connection_id}")
                            
                            # 获取或创建对应的 MilvusService
                            if connection_id:
                                milvus_service = await self.get_milvus_service_for_connection(connection_id)
                            else:
                                milvus_service = self.milvus_service
                            
                            # 执行更新
                            result = await milvus_service.update_qa_pair(qa_id, update_data, new_vector)
                            if result:
                                await self._update_neo4j_qa_pair(qa_id, update_data)
                                logger.info(f"Successfully updated QA pair {qa_id}")
                                return True
                    except Exception as e:
                        # 这个 collection 中没有找到或出错，继续下一个
                        logger.debug(f"QA pair {qa_id} not found in collection {collection_name}: {str(e)}")
                        continue
                
                raise ValueError(f"QA pair with id {qa_id} not found in any collection")
                
            except Exception as e:
                logger.error(f"Failed to search collections: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Failed to update QA pair {qa_id}: {str(e)}")
            raise

    async def _update_neo4j_qa_pair(self, qa_id: str, update_data: Dict):
        """更新Neo4j中的问答对数据"""
        try:
            if not self.neo4j_service._initialized:
                await self.neo4j_service.initialize()
            
            with self.neo4j_service.driver.session() as session:
                # 构建SET子句
                set_clauses = []
                params = {"qa_id": qa_id}
                
                field_mapping = {
                    "question": "question",
                    "sql": "sql",
                    "difficulty_level": "difficulty_level",
                    "query_type": "query_type",
                    "verified": "verified",
                    "success_rate": "success_rate"
                }
                
                for field, neo4j_field in field_mapping.items():
                    if field in update_data:
                        set_clauses.append(f"qa.{neo4j_field} = ${field}")
                        params[field] = update_data[field]
                
                if set_clauses:
                    query = f"""
                        MATCH (qa:QAPair {{id: $qa_id}})
                        SET {', '.join(set_clauses)}
                        RETURN qa
                    """
                    session.run(query, params)
                    logger.info(f"Updated QA pair in Neo4j: {qa_id}")
                    
        except Exception as e:
            logger.warning(f"Failed to update QA pair in Neo4j: {str(e)}")

    async def delete_qa_pair(self, qa_id: str) -> bool:
        """删除问答对"""
        if not self._initialized:
            await self.initialize()

        try:
            # 策略：从 Milvus 获取所有 collections，然后在每个 collection 中查找并删除
            deleted = False
            
            try:
                collections = self.milvus_service.client.list_collections()
                logger.info(f"Searching for QA pair {qa_id} to delete in {len(collections)} collections")
                
                for collection_name in collections:
                    try:
                        # 尝试在这个 collection 中查询
                        results = self.milvus_service.client.query(
                            collection_name=collection_name,
                            filter=f'id == "{qa_id}"',
                            output_fields=["id", "connection_id"],
                            limit=1
                        )
                        
                        if results and len(results) > 0:
                            # 找到了！获取 connection_id
                            connection_id = results[0].get("connection_id")
                            logger.info(f"Found QA pair {qa_id} in collection {collection_name}, connection_id={connection_id}")
                            
                            # 获取或创建对应的 MilvusService
                            if connection_id:
                                milvus_service = await self.get_milvus_service_for_connection(connection_id)
                            else:
                                milvus_service = self.milvus_service
                            
                            # 执行删除
                            await milvus_service.delete_qa_pair(qa_id)
                            deleted = True
                            logger.info(f"Deleted QA pair {qa_id} from collection {collection_name}")
                            break  # 找到并删除后退出循环
                    except Exception as e:
                        logger.debug(f"QA pair {qa_id} not found in collection {collection_name}: {str(e)}")
                        continue
                
                if not deleted:
                    raise ValueError(f"QA pair with id {qa_id} not found in any collection")
                
            except Exception as e:
                if "not found" in str(e).lower():
                    raise
                logger.error(f"Failed to search collections: {str(e)}")
                raise
            
            # 从Neo4j中删除
            await self._delete_neo4j_qa_pair(qa_id)
            
            logger.info(f"Successfully deleted QA pair: {qa_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete QA pair {qa_id}: {str(e)}")
            raise

    async def _delete_neo4j_qa_pair(self, qa_id: str):
        """从Neo4j中删除问答对"""
        try:
            if not self.neo4j_service._initialized:
                await self.neo4j_service.initialize()
            
            with self.neo4j_service.driver.session() as session:
                # 删除问答对及其关系
                session.run("""
                    MATCH (qa:QAPair {id: $qa_id})
                    DETACH DELETE qa
                """, qa_id=qa_id)
                logger.info(f"Deleted QA pair from Neo4j: {qa_id}")
                
        except Exception as e:
            logger.warning(f"Failed to delete QA pair from Neo4j: {str(e)}")

    async def clear_caches(self):
        """清理所有缓存"""
        if self.vector_service:
            self.vector_service.clear_cache()
        logger.info("All caches cleared")

    def close(self):
        """关闭所有连接"""
        if self.neo4j_service:
            self.neo4j_service.close()

        # 清理向量服务缓存
        if self.vector_service:
            self.vector_service.clear_cache()
