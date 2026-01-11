import os
from langchain_deepseek import ChatDeepSeek
from app.core.config import settings


def get_default_model():
    """
    获取默认的 LLM 模型实例
    从 settings 对象读取 API key 和配置，确保使用 .env 文件中的最新配置
    """
    # 从 settings 读取 API key，而不是直接从环境变量读取
    api_key = settings.OPENAI_API_KEY
    api_base = settings.OPENAI_API_BASE
    model_name = settings.LLM_MODEL
    
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