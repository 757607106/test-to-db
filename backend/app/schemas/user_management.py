"""用户管理相关的 Pydantic 模型"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreateByAdmin(BaseModel):
    """租户管理员创建用户"""
    username: str = Field(..., min_length=3, max_length=100, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")
    role: str = Field(default="user", description="角色: user")
    permissions: Optional[dict] = Field(None, description="权限配置")


class UserUpdateByAdmin(BaseModel):
    """租户管理员更新用户"""
    display_name: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, description="角色: user, tenant_admin")
    permissions: Optional[dict] = Field(None, description="权限配置")
    is_active: Optional[bool] = Field(None, description="是否启用")


class UserPermissionsUpdate(BaseModel):
    """更新用户权限"""
    permissions: dict = Field(..., description="权限配置")


class UserListResponse(BaseModel):
    """用户列表响应"""
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    role: str
    permissions: Optional[dict] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantUserListResponse(BaseModel):
    """租户用户列表响应"""
    total: int
    users: List[UserListResponse]


# 默认权限配置
DEFAULT_PERMISSIONS = {
    "menus": ["chat", "connections", "training", "llm_configs", "agents"],
    "features": {
        "connections": ["view", "create", "edit", "delete"],
        "training": ["view", "edit"],
        "llm_configs": ["view", "create", "edit", "delete"],
        "agents": ["view", "create", "edit", "delete"],
        "chat": ["view", "query"]
    }
}

# 受限用户权限（普通用户默认）
RESTRICTED_PERMISSIONS = {
    "menus": ["chat", "connections"],
    "features": {
        "connections": ["view"],
        "chat": ["view", "query"]
    }
}
