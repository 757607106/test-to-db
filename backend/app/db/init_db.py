import logging
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def init_db(db: Session) -> None:
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created")


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


if __name__ == "__main__":
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        init_db(db)
        # create_initial_data(db)
    finally:
        db.close()
