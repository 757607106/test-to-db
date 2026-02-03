"""
模型注册表 - 统一管理所有LLM Provider的配置和实例化

设计原则：
1. 消除硬编码：Provider类型通过注册表动态管理
2. OpenAI兼容优先：国内大部分模型支持OpenAI兼容API，统一使用ChatOpenAI
3. 可扩展性：新增Provider只需在注册表添加配置，无需修改核心逻辑
4. 向后兼容：保持现有API不变，仅替换内部实现

支持的模型类型：
- OpenAI兼容层：OpenAI, DeepSeek, 通义千问(Aliyun), 火山引擎, Moonshot, 智谱, 百川等
- 专用SDK：百度千帆(需要AK/SK), Google Gemini
"""
import os
import logging
from typing import Dict, Any, Optional, List, Type, Callable
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


# ============================================================================
# Provider 类型枚举
# ============================================================================

class ProviderType(str, Enum):
    """Provider 接入类型"""
    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI 兼容 API
    NATIVE_SDK = "native_sdk"  # 需要专用 SDK


# ============================================================================
# Provider 配置数据类
# ============================================================================

@dataclass
class ProviderConfig:
    """Provider 配置"""
    name: str  # Provider 名称（小写）
    display_name: str  # 显示名称
    provider_type: ProviderType  # 接入类型
    
    # Chat 模型配置
    chat_module: str = ""  # 模块路径，如 "langchain_openai"
    chat_class: str = ""  # 类名，如 "ChatOpenAI"
    
    # Embedding 模型配置
    embedding_module: str = ""
    embedding_class: str = ""
    
    # 是否支持 base_url 参数
    supports_base_url: bool = True
    
    # 默认 base_url（如果有）
    default_base_url: Optional[str] = None
    
    # 额外必需的环境变量
    required_env_vars: List[str] = field(default_factory=list)
    
    # 额外必需的配置参数（用于数据库扩展配置）
    extra_config_keys: List[str] = field(default_factory=list)
    
    # 参数映射（将统一参数映射到Provider特定参数）
    param_mapping: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# 模型注册表
# ============================================================================

# Provider 注册表：定义所有支持的 Provider
MODEL_PROVIDER_REGISTRY: Dict[str, ProviderConfig] = {}


def register_provider(config: ProviderConfig) -> None:
    """注册一个 Provider 配置"""
    MODEL_PROVIDER_REGISTRY[config.name.lower()] = config
    logger.debug(f"Registered provider: {config.name}")


def get_provider_config(provider_name: str) -> Optional[ProviderConfig]:
    """获取 Provider 配置"""
    return MODEL_PROVIDER_REGISTRY.get(provider_name.lower())


def get_all_providers() -> List[ProviderConfig]:
    """获取所有注册的 Provider"""
    return list(MODEL_PROVIDER_REGISTRY.values())


def get_chat_providers() -> List[ProviderConfig]:
    """获取支持 Chat 模型的 Provider"""
    return [p for p in MODEL_PROVIDER_REGISTRY.values() if p.chat_class]


def get_embedding_providers() -> List[ProviderConfig]:
    """获取支持 Embedding 模型的 Provider"""
    return [p for p in MODEL_PROVIDER_REGISTRY.values() if p.embedding_class]


def is_openai_compatible(provider_name: str) -> bool:
    """判断 Provider 是否为 OpenAI 兼容类型"""
    config = get_provider_config(provider_name)
    return config is not None and config.provider_type == ProviderType.OPENAI_COMPATIBLE


# ============================================================================
# 注册默认 Provider
# ============================================================================

