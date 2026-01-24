"""用户模型"""
from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=True, index=True)  # 所属租户
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), nullable=False, default='user')  # super_admin, tenant_admin, user
    permissions = Column(JSON, nullable=True)  # 菜单/功能权限配置
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    last_login_at = Column(TIMESTAMP, nullable=True)

    # 关系
    tenant = relationship("Tenant", back_populates="users")
    owned_dashboards = relationship("Dashboard", back_populates="owner", foreign_keys="Dashboard.owner_id")
    dashboard_permissions = relationship("DashboardPermission", back_populates="user", foreign_keys="DashboardPermission.user_id")
    connections = relationship("DBConnection", back_populates="owner")
    agent_profiles = relationship("AgentProfile", back_populates="owner")
