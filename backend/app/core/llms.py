import os
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from app.core.config import settings


def get_default_model():
    """
    获取默认的 LLM 模型实例
    根据配置选择 ChatOpenAI (兼容模式) 或 ChatDeepSeek (专用模式)
    """
    api_key = settings.OPENAI_API_KEY
    api_base = settings.OPENAI_API_BASE
    model_name = settings.LLM_MODEL
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        # 使用 OpenAI 兼容接口 (如 DashScope/Qwen, SiliconFlow 等)
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=api_base,
            max_tokens=8192,
            temperature=0.2
        )
    else:
        # 默认使用 DeepSeek 专用接口
        # 设置环境变量供 langchain_deepseek 使用
        os.environ["DEEPSEEK_API_KEY"] = api_key
        if api_base:
            os.environ["DEEPSEEK_API_BASE"] = api_base
        
        return ChatDeepSeek(
            model=model_name,
            max_tokens=8192,
            temperature=0.2,
            api_key=api_key
        )
