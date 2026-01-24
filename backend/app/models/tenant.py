"""租户模型"""
from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Tenant(Base):
    """租户/公司表"""
    __tablename__ = "tenants"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # 公司标识
    display_name = Column(String(200), nullable=False)  # 公司显示名称
    description = Column(Text, nullable=True)  # 公司描述
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    # 关系
    users = relationship("User", back_populates="tenant")
    connections = relationship("DBConnection", back_populates="tenant")
    llm_configs = relationship("LLMConfiguration", back_populates="tenant")
    agent_profiles = relationship("AgentProfile", back_populates="tenant")
