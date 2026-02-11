"""
LLM 模型管理模块

提供统一的 LLM 模型获取接口，支持：
- 数据库配置的模型
- 环境变量配置的模型
- 实例缓存优化
- LLM 包装器（重试、超时、监控）

重构说明 (2026-01-25):
- 移除硬编码的 Provider 判断逻辑
- 使用 model_registry 工厂函数动态创建模型
- 支持所有 OpenAI 兼容的国内外模型

重构说明 (2026-01-28):
- 集成 LLM 包装器，提供统一的重试和超时控制
- 支持 LangSmith 追踪
"""
import time
import logging
from typing import Optional, Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_registry import (
    create_chat_model,
    create_embedding_model,
    get_provider_config,
)
from app.core.llm_wrapper import (
    LLMWrapper,
    LLMWrapperConfig,
    get_llm_wrapper,
    reset_llm_wrapper,
)
from app.db.session import SessionLocal
from app.models.llm_config import LLMConfiguration
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


# ============================================================================
# LLM实例缓存（性能优化）
# ============================================================================

# 缓存配置
LLM_CACHE_TTL = 300  # 缓存有效期：5分钟
LLM_CONFIG_CACHE_TTL = 60  # 配置缓存有效期：1分钟

# LLM实例缓存
_llm_cache: Dict[str, Any] = {}
_llm_cache_timestamps: Dict[str, float] = {}

# LLM配置缓存（减少数据库查询）
_config_cache: Dict[str, Optional[LLMConfiguration]] = {}
_config_cache_timestamps: Dict[str, float] = {}


def _generate_llm_cache_key(config: Optional[LLMConfiguration]) -> str:
    """
    生成LLM实例的缓存键
    
    Args:
        config: LLM配置对象
        
    Returns:
        唯一的缓存键字符串
    """
    if config:
        return f"llm:{config.id}:{config.provider}:{config.model_name}"
    else:
        # 使用环境变量配置
        return f"llm:env:{settings.LLM_PROVIDER}:{settings.LLM_MODEL}"


def _is_llm_cache_valid(cache_key: str) -> bool:
    """
    检查LLM缓存是否有效
    
    Args:
        cache_key: 缓存键
        
    Returns:
        缓存是否有效
    """
    if cache_key not in _llm_cache:
        return False
    
    cache_time = _llm_cache_timestamps.get(cache_key, 0)
    cache_age = time.time() - cache_time
    
    return cache_age < LLM_CACHE_TTL


def _is_config_cache_valid(cache_key: str) -> bool:
    """
    检查配置缓存是否有效
    
    Args:
        cache_key: 缓存键
        
    Returns:
        缓存是否有效
    """
    if cache_key not in _config_cache:
        return False
    
    cache_time = _config_cache_timestamps.get(cache_key, 0)
    cache_age = time.time() - cache_time
    
    return cache_age < LLM_CONFIG_CACHE_TTL


def clear_llm_cache():
    """
    清除LLM缓存（用于配置更新后强制刷新）
    """
    global _llm_cache, _llm_cache_timestamps, _config_cache, _config_cache_timestamps
    _llm_cache.clear()
    _llm_cache_timestamps.clear()
    _config_cache.clear()
    _config_cache_timestamps.clear()
    logger.info("LLM cache cleared")

def get_active_llm_config(model_type: str = "chat", use_cache: bool = True) -> Optional[LLMConfiguration]:
    """
    Fetch the active LLM configuration from the database.
    按 ID 降序返回第一个活跃配置（最新创建的）
    
    优化：支持配置缓存，减少数据库查询
    
    Args:
        model_type: 模型类型 ("chat" 或 "embedding")
        use_cache: 是否使用缓存（默认True）
        
    Returns:
        LLMConfiguration对象或None
    """
    cache_key = f"config:{model_type}"
    
    # 检查缓存
    if use_cache and _is_config_cache_valid(cache_key):
        cached_config = _config_cache.get(cache_key)
        if cached_config:
            logger.debug(f"Using cached LLM config: id={cached_config.id}")
        return cached_config
    
    db: Session = SessionLocal()
    try:
        config = db.query(LLMConfiguration).filter(
            LLMConfiguration.is_active == True,
            LLMConfiguration.model_type == model_type
        ).order_by(LLMConfiguration.id.desc()).first()  # 按 ID 降序，使用最新配置
        # If specific type not found, try any active one (fallback logic could be better)
        if not config and model_type == "chat":
             config = db.query(LLMConfiguration).filter(LLMConfiguration.is_active == True).order_by(LLMConfiguration.id.desc()).first()
        
        if config:
            logger.info(f"Found active LLM config in DB: provider={config.provider}, model={config.model_name}, base_url={config.base_url}, id={config.id}")
        else:
            logger.info(f"No active LLM config found in DB for type {model_type}")
        
        # 更新缓存
        _config_cache[cache_key] = config
        _config_cache_timestamps[cache_key] = time.time()
            
        return config
    except Exception as e:
        logger.error(f"Error fetching LLM config from DB: {e}")
        return None
    finally:
        db.close()

