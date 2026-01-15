from sqlalchemy import Column, BigInteger, String, Text, DateTime, JSON
from sqlalchemy.sql import func

from app.db.base_class import Base

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True) # Store as JSON list of floats for MySQL compatibility
    connection_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Metadata like execution success, result summary, etc.
    meta_info = Column(JSON, nullable=True)
