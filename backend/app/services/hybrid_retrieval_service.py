# 混合检索服务 - 核心实现

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import json
import uuid
import re
import logging
import time
from functools import lru_cache
from neo4j import GraphDatabase
from pymilvus import MilvusClient, DataType
# from sentence_transformers import SentenceTransformer
from langchain_ollama import OllamaEmbeddings

import numpy as np

from app.core.config import settings
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ===== 工具函数 =====

def get_database_name_by_connection_id(connection_id: int) -> Optional[str]:
    """根据连接ID获取数据库名称"""
    try:
        # from app.core.deps import get_db
        from app.db.session import get_db
        from app.models.db_connection import DBConnection

        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 查询数据库连接信息
            connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
            if connection:
                return connection.database_name
            else:
                logger.warning(f"Connection with ID {connection_id} not found")
                return None
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get database name for connection {connection_id}: {str(e)}")
        return None

# ===== 数据模型 =====

@dataclass
class QAPairWithContext:
    """带上下文的问答对"""
    id: str
    question: str
    sql: str
    connection_id: int
    difficulty_level: int
    query_type: str
    success_rate: float
    verified: bool
    created_at: datetime

    # 上下文信息
    used_tables: List[str]
    used_columns: List[str]
    query_pattern: str
    mentioned_entities: List[str]

    # 向量表示
    embedding_vector: Optional[List[float]] = None

@dataclass
class RetrievalResult:
    """检索结果"""
    qa_pair: QAPairWithContext
    semantic_score: float = 0.0
    structural_score: float = 0.0
    pattern_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0
    explanation: str = ""

# ===== 向量化服务 =====

