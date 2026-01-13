"""Dashboard Widget模型"""
from sqlalchemy import Column, BigInteger, String, Integer, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class DashboardWidget(Base):
    """Dashboard组件表"""
    __tablename__ = "dashboard_widgets"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    dashboard_id = Column(BigInteger, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    widget_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    connection_id = Column(BigInteger, ForeignKey("dbconnection.id"), nullable=False, index=True)
    query_config = Column(JSON, nullable=False)
    chart_config = Column(JSON, nullable=True)
    position_config = Column(JSON, nullable=False)
    refresh_interval = Column(Integer, nullable=False, default=0)
    last_refresh_at = Column(TIMESTAMP, nullable=True)
    data_cache = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    # 关系
    dashboard = relationship("Dashboard", back_populates="widgets")
    connection = relationship("DBConnection")
