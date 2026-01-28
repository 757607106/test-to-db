"""
LangGraph Checkpointer 模块 V2 (纯异步版本)

重构目标：
1. 统一使用异步模式，消除同步/异步混用问题
2. 使用应用生命周期管理连接池
3. 支持 LangSmith 追踪
4. 提供健康检查和监控

使用方式：
    # 在 FastAPI 应用启动时初始化
    from app.core.checkpointer_v2 import CheckpointerManager
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await CheckpointerManager.initialize()
        yield
        await CheckpointerManager.shutdown()
    
    # 获取 checkpointer
    checkpointer = await CheckpointerManager.get_checkpointer()

官方文档参考：
https://langchain-ai.github.io/langgraph/reference/checkpoints/#asyncpostgressaver
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# 配置
# ============================================================================

class CheckpointerConfig:
    """Checkpointer 配置"""
    # 连接池配置
    POOL_MIN_SIZE: int = 1
    POOL_MAX_SIZE: int = 10
    POOL_TIMEOUT: float = 30.0
    
    # 健康检查配置
    HEALTH_CHECK_INTERVAL: int = 60  # 秒
    HEALTH_CHECK_TIMEOUT: float = 5.0
    
    # 重试配置
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0


# ============================================================================
# Checkpointer 管理器
# ============================================================================

class CheckpointerManager:
    """
    Checkpointer 管理器（单例模式）
    
    负责：
    - 管理数据库连接池生命周期
    - 提供 AsyncPostgresSaver 实例
    - 健康检查和监控
    """
    
    _instance: Optional['CheckpointerManager'] = None
    _lock: asyncio.Lock = asyncio.Lock()
    
    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None
        self._checkpointer: Optional[AsyncPostgresSaver] = None
        self._initialized: bool = False
        self._last_health_check: float = 0
        self._health_status: bool = False
        
        # 监控指标
        self._metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "pool_connections_used": 0,
        }
    
    @classmethod
    async def get_instance(cls) -> 'CheckpointerManager':
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = CheckpointerManager()
        return cls._instance
    
    @classmethod
    async def initialize(cls) -> Optional[AsyncPostgresSaver]:
        """
        初始化 Checkpointer（应用启动时调用）
        
        Returns:
            AsyncPostgresSaver 实例，如果禁用则返回 None
        """
        instance = await cls.get_instance()
        return await instance._initialize()
    
    @classmethod
    async def shutdown(cls):
        """关闭 Checkpointer（应用关闭时调用）"""
        if cls._instance is not None:
            await cls._instance._shutdown()
            cls._instance = None
    
    @classmethod
    async def get_checkpointer(cls) -> Optional[AsyncPostgresSaver]:
        """
        获取 Checkpointer 实例
        
        Returns:
            AsyncPostgresSaver 实例，如果未初始化或禁用则返回 None
        """
        instance = await cls.get_instance()
        
        if not instance._initialized:
            logger.warning("Checkpointer not initialized, initializing now...")
            await instance._initialize()
        
        return instance._checkpointer
    
    @classmethod
    async def health_check(cls) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            健康状态信息
        """
        instance = await cls.get_instance()
        return await instance._health_check()
    
    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """获取监控指标"""
        if cls._instance is None:
            return {"status": "not_initialized"}
        return cls._instance._metrics.copy()
    
    # ========================================
    # 内部方法
    # ========================================
    
    async def _initialize(self) -> Optional[AsyncPostgresSaver]:
        """内部初始化方法"""
        if self._initialized:
            return self._checkpointer
        
        mode = settings.CHECKPOINT_MODE.lower()
        
        # 检查是否禁用
        if mode == "none" or mode == "":
            logger.info("Checkpointer 已禁用 (mode=none)")
            self._initialized = True
            return None
        
        # 检查是否为 postgres 模式
        if mode != "postgres":
            logger.warning(f"不支持的 Checkpointer 模式: {mode}，已禁用")
            self._initialized = True
            return None
        
        # 检查 PostgreSQL URI 配置
        if not settings.CHECKPOINT_POSTGRES_URI:
            logger.error("CHECKPOINT_POSTGRES_URI 未配置")
            raise ValueError("PostgreSQL URI 是必需的")
        
        try:
            logger.info("正在初始化 AsyncPostgresSaver...")
            logger.info(f"连接地址: {self._mask_password(settings.CHECKPOINT_POSTGRES_URI)}")
            
            # 创建连接池
            self._pool = AsyncConnectionPool(
                conninfo=settings.CHECKPOINT_POSTGRES_URI,
                min_size=CheckpointerConfig.POOL_MIN_SIZE,
                max_size=CheckpointerConfig.POOL_MAX_SIZE,
                timeout=CheckpointerConfig.POOL_TIMEOUT,
                kwargs={"autocommit": True}
            )
            
            # 打开连接池
            await self._pool.open()
            logger.info(
                f"数据库连接池已创建 "
                f"(min={CheckpointerConfig.POOL_MIN_SIZE}, "
                f"max={CheckpointerConfig.POOL_MAX_SIZE})"
            )
            
            # 创建 AsyncPostgresSaver
            self._checkpointer = AsyncPostgresSaver(pool=self._pool)
            
            # 初始化数据库表结构
            await self._checkpointer.setup()
            
            self._initialized = True
            self._health_status = True
            self._last_health_check = time.time()
            
            logger.info("✓ AsyncPostgresSaver 初始化成功")
            return self._checkpointer
            
        except Exception as e:
            logger.error(f"创建 AsyncPostgresSaver 失败: {str(e)}")
            logger.error("请确保：")
            logger.error("1. PostgreSQL 服务已启动")
            logger.error("2. CHECKPOINT_POSTGRES_URI 配置正确")
            logger.error("3. 数据库连接正常")
            raise
    
    async def _shutdown(self):
        """内部关闭方法"""
        logger.info("正在关闭 Checkpointer...")
        
        if self._pool is not None:
            try:
                await self._pool.close()
                logger.info("数据库连接池已关闭")
            except Exception as e:
                logger.error(f"关闭连接池失败: {e}")
        
        self._pool = None
        self._checkpointer = None
        self._initialized = False
        self._health_status = False
        
        logger.info("Checkpointer 已关闭")
    
    async def _health_check(self) -> Dict[str, Any]:
        """内部健康检查方法"""
        result = {
            "status": "unknown",
            "mode": settings.CHECKPOINT_MODE,
            "initialized": self._initialized,
            "last_check": self._last_health_check,
            "pool_status": None,
            "error": None
        }
        
        if not self._initialized:
            result["status"] = "not_initialized"
            return result
        
        if self._checkpointer is None:
            result["status"] = "disabled"
            return result
        
        try:
            # 测试数据库连接
            test_config = {"configurable": {"thread_id": "__health_check__"}}
            await asyncio.wait_for(
                self._checkpointer.aget(test_config),
                timeout=CheckpointerConfig.HEALTH_CHECK_TIMEOUT
            )
            
            # 获取连接池状态
            if self._pool is not None:
                result["pool_status"] = {
                    "size": self._pool.get_stats().get("pool_size", 0),
                    "available": self._pool.get_stats().get("pool_available", 0),
                }
            
            self._health_status = True
            self._last_health_check = time.time()
            result["status"] = "healthy"
            
        except asyncio.TimeoutError:
            self._health_status = False
            result["status"] = "unhealthy"
            result["error"] = "Health check timeout"
            
        except Exception as e:
            self._health_status = False
            result["status"] = "unhealthy"
            result["error"] = str(e)
        
        return result
    
    def _mask_password(self, uri: str) -> str:
        """隐藏连接字符串中的密码"""
        try:
            if "://" in uri and "@" in uri:
                protocol, rest = uri.split("://", 1)
                if "@" in rest:
                    credentials, location = rest.split("@", 1)
                    if ":" in credentials:
                        user, _ = credentials.split(":", 1)
                        return f"{protocol}://{user}:****@{location}"
            return uri
        except Exception:
            return "****"