class VectorService:
    """优化的向量化服务 - 支持Ollama和SentenceTransformer"""

    def __init__(self, service_type: str = None, model_name: str = None):
        self.service_type = service_type or settings.VECTOR_SERVICE_TYPE
        self.model_name = model_name or (
            settings.OLLAMA_EMBEDDING_MODEL if self.service_type == "ollama"
            else settings.EMBEDDING_MODEL
        )
        self.model = None
        self.dimension = None
        self._initialized = False
        self._cache = {} if settings.VECTOR_CACHE_ENABLED else None
        self._cache_timestamps = {} if settings.VECTOR_CACHE_ENABLED else None

        # 性能配置
        self.batch_size = settings.VECTOR_BATCH_SIZE
        self.max_retries = settings.VECTOR_MAX_RETRIES
        self.retry_delay = settings.VECTOR_RETRY_DELAY

    async def initialize(self):
        """初始化模型"""
        if not self._initialized:
            try:
                if self.service_type == "ollama":
                    await self._initialize_ollama()
                else:
                    pass
                    # await self._initialize_sentence_transformer()

                self._initialized = True
                logger.info(f"Vector service initialized successfully with {self.service_type}")

            except Exception as e:
                logger.error(f"Failed to initialize vector service: {str(e)}")
                raise

    async def _initialize_ollama(self):
        """初始化Ollama嵌入模型"""

        logger.info(f"Initializing Ollama embedding model: {self.model_name}")

        self.model = OllamaEmbeddings(
            model=self.model_name,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.OLLAMA_TEMPERATURE,
        )

        # 测试连接并获取维度
        test_text = "test"
        test_embedding = await self._embed_with_retry(test_text)
        self.dimension = len(test_embedding)

        logger.info(f"Ollama model loaded, dimension: {self.dimension}")

    async def _initialize_sentence_transformer(self):
        """初始化SentenceTransformer模型"""
        # logger.info(f"Initializing SentenceTransformer model: {self.model_name}")
        #
        # # 使用配置的缓存路径或默认路径
        # cache_folder = getattr(settings, 'SENTENCE_TRANSFORMER_CACHE', None)
        # if not cache_folder:
        #     cache_folder = r"C:\Users\86134\.cache\huggingface\hub"
        #
        # self.model = SentenceTransformer(self.model_name, cache_folder=cache_folder)
        # self.dimension = self.model.get_sentence_embedding_dimension()
        #
        # logger.info(f"SentenceTransformer model loaded, dimension: {self.dimension}")

    async def embed_question(self, question: str) -> List[float]:
        """将问题转换为向量"""
        if not self._initialized:
            await self.initialize()

        # 检查缓存
        if self._cache is not None:
            cached_result = self._get_from_cache(question)
            if cached_result is not None:
                return cached_result

        processed_question = self._preprocess_question(question)

        try:
            if self.service_type == "ollama":
                embedding = await self._embed_with_retry(processed_question)
            else:
                embedding = self.model.encode(processed_question).tolist()

            # 存储到缓存
            if self._cache is not None:
                self._store_to_cache(question, embedding)

            return embedding

        except Exception as e:
            logger.error(f"Failed to embed question: {str(e)}")
            raise

    async def batch_embed(self, questions: List[str]) -> List[List[float]]:
        """批量向量化"""
        if not self._initialized:
            await self.initialize()

        if not questions:
            return []

        # 检查缓存中的结果
        cached_results = {}
        uncached_questions = []

        if self._cache is not None:
            for i, question in enumerate(questions):
                cached_result = self._get_from_cache(question)
                if cached_result is not None:
                    cached_results[i] = cached_result
                else:
                    uncached_questions.append((i, question))
        else:
            uncached_questions = list(enumerate(questions))

        # 处理未缓存的问题
        if uncached_questions:
            uncached_indices, uncached_texts = zip(*uncached_questions)
            processed_questions = [self._preprocess_question(q) for q in uncached_texts]

            try:
                if self.service_type == "ollama":
                    # Ollama批量处理
                    embeddings = await self._batch_embed_ollama(processed_questions)
                else:
                    # SentenceTransformer批量处理
                    embeddings = self.model.encode(processed_questions).tolist()

                # 存储到缓存并合并结果
                for i, (original_idx, original_question) in enumerate(uncached_questions):
                    embedding = embeddings[i]
                    if self._cache is not None:
                        self._store_to_cache(original_question, embedding)
                    cached_results[original_idx] = embedding

            except Exception as e:
                logger.error(f"Failed to batch embed questions: {str(e)}")
                raise

        # 按原始顺序返回结果
        return [cached_results[i] for i in range(len(questions))]

    async def _batch_embed_ollama(self, questions: List[str]) -> List[List[float]]:
        """Ollama批量嵌入"""
        embeddings = []

        # 分批处理以避免超时
        for i in range(0, len(questions), self.batch_size):
            batch = questions[i:i + self.batch_size]
            batch_embeddings = await self._embed_batch_with_retry(batch)
            embeddings.extend(batch_embeddings)

        return embeddings

    async def _embed_with_retry(self, text: str) -> List[float]:
        """带重试的单个文本嵌入"""
        for attempt in range(self.max_retries):
            try:
                if self.service_type == "ollama":
                    # 使用异步方法
                    embedding = await self.model.aembed_query(text)
                    return embedding
                else:
                    return self.model.encode(text).tolist()

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                logger.warning(f"Embedding attempt {attempt + 1} failed: {str(e)}, retrying...")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 指数退避

    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """带重试的批量文本嵌入"""
        for attempt in range(self.max_retries):
            try:
                if self.service_type == "ollama":
                    # Ollama批量嵌入
                    embeddings = await self.model.aembed_documents(texts)
                    return embeddings
                else:
                    return self.model.encode(texts).tolist()

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                logger.warning(f"Batch embedding attempt {attempt + 1} failed: {str(e)}, retrying...")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))

    def _preprocess_question(self, question: str) -> str:
        """增强的预处理问题文本"""
        if not question:
            return ""

        # 基本清理
        processed = question.strip()

        # 移除多余的空白字符
        processed = re.sub(r'\s+', ' ', processed)

        # 可选：转换为小写（根据模型需求）
        if self.service_type != "ollama":  # Ollama模型通常对大小写敏感
            processed = processed.lower()

        return processed

    def _get_from_cache(self, question: str) -> Optional[List[float]]:
        """从缓存获取结果"""
        if self._cache is None:
            return None

        cache_key = self._get_cache_key(question)

        # 检查是否过期
        if cache_key in self._cache_timestamps:
            if time.time() - self._cache_timestamps[cache_key] > settings.VECTOR_CACHE_TTL:
                # 清理过期缓存
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                return None

        return self._cache.get(cache_key)

    def _store_to_cache(self, question: str, embedding: List[float]):
        """存储到缓存"""
        if self._cache is None:
            return

        cache_key = self._get_cache_key(question)
        self._cache[cache_key] = embedding
        self._cache_timestamps[cache_key] = time.time()

    def _get_cache_key(self, question: str) -> str:
        """生成缓存键"""
        return f"{self.service_type}:{self.model_name}:{hash(question)}"

    def clear_cache(self):
        """清理缓存"""
        if self._cache is not None:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Vector service cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self._cache is None:
            return {"cache_enabled": False}

        current_time = time.time()
        valid_entries = sum(
            1 for timestamp in self._cache_timestamps.values()
            if current_time - timestamp <= settings.VECTOR_CACHE_TTL
        )

        return {
            "cache_enabled": True,
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "cache_hit_rate": getattr(self, '_cache_hits', 0) / max(getattr(self, '_cache_requests', 1), 1)
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self._initialized:
                return {
                    "status": "unhealthy",
                    "message": "Service not initialized",
                    "service_type": self.service_type
                }

            # 测试嵌入功能
            start_time = time.time()
            test_embedding = await self.embed_question("health check test")
            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "service_type": self.service_type,
                "model_name": self.model_name,
                "dimension": self.dimension,
                "response_time_ms": round(response_time * 1000, 2),
                "cache_stats": self.get_cache_stats()
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "service_type": self.service_type,
                "error": str(e)
            }


