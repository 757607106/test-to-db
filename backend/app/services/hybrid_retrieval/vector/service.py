"""
向量化服务 - VectorService

支持多种Embedding提供商（OpenAI, Ollama, Aliyun等）
"""

import re
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.llm_config import LLMConfiguration
from app.core.model_registry import (
    is_openai_compatible,
    get_provider_config,
)

logger = logging.getLogger(__name__)


class VectorService:
    """优化的向量化服务 - 支持多种Embedding提供商（OpenAI, Ollama, Aliyun等）"""

    def __init__(self, llm_config: Optional[LLMConfiguration] = None, service_type: str = None, model_name: str = None):
        """
        初始化向量服务
        
        Args:
            llm_config: LLM配置对象（优先级最高）
            service_type: 服务类型（兼容旧代码，用于fallback）
            model_name: 模型名称（兼容旧代码，用于fallback）
        """
        # 如果提供了llm_config，优先使用
        if llm_config:
            self.llm_config = llm_config
            self.provider = llm_config.provider.lower()
            self.model_name = llm_config.model_name
            self.api_key = llm_config.api_key
            self.base_url = llm_config.base_url
            self.service_type = self._map_provider_to_service_type(self.provider)
        else:
            # Fallback到旧的参数模式
            self.llm_config = None
            self.service_type = service_type or settings.VECTOR_SERVICE_TYPE
            
            # 根据服务类型选择正确的模型名称
            if model_name:
                self.model_name = model_name
            elif self.service_type == "ollama":
                self.model_name = settings.OLLAMA_EMBEDDING_MODEL
            elif self.service_type == "aliyun":
                self.model_name = settings.DASHSCOPE_EMBEDDING_MODEL
            else:
                self.model_name = settings.EMBEDDING_MODEL
            
            self.provider = self.service_type
            self.api_key = None
            self.base_url = None
        
        self.model = None
        self.client = None  # For AsyncOpenAI
        self.dimension = None
        self._initialized = False
        self._cache = {} if settings.VECTOR_CACHE_ENABLED else None
        self._cache_timestamps = {} if settings.VECTOR_CACHE_ENABLED else None

        # 性能配置
        self.batch_size = settings.VECTOR_BATCH_SIZE
        self.max_retries = settings.VECTOR_MAX_RETRIES
        self.retry_delay = settings.VECTOR_RETRY_DELAY

    def _map_provider_to_service_type(self, provider: str) -> str:
        """
        将provider映射到service_type（用于兼容旧代码）
        使用 model_registry 动态判断，消除硬编码
        """
        provider_lower = provider.lower()
        
        # Ollama 特殊处理（使用 LangChain 的 OllamaEmbeddings）
        if provider_lower == "ollama":
            return "ollama"
        
        # 使用 model_registry 判断是否为 OpenAI 兼容
        if is_openai_compatible(provider_lower):
            return "openai_compatible"  # 使用 AsyncOpenAI 客户端
        
        # 默认使用 OpenAI 兼容方式
        return "openai_compatible"

    async def initialize(self):
        """初始化模型"""
        if not self._initialized:
            try:
                if self.llm_config:
                    # 使用数据库配置初始化（推荐方式）
                    await self._initialize_from_config()
                elif self.service_type == "ollama":
                    # Fallback: 使用环境变量配置的 Ollama
                    await self._initialize_ollama()
                elif self.service_type in ["aliyun", "openai_compatible"]:
                    # Fallback: 使用环境变量配置的 OpenAI 兼容服务
                    await self._initialize_aliyun()
                else:
                    # 未知类型，尝试 OpenAI 兼容方式
                    logger.warning(f"Unknown service_type '{self.service_type}', attempting OpenAI-compatible mode")
                    await self._initialize_aliyun()

                self._initialized = True
                logger.info(f"Vector service initialized successfully with provider={self.provider}, model={self.model_name}")

            except Exception as e:
                logger.error(f"Failed to initialize vector service: {str(e)}")
                raise

    async def _initialize_from_config(self):
        """
        从LLMConfiguration初始化模型
        使用 model_registry 动态判断 Provider 类型，消除硬编码
        """
        if not self.llm_config:
            raise ValueError("llm_config is required for _initialize_from_config")
        
        provider = self.llm_config.provider.lower()
        logger.info(f"Initializing embedding model from config: provider={provider}, model={self.model_name}")
        
        # 使用 model_registry 判断 Provider 类型
        if is_openai_compatible(provider):
            # OpenAI 兼容的提供商（使用 AsyncOpenAI 客户端）
            api_key = self.llm_config.api_key
            base_url = self.llm_config.base_url
            
            # 如果没有提供 base_url，尝试从注册表获取默认值
            if not base_url:
                provider_config = get_provider_config(provider)
                if provider_config and provider_config.default_base_url:
                    base_url = provider_config.default_base_url
            
            if not api_key:
                raise ValueError(f"API key is required for provider '{provider}'")
            
            # 使用 AsyncOpenAI 客户端
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            
            # 测试连接并获取维度
            try:
                response = await self.client.embeddings.create(
                    model=self.model_name,
                    input="test"
                )
                self.dimension = len(response.data[0].embedding)
                logger.info(f"Embedding model loaded: provider={provider}, dimension={self.dimension}")
            except Exception as e:
                logger.error(f"Failed to connect to {provider}: {e}")
                raise
        
        # Ollama 特殊处理（使用 LangChain 的 OllamaEmbeddings）
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            
            base_url = self.llm_config.base_url or settings.OLLAMA_BASE_URL
            
            self.model = OllamaEmbeddings(
                model=self.model_name,
                base_url=base_url,
                temperature=settings.OLLAMA_TEMPERATURE,
            )
            
            # 测试连接并获取维度
            test_text = "test"
            test_embedding = await self._embed_with_retry(test_text)
            self.dimension = len(test_embedding)
            
            logger.info(f"Ollama model loaded: model={self.model_name}, dimension={self.dimension}")
        
        else:
            # 未知 Provider，尝试 OpenAI 兼容方式
            logger.warning(f"Unknown provider '{provider}', attempting OpenAI-compatible mode")
            api_key = self.llm_config.api_key
            base_url = self.llm_config.base_url
            
            if not api_key:
                raise ValueError(f"API key is required for provider '{provider}'")
            
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model_name,
                    input="test"
                )
                self.dimension = len(response.data[0].embedding)
                logger.info(f"Embedding model loaded (OpenAI-compatible): provider={provider}, dimension={self.dimension}")
            except Exception as e:
                logger.error(f"Failed to connect to {provider}: {e}")
                raise

    async def _initialize_aliyun(self):
        """初始化阿里云DashScope嵌入模型（Fallback到环境变量）"""
        logger.info(f"Initializing Aliyun DashScope embedding model: {self.model_name}")
        
        api_key = settings.DASHSCOPE_API_KEY
        base_url = settings.DASHSCOPE_BASE_URL
        
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set in environment variables")
            
        # 使用 AsyncOpenAI 客户端
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        # 测试连接并获取维度
        try:
            response = await self.client.embeddings.create(
                model=self.model_name,
                input="test"
            )
            self.dimension = len(response.data[0].embedding)
            logger.info(f"Aliyun DashScope model loaded, dimension: {self.dimension}")
        except Exception as e:
            logger.error(f"Failed to connect to Aliyun DashScope: {e}")
            raise

    async def _initialize_ollama(self):
        """初始化Ollama嵌入模型（Fallback到环境变量）"""
        from langchain_ollama import OllamaEmbeddings

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
            embedding = await self._embed_with_retry(processed_question)

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
                # 批量处理
                embeddings = await self._batch_embed_ollama(processed_questions)

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
                # 如果使用client（OpenAI兼容的API）
                if self.client:
                    response = await self.client.embeddings.create(
                        model=self.model_name,
                        input=text
                    )
                    return response.data[0].embedding
                
                # 如果使用model（Ollama）
                elif self.model:
                    embedding = await self.model.aembed_query(text)
                    return embedding
                
                else:
                    raise ValueError("Neither client nor model is initialized")

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                logger.warning(f"Embedding attempt {attempt + 1} failed: {str(e)}, retrying...")
                await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 指数退避

    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """带重试的批量文本嵌入"""
        for attempt in range(self.max_retries):
            try:
                # 如果使用client（OpenAI兼容的API），批量调用
                if self.client:
                    response = await self.client.embeddings.create(
                        model=self.model_name,
                        input=texts
                    )
                    return [item.embedding for item in response.data]
                
                # 如果使用model（Ollama）
                elif self.model:
                    embeddings = await self.model.aembed_documents(texts)
                    return embeddings
                
                else:
                    raise ValueError("Neither client nor model is initialized")

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

        # 对于Ollama和OpenAI兼容的API，保留大小写
        # 一般来说，保留大小写可能包含更多语义信息

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
