import os
import logging
from typing import Optional
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.llm_config import LLMConfiguration

logger = logging.getLogger(__name__)

def get_active_llm_config(model_type: str = "chat") -> Optional[LLMConfiguration]:
    """
    Fetch the active LLM configuration from the database.
    按 ID 降序返回第一个活跃配置（最新创建的）
    """
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
            
        return config
    except Exception as e:
        logger.error(f"Error fetching LLM config from DB: {e}")
        return None
    finally:
        db.close()

def get_default_model(config_override: Optional[LLMConfiguration] = None, caller: str = None):
    """
    Get LLM model instance.
    
    Args:
        config_override: 指定的 LLM 配置
        caller: 调用者标识，用于日志追踪
    
    Returns:
        BaseChatModel实例
    
    Raises:
        Exception: 当模型初始化失败时
    """
    try:
        # Try to get from DB if no override
        config = config_override or get_active_llm_config(model_type="chat")

        if config:
            api_key = config.api_key
            api_base = config.base_url
            model_name = config.model_name
            provider = config.provider.lower()
            
            # 打印详细的模型初始化日志
            print(f"\n📡 LLM 模型初始化")
            print(f"   提供商: {config.provider}")
            print(f"   模型: {model_name}")
            print(f"   API Base: {api_base or '默认'}")
            if caller:
                print(f"   调用者: {caller}")
            
            logger.info(
                f"Initializing LLM model: provider={provider}, "
                f"model={model_name}, base_url={api_base or 'default'}, "
                f"caller={caller or 'unknown'}"
            )
        else:
            # Fallback to settings
            api_key = settings.OPENAI_API_KEY
            api_base = settings.OPENAI_API_BASE
            model_name = settings.LLM_MODEL
            provider = settings.LLM_PROVIDER.lower()
            
            print(f"\n📡 LLM 模型初始化 (环境变量配置)")
            print(f"   提供商: {provider}")
            print(f"   模型: {model_name}")
            print(f"   API Base: {api_base or '默认'}")
            if caller:
                print(f"   调用者: {caller}")
            
            logger.info(
                f"Initializing LLM model from env: provider={provider}, "
                f"model={model_name}, caller={caller or 'unknown'}"
            )

        # Common parameters
        max_tokens = 8192
        temperature = 0.2

        if provider == "openai" or provider == "aliyun" or provider == "volcengine": 
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30.0,
                max_retries=3
            )
        elif provider == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key
            if api_base:
                os.environ["DEEPSEEK_API_BASE"] = api_base
            
            return ChatDeepSeek(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
                api_base=api_base,
                timeout=30.0,
                max_retries=3
            )
        else:
            # Default fallback to ChatOpenAI
            logger.warning(f"Unknown provider '{provider}', falling back to ChatOpenAI")
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30.0,
                max_retries=3
            )
    except Exception as e:
        logger.error(
            f"Failed to initialize LLM model: {e}, "
            f"provider={provider if 'provider' in locals() else 'unknown'}, "
            f"model={model_name if 'model_name' in locals() else 'unknown'}",
            exc_info=True
        )
        raise

def get_default_embedding_model():
    """
    Get Embedding model instance.
    """
    config = get_active_llm_config(model_type="embedding")
    
    if config:
        api_key = config.api_key
        api_base = config.base_url
        model_name = config.model_name
        provider = config.provider.lower()
        
        print(f"\n📡 Embedding 模型初始化")
        print(f"   提供商: {config.provider}")
        print(f"   模型: {model_name}")
        print(f"   API Base: {api_base or '默认'}")
    else:
        # Fallback based on VECTOR_SERVICE_TYPE
        if settings.VECTOR_SERVICE_TYPE == "aliyun":
             api_key = settings.DASHSCOPE_API_KEY
             api_base = settings.DASHSCOPE_BASE_URL
             model_name = settings.DASHSCOPE_EMBEDDING_MODEL
        else:
             api_key = settings.OPENAI_API_KEY
             api_base = settings.OPENAI_API_BASE
             model_name = "text-embedding-3-small" # Default fallback
        
        print(f"\n📡 Embedding 模型初始化 (环境变量配置)")
        print(f"   模型: {model_name}")
        print(f"   API Base: {api_base or '默认'}")
        
    return OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=api_base
    )


def create_llm_from_config(config: LLMConfiguration):
    """
    根据LLMConfiguration创建LLM实例。
    这是get_default_model的简化版本，专门用于从配置创建模型。
    
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
        
        # Common parameters
        max_tokens = 8192
        temperature = 0.2
        
        if provider == "openai" or provider == "aliyun" or provider == "volcengine":
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30.0,
                max_retries=3
            )
        elif provider == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key
            if api_base:
                os.environ["DEEPSEEK_API_BASE"] = api_base
            
            return ChatDeepSeek(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
                api_base=api_base,
                timeout=30.0,
                max_retries=3
            )
        else:
            logger.warning(f"Unknown provider '{provider}', falling back to ChatOpenAI")
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30.0,
                max_retries=3
            )
    except Exception as e:
        logger.error(
            f"Failed to create LLM from config (id={config.id}): {e}",
            exc_info=True
        )
        raise