class VectorServiceFactory:
    """向量服务工厂类"""

    _instances = {}

    @classmethod
    async def create_service(cls, service_type: str = None, model_name: str = None) -> VectorService:
        """创建或获取向量服务实例"""
        service_type = service_type or settings.VECTOR_SERVICE_TYPE
        model_name = model_name or (
            settings.OLLAMA_EMBEDDING_MODEL if service_type == "ollama"
            else settings.EMBEDDING_MODEL
        )

        instance_key = f"{service_type}:{model_name}"

        if instance_key not in cls._instances:
            service = VectorService(service_type=service_type, model_name=model_name)
            await service.initialize()
            cls._instances[instance_key] = service
            logger.info(f"Created new vector service instance: {instance_key}")

        return cls._instances[instance_key]

    @classmethod
    async def get_default_service(cls) -> VectorService:
        """获取默认向量服务"""
        return await cls.create_service()

    @classmethod
    def clear_instances(cls):
        """清理所有实例"""
        for service in cls._instances.values():
            if hasattr(service, 'clear_cache'):
                service.clear_cache()
        cls._instances.clear()
        logger.info("Cleared all vector service instances")


class VectorServiceMonitor:
    """向量服务监控类"""

    def __init__(self, service: VectorService):
        self.service = service
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    async def embed_with_monitoring(self, question: str) -> List[float]:
        """带监控的嵌入"""
        start_time = time.time()
        self.metrics["total_requests"] += 1

        # 检查缓存
        if self.service._cache is not None:
            cached_result = self.service._get_from_cache(question)
            if cached_result is not None:
                self.metrics["cache_hits"] += 1
                return cached_result
            else:
                self.metrics["cache_misses"] += 1

        try:
            result = await self.service.embed_question(question)
            self.metrics["successful_requests"] += 1
            return result

        except Exception as e:
            self.metrics["failed_requests"] += 1
            raise e

        finally:
            response_time = time.time() - start_time
            self.metrics["total_response_time"] += response_time

    def get_metrics(self) -> Dict[str, Any]:
        """获取监控指标"""
        avg_response_time = (
            self.metrics["total_response_time"] / max(self.metrics["total_requests"], 1)
        )

        success_rate = (
            self.metrics["successful_requests"] / max(self.metrics["total_requests"], 1)
        )

        cache_hit_rate = (
            self.metrics["cache_hits"] / max(
                self.metrics["cache_hits"] + self.metrics["cache_misses"], 1
            )
        )

        return {
            **self.metrics,
            "average_response_time_ms": round(avg_response_time * 1000, 2),
            "success_rate": round(success_rate, 4),
            "cache_hit_rate": round(cache_hit_rate, 4)
        }