def _register_default_providers():
    """注册默认支持的 Provider"""
    
    # === OpenAI 兼容层 Provider ===
    
    # OpenAI 原生
    register_provider(ProviderConfig(
        name="openai",
        display_name="OpenAI",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.openai.com/v1",
    ))
    
    # DeepSeek（支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="deepseek",
        display_name="DeepSeek",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.deepseek.com/v1",
    ))
    
    # 阿里云通义千问（支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="aliyun",
        display_name="阿里云通义千问",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ))
    
    # 火山引擎（字节跳动，支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="volcengine",
        display_name="火山引擎",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
    ))
    
    # Moonshot（月之暗面，支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="moonshot",
        display_name="Moonshot (月之暗面)",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.moonshot.cn/v1",
    ))
    
    # 智谱AI（支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="zhipu",
        display_name="智谱AI",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
    ))
    
    # 百川（支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="baichuan",
        display_name="百川",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.baichuan-ai.com/v1",
    ))
    
    # MiniMax（支持 OpenAI 兼容 API）
    register_provider(ProviderConfig(
        name="minimax",
        display_name="MiniMax",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.minimax.chat/v1",
    ))
    
    # Azure OpenAI
    register_provider(ProviderConfig(
        name="azure",
        display_name="Azure OpenAI",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
    ))
    
    # Ollama（本地部署，使用 SERVICE_HOST 作为默认主机）
    ollama_base_url = os.getenv("OLLAMA_BASE_URL") or f"http://{os.getenv('SERVICE_HOST', 'localhost')}:11434/v1"
    register_provider(ProviderConfig(
        name="ollama",
        display_name="Ollama (本地)",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_ollama",
        embedding_class="OllamaEmbeddings",
        supports_base_url=True,
        default_base_url=ollama_base_url,
    ))
    
    # OpenRouter（聚合平台）
    register_provider(ProviderConfig(
        name="openrouter",
        display_name="OpenRouter",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://openrouter.ai/api/v1",
    ))
    
    # SiliconFlow（硅基流动）
    register_provider(ProviderConfig(
        name="siliconflow",
        display_name="SiliconFlow (硅基流动)",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        chat_module="langchain_openai",
        chat_class="ChatOpenAI",
        embedding_module="langchain_openai",
        embedding_class="OpenAIEmbeddings",
        supports_base_url=True,
        default_base_url="https://api.siliconflow.cn/v1",
    ))
    
    # === 需要专用 SDK 的 Provider ===
    
    # 百度千帆（需要 AK/SK 认证）
    register_provider(ProviderConfig(
        name="baidu",
        display_name="百度千帆",
        provider_type=ProviderType.NATIVE_SDK,
        chat_module="langchain_community.chat_models",
        chat_class="QianfanChatEndpoint",
        embedding_module="langchain_community.embeddings",
        embedding_class="QianfanEmbeddingsEndpoint",
        supports_base_url=False,
        required_env_vars=["QIANFAN_AK", "QIANFAN_SK"],
        extra_config_keys=["qianfan_ak", "qianfan_sk"],
    ))
    
    # Google Gemini
    register_provider(ProviderConfig(
        name="google",
        display_name="Google Gemini",
        provider_type=ProviderType.NATIVE_SDK,
        chat_module="langchain_google_genai",
        chat_class="ChatGoogleGenerativeAI",
        embedding_module="langchain_google_genai",
        embedding_class="GoogleGenerativeAIEmbeddings",
        supports_base_url=False,
        param_mapping={"api_key": "google_api_key"},
    ))
    
    logger.info(f"Registered {len(MODEL_PROVIDER_REGISTRY)} providers")


# ============================================================================
# 模型工厂函数
# ============================================================================

def _import_class(module_path: str, class_name: str) -> Type:
    """动态导入类"""
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _normalize_openai_compatible_base_url(base_url: str) -> str:
    s = (base_url or "").strip()
    if not s:
        return s
    s = s.rstrip("/")
    lowered = s.lower()
    if lowered.endswith("/chat/completions"):
        s = s[: -len("/chat/completions")].rstrip("/")
    elif lowered.endswith("/embeddings"):
        s = s[: -len("/embeddings")].rstrip("/")
    return s


