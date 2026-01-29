"""
Milvus 向量数据库服务
"""

import logging
from typing import Dict, Any, List, Optional

from pymilvus import MilvusClient, DataType

from app.core.config import settings
from ..models import QAPairWithContext
from ..utils import get_database_name_by_connection_id

logger = logging.getLogger(__name__)


class MilvusService:
    """Milvus向量数据库服务 - 使用MilvusClient"""

    def __init__(self, host: str = None, port: str = None, database_name: str = None, connection_id: int = None):
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT

        # 优先使用传入的database_name，否则根据connection_id获取
        if database_name:
            self.database_name = database_name
        elif connection_id:
            self.database_name = get_database_name_by_connection_id(connection_id)
        else:
            self.database_name = None

        self.connection_id = connection_id
        self.collection_name = self._generate_collection_name(self.database_name)

        # 构建连接URI
        self.uri = f"http://{self.host}:{self.port}"
        self.client = None
        self._initialized = False

    def _generate_collection_name(self, database_name: str = None) -> str:
        """根据数据库名称生成集合名称"""
        if database_name:
            # 清理数据库名称，确保符合Milvus集合命名规范
            # Milvus集合名称只能包含字母、数字和下划线，且以字母或下划线开头
            clean_name = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in database_name.lower())
            # 确保以字母或下划线开头
            if clean_name and not (clean_name[0].isalpha() or clean_name[0] == "_"):
                clean_name = "db_" + clean_name
            # 如果清理后为空或只有下划线，使用默认前缀
            if not clean_name or clean_name.replace("_", "") == "":
                clean_name = "db_unknown"
            # 限制长度（Milvus集合名称最大长度为255）
            clean_name = clean_name[:50]  # 保留足够空间给后缀
            return f"{clean_name}_qa_pairs"
        else:
            # 默认集合名称
            return "default_qa_pairs"

    async def initialize(self, dimension: int):
        """初始化Milvus连接和集合"""
        try:
            # 创建MilvusClient连接
            self.client = MilvusClient(uri=self.uri)
            logger.info(f"Connected to Milvus at {self.uri}")

            # 检查集合是否存在
            if self.client.has_collection(collection_name=self.collection_name):
                logger.info(f"Collection {self.collection_name} exists, checking schema compatibility...")
                # 检查现有集合的schema是否兼容
                try:
                    # 尝试获取集合信息来验证schema
                    collection_info = self.client.describe_collection(collection_name=self.collection_name)
                    logger.info(f"Existing collection schema: {collection_info}")

                    # 检查是否有vector字段
                    has_vector_field = any(field.get('name') == 'vector' for field in collection_info.get('fields', []))
                    if not has_vector_field:
                        logger.warning(f"Collection {self.collection_name} missing vector field, recreating...")
                        # 删除旧集合并重新创建
                        self.client.drop_collection(collection_name=self.collection_name)
                        logger.info(f"Dropped incompatible collection: {self.collection_name}")
                        await self._create_new_collection(dimension)
                    else:
                        logger.info(f"Using existing compatible collection: {self.collection_name}")
                except Exception as e:
                    logger.warning(f"Failed to check collection schema: {e}, recreating collection...")
                    # 如果无法检查schema，删除并重新创建
                    try:
                        self.client.drop_collection(collection_name=self.collection_name)
                        logger.info(f"Dropped problematic collection: {self.collection_name}")
                    except:
                        pass
                    await self._create_new_collection(dimension)
            else:
                await self._create_new_collection(dimension)

            self._initialized = True
            logger.info("Milvus service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Milvus service: {str(e)}")
            raise

    async def _create_new_collection(self, dimension: int):
        """创建新的集合"""
        try:
            # 创建新集合 - 使用MilvusClient.create_schema方法
            schema = self.client.create_schema(
                auto_id=False,
                enable_dynamic_field=False,
                description="QA pairs for Text2SQL optimization"
            )

            # 添加字段到schema
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=100, is_primary=True)
            schema.add_field(field_name="question", datatype=DataType.VARCHAR, max_length=2000)
            schema.add_field(field_name="sql", datatype=DataType.VARCHAR, max_length=5000)
            schema.add_field(field_name="connection_id", datatype=DataType.INT64)
            schema.add_field(field_name="difficulty_level", datatype=DataType.INT64)
            schema.add_field(field_name="query_type", datatype=DataType.VARCHAR, max_length=50)
            schema.add_field(field_name="success_rate", datatype=DataType.FLOAT)
            schema.add_field(field_name="verified", datatype=DataType.BOOL)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)

            # 创建索引参数
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="IVF_FLAT",
                metric_type="COSINE",
                params={"nlist": 128}
            )

            # 创建集合
            self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params
            )
            logger.info(f"Created new collection: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to create collection {self.collection_name}: {str(e)}")
            raise

    async def insert_qa_pair(self, qa_pair: QAPairWithContext) -> str:
        """插入问答对"""
        if not self._initialized:
            raise RuntimeError("Milvus service not initialized")

        try:
            # 准备数据
            data = {
                "id": qa_pair.id,
                "question": qa_pair.question,
                "sql": qa_pair.sql,
                "connection_id": qa_pair.connection_id,
                "difficulty_level": qa_pair.difficulty_level,
                "query_type": qa_pair.query_type,
                "success_rate": qa_pair.success_rate,
                "verified": qa_pair.verified,
                "vector": qa_pair.embedding_vector
            }

            # 插入数据
            self.client.insert(
                collection_name=self.collection_name,
                data=[data]
            )
            
            # 立即刷新以确保插入生效
            self.client.flush(collection_name=self.collection_name)

            logger.info(f"Inserted QA pair: {qa_pair.id}")
            return qa_pair.id

        except Exception as e:
            logger.error(f"Failed to insert QA pair: {str(e)}")
            raise

    async def search_similar(self,
                           query_vector: List[float],
                           top_k: int = 5,
                           connection_id: Optional[int] = None) -> List[Dict]:
        """搜索相似的问答对"""
        if not self._initialized:
            raise RuntimeError("Milvus service not initialized")

        try:
            # 构建过滤表达式
            filter_expr = None
            if connection_id:
                filter_expr = f"connection_id == {connection_id}"

            # 使用MilvusClient进行搜索
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }

            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                search_params=search_params,
                filter=filter_expr,
                output_fields=["id", "question", "sql", "connection_id",
                              "difficulty_level", "query_type", "success_rate", "verified"]
            )

            return self._format_search_results(results[0])

        except Exception as e:
            logger.error(f"Failed to search similar QA pairs: {str(e)}")
            return []

    def _format_search_results(self, results) -> List[Dict]:
        """格式化搜索结果"""
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result["entity"]["id"],
                "question": result["entity"]["question"],
                "sql": result["entity"]["sql"],
                "connection_id": result["entity"]["connection_id"],
                "difficulty_level": result["entity"]["difficulty_level"],
                "query_type": result["entity"]["query_type"],
                "success_rate": result["entity"]["success_rate"],
                "verified": result["entity"]["verified"],
                "similarity_score": result["distance"]
            })
        return formatted_results

    async def get_stats(self, connection_id: Optional[int] = None) -> Dict[str, Any]:
        """获取问答对统计信息"""
        if not self._initialized:
            return {"total": 0, "error": "Service not initialized"}

        try:
            # 获取集合中的实体数量
            collection_info = self.client.describe_collection(collection_name=self.collection_name)
            
            # 查询所有数据以计算统计信息
            filter_expr = f"connection_id == {connection_id}" if connection_id else None
            
            # 查询数据
            results = self.client.query(
                collection_name=self.collection_name,
                filter=filter_expr if filter_expr else "id != ''",
                output_fields=["id", "query_type", "difficulty_level", "verified", "success_rate"],
                limit=10000  # 限制查询数量
            )
            
            # 统计信息
            total = len(results)
            verified_count = sum(1 for r in results if r.get("verified", False))
            
            # 查询类型统计
            query_types = {}
            for r in results:
                qt = r.get("query_type", "UNKNOWN")
                query_types[qt] = query_types.get(qt, 0) + 1
            
            # 难度分布
            difficulty_dist = {}
            for r in results:
                dl = str(r.get("difficulty_level", 3))
                difficulty_dist[dl] = difficulty_dist.get(dl, 0) + 1
            
            # 平均成功率
            success_rates = [r.get("success_rate", 0) for r in results]
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
            
            return {
                "total": total,
                "verified": verified_count,
                "query_types": query_types,
                "difficulty_distribution": difficulty_dist,
                "average_success_rate": round(avg_success_rate, 2),
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {"total": 0, "error": str(e)}

    async def get_all_qa_pairs(self, connection_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """获取所有问答对"""
        if not self._initialized:
            return []

        try:
            filter_expr = f"connection_id == {connection_id}" if connection_id else "id != ''"
            
            results = self.client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                output_fields=["id", "question", "sql", "connection_id", 
                              "difficulty_level", "query_type", "success_rate", "verified"],
                limit=limit
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get all QA pairs: {str(e)}")
            return []

    async def get_qa_pair_by_id(self, qa_id: str) -> Optional[Dict]:
        """根据ID获取问答对"""
        if not self._initialized:
            return None

        try:
            results = self.client.query(
                collection_name=self.collection_name,
                filter=f'id == "{qa_id}"',
                output_fields=["id", "question", "sql", "connection_id", 
                              "difficulty_level", "query_type", "success_rate", "verified"]
            )
            
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Failed to get QA pair by id {qa_id}: {str(e)}")
            return None

    async def update_qa_pair(self, qa_id: str, update_data: Dict, new_vector: List[float] = None) -> bool:
        """更新问答对（Milvus不支持直接更新，需要删除后重新插入）"""
        if not self._initialized:
            raise RuntimeError("Milvus service not initialized")

        try:
            # 1. 获取原始数据
            original = await self.get_qa_pair_by_id(qa_id)
            if not original:
                raise ValueError(f"QA pair with id {qa_id} not found")
            
            # 2. 合并更新数据
            updated_data = {**original, **update_data}
            
            # 3. 删除原始记录
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'id == "{qa_id}"'
            )
            
            # 立即刷新以确保删除生效
            self.client.flush(collection_name=self.collection_name)
            
            # 4. 重新插入更新后的数据
            data = {
                "id": updated_data["id"],
                "question": updated_data["question"],
                "sql": updated_data["sql"],
                "connection_id": updated_data["connection_id"],
                "difficulty_level": updated_data["difficulty_level"],
                "query_type": updated_data["query_type"],
                "success_rate": updated_data.get("success_rate", 0.0),
                "verified": updated_data.get("verified", False),
                "vector": new_vector if new_vector else [0.0] * 1024  # 需要重新生成向量
            }
            
            self.client.insert(
                collection_name=self.collection_name,
                data=[data]
            )
            
            # 再次刷新以确保插入生效
            self.client.flush(collection_name=self.collection_name)
            
            logger.info(f"Updated QA pair: {qa_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update QA pair {qa_id}: {str(e)}")
            raise

    async def delete_qa_pair(self, qa_id: str) -> bool:
        """删除问答对"""
        if not self._initialized:
            raise RuntimeError("Milvus service not initialized")

        try:
            # 执行删除
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'id == "{qa_id}"'
            )
            
            # 立即刷新以确保删除生效
            self.client.flush(collection_name=self.collection_name)
            
            logger.info(f"Deleted QA pair from Milvus: {qa_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete QA pair {qa_id}: {str(e)}")
            raise