# ===== Milvus服务 =====

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

# ===== 扩展的Neo4j服务 =====

class EnhancedNeo4jService:
    """扩展的Neo4j服务"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver = None
        self._initialized = False

    async def initialize(self):
        """初始化Neo4j连接"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # 测试连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            self._initialized = True
            logger.info("Neo4j service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j service: {str(e)}")
            raise

    async def store_qa_pair_with_context(self, qa_pair: QAPairWithContext,
                                       schema_context: Dict[str, Any]):
        """存储问答对及其完整上下文信息"""
        if not self._initialized:
            await self.initialize()

        with self.driver.session() as session:
            try:
                # 1. 创建QAPair节点
                session.run("""
                    CREATE (qa:QAPair {
                        id: $id,
                        question: $question,
                        sql: $sql,
                        connection_id: $connection_id,
                        difficulty_level: $difficulty_level,
                        query_type: $query_type,
                        success_rate: $success_rate,
                        verified: $verified,
                        created_at: datetime($created_at)
                    })
                """,
                    id=qa_pair.id,
                    question=qa_pair.question,
                    sql=qa_pair.sql,
                    connection_id=qa_pair.connection_id,
                    difficulty_level=qa_pair.difficulty_level,
                    query_type=qa_pair.query_type,
                    success_rate=qa_pair.success_rate,
                    verified=qa_pair.verified,
                    created_at=qa_pair.created_at.isoformat()
                )

                # 2. 建立与Table的USES_TABLES关系
                # 如果used_tables为空，尝试从SQL中提取
                tables_to_use = qa_pair.used_tables
                if not tables_to_use and qa_pair.sql:
                    tables_to_use = extract_tables_from_sql(qa_pair.sql)
                    logger.info(f"从SQL中提取表名: {tables_to_use} for QA {qa_pair.id}")

                for table_name in tables_to_use:
                    # 检查表是否存在
                    table_exists = session.run("""
                        MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                        RETURN count(t) > 0 as exists
                    """, table_name=table_name, connection_id=qa_pair.connection_id).single()['exists']

                    if table_exists:
                        session.run("""
                            MATCH (qa:QAPair {id: $qa_id})
                            MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                            CREATE (qa)-[:USES_TABLES]->(t)
                        """, qa_id=qa_pair.id, table_name=table_name,
                            connection_id=qa_pair.connection_id)
                    else:
                        logger.warning(f"表 {table_name} 在连接 {qa_pair.connection_id} 中不存在")

                # 3. 创建或更新QueryPattern
                await self._create_or_update_pattern(session, qa_pair)

                # 4. 创建Entity节点和关系
                await self._create_entity_relationships(session, qa_pair)

                logger.info(f"Stored QA pair with context: {qa_pair.id}")

            except Exception as e:
                logger.error(f"Failed to store QA pair with context: {str(e)}")
                raise

    async def _create_or_update_pattern(self, session, qa_pair: QAPairWithContext):
        """创建或更新查询模式"""
        pattern_id = f"pattern_{qa_pair.query_type}_{qa_pair.difficulty_level}"

        # 检查模式是否存在
        result = session.run("""
            MATCH (p:QueryPattern {id: $pattern_id})
            RETURN p
        """, pattern_id=pattern_id)

        if result.single():
            # 更新使用计数
            session.run("""
                MATCH (p:QueryPattern {id: $pattern_id})
                SET p.usage_count = p.usage_count + 1
            """, pattern_id=pattern_id)
        else:
            # 创建新模式
            session.run("""
                CREATE (p:QueryPattern {
                    id: $pattern_id,
                    name: $query_type,
                    difficulty_level: $difficulty_level,
                    usage_count: 1,
                    created_at: datetime()
                })
            """,
                pattern_id=pattern_id,
                query_type=qa_pair.query_type,
                difficulty_level=qa_pair.difficulty_level
            )

        # 建立QAPair与Pattern的关系
        session.run("""
            MATCH (qa:QAPair {id: $qa_id})
            MATCH (p:QueryPattern {id: $pattern_id})
            CREATE (qa)-[:FOLLOWS_PATTERN]->(p)
        """, qa_id=qa_pair.id, pattern_id=pattern_id)

    async def _create_entity_relationships(self, session, qa_pair: QAPairWithContext):
        """创建实体关系"""
        for entity in qa_pair.mentioned_entities:
            entity_id = f"entity_{entity.lower().replace(' ', '_')}"

            # 创建或获取Entity节点
            session.run("""
                MERGE (e:Entity {id: $entity_id})
                ON CREATE SET e.name = $entity_name, e.created_at = datetime()
            """, entity_id=entity_id, entity_name=entity)

            # 建立关系
            session.run("""
                MATCH (qa:QAPair {id: $qa_id})
                MATCH (e:Entity {id: $entity_id})
                CREATE (qa)-[:MENTIONS_ENTITY]->(e)
            """, qa_id=qa_pair.id, entity_id=entity_id)

    async def structural_search(self, schema_context: Dict[str, Any],
                              connection_id: int, top_k: int = 20) -> List[RetrievalResult]:
        """基于schema结构的检索"""
        if not self._initialized:
            await self.initialize()

        table_names = [table.get('name') for table in schema_context.get('tables', [])]

        with self.driver.session() as session:
            result = session.run("""
                MATCH (qa:QAPair)-[:USES_TABLES]->(t:Table)
                WHERE t.name IN $table_names AND qa.connection_id = $connection_id
                WITH qa, count(t) as table_overlap, collect(t.name) as used_tables
                ORDER BY table_overlap DESC, qa.success_rate DESC
                LIMIT $top_k
                RETURN qa, table_overlap, used_tables
            """, table_names=table_names, connection_id=connection_id, top_k=top_k)

            results = []
            for record in result:
                qa_data = record['qa']
                table_overlap = record['table_overlap']
                used_tables = record['used_tables']

                # 计算结构相似性分数
                structural_score = table_overlap / max(len(table_names), 1)

                qa_pair = self._build_qa_pair_from_record(qa_data, used_tables)
                results.append(RetrievalResult(
                    qa_pair=qa_pair,
                    structural_score=structural_score,
                    explanation=f"使用了{table_overlap}个相同的表"
                ))

            return results

    async def pattern_search(self, query_type: str, difficulty_level: int,
                           connection_id: int, top_k: int = 20) -> List[RetrievalResult]:
        """基于查询模式的检索"""
        if not self._initialized:
            await self.initialize()

        with self.driver.session() as session:
            result = session.run("""
                MATCH (qa:QAPair)-[:FOLLOWS_PATTERN]->(p:QueryPattern)
                WHERE p.name = $query_type
                AND p.difficulty_level <= $difficulty_level + 1
                AND qa.connection_id = $connection_id
                RETURN qa, p.usage_count
                ORDER BY qa.success_rate DESC, p.usage_count DESC
                LIMIT $top_k
            """, query_type=query_type, difficulty_level=difficulty_level,
                connection_id=connection_id, top_k=top_k)

            results = []
            for record in result:
                qa_data = record['qa']
                usage_count = record['p.usage_count']

                # 计算模式匹配分数
                pattern_score = min(1.0, usage_count / 100.0)  # 归一化使用次数

                qa_pair = self._build_qa_pair_from_record(qa_data)
                results.append(RetrievalResult(
                    qa_pair=qa_pair,
                    pattern_score=pattern_score,
                    explanation=f"匹配查询模式，使用次数: {usage_count}"
                ))

            return results

    def _build_qa_pair_from_record(self, qa_data, used_tables=None) -> QAPairWithContext:
        """从Neo4j记录构建QAPair对象"""
        return QAPairWithContext(
            id=qa_data['id'],
            question=qa_data['question'],
            sql=qa_data['sql'],
            connection_id=qa_data['connection_id'],
            difficulty_level=qa_data['difficulty_level'],
            query_type=qa_data['query_type'],
            success_rate=qa_data['success_rate'],
            verified=qa_data['verified'],
            created_at=datetime.fromisoformat(qa_data['created_at']) if isinstance(qa_data['created_at'], str) else qa_data['created_at'],
            used_tables=used_tables or [],
            used_columns=[],
            query_pattern=qa_data['query_type'],
            mentioned_entities=[]
        )

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()