def create_chat_model(
    provider: str,
    model_name: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    timeout: float = 30.0,
    max_retries: int = 3,
    extra_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> BaseChatModel:
    """
    创建 Chat 模型实例
    
    Args:
        provider: Provider 名称（如 openai, deepseek, aliyun 等）
        model_name: 模型名称（如 gpt-4o, deepseek-chat 等）
        api_key: API 密钥
        base_url: API 基础 URL（可选，OpenAI 兼容类型需要）
        temperature: 温度参数
        max_tokens: 最大 token 数
        timeout: 请求超时时间
        max_retries: 最大重试次数
        extra_config: 额外配置（用于特殊 Provider，如百度的 ak/sk）
        **kwargs: 其他参数
        
    Returns:
        BaseChatModel 实例
        
    Raises:
        ValueError: Provider 不支持或配置错误
        ImportError: 缺少依赖包
    """
    provider_lower = provider.lower()
    config = get_provider_config(provider_lower)
    
    if not config:
        # 未知 Provider，尝试使用 OpenAI 兼容方式
        logger.warning(f"Unknown provider '{provider}', attempting OpenAI-compatible mode")
        config = get_provider_config("openai")
    
    if not config or not config.chat_class:
        raise ValueError(f"Provider '{provider}' does not support chat models")
    
    try:
        # 动态导入模型类
        model_class = _import_class(config.chat_module, config.chat_class)
        
        # 构建参数
        params: Dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        
        # 处理 API Key
        if api_key:
            # 检查是否需要参数映射
            key_param = config.param_mapping.get("api_key", "api_key")
            params[key_param] = api_key
        
        # 处理 base_url（仅 OpenAI 兼容类型）
        if config.supports_base_url:
            effective_base_url = base_url or config.default_base_url
            if effective_base_url:
                params["base_url"] = _normalize_openai_compatible_base_url(effective_base_url)
        
        # 处理额外配置（如百度的 ak/sk）
        if extra_config and config.extra_config_keys:
            for key in config.extra_config_keys:
                if key in extra_config:
                    params[key] = extra_config[key]
        
        # 合并额外参数
        params.update(kwargs)
        
        logger.info(f"Creating chat model: provider={provider}, model={model_name}")
        return model_class(**params)
        
    except ImportError as e:
        logger.error(f"Failed to import {config.chat_module}.{config.chat_class}: {e}")
        raise ImportError(
            f"Provider '{provider}' requires package '{config.chat_module}'. "
            f"Please install it with: pip install {config.chat_module.split('.')[0]}"
        )
    except Exception as e:
        logger.error(f"Failed to create chat model for provider '{provider}': {e}")
        raise


def create_embedding_model(
    provider: str,
    model_name: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    extra_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Embeddings:
    """
    创建 Embedding 模型实例
    
    Args:
        provider: Provider 名称
        model_name: 模型名称
        api_key: API 密钥
        base_url: API 基础 URL
        extra_config: 额外配置
        **kwargs: 其他参数
        
    Returns:
        Embeddings 实例
    """
    provider_lower = provider.lower()
    config = get_provider_config(provider_lower)
    
    if not config:
        logger.warning(f"Unknown provider '{provider}', attempting OpenAI-compatible mode")
        config = get_provider_config("openai")
    
    if not config or not config.embedding_class:
        raise ValueError(f"Provider '{provider}' does not support embedding models")
    
    try:
        model_class = _import_class(config.embedding_module, config.embedding_class)
        
        params: Dict[str, Any] = {"model": model_name}
        
        # 处理 API Key
        if api_key:
            key_param = config.param_mapping.get("api_key", "api_key")
            params[key_param] = api_key
        
        # 处理 base_url
        if config.supports_base_url:
            effective_base_url = base_url or config.default_base_url
            if effective_base_url:
                params["base_url"] = _normalize_openai_compatible_base_url(effective_base_url)
        
        # Ollama Embedding 特殊处理
        if provider_lower == "ollama" and config.embedding_class == "OllamaEmbeddings":
            # OllamaEmbeddings 不使用 api_key
            params.pop("api_key", None)
        
        # 处理额外配置
        if extra_config and config.extra_config_keys:
            for key in config.extra_config_keys:
                if key in extra_config:
                    params[key] = extra_config[key]
        
        params.update(kwargs)
        
        logger.info(f"Creating embedding model: provider={provider}, model={model_name}")
        return model_class(**params)
        
    except ImportError as e:
        logger.error(f"Failed to import {config.embedding_module}.{config.embedding_class}: {e}")
        raise ImportError(
            f"Provider '{provider}' requires package '{config.embedding_module}'. "
            f"Please install it with: pip install {config.embedding_module.split('.')[0]}"
        )
    except Exception as e:
        logger.error(f"Failed to create embedding model for provider '{provider}': {e}")
        raise


# ============================================================================
# 辅助函数
# ============================================================================

def get_provider_list_for_frontend() -> List[Dict[str, Any]]:
    """
    获取供前端使用的 Provider 列表
    
    Returns:
        Provider 信息列表，包含 value, label, defaultBaseUrl 等
    """
    result = []
    for config in get_all_providers():
        result.append({
            "value": config.name,
            "label": config.display_name,
            "defaultBaseUrl": config.default_base_url,
            "supportsBaseUrl": config.supports_base_url,
            "supportsChat": bool(config.chat_class),
            "supportsEmbedding": bool(config.embedding_class),
            "providerType": config.provider_type.value,
            "extraConfigKeys": config.extra_config_keys,
        })
    return result


def validate_provider_config(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    extra_config: Optional[Dict[str, Any]] = None
) -> tuple[bool, str]:
    """
    验证 Provider 配置是否完整
    
    Returns:
        (is_valid, error_message)
    """
    config = get_provider_config(provider)
    
    if not config:
        return True, ""  # 未知 Provider 允许尝试
    
    # 检查必需的环境变量
    missing_env = []
    for env_var in config.required_env_vars:
        if not os.getenv(env_var):
            # 检查是否在 extra_config 中提供
            key = env_var.lower()
            if not extra_config or key not in extra_config:
                missing_env.append(env_var)
    
    if missing_env:
        return False, f"Missing required configuration: {', '.join(missing_env)}"
    
    # OpenAI 兼容类型需要 API Key
    if config.provider_type == ProviderType.OPENAI_COMPATIBLE and not api_key:
        return False, "API Key is required"
    
    return True, ""


# ============================================================================
# 初始化
# ============================================================================

# 模块加载时自动注册默认 Provider
_register_default_providers()
