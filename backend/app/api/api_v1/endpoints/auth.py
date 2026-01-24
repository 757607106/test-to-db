"""Authentication API endpoints for user registration, login, and profile management."""
from typing import Any

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