# ===== 融合排序器 =====

class FusionRanker:
    """多维度融合排序器"""

    def __init__(self):
        self.weights = {
            'semantic': settings.SEMANTIC_WEIGHT,
            'structural': settings.STRUCTURAL_WEIGHT,
            'pattern': settings.PATTERN_WEIGHT,
            'quality': settings.QUALITY_WEIGHT
        }

    def fuse_and_rank(self, semantic_results: List[RetrievalResult],
                     structural_results: List[RetrievalResult],
                     pattern_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """融合多个检索结果并排序"""

        # 1. 收集所有唯一的QA对
        all_qa_pairs = {}

        # 处理语义检索结果
        for result in semantic_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].semantic_score = max(
                    all_qa_pairs[qa_id].semantic_score, result.semantic_score
                )

        # 处理结构检索结果
        for result in structural_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].structural_score = max(
                    all_qa_pairs[qa_id].structural_score, result.structural_score
                )

        # 处理模式检索结果
        for result in pattern_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].pattern_score = max(
                    all_qa_pairs[qa_id].pattern_score, result.pattern_score
                )

        # 2. 计算质量分数和最终分数
        final_results = []
        for qa_id, result in all_qa_pairs.items():
            # 计算质量分数
            quality_score = self._calculate_quality_score(result.qa_pair)
            result.quality_score = quality_score

            # 计算最终分数 - 使用动态权重调整
            final_score = self._calculate_dynamic_final_score(
                result.semantic_score,
                result.structural_score,
                result.pattern_score,
                quality_score
            )
            result.final_score = final_score

            # 生成解释
            result.explanation = self._generate_explanation(result)

            final_results.append(result)

        # 3. 按最终分数排序
        return sorted(final_results, key=lambda x: x.final_score, reverse=True)

    def _calculate_quality_score(self, qa_pair: QAPairWithContext) -> float:
        """计算问答对的质量分数"""
        quality_score = 0.0

        # 验证状态加分
        if qa_pair.verified:
            quality_score += 0.3

        # 成功率加分
        quality_score += qa_pair.success_rate * 0.5

        # 难度适中加分（难度2-3的问答对通常质量较高）
        if 2 <= qa_pair.difficulty_level <= 3:
            quality_score += 0.2

        return min(1.0, quality_score)

    def _calculate_dynamic_final_score(self, semantic_score: float, structural_score: float,
                                     pattern_score: float, quality_score: float) -> float:
        """
        动态权重计算最终分数
        当语义相似度很高时，增加其权重；当语义相似度较低时，更多依赖结构和模式匹配
        """
        # 基础权重
        base_weights = {
            'semantic': self.weights['semantic'],
            'structural': self.weights['structural'],
            'pattern': self.weights['pattern'],
            'quality': self.weights['quality']
        }

        # 动态调整权重
        if semantic_score >= 0.9:
            # 语义高度匹配时，大幅提升语义权重
            adjusted_weights = {
                'semantic': 0.80,
                'structural': 0.10,
                'pattern': 0.05,
                'quality': 0.05
            }
        elif semantic_score >= 0.7:
            # 语义较好匹配时，适度提升语义权重
            adjusted_weights = {
                'semantic': 0.70,
                'structural': 0.15,
                'pattern': 0.10,
                'quality': 0.05
            }
        elif semantic_score >= 0.5:
            # 语义中等匹配时，使用调整后的基础权重
            adjusted_weights = base_weights
        else:
            # 语义匹配较差时，更多依赖结构和模式
            adjusted_weights = {
                'semantic': 0.40,
                'structural': 0.35,
                'pattern': 0.20,
                'quality': 0.05
            }

        # 计算最终分数
        final_score = (
            semantic_score * adjusted_weights['semantic'] +
            structural_score * adjusted_weights['structural'] +
            pattern_score * adjusted_weights['pattern'] +
            quality_score * adjusted_weights['quality']
        )

        return final_score

    def _generate_explanation(self, result: RetrievalResult) -> str:
        """生成推荐解释"""
        explanations = []

        # 语义相似度解释
        if result.semantic_score >= 0.9:
            explanations.append(f"语义高度相似({result.semantic_score:.2f})")
        elif result.semantic_score >= 0.7:
            explanations.append(f"语义相似({result.semantic_score:.2f})")
        elif result.semantic_score >= 0.5:
            explanations.append(f"语义部分相似({result.semantic_score:.2f})")

        # 结构相似度解释
        if result.structural_score > 0.7:
            explanations.append("使用相同的表结构")
        elif result.structural_score > 0.3:
            explanations.append("使用部分相同的表")

        # 模式匹配解释
        if result.pattern_score > 0.5:
            explanations.append("匹配相似的查询模式")

        # 质量指标解释
        if result.qa_pair.verified:
            explanations.append("已验证的高质量示例")

        # 动态权重提示
        if result.semantic_score >= 0.9:
            explanations.append("(语义优先权重)")
        elif result.semantic_score < 0.5:
            explanations.append("(结构模式优先权重)")

        return "; ".join(explanations) if explanations else "相关示例"

