"""Dashboard Schema定义"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Dashboard基础Schema
class DashboardBase(BaseModel):
    """Dashboard基础Schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Dashboard名称")
    description: Optional[str] = Field(None, max_length=2000, description="Dashboard描述")
    is_public: bool = Field(False, description="是否公开")
    tags: Optional[List[str]] = Field(None, description="标签列表")


# 创建Dashboard的请求Schema
class DashboardCreate(DashboardBase):
    """创建Dashboard的请求Schema"""
    pass


# 更新Dashboard的请求Schema
class DashboardUpdate(BaseModel):
    """更新Dashboard的请求Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


# Dashboard的响应Schema (简略版,用于列表)
class DashboardListItem(DashboardBase):
    """Dashboard列表项Schema"""
    id: int
    owner_id: int
    owner: Optional[Dict[str, Any]] = Field(None, description="创建者信息")
    widget_count: int = Field(0, description="Widget数量")
    permission_level: Optional[str] = Field(None, description="当前用户的权限级别")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Dashboard的详情响应Schema
class DashboardDetail(DashboardBase):
    """Dashboard详情Schema"""
    id: int
    owner_id: int
    owner: Optional[Dict[str, Any]] = Field(None, description="创建者信息")
    layout_config: List[Dict[str, Any]] = Field(default_factory=list, description="布局配置")
    widgets: List[Dict[str, Any]] = Field(default_factory=list, description="Widget列表")
    permissions: List[Dict[str, Any]] = Field(default_factory=list, description="权限列表")
    permission_level: Optional[str] = Field(None, description="当前用户的权限级别")
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Dashboard列表的分页响应
class DashboardListResponse(BaseModel):
    """Dashboard列表的分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    items: List[DashboardListItem] = Field(..., description="Dashboard列表")


# 布局更新请求Schema
class LayoutUpdateRequest(BaseModel):
    """布局更新请求Schema"""
    layout: List[Dict[str, Any]] = Field(..., description="布局配置数组")


# 权限级别枚举
class PermissionLevel(str):
    """权限级别"""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


# 权限相关Schema
class PermissionBase(BaseModel):
    """权限基础Schema"""
    user_id: int
    permission_level: str = Field(..., description="权限级别: owner/editor/viewer")


class PermissionCreate(PermissionBase):
    """创建权限请求Schema"""
    pass


class PermissionUpdate(BaseModel):
    """更新权限请求Schema"""
    permission_level: str


class PermissionResponse(PermissionBase):
    """权限响应Schema"""
    id: int
    dashboard_id: int
    user: Optional[Dict[str, Any]] = Field(None, description="用户信息")
    granted_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class PermissionListResponse(BaseModel):
    """权限列表响应Schema"""
    permissions: List[PermissionResponse]
