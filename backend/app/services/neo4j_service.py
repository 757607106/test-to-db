"""
Neo4j 公共服务 (Neo4j Service)

统一管理 Neo4j 驱动连接，消除各服务中的重复代码。

使用方式：
    from app.services.neo4j_service import neo4j_service
    
    driver = neo4j_service.get_driver()
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN n LIMIT 10")
"""
from typing import Optional
import logging

from neo4j import GraphDatabase, Driver

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jService:
    """
    Neo4j 公共服务
    
    提供：
    - 统一的驱动管理
    - 连接复用
    - 优雅的关闭
    """
    
    _driver: Optional[Driver] = None
    _initialized: bool = False
    
    @classmethod
    def get_driver(cls) -> Optional[Driver]:
        """
        获取 Neo4j 驱动（单例模式）
        
        Returns:
            Neo4j Driver 实例，连接失败返回 None
        """
        if cls._driver is None:
            try:
                cls._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                logger.info("Neo4j driver initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to connect to Neo4j: {e}")
                return None
        return cls._driver
    
    @classmethod
    def is_available(cls) -> bool:
        """检查 Neo4j 是否可用"""
        driver = cls.get_driver()
        if not driver:
            return False
        try:
            with driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False
    
    @classmethod
    def close(cls):
        """关闭 Neo4j 连接"""
        if cls._driver:
            try:
                cls._driver.close()
                logger.info("Neo4j driver closed")
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")
            finally:
                cls._driver = None
    
    @classmethod
    async def initialize(cls):
        """初始化服务（异步兼容）"""
        if cls._initialized:
            return
        
        driver = cls.get_driver()
        if driver:
            cls._initialized = True
            logger.info("Neo4j service initialized")


# 创建全局实例
neo4j_service = Neo4jService()