# ===== 混合检索引擎 =====

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

# ===== 工具函数 =====

def extract_tables_from_sql(sql: str) -> List[str]:
    """从SQL中提取表名"""
    # 简单的表名提取逻辑
    import re

    # 移除注释和多余空格
    sql_clean = re.sub(r'--.*?\n', '', sql)
    sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
    sql_clean = ' '.join(sql_clean.split())

    # 查找FROM和JOIN后的表名
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql_clean, re.IGNORECASE)

    return list(set(matches))

def extract_entities_from_question(question: str) -> List[str]:
    """从问题中提取实体"""
    # 简单的实体提取逻辑，可以后续用NER模型替换
    entities = []

    # 常见的业务实体关键词
    entity_keywords = {
        '用户': ['用户', '客户', '会员', 'user', 'customer'],
        '订单': ['订单', '交易', 'order', 'transaction'],
        '产品': ['产品', '商品', '物品', 'product', 'item'],
        '部门': ['部门', '科室', 'department'],
        '员工': ['员工', '职员', 'employee', 'staff']
    }

    question_lower = question.lower()
    for entity, keywords in entity_keywords.items():
        if any(keyword in question_lower for keyword in keywords):
            entities.append(entity)

    return entities

def clean_sql(sql: str) -> str:
    """清理SQL语句"""
    # 移除代码块标记
    sql = re.sub(r'```sql\n?', '', sql)
    sql = re.sub(r'```\n?', '', sql)

    # 移除多余的空格和换行
    sql = ' '.join(sql.split())

    # 确保以分号结尾
    if not sql.strip().endswith(';'):
        sql = sql.strip() + ';'

    return sql

def generate_qa_id() -> str:
    """生成问答对ID"""
    return f"qa_{uuid.uuid4().hex[:12]}"
