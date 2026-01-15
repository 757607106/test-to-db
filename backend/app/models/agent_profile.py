from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base

class AgentProfile(Base):
    __tablename__ = "agent_profile"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    role_description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    tools = Column(JSON, nullable=True) # List of tool names or config
    
    # Optional: Link to a specific LLM config, otherwise use system default
    llm_config_id = Column(BigInteger, ForeignKey("llm_configuration.id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    llm_config = relationship("LLMConfiguration")
