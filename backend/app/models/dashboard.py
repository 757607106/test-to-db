"""Dashboard模型"""
from sqlalchemy import Column, BigInteger, String, Text, Boolean, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Dashboard(Base):
    """Dashboard仪表盘表"""
    __tablename__ = "dashboards"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    layout_config = Column(JSON, nullable=False, default=list)
    is_public = Column(Boolean, nullable=False, default=False)
    tags = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True, index=True)

    # 关系
    owner = relationship("User", back_populates="owned_dashboards", foreign_keys=[owner_id])
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")
    permissions = relationship("DashboardPermission", back_populates="dashboard", cascade="all, delete-orphan")
