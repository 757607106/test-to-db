from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func

from app.db.base_class import Base

class LLMConfiguration(Base):
    __tablename__ = "llm_configuration"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    provider = Column(String(50), nullable=False, index=True)  # openai, deepseek, aliyun, etc.
    api_key = Column(String(500), nullable=True) # Store encrypted if possible, or plain for MVP
    base_url = Column(String(500), nullable=True)
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(20), nullable=False, default='chat')  # chat, embedding
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