def get_default_model(config_override: Optional[LLMConfiguration] = None, caller: str = None, temperature: float = 0.2) -> BaseChatModel:
    """
    Get LLM model instance with caching support.
    
    优化：使用LLM实例缓存，避免重复创建实例和数据库查询
    
    Args:
        config_override: 指定的 LLM 配置
        caller: 调用者标识，用于日志追踪
        temperature: 温度参数，控制输出随机性（0.0-1.0），默认0.2
    
    Returns:
        BaseChatModel实例
    
    Raises:
        Exception: 当模型初始化失败时
    """
    provider = None
    model_name = None
    
    try:
        # Try to get from DB if no override
        config = config_override or get_active_llm_config(model_type="chat")
        
        # 生成缓存键并检查缓存（包含 temperature）
        cache_key = f"{_generate_llm_cache_key(config)}_t{temperature}"
        
        if _is_llm_cache_valid(cache_key):
            cached_llm = _llm_cache[cache_key]
            logger.debug(f"Using cached LLM instance: {cache_key}, caller={caller or 'unknown'}")
            return cached_llm

        if config:
            api_key = config.api_key
            api_base = config.base_url
            model_name = config.model_name
            provider = config.provider.lower()
            
            # 简化日志：只输出关键信息
            logger.info(f"Creating LLM: {provider}/{model_name}")
        else:
            # Fallback to settings
            api_key = settings.OPENAI_API_KEY
            api_base = settings.OPENAI_API_BASE
            model_name = settings.LLM_MODEL
            provider = settings.LLM_PROVIDER.lower()
            
            logger.info(f"Creating LLM from env: {provider}/{model_name}")

        # 使用工厂函数创建模型(消除硬编码)
        # 注意: max_retries=0, 重试由 LLMWrapper 统一处理
        # timeout=None 禁用超时限制，复杂任务执行时间无法预估
        llm = create_chat_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=temperature,
            max_tokens=8192,
            timeout=None,  # 禁用超时限制
            max_retries=0  # 重试由 LLMWrapper 统一处理
        )
        
        # 缓存LLM实例
        _llm_cache[cache_key] = llm
        _llm_cache_timestamps[cache_key] = time.time()
        logger.debug(f"LLM instance cached: {cache_key}")
        
        return llm
        
    except Exception as e:
        logger.error(
            f"Failed to initialize LLM model: {e}, "
            f"provider={provider or 'unknown'}, "
            f"model={model_name or 'unknown'}",
            exc_info=True
        )
        raise

def get_default_embedding_config() -> Optional[LLMConfiguration]:
    """
    Get the default embedding model configuration from system_config table.
    Returns the LLMConfiguration object if found, None otherwise.
    """
    db: Session = SessionLocal()
    try:
        # Get default embedding model ID from system_config
        system_config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "default_embedding_model_id"
        ).first()
        
        if not system_config or not system_config.config_value:
            return None
        
        try:
            config_id = int(system_config.config_value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid default_embedding_model_id value: {system_config.config_value}")
            return None
        
        # Get the LLM configuration
        config = db.query(LLMConfiguration).filter(
            LLMConfiguration.id == config_id,
            LLMConfiguration.is_active == True,
            LLMConfiguration.model_type == "embedding"
        ).first()
        
        if config:
            logger.info(f"Found default embedding config: id={config.id}, provider={config.provider}, model={config.model_name}")
        
        return config
    except Exception as e:
        logger.error(f"Error fetching default embedding config: {e}")
        return None
    finally:
        db.close()


def create_embedding_from_config(config: LLMConfiguration) -> Embeddings:
    """
    Create an embedding model instance from LLMConfiguration.
    使用 model_registry 工厂函数，支持所有注册的 Provider。
    
    Args:
        config: LLM configuration object with model_type="embedding"
    
    Returns:
        Embeddings instance
    
    Raises:
        ValueError: When configuration is invalid
        Exception: When model initialization fails
    """
    if not config:
        raise ValueError("Embedding configuration cannot be None")
    
    if config.model_type != "embedding":
        raise ValueError(f"Configuration model_type must be 'embedding', got '{config.model_type}'")
    
    if not config.is_active:
        raise ValueError(f"Embedding configuration (id={config.id}) is not active")
    
    try:
        provider = config.provider.lower()
        model_name = config.model_name
        api_key = config.api_key
        base_url = config.base_url
        
        logger.info(f"Creating embedding: {provider}/{model_name}")
        
        # 使用工厂函数创建 Embedding 模型（消除硬编码）
        return create_embedding_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url
        )
    
    except Exception as e:
        logger.error(f"Failed to create embedding model from config (id={config.id}): {e}", exc_info=True)
        raise


