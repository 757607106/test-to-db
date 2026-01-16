"""
初始化系统内置智能体
"""
import logging
from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.core.agent_config import (
    CORE_AGENT_SQL_GENERATOR,
    CORE_AGENT_CHART_ANALYST,
    CORE_AGENT_ROUTER,
    AGENT_DISPLAY_NAMES
)

logger = logging.getLogger(__name__)


def init_system_agents(db: Session) -> None:
    """
    初始化系统内置智能体
    如果智能体已存在，则跳过
    """
    system_agents = [
        {
            "name": CORE_AGENT_SQL_GENERATOR,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_SQL_GENERATOR],
            "system_prompt": "你是一个专业的SQL生成专家，负责将自然语言转换为准确的SQL查询语句。",
            "is_system": True,
            "is_active": True
        },
        {
            "name": CORE_AGENT_CHART_ANALYST,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_CHART_ANALYST],
            "system_prompt": "你是一个专业的数据分析专家，负责数据解读与可视化分析。",
            "is_system": True,
            "is_active": True
        },
        {
            "name": CORE_AGENT_ROUTER,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_ROUTER],
            "system_prompt": "你是一个智能路由，负责判断用户意图（闲聊 vs 查询）。",
            "is_system": True,
            "is_active": True
        }
    ]
    
    for agent_data in system_agents:
        # 检查是否已存在
        existing = db.query(AgentProfile).filter(
            AgentProfile.name == agent_data["name"]
        ).first()
        
        if existing:
            logger.info(f"System agent [{agent_data['name']}] already exists, skipping")
            continue
        
        # 创建新的系统智能体
        agent = AgentProfile(**agent_data)
        db.add(agent)
        logger.info(f"Created system agent: {agent_data['name']}")
    
    db.commit()
    logger.info("System agents initialization completed")


if __name__ == "__main__":
    from app.db.session import SessionLocal
    
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        init_system_agents(db)
    finally:
        db.close()