# ============================================================================
# 便捷函数（兼容旧代码）
# ============================================================================

async def get_checkpointer_async() -> Optional[AsyncPostgresSaver]:
    """
    异步获取 Checkpointer 实例
    
    Returns:
        AsyncPostgresSaver 实例，如果禁用则返回 None
    """
    return await CheckpointerManager.get_checkpointer()


async def create_checkpointer_async() -> Optional[AsyncPostgresSaver]:
    """
    创建并初始化 Checkpointer
    
    Returns:
        AsyncPostgresSaver 实例，如果禁用则返回 None
    """
    return await CheckpointerManager.initialize()


async def reset_checkpointer_async():
    """重置 Checkpointer"""
    await CheckpointerManager.shutdown()


async def check_checkpointer_health_async() -> bool:
    """
    检查 Checkpointer 健康状态
    
    Returns:
        True 表示健康，False 表示不健康或未启用
    """
    result = await CheckpointerManager.health_check()
    return result.get("status") == "healthy"


# ============================================================================
# FastAPI 生命周期集成
# ============================================================================

@asynccontextmanager
async def checkpointer_lifespan():
    """
    Checkpointer 生命周期管理器
    
    使用方式：
        from app.core.checkpointer_v2 import checkpointer_lifespan
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with checkpointer_lifespan():
                yield
    """
    try:
        await CheckpointerManager.initialize()
        yield
    finally:
        await CheckpointerManager.shutdown()


__all__ = [
    "CheckpointerManager",
    "CheckpointerConfig",
    "get_checkpointer_async",
    "create_checkpointer_async",
    "reset_checkpointer_async",
    "check_checkpointer_health_async",
    "checkpointer_lifespan",
]
