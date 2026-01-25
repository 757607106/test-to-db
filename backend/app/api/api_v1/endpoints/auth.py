"""Authentication API endpoints for user registration, login, and profile management."""
from typing import Any, Dict
import secrets
import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.core.security import create_access_token, get_password_hash
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    Token,
    UserResponse,
    UserResponseWithTenant,
    UserUpdate,
    PasswordChange,
)
from app.models.user import User
from app.schemas.tenant import TenantCreate

router = APIRouter()

# ============================================================================
# Session Code 存储 (内存缓存，生产环境建议使用 Redis)
# ============================================================================
_session_codes: Dict[str, Dict[str, Any]] = {}
_session_codes_lock = Lock()
SESSION_CODE_TTL = 300  # 5分钟过期


def _cleanup_expired_codes():
    """清理过期的 session codes"""
    now = time.time()
    expired = [k for k, v in _session_codes.items() if v["expires_at"] < now]
    for k in expired:
        del _session_codes[k]


def _store_session_code(code: str, user_id: int, tenant_id: int) -> None:
    """存储 session code"""
    with _session_codes_lock:
        _cleanup_expired_codes()
        _session_codes[code] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "expires_at": time.time() + SESSION_CODE_TTL
        }


def _get_and_remove_session_code(code: str) -> Dict[str, Any]:
    """获取并删除 session code (一次性使用)"""
    with _session_codes_lock:
        _cleanup_expired_codes()
        if code not in _session_codes:
            return None
        data = _session_codes.pop(code)
        if data["expires_at"] < time.time():
            return None
        return data


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserCreate,
) -> Any:
    """
    Register a new user with a new tenant (company).
    If tenant_name is provided, creates a new tenant and makes the user a tenant_admin.
    """
    # Check if username already exists
    if crud.user.get_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if email already exists
    if crud.user.get_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    tenant_id = None
    role = "user"
    
    # If tenant_name is provided, create a new tenant
    if user_in.tenant_name:
        # Check if tenant already exists
        existing_tenant = crud.tenant.get_by_name(db, name=user_in.tenant_name)
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name already registered",
            )
        
        # Create new tenant
        tenant_data = TenantCreate(
            name=user_in.tenant_name,
            display_name=user_in.tenant_name,
        )
        tenant = crud.tenant.create(db, obj_in=tenant_data)
        tenant_id = tenant.id
        role = "tenant_admin"  # First user of a tenant is admin
    
    # Create user with tenant association
    user = crud.user.create_with_tenant(
        db, obj_in=user_in, tenant_id=tenant_id, role=role
    )
    return user


@router.post("/login", response_model=Token)
def login(
    *,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    Accepts username or email in the 'username' field.
    """
    user = crud.user.authenticate(
        db, username_or_email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not crud.user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Update last login time
    crud.user.update_last_login(db, user=user)
    
    # Create access token
    access_token = create_access_token(subject=user.id)
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/json", response_model=Token)
def login_json(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserLogin,
) -> Any:
    """
    JSON-based login endpoint (alternative to OAuth2 form).
    Accepts username or email.
    """
    user = crud.user.authenticate(
        db, username_or_email=user_in.username, password=user_in.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
        )
    
    if not crud.user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Update last login time
    crud.user.update_last_login(db, user=user)
    
    # Create access token
    access_token = create_access_token(subject=user.id)
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user information.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update current user profile.
    """
    user = crud.user.update(db, db_obj=current_user, obj_in=user_in)
    return user


@router.post("/change-password", response_model=dict)
def change_password(
    *,
    db: Session = Depends(deps.get_db),
    password_in: PasswordChange,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Change current user's password.
    """
    from app.core.security import verify_password, get_password_hash
    
    # Verify old password
    if not verify_password(password_in.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_in.new_password)
    db.add(current_user)
    db.commit()
    
    return {"message": "Password changed successfully"}


# ============================================================================
# Session Code 端点 (用于安全的跨域 token 传递)
# ============================================================================

@router.post("/session-code", response_model=dict)
def create_session_code(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    创建一次性 Session Code，用于安全地将认证传递给 Chat 页面。
    
    安全机制:
    - Code 是随机生成的，不可预测
    - 5分钟内有效
    - 只能使用一次
    - 不包含敏感信息 (token)
    
    使用流程:
    1. Admin 调用此接口获取 code
    2. 重定向到 Chat 页面: /chat?code=xxx
    3. Chat 页面调用 /exchange-code 用 code 换取 token
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    # 生成安全的随机 code
    code = secrets.token_urlsafe(32)
    
    # 存储 code 与用户信息的映射
    _store_session_code(code, current_user.id, current_user.tenant_id)
    
    return {"code": code, "expires_in": SESSION_CODE_TTL}


@router.post("/exchange-code", response_model=Token)
def exchange_session_code(
    code: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    用 Session Code 交换 Access Token。
    
    安全机制:
    - Code 只能使用一次
    - 过期自动失效
    - 成功后立即删除 code
    """
    # 获取并验证 code
    code_data = _get_and_remove_session_code(code)
    
    if not code_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session code"
        )
    
    # 验证用户仍然有效
    user = db.query(User).filter(User.id == code_data["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # 更新最后登录时间
    crud.user.update_last_login(db, user=user)
    
    # 创建 access token
    access_token = create_access_token(subject=user.id)
    
    return {"access_token": access_token, "token_type": "bearer"}
