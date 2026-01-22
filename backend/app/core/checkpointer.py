"""
LangGraph Checkpointer 工厂模块 (异步版本)

功能：
- 创建 AsyncPostgresSaver 实例（官方推荐的异步 Checkpointer）
- 管理数据库连接池
- 提供单例模式访问
- 支持 LangGraph 的 interrupt() 和多轮对话

使用 Docker 部署的 PostgreSQL 作为持久化存储

官方文档参考：
https://langchain-ai.github.io/langgraph/reference/checkpoints/#asyncpostgressaver
"""
from typing import Optional
import logging
import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局连接池
_connection_pool: Optional[AsyncConnectionPool] = None


async def create_checkpointer_async() -> Optional[AsyncPostgresSaver]:
    """
    创建 AsyncPostgresSaver 实例（官方推荐）
    
    Returns:
        AsyncPostgresSaver: 异步 PostgreSQL Checkpointer 实例，如果配置为禁用则返回 None
        
    说明:
        - 使用 AsyncPostgresSaver 替代同步的 PostgresSaver
        - 使用连接池管理数据库连接
        - 完全异步，避免在异步环境中阻塞
    
    官方推荐理由:
        - 在异步应用中使用同步 checkpointer 会导致性能问题
        - AsyncPostgresSaver 支持连接池，更适合高并发场景
    """
    global _connection_pool
    
    mode = settings.CHECKPOINT_MODE.lower()
    
    # 检查是否禁用
    if mode == "none" or mode == "":
        logger.info("Checkpointer 已禁用 (mode=none)")
        return None
    
    # 检查是否为 postgres 模式
    if mode != "postgres":
        logger.warning(f"不支持的 Checkpointer 模式: {mode}，已禁用 Checkpointer")
        return None
    
    # 检查 PostgreSQL URI 配置
    if not settings.CHECKPOINT_POSTGRES_URI:
        logger.error("CHECKPOINT_POSTGRES_URI 未配置，无法创建 PostgreSQL Checkpointer")
        raise ValueError("PostgreSQL URI 是必需的，请在 .env 文件中配置 CHECKPOINT_POSTGRES_URI")
    
    try:
        logger.info("正在创建 AsyncPostgresSaver (异步 Checkpointer)...")
        logger.info(f"连接地址: {_mask_password(settings.CHECKPOINT_POSTGRES_URI)}")
        
        # 创建连接池（如果尚未创建）
        if _connection_pool is None:
            _connection_pool = AsyncConnectionPool(
                conninfo=settings.CHECKPOINT_POSTGRES_URI,
                min_size=1,
                max_size=10,
                kwargs={"autocommit": True}
            )
            # 打开连接池
            await _connection_pool.open()
            logger.info("数据库连接池已创建 (min=1, max=10)")
        
        # 创建 AsyncPostgresSaver
        checkpointer = AsyncPostgresSaver(pool=_connection_pool)
        
        # 初始化数据库表结构
        await checkpointer.setup()
        
        logger.info("✓ AsyncPostgresSaver 创建并初始化成功")
        logger.info("  数据库表已就绪: checkpoints, checkpoint_writes")
        return checkpointer
        
    except Exception as e:
        logger.error(f"创建 AsyncPostgresSaver 失败: {str(e)}")
        logger.error("请确保：")
        logger.error("1. PostgreSQL 服务已启动 (docker-compose -f docker-compose.checkpointer.yml up -d)")
        logger.error("2. CHECKPOINT_POSTGRES_URI 配置正确")
        logger.error("3. 数据库连接正常")
        raise


def create_checkpointer_sync() -> Optional[AsyncPostgresSaver]:
    """
    同步包装器：在同步上下文中创建 AsyncPostgresSaver
    
    注意：这是为了兼容现有代码，推荐直接使用 create_checkpointer_async()
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已有事件循环在运行，需要在新线程中创建
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(create_checkpointer_async())
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(create_checkpointer_async())
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(create_checkpointer_async())


def _mask_password(uri: str) -> str:
    """
    隐藏连接字符串中的密码（用于日志输出）
    
    Args:
        uri: 数据库连接字符串
        
    Returns:
        隐藏密码后的连接字符串
    """
    try:
        # postgresql://user:password@host:port/database
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


# 全局 Checkpointer 实例（单例模式）
_global_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None


async def get_checkpointer_async() -> Optional[AsyncPostgresSaver]:
    """
    异步获取全局 Checkpointer 实例（单例模式）
    
    Returns:
        AsyncPostgresSaver: 全局异步 Checkpointer 实例，如果禁用则返回 None
        
    说明:
        - 使用单例模式，避免重复创建连接
        - 首次调用时创建实例
        - 后续调用返回同一实例
        - 线程安全（使用锁）
    """
    global _global_checkpointer
    
    if _global_checkpointer is None:
        # 使用锁确保只创建一次
        lock = asyncio.Lock()
        async with lock:
            if _global_checkpointer is None:
                _global_checkpointer = await create_checkpointer_async()
    
    return _global_checkpointer


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    """
    同步获取全局 Checkpointer 实例（兼容旧代码）
    
    Returns:
        AsyncPostgresSaver: 全局 Checkpointer 实例，如果禁用则返回 None
        
    注意:
        这是为了兼容现有代码。在新代码中，推荐使用 get_checkpointer_async()
    """
    global _global_checkpointer
    
    if _global_checkpointer is None:
        _global_checkpointer = create_checkpointer_sync()
        
    return _global_checkpointer


async def reset_checkpointer_async():
    """
    异步重置全局 Checkpointer 实例
    
    说明:
        - 关闭连接池
        - 重置全局实例
        - 主要用于测试场景
    """
    global _global_checkpointer, _connection_pool
    
    if _connection_pool is not None:
        logger.info("关闭数据库连接池...")
        await _connection_pool.close()
        _connection_pool = None
    
    if _global_checkpointer is not None:
        logger.info("重置 Checkpointer 实例")
        _global_checkpointer = None


def reset_checkpointer():
    """
    同步重置全局 Checkpointer 实例（兼容旧代码）
    """
    global _global_checkpointer, _connection_pool
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在运行中的事件循环中，只能设置标志
            _global_checkpointer = None
            _connection_pool = None
            logger.info("重置 Checkpointer 实例（连接池将在下次使用时重建）")
        else:
            loop.run_until_complete(reset_checkpointer_async())
    except RuntimeError:
        asyncio.run(reset_checkpointer_async())


async def check_checkpointer_health_async() -> bool:
    """
    异步检查 Checkpointer 健康状态
    
    Returns:
        bool: True 表示健康，False 表示不健康或未启用
    """
    try:
        checkpointer = await get_checkpointer_async()
        
        if checkpointer is None:
            logger.info("Checkpointer 未启用")
            return False
        
        # 尝试获取一个不存在的 checkpoint 来验证连接
        # 这不会抛出异常，只会返回 None
        test_config = {"configurable": {"thread_id": "__health_check__"}}
        await checkpointer.aget(test_config)
        
        logger.info("✓ Checkpointer 健康检查通过")
        return True
        
    except Exception as e:
        logger.error(f"Checkpointer 健康检查失败: {str(e)}")
        return False


def check_checkpointer_health() -> bool:
    """
    同步检查 Checkpointer 健康状态（兼容旧代码）
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环在运行，只检查实例是否存在
            return _global_checkpointer is not None
        else:
            return loop.run_until_complete(check_checkpointer_health_async())
    except RuntimeError:
        return asyncio.run(check_checkpointer_health_async())
