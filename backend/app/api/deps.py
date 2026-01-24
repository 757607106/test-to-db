from typing import Generator, Optional, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import verify_token
from app.models.user import User

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are active.
    
    Raises:
        HTTPException: 403 if user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


def get_current_tenant_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user and verify they are a tenant admin or super admin.
    
    Raises:
        HTTPException: 403 if user is not an admin
    """
    if current_user.role not in ["super_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Tenant admin required."
        )
    return current_user


def get_current_super_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user and verify they are a super admin.
    
    Raises:
        HTTPException: 403 if user is not a super admin
    """
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Super admin required."
        )
    return current_user


def check_permission(menu: str = None, feature: str = None, action: str = None):
    """
    Permission checker dependency factory.
    
    Usage:
        @router.get("/", dependencies=[Depends(check_permission(menu="connections"))])
        or
        @router.post("/", dependencies=[Depends(check_permission(feature="connections", action="create"))])
    """
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        # Super admin and tenant admin always have full access
        if current_user.role in ["super_admin", "tenant_admin"]:
            return current_user
        
        # Check user permissions
        permissions = current_user.permissions or {}
        
        # Check menu access
        if menu:
            allowed_menus = permissions.get("menus", [])
            if menu not in allowed_menus:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No access to {menu}"
                )
        
        # Check feature action access
        if feature and action:
            features = permissions.get("features", {})
            allowed_actions = features.get(feature, [])
            if action not in allowed_actions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No permission to {action} {feature}"
                )
        
        return current_user
    
    return permission_checker


def get_optional_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work both with and without auth.
    """
    if not token:
        return None
    
    user_id = verify_token(token)
    if user_id is None:
        return None
    
    return db.query(User).filter(User.id == int(user_id)).first()