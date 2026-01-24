"""Authentication schemas for user registration, login, and token management."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class TenantInfo(BaseModel):
    """Schema for tenant information in user response."""
    id: int
    name: str
    display_name: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=100, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    display_name: Optional[str] = Field(None, max_length=100, description="Display name")
    tenant_name: Optional[str] = Field(None, description="Company/tenant name for registration")


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: Optional[int] = None


class UserResponse(BaseModel):
    """Schema for user information response."""
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    tenant_id: Optional[int] = None
    permissions: Optional[dict] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserResponseWithTenant(UserResponse):
    """Schema for user information response with tenant details."""
    tenant: Optional[TenantInfo] = None


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)


class PasswordChange(BaseModel):
    """Schema for password change."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, max_length=100, description="New password")
