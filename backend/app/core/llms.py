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
    """
    db: Session = SessionLocal()
    try:
        config = db.query(LLMConfiguration).filter(
            LLMConfiguration.is_active == True,
            LLMConfiguration.model_type == model_type
        ).order_by(LLMConfiguration.updated_at.desc()).first()
        # If specific type not found, try any active one (fallback logic could be better)
        if not config and model_type == "chat":
             config = db.query(LLMConfiguration).filter(LLMConfiguration.is_active == True).order_by(LLMConfiguration.updated_at.desc()).first()
        
        if config:
            logger.info(f"Found active LLM config in DB: provider={config.provider}, model={config.model_name}, base_url={config.base_url}")
        else:
            logger.info(f"No active LLM config found in DB for type {model_type}")
            
        return config
    except Exception as e:
        logger.error(f"Error fetching LLM config from DB: {e}")
        return None
    finally:
        db.close()

def get_default_model(config_override: Optional[LLMConfiguration] = None):
    """
    Get LLM model instance.
    """
    # Try to get from DB if no override
    config = config_override or get_active_llm_config(model_type="chat")

    if config:
        logger.info(f"Using DB config for LLM: provider={config.provider}, model={config.model_name}")
        api_key = config.api_key
        api_base = config.base_url
        model_name = config.model_name
        provider = config.provider.lower()
    else:
        logger.info(f"Using env config for LLM: provider={settings.LLM_PROVIDER}, model={settings.LLM_MODEL}")
        # Fallback to settings
        api_key = settings.OPENAI_API_KEY
        api_base = settings.OPENAI_API_BASE
        model_name = settings.LLM_MODEL
        provider = settings.LLM_PROVIDER.lower()

    # Common parameters
    max_tokens = 8192
    temperature = 0.2
    
    logger.info(f"Initializing LLM with: provider={provider}, model={model_name}, base_url={api_base}")

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
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=30.0,
            max_retries=3
        )

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
        
    return OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=api_base
    )