def get_default_embedding_model_v2():
    """
    Get Embedding model instance with database configuration support.
    Priority:
    1. Try to load from system_config (default_embedding_model_id)
    2. Fallback to get_default_embedding_model() (old logic with env vars)
    
    Returns:
        Embeddings instance
    """
    try:
        # Try to get default embedding config from database
        config = get_default_embedding_config()
        
        if config:
            return create_embedding_from_config(config)
        
        # Fallback to old logic
        logger.info("No default embedding config in database, falling back to environment variables")
        return get_default_embedding_model()
    
    except Exception as e:
        logger.error(f"Failed to get embedding model, falling back to environment config: {e}")
        return get_default_embedding_model()


def get_default_embedding_model() -> Embeddings:
    """
    Get Embedding model instance (Legacy function for backward compatibility).
    Uses environment variables for configuration.
    
    Returns:
        Embeddings instance
    """
    config = get_active_llm_config(model_type="embedding")
    
    if config:
        api_key = config.api_key
        api_base = config.base_url
        model_name = config.model_name
        provider = config.provider.lower()
        
        logger.info(f"Creating embedding: {provider}/{model_name}")
    else:
        # Fallback based on VECTOR_SERVICE_TYPE
        if settings.VECTOR_SERVICE_TYPE == "aliyun":
            api_key = settings.DASHSCOPE_API_KEY
            api_base = settings.DASHSCOPE_BASE_URL
            model_name = settings.DASHSCOPE_EMBEDDING_MODEL
            provider = "aliyun"
        else:
            api_key = settings.OPENAI_API_KEY
            api_base = settings.OPENAI_API_BASE
            model_name = "text-embedding-3-small"  # Default fallback
            provider = "openai"
        
        logger.info(f"Creating embedding from env: {model_name}")
    
    # 使用工厂函数创建 Embedding 模型（消除硬编码）
    return create_embedding_model(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        base_url=api_base
    )


def create_llm_from_config(config: LLMConfiguration) -> BaseChatModel:
    """
    根据LLMConfiguration创建LLM实例。
    使用 model_registry 工厂函数，支持所有注册的 Provider。
    
    Args:
        config: LLM配置对象
    
    Returns:
        BaseChatModel实例
    
    Raises:
        ValueError: 当配置无效时
        Exception: 当模型初始化失败时
    """
    if not config:
        raise ValueError("LLM configuration cannot be None")
    
    if not config.is_active:
        raise ValueError(f"LLM configuration (id={config.id}) is not active")
    
    try:
        api_key = config.api_key
        api_base = config.base_url
        model_name = config.model_name
        provider = config.provider.lower()
        
        logger.info(
            f"Creating LLM from config: id={config.id}, "
            f"provider={provider}, model={model_name}"
        )
        
        # 使用工厂函数创建模型(消除硬编码)
        # 注意: max_retries=0, 重试由 LLMWrapper 统一处理
        return create_chat_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=0.2,
            max_tokens=8192,
            timeout=30.0,
            max_retries=0  # 重试由 LLMWrapper 统一处理
        )
    except Exception as e:
        logger.error(
            f"Failed to create LLM from config (id={config.id}): {e}",
            exc_info=True
        )
        raise


# ============================================================================
# LLM 包装器集成
# ============================================================================

def get_wrapped_llm(
    config_override: Optional[LLMConfiguration] = None,
    caller: str = None,
    wrapper_config: Optional[LLMWrapperConfig] = None
) -> LLMWrapper:
    """
    获取带包装器的 LLM 实例
    
    包装器提供：
    - 统一的重试策略（指数退避）
    - 超时控制
    - 错误分类和处理
    - 性能监控
    - LangSmith 追踪集成
    
    Args:
        config_override: 指定的 LLM 配置
        caller: 调用者标识，用于日志追踪
        wrapper_config: 包装器配置（可选）
    
    Returns:
        LLMWrapper 实例
    
    使用示例:
        wrapper = get_wrapped_llm(caller="sql_generator")
        response = await wrapper.ainvoke(messages, trace_id="req-123")
    """
    # 获取底层 LLM
    llm = get_default_model(config_override=config_override, caller=caller)
    
    # 创建包装器配置
    if wrapper_config is None:
        wrapper_config = LLMWrapperConfig(
            max_retries=3,
            retry_base_delay=1.0,
            timeout=60.0,
            enable_tracing=settings.LANGCHAIN_TRACING_V2,
        )
    
    # 创建并返回包装器
    return LLMWrapper(
        llm=llm,
        config=wrapper_config,
        name=caller or "default"
    )


def get_global_llm_wrapper() -> LLMWrapper:
    """
    获取全局 LLM 包装器实例
    
    适用于不需要特定配置的场景，使用全局共享的包装器实例。
    
    Returns:
        全局 LLMWrapper 实例
    """
    return get_llm_wrapper()


def get_llm_metrics() -> Dict[str, Any]:
    """
    获取全局 LLM 调用指标
    
    Returns:
        包含调用统计的字典
    """
    wrapper = get_llm_wrapper()
    return wrapper.get_metrics()


def clear_all_llm_caches():
    """
    清除所有 LLM 相关缓存
    
    包括：
    - LLM 实例缓存
    - 配置缓存
    - 全局包装器
    """
    clear_llm_cache()
    reset_llm_wrapper()
    logger.info("All LLM caches cleared")
