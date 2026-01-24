from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class DBConnection(Base):
    __tablename__ = "dbconnection"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    db_type = Column(String(50), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(String(255), nullable=False)
    database_name = Column(String(255), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tables = relationship("SchemaTable", back_populates="connection")
    owner = relationship("User", back_populates="connections")
    tenant = relationship("Tenant", back_populates="connections")
