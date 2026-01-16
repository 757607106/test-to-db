import logging
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.core.security import get_password_hash
from app.core.agent_config import CORE_AGENT_SQL_GENERATOR, CORE_AGENT_CHART_ANALYST, CORE_AGENT_ROUTER
from app.models.agent_profile import AgentProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def init_db(db: Session) -> None:
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created")


def init_core_agents(db: Session) -> None:
    """Initialize core system agents"""
    from app.core.agent_config import AGENT_DISPLAY_NAMES
    
    core_agents = [
        {
            "name": CORE_AGENT_SQL_GENERATOR,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_SQL_GENERATOR],
            "system_prompt": "你是一个专业的SQL生成专家，负责将自然语言转换为准确的SQL查询语句。你需要理解用户的查询意图，分析数据库结构，生成高质量、安全的SQL语句。",
            "is_system": True,
            "is_active": True,
            "tools": ["sql_generator"]
        },
        {
            "name": CORE_AGENT_CHART_ANALYST,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_CHART_ANALYST],
            "system_prompt": "你是一个专业的数据分析专家，负责数据解读与可视化分析。你需要理解数据的含义，选择合适的图表类型，生成清晰、有洞察力的数据可视化。",
            "is_system": True,
            "is_active": True,
            "tools": ["chart_generator"]
        },
        {
            "name": CORE_AGENT_ROUTER,
            "role_description": AGENT_DISPLAY_NAMES[CORE_AGENT_ROUTER],
            "system_prompt": "你是一个智能路由，负责判断用户意图（闲聊 vs 查询）。你需要快速准确地识别用户的意图，将请求路由到合适的处理流程。",
            "is_system": True,
            "is_active": True,
            "tools": []
        }
    ]
    
    for agent_data in core_agents:
        agent = db.query(AgentProfile).filter(AgentProfile.name == agent_data["name"]).first()
        if not agent:
            # Create new system agent
            agent = AgentProfile(**agent_data)
            db.add(agent)
            db.commit()
            logger.info(f"Created core agent: {agent.name}")
        else:
            # Update existing agent to ensure it's marked as system and active
            if not agent.is_system:
                agent.is_system = True
                logger.info(f"Updated agent to system: {agent.name}")
            if not agent.is_active:
                agent.is_active = True
                logger.info(f"Activated system agent: {agent.name}")
            # Update role_description and system_prompt if they were default values
            if agent.role_description in ["System Core SQL Generator", "Default Data Analyst", "System Core Router", "System Internal Agent"]:
                agent.role_description = agent_data["role_description"]
                agent.system_prompt = agent_data["system_prompt"]
                logger.info(f"Updated system agent descriptions: {agent.name}")
            db.add(agent)
            db.commit()


def create_initial_data(db: Session) -> None:
    # 创建默认用户
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        user = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            display_name="Administrator",
            role="admin",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created default user: {user.username} (id: {user.id})")
    
    # Check if we already have connections
    connection = crud.db_connection.get_by_name(db, name="Sample Database")
    if not connection:
        connection_in = schemas.DBConnectionCreate(
            name="Sample Database",
            db_type="mysql",
            host="localhost",
            port=3306,
            username="root",
            password="mysql",
            database_name="chat_db"
        )
        connection = crud.db_connection.create(db=db, obj_in=connection_in)
        logger.info(f"Created sample connection: {connection.name}")
    
    # Initialize core agents
    init_core_agents(db)


if __name__ == "__main__":
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        init_db(db)
        # create_initial_data(db)
    finally:
        db.close()
