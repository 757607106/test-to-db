"""租户用户管理 API 端点"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.models.user import User
from app.models.tenant import Tenant
from app.core.security import get_password_hash
from app.schemas.user_management import (
    UserCreateByAdmin,
    UserUpdateByAdmin,
    UserPermissionsUpdate,
    UserListResponse,
    TenantUserListResponse,
    DEFAULT_PERMISSIONS,
    RESTRICTED_PERMISSIONS,
)
from app.schemas.tenant import TenantResponse, TenantUpdate

router = APIRouter()


# ==================== 租户信息 ====================

@router.get("/me", response_model=TenantResponse)
def get_current_tenant(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """获取当前用户所属租户信息"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a tenant"
        )
    
    tenant = crud.tenant.get(db, id=current_user.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant


@router.put("/me", response_model=TenantResponse)
def update_current_tenant(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    tenant_in: TenantUpdate,
) -> Any:
    """更新当前租户信息（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a tenant"
        )
    
    tenant = crud.tenant.get(db, id=current_user.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    tenant = crud.tenant.update(db, db_obj=tenant, obj_in=tenant_in)
    return tenant


# ==================== 用户管理 ====================

@router.get("/users", response_model=TenantUserListResponse)
def list_tenant_users(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """获取租户下的用户列表（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    users = crud.user.get_multi_by_tenant(
        db, tenant_id=current_user.tenant_id, skip=skip, limit=limit
    )
    
    # 获取总数
    total = db.query(User).filter(User.tenant_id == current_user.tenant_id).count()
    
    return TenantUserListResponse(total=total, users=users)


@router.post("/users", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_user(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_in: UserCreateByAdmin,
) -> Any:
    """创建租户用户（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    # 检查用户名是否已存在
    if crud.user.get_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # 检查邮箱是否已存在
    if crud.user.get_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 限制角色只能是 user（租户管理员不能创建其他租户管理员，除非是超级管理员）
    role = user_in.role
    if role == "tenant_admin" and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create tenant admins"
        )
    if role not in ["user", "tenant_admin"]:
        role = "user"
    
    # 设置默认权限
    permissions = user_in.permissions
    if permissions is None:
        permissions = RESTRICTED_PERMISSIONS if role == "user" else DEFAULT_PERMISSIONS
    
    # 创建用户
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        tenant_id=current_user.tenant_id,
        role=role,
        permissions=permissions,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.get("/users/{user_id}", response_model=UserListResponse)
def get_tenant_user(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_id: int,
) -> Any:
    """获取租户用户详情（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/users/{user_id}", response_model=UserListResponse)
def update_tenant_user(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_id: int,
    user_in: UserUpdateByAdmin,
) -> Any:
    """更新租户用户（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 不能修改自己的角色（防止自己降级）
    if user.id == current_user.id and user_in.role and user_in.role != current_user.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    # 只有超级管理员可以设置 tenant_admin 角色
    if user_in.role == "tenant_admin" and current_user.role != "super_admin":
        # 如果用户已经是 tenant_admin，允许保持不变
        if user.role != "tenant_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admin can assign tenant admin role"
            )
    
    # 更新字段
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.put("/users/{user_id}/permissions", response_model=UserListResponse)
def update_user_permissions(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_id: int,
    permissions_in: UserPermissionsUpdate,
) -> Any:
    """更新用户权限（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 不能修改管理员的权限
    if user.role in ["super_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify admin permissions"
        )
    
    user.permissions = permissions_in.permissions
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.put("/users/{user_id}/status", response_model=UserListResponse)
def toggle_user_status(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_id: int,
) -> Any:
    """切换用户启用/禁用状态（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 不能禁用自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable yourself"
        )
    
    # 不能禁用租户管理员（除非是超级管理员）
    if user.role == "tenant_admin" and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot disable tenant admin"
        )
    
    user.is_active = not user.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/users/{user_id}")
def delete_tenant_user(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_tenant_admin),
    user_id: int,
) -> Any:
    """删除租户用户（仅租户管理员）"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    # 不能删除租户管理员（除非是超级管理员）
    if user.role == "tenant_admin" and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete tenant admin"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully", "id": user_id}


# ==================== 权限配置模板 ====================

@router.get("/permissions/templates")
def get_permission_templates(
    current_user: User = Depends(deps.get_current_tenant_admin),
) -> Any:
    """获取权限配置模板"""
    return {
        "default": DEFAULT_PERMISSIONS,
        "restricted": RESTRICTED_PERMISSIONS,
        "available_menus": ["chat", "connections", "training", "llm_configs", "agents", "users"],
        "available_features": {
            "connections": ["view", "create", "edit", "delete"],
            "training": ["view", "edit", "publish"],
            "llm_configs": ["view", "create", "edit", "delete"],
            "agents": ["view", "create", "edit", "delete"],
            "chat": ["view", "query"],
            "users": ["view", "create", "edit", "delete"]
        }
    }
