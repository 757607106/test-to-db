"""Dashboard CRUD操作"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime
import logging

from app.crud.base import CRUDBase
from app.models.dashboard import Dashboard
from app.models.dashboard_permission import DashboardPermission
from app.models.user import User
from app.schemas.dashboard import DashboardCreate, DashboardUpdate

logger = logging.getLogger(__name__)


class CRUDDashboard(CRUDBase[Dashboard, DashboardCreate, DashboardUpdate]):
    """Dashboard CRUD操作类"""

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        scope: str = "mine",
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None
    ) -> tuple[List[Dashboard], int]:
        """获取用户可访问的Dashboard列表
        
        优化：使用 joinedload 预加载关联数据，避免 N+1 查询
        
        Args:
            user_id: 用户ID
            scope: 范围 (mine/shared/public)
            skip: 跳过数量
            limit: 限制数量
            search: 搜索关键词
            
        Returns:
            (Dashboard列表, 总数)
        """
        # 基础查询，预加载 widgets、permissions 和 owner
        base_query = db.query(Dashboard).options(
            joinedload(Dashboard.widgets),
            joinedload(Dashboard.owner)
        ).filter(Dashboard.deleted_at.is_(None))
        
        # 根据scope过滤
        if scope == "mine":
            query = base_query.filter(Dashboard.owner_id == user_id)
        elif scope == "shared":
            # 共享给我的Dashboard - 需要单独处理以避免重复
            shared_dashboard_ids = db.query(DashboardPermission.dashboard_id).filter(
                DashboardPermission.user_id == user_id
            ).subquery()
            query = base_query.filter(
                Dashboard.id.in_(shared_dashboard_ids),
                Dashboard.owner_id != user_id
            )
        elif scope == "public":
            # 公开的Dashboard
            query = base_query.filter(Dashboard.is_public == True)
        else:
            # 全部可访问的
            query = base_query.filter(
                or_(
                    Dashboard.owner_id == user_id,
                    Dashboard.is_public == True,
                    Dashboard.id.in_(
                        db.query(DashboardPermission.dashboard_id).filter(
                            DashboardPermission.user_id == user_id
                        )
                    )
                )
            )
        
        # 搜索过滤 - 使用参数化查询防止 SQL 注入
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Dashboard.name.ilike(search_pattern),
                    Dashboard.description.ilike(search_pattern)
                )
            )
        
        # 获取总数（在分页前）
        # 使用子查询避免 joinedload 影响 count
        count_query = db.query(Dashboard.id).filter(Dashboard.deleted_at.is_(None))
        if scope == "mine":
            count_query = count_query.filter(Dashboard.owner_id == user_id)
        elif scope == "shared":
            shared_ids = db.query(DashboardPermission.dashboard_id).filter(
                DashboardPermission.user_id == user_id
            ).subquery()
            count_query = count_query.filter(
                Dashboard.id.in_(shared_ids),
                Dashboard.owner_id != user_id
            )
        elif scope == "public":
            count_query = count_query.filter(Dashboard.is_public == True)
        else:
            count_query = count_query.filter(
                or_(
                    Dashboard.owner_id == user_id,
                    Dashboard.is_public == True,
                    Dashboard.id.in_(
                        db.query(DashboardPermission.dashboard_id).filter(
                            DashboardPermission.user_id == user_id
                        )
                    )
                )
            )
        
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.filter(
                or_(
                    Dashboard.name.ilike(search_pattern),
                    Dashboard.description.ilike(search_pattern)
                )
            )
        
        total = count_query.count()
        
        # 分页和排序
        items = query.order_by(Dashboard.updated_at.desc()).offset(skip).limit(limit).all()
        
        return items, total

    def get_user_permission_batch(
        self,
        db: Session,
        *,
        dashboard_ids: List[int],
        user_id: int
    ) -> Dict[int, str]:
        """批量获取用户对多个 Dashboard 的权限级别
        
        优化：一次查询获取所有权限，避免 N+1
        
        Args:
            dashboard_ids: Dashboard ID 列表
            user_id: 用户ID
            
        Returns:
            {dashboard_id: permission_level} 字典
        """
        if not dashboard_ids:
            return {}
        
        result = {}
        
        # 1. 查询用户拥有的 Dashboard
        owned_dashboards = db.query(Dashboard.id).filter(
            Dashboard.id.in_(dashboard_ids),
            Dashboard.owner_id == user_id,
            Dashboard.deleted_at.is_(None)
        ).all()
        
        for (dashboard_id,) in owned_dashboards:
            result[dashboard_id] = "owner"
        
        # 2. 查询显式权限
        remaining_ids = [did for did in dashboard_ids if did not in result]
        if remaining_ids:
            permissions = db.query(
                DashboardPermission.dashboard_id,
                DashboardPermission.permission_level
            ).filter(
                DashboardPermission.dashboard_id.in_(remaining_ids),
                DashboardPermission.user_id == user_id
            ).all()
            
            for dashboard_id, level in permissions:
                result[dashboard_id] = level
        
        # 3. 查询公开的 Dashboard
        remaining_ids = [did for did in dashboard_ids if did not in result]
        if remaining_ids:
            public_dashboards = db.query(Dashboard.id).filter(
                Dashboard.id.in_(remaining_ids),
                Dashboard.is_public == True,
                Dashboard.deleted_at.is_(None)
            ).all()
            
            for (dashboard_id,) in public_dashboards:
                result[dashboard_id] = "viewer"
        
        return result

    def get_with_details(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Dashboard]:
        """获取Dashboard详情(包含widgets和permissions)
        
        Args:
            dashboard_id: Dashboard ID
            user_id: 当前用户ID(用于检查权限)
            
        Returns:
            Dashboard对象或None
        """
        query = db.query(Dashboard).options(
            joinedload(Dashboard.widgets),
            joinedload(Dashboard.permissions),
            joinedload(Dashboard.owner)
        ).filter(
            Dashboard.id == dashboard_id,
            Dashboard.deleted_at.is_(None)
        )
        
        dashboard = query.first()
        
        if not dashboard:
            return None
        
        # 检查访问权限
        if user_id:
            has_access = (
                dashboard.is_public or
                dashboard.owner_id == user_id or
                db.query(DashboardPermission).filter(
                    DashboardPermission.dashboard_id == dashboard_id,
                    DashboardPermission.user_id == user_id
                ).first() is not None
            )
            
            if not has_access:
                return None
        
        return dashboard

    def create_with_permission(
        self,
        db: Session,
        *,
        obj_in: DashboardCreate,
        owner_id: int
    ) -> Dashboard:
        """创建Dashboard并自动添加owner权限
        
        P2-10修复: 添加事务异常处理
        
        Args:
            obj_in: Dashboard创建数据
            owner_id: 创建者ID
            
        Returns:
            创建的Dashboard对象
        """
        try:
            # 创建Dashboard
            dashboard_data = obj_in.model_dump()
            dashboard_data["owner_id"] = owner_id
            dashboard_data["layout_config"] = []  # 初始化为空数组
            
            dashboard = Dashboard(**dashboard_data)
            db.add(dashboard)
            db.flush()
            
            # 创建owner权限
            permission = DashboardPermission(
                dashboard_id=dashboard.id,
                user_id=owner_id,
                permission_level="owner",
                granted_by=owner_id
            )
            db.add(permission)
            db.commit()
            db.refresh(dashboard)
            
            return dashboard
        except Exception:
            db.rollback()
            raise

    def soft_delete(self, db: Session, *, dashboard_id: int) -> bool:
        """软删除Dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            是否成功
        """
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            return False
        
        dashboard.deleted_at = datetime.utcnow()
        db.commit()
        return True

    def get_user_permission(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int
    ) -> Optional[str]:
        """获取用户对Dashboard的权限级别
        
        Args:
            dashboard_id: Dashboard ID
            user_id: 用户ID
            
        Returns:
            权限级别(owner/editor/viewer)或None
        """
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            return None
        
        # 检查是否是owner
        if dashboard.owner_id == user_id:
            return "owner"
        
        # 检查是否有显式权限
        permission = db.query(DashboardPermission).filter(
            DashboardPermission.dashboard_id == dashboard_id,
            DashboardPermission.user_id == user_id
        ).first()
        
        if permission:
            return permission.permission_level
        
        # 检查是否是公开的
        if dashboard.is_public:
            return "viewer"
        
        return None

    def check_permission(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int,
        required_level: str
    ) -> bool:
        """检查用户是否有足够的权限
        
        Args:
            dashboard_id: Dashboard ID
            user_id: 用户ID
            required_level: 需要的权限级别(owner/editor/viewer)
            
        Returns:
            是否有权限
        """
        user_level = self.get_user_permission(db, dashboard_id=dashboard_id, user_id=user_id)
        
        if not user_level:
            return False
        
        # 权限级别映射
        level_hierarchy = {"owner": 3, "editor": 2, "viewer": 1}
        
        return level_hierarchy.get(user_level, 0) >= level_hierarchy.get(required_level, 0)


# 创建全局实例
crud_dashboard = CRUDDashboard(Dashboard)
