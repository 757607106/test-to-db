"""租户相关的 Pydantic 模型"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TenantBase(BaseModel):
    """租户基础模型"""
    name: str = Field(..., min_length=2, max_length=100, description="公司标识")
    display_name: str = Field(..., min_length=2, max_length=200, description="公司显示名称")
    description: Optional[str] = Field(None, description="公司描述")


class TenantCreate(TenantBase):
    """创建租户"""
    pass


class TenantUpdate(BaseModel):
    """更新租户"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(TenantBase):
    """租户响应"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantWithStats(TenantResponse):
    """带统计信息的租户响应"""
    user_count: int = 0
    connection_count: int = 0
