"""Dashboard权限模型"""
from sqlalchemy import Column, BigInteger, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class DashboardPermission(Base):
    """Dashboard权限表"""
    __tablename__ = "dashboard_permissions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    dashboard_id = Column(BigInteger, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    permission_level = Column(String(20), nullable=False)  # owner, editor, viewer
    granted_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # 关系
    dashboard = relationship("Dashboard", back_populates="permissions")
    user = relationship("User", back_populates="dashboard_permissions", foreign_keys=[user_id])
    grantor = relationship("User", foreign_keys=[granted_by])
