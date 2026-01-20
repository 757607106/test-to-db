"""
LangGraph Checkpointer 工厂模块

功能：
- 创建 PostgreSQL Checkpointer 实例
- 管理数据库连接
- 提供单例模式访问

使用 Docker 部署的 PostgreSQL 作为持久化存储
"""
from typing import Optional
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
import logging
import psycopg

logger = logging.getLogger(__name__)


def create_checkpointer() -> Optional[PostgresSaver]:
    """
    创建 PostgreSQL Checkpointer 实例
    
    Returns:
        PostgresSaver: PostgreSQL Checkpointer 实例，如果配置为禁用则返回 None
        
    说明:
        - 使用 Docker 部署的 PostgreSQL 作为持久化存储
        - 连接信息从环境变量读取
        - 支持通过 CHECKPOINT_MODE 配置启用/禁用
    
    环境变量:
        CHECKPOINT_MODE: "postgres" 启用，"none" 或其他值禁用
        CHECKPOINT_POSTGRES_URI: PostgreSQL 连接字符串
            格式: postgresql://user:password@host:port/database
            示例: postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints
    """
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
        logger.info(f"正在创建 PostgreSQL Checkpointer...")
        logger.info(f"连接地址: {_mask_password(settings.CHECKPOINT_POSTGRES_URI)}")
        
        # 创建 PostgreSQL Checkpointer
        # 步骤：
        # 1. 使用 psycopg 创建数据库连接（autocommit 模式以支持 CREATE INDEX CONCURRENTLY）
        # 2. 将连接传递给 PostgresSaver 构造函数
        # 3. 调用 setup() 初始化数据库表结构
        conn = psycopg.connect(settings.CHECKPOINT_POSTGRES_URI, autocommit=True)
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        
        logger.info("PostgreSQL Checkpointer 创建并初始化成功")
        logger.info(f"数据库表已就绪: checkpoints, checkpoint_writes")
        return checkpointer
        
    except Exception as e:
        logger.error(f"创建 PostgreSQL Checkpointer 失败: {str(e)}")
        logger.error("请确保：")
        logger.error("1. PostgreSQL 服务已启动 (docker-compose -f docker-compose.checkpointer.yml up -d)")
        logger.error("2. CHECKPOINT_POSTGRES_URI 配置正确")
        logger.error("3. 数据库连接正常")
        raise


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
_global_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> Optional[PostgresSaver]:
    """
    获取全局 Checkpointer 实例（单例模式）
    
    Returns:
        PostgresSaver: 全局 Checkpointer 实例，如果禁用则返回 None
        
    说明:
        - 使用单例模式，避免重复创建连接
        - 首次调用时创建实例
        - 后续调用返回同一实例
    """
    global _global_checkpointer
    
    if _global_checkpointer is None:
        _global_checkpointer = create_checkpointer()
        
    return _global_checkpointer


def reset_checkpointer():
    """
    重置全局 Checkpointer 实例
    
    说明:
        - 主要用于测试场景
        - 强制重新创建 Checkpointer 实例
        - 生产环境不建议使用
    """
    global _global_checkpointer
    
    if _global_checkpointer is not None:
        logger.info("重置 Checkpointer 实例")
        _global_checkpointer = None


def check_checkpointer_health() -> bool:
    """
    检查 Checkpointer 健康状态
    
    Returns:
        bool: True 表示健康，False 表示不健康或未启用
        
    说明:
        - 检查 Checkpointer 是否已创建
        - 检查数据库连接是否正常
        - 可用于健康检查接口
    """
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            logger.info("Checkpointer 未启用")
            return False
        
        # 尝试执行简单查询验证连接
        # PostgresSaver 内部会管理连接池
        logger.info("Checkpointer 健康检查通过")
        return True
        
    except Exception as e:
        logger.error(f"Checkpointer 健康检查失败: {str(e)}")
        return False
