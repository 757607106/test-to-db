"""Dashboard Permission CRUD操作"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.dashboard_permission import DashboardPermission
from app.schemas.dashboard import PermissionCreate, PermissionUpdate


class CRUDDashboardPermission(CRUDBase[DashboardPermission, PermissionCreate, PermissionUpdate]):
    """Dashboard Permission CRUD操作类"""

    def get_by_dashboard(
        self,
        db: Session,
        *,
        dashboard_id: int
    ) -> List[DashboardPermission]:
        """获取Dashboard的所有权限
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            权限列表
        """
        return db.query(DashboardPermission).options(
            joinedload(DashboardPermission.user)
        ).filter(
            DashboardPermission.dashboard_id == dashboard_id
        ).all()

    def get_by_user_and_dashboard(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int
    ) -> Optional[DashboardPermission]:
        """获取用户对Dashboard的权限
        
        Args:
            dashboard_id: Dashboard ID
            user_id: 用户ID
            
        Returns:
            权限对象或None
        """
        return db.query(DashboardPermission).filter(
            DashboardPermission.dashboard_id == dashboard_id,
            DashboardPermission.user_id == user_id
        ).first()

    def create_permission(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int,
        permission_level: str,
        granted_by: int
    ) -> DashboardPermission:
        """创建权限
        
        Args:
            dashboard_id: Dashboard ID
            user_id: 用户ID
            permission_level: 权限级别
            granted_by: 授权人ID
            
        Returns:
            创建的权限对象
        """
        # 检查是否已存在
        existing = self.get_by_user_and_dashboard(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id
        )
        
        if existing:
            # 如果已存在,更新权限级别
            existing.permission_level = permission_level
            existing.granted_by = granted_by
            db.commit()
            db.refresh(existing)
            return existing
        
        # 创建新权限
        permission = DashboardPermission(
            dashboard_id=dashboard_id,
            user_id=user_id,
            permission_level=permission_level,
            granted_by=granted_by
        )
        db.add(permission)
        db.commit()
        db.refresh(permission)
        
        return permission

    def update_permission_level(
        self,
        db: Session,
        *,
        permission_id: int,
        permission_level: str
    ) -> Optional[DashboardPermission]:
        """更新权限级别
        
        Args:
            permission_id: 权限ID
            permission_level: 新的权限级别
            
        Returns:
            更新后的权限对象
        """
        permission = db.query(DashboardPermission).filter(
            DashboardPermission.id == permission_id
        ).first()
        
        if not permission:
            return None
        
        permission.permission_level = permission_level
        db.commit()
        db.refresh(permission)
        
        return permission

    def delete_permission(
        self,
        db: Session,
        *,
        permission_id: int
    ) -> bool:
        """删除权限
        
        Args:
            permission_id: 权限ID
            
        Returns:
            是否成功
        """
        permission = db.query(DashboardPermission).filter(
            DashboardPermission.id == permission_id
        ).first()
        
        if not permission:
            return False
        
        # 不允许删除owner权限
        if permission.permission_level == "owner":
            return False
        
        db.delete(permission)
        db.commit()
        
        return True


# 创建全局实例
crud_dashboard_permission = CRUDDashboardPermission(DashboardPermission)
