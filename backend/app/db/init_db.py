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
    core_agents = [
        {
            "name": CORE_AGENT_SQL_GENERATOR,
            "role_description": "System Core SQL Generator",
            "system_prompt": "System Internal Agent",
            "is_system": True,
            "tools": ["sql_generator"]
        },
        {
            "name": CORE_AGENT_CHART_ANALYST,
            "role_description": "Default Data Analyst",
            "system_prompt": "System Internal Agent",
            "is_system": True,
            "tools": ["chart_generator"]
        },
        {
            "name": CORE_AGENT_ROUTER,
            "role_description": "System Core Router",
            "system_prompt": "System Internal Agent",
            "is_system": True,
            "tools": []
        }
    ]
    
    for agent_data in core_agents:
        agent = db.query(AgentProfile).filter(AgentProfile.name == agent_data["name"]).first()
        if not agent:
            # Convert tools list to JSON if needed, but sqlalchemy JSON type handles list/dict
            agent = AgentProfile(**agent_data)
            db.add(agent)
            db.commit()
            logger.info(f"Created core agent: {agent.name}")
        else:
            # Ensure is_system is True for these agents
            if not agent.is_system:
                agent.is_system = True
                db.add(agent)
                db.commit()
                logger.info(f"Updated core agent to system: {agent.name}")


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
