"""
向量服务工厂类
"""

import logging
from typing import Dict

from app.models.llm_config import LLMConfiguration
from app.core.llms import get_default_embedding_config
from .service import VectorService

logger = logging.getLogger(__name__)


class VectorServiceFactory:
    """向量服务工厂类 - 使用用户在模型配置页面设置的嵌入模型"""

    _instances: Dict[str, VectorService] = {}

    @classmethod
    async def create_service_from_config(cls, llm_config: LLMConfiguration) -> VectorService:
        """从数据库LLM配置创建向量服务实例"""
        instance_key = f"config:{llm_config.id}:{llm_config.model_name}"
        
        if instance_key not in cls._instances:
            service = VectorService(llm_config=llm_config)
            await service.initialize()
            cls._instances[instance_key] = service
            logger.info(f"Created vector service from DB config: id={llm_config.id}, model={llm_config.model_name}")
        
        return cls._instances[instance_key]

    @classmethod
    async def get_default_service(cls) -> VectorService:
        """
        获取默认向量服务（使用用户在模型配置页面设置的嵌入模型）
        """
        # 从数据库获取用户配置的默认嵌入模型
        default_config = get_default_embedding_config()
        
        if not default_config:
            raise ValueError(
                "未配置默认嵌入模型。请在管理后台的「模型配置」页面中添加一个嵌入(Embedding)模型，"
                "并将其设置为默认模型。"
            )
        
        logger.info(f"Using database embedding config: id={default_config.id}, model={default_config.model_name}")
        return await cls.create_service_from_config(default_config)

    @classmethod
    def clear_instances(cls):
        """清理所有实例"""
        for service in cls._instances.values():
            if hasattr(service, 'clear_cache'):
                service.clear_cache()
        cls._instances.clear()
        logger.info("Cleared all vector service instances")
