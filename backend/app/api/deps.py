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
    """P2-10修复: 添加异常时的rollback处理"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
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


def verify_tenant_user(current_user: User = Depends(get_current_user)) -> User:
    """
    验证用户属于某个租户
    
    Raises:
        HTTPException: 403 如果用户未关联租户
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    return current_user


def verify_connection_access(connection_id: int):
    """
    验证用户对数据库连接的访问权限（工厂函数）
    
    用法：
        @router.get("/data")
        async def get_data(
            connection: DBConnection = Depends(verify_connection_access(connection_id))
        ):
            ...
    
    或者更常用的方式，使用 get_verified_connection 依赖：
        @router.get("/data")
        async def get_data(
            connection_id: int = Query(...),
            db: Session = Depends(get_db),
            current_user: User = Depends(verify_tenant_user)
        ):
            connection = get_verified_connection(db, connection_id, current_user)
            ...
    """
    def _verify(
        db: Session = Depends(get_db),
        current_user: User = Depends(verify_tenant_user)
    ):
        from app import crud
        connection = crud.db_connection.get_by_tenant(
            db=db, id=connection_id, tenant_id=current_user.tenant_id
        )
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        return connection
    return _verify


def get_verified_connection(db: Session, connection_id: int, current_user: User):
    """
    获取并验证用户对数据库连接的访问权限
    
    这是一个辅助函数，用于在 endpoint 内部调用。
    
    Args:
        db: 数据库会话
        connection_id: 连接 ID
        current_user: 当前用户（需要先验证 tenant）
        
    Returns:
        DBConnection 对象
        
    Raises:
        HTTPException: 404 如果连接不存在或无权限访问
    """
    from app import crud
    
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant"
        )
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    return connection