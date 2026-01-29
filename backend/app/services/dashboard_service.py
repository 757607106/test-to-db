"""Dashboard业务服务"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
import logging

from app import crud
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate,
    DashboardListItem, DashboardDetail
)
from app.models.dashboard import Dashboard

logger = logging.getLogger(__name__)


class DashboardService:
    """Dashboard业务服务类"""

    def get_dashboards_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        scope: str = "mine",
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Tuple[List[DashboardListItem], int]:
        """获取用户的Dashboard列表
        
        优化：使用批量权限查询，避免 N+1 问题
        
        Returns:
            (Dashboard列表, 总数)
        """
        skip = (page - 1) * page_size
        
        dashboards, total = crud.crud_dashboard.get_by_user(
            db,
            user_id=user_id,
            scope=scope,
            skip=skip,
            limit=page_size,
            search=search
        )
        
        # 批量获取权限
        dashboard_ids = [d.id for d in dashboards]
        permissions_map = crud.crud_dashboard.get_user_permission_batch(
            db,
            dashboard_ids=dashboard_ids,
            user_id=user_id
        )
        
        # 转换为响应格式
        items = []
        for dashboard in dashboards:
            # 获取widget数量（已通过 joinedload 预加载）
            widget_count = len(dashboard.widgets) if dashboard.widgets else 0
            
            # 从批量查询结果获取权限
            permission_level = permissions_map.get(dashboard.id)
            
            # 构建owner信息（已通过 joinedload 预加载）
            owner_info = None
            if dashboard.owner:
                owner_info = {
                    "id": dashboard.owner.id,
                    "username": dashboard.owner.username,
                    "display_name": dashboard.owner.display_name
                }
            
            item = DashboardListItem(
                id=dashboard.id,
                name=dashboard.name,
                description=dashboard.description,
                is_public=dashboard.is_public,
                tags=dashboard.tags or [],
                owner_id=dashboard.owner_id,
                owner=owner_info,
                widget_count=widget_count,
                permission_level=permission_level,
                created_at=dashboard.created_at,
                updated_at=dashboard.updated_at
            )
            items.append(item)
        
        return items, total

    def get_dashboard_detail(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int
    ) -> Optional[DashboardDetail]:
        """获取Dashboard详情"""
        dashboard = crud.crud_dashboard.get_with_details(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id
        )
        
        if not dashboard:
            return None
        
        # 获取用户权限
        permission_level = crud.crud_dashboard.get_user_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id
        )
        
        # 构建widgets列表
        widgets_data = []
        for widget in dashboard.widgets:
            widgets_data.append({
                "id": widget.id,
                "widget_type": widget.widget_type,
                "title": widget.title,
                "connection_id": widget.connection_id,
                "query_config": widget.query_config,
                "chart_config": widget.chart_config,
                "position_config": widget.position_config,
                "refresh_interval": widget.refresh_interval,
                "last_refresh_at": widget.last_refresh_at,
                "data_cache": widget.data_cache
            })
        
        # 构建permissions列表
        permissions_data = []
        for perm in dashboard.permissions:
            user_info = None
            if perm.user:
                user_info = {
                    "id": perm.user.id,
                    "username": perm.user.username,
                    "display_name": perm.user.display_name
                }
            permissions_data.append({
                "id": perm.id,
                "user_id": perm.user_id,
                "user": user_info,
                "permission_level": perm.permission_level
            })
        
        # 构建owner信息
        owner_info = None
        if dashboard.owner:
            owner_info = {
                "id": dashboard.owner.id,
                "username": dashboard.owner.username,
                "display_name": dashboard.owner.display_name
            }
        
        return DashboardDetail(
            id=dashboard.id,
            name=dashboard.name,
            description=dashboard.description,
            is_public=dashboard.is_public,
            tags=dashboard.tags or [],
            owner_id=dashboard.owner_id,
            owner=owner_info,
            layout_config=dashboard.layout_config or [],
            widgets=widgets_data,
            permissions=permissions_data,
            permission_level=permission_level,
            created_at=dashboard.created_at,
            updated_at=dashboard.updated_at,
            deleted_at=dashboard.deleted_at
        )

    def create_dashboard(
        self,
        db: Session,
        *,
        obj_in: DashboardCreate,
        owner_id: int
    ) -> Dashboard:
        """创建Dashboard"""
        return crud.crud_dashboard.create_with_permission(
            db,
            obj_in=obj_in,
            owner_id=owner_id
        )

    def update_dashboard(
        self,
        db: Session,
        *,
        dashboard_id: int,
        obj_in: DashboardUpdate,
        user_id: int
    ) -> Optional[Dashboard]:
        """更新Dashboard"""
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="owner"
        ):
            return None
        
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if not dashboard:
            return None
        
        return crud.crud_dashboard.update(db, db_obj=dashboard, obj_in=obj_in)

    def delete_dashboard(
        self,
        db: Session,
        *,
        dashboard_id: int,
        user_id: int
    ) -> bool:
        """删除Dashboard(软删除)"""
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="owner"
        ):
            return False
        
        return crud.crud_dashboard.soft_delete(db, dashboard_id=dashboard_id)

    def update_layout(
        self,
        db: Session,
        *,
        dashboard_id: int,
        layout: List[Dict[str, Any]],
        user_id: int
    ) -> bool:
        """更新Dashboard布局"""
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return False
        
        # 更新每个widget的position_config
        for item in layout:
            widget_id = item.get("widget_id")
            if not widget_id:
                continue
            
            position = {
                "x": item.get("x", 0),
                "y": item.get("y", 0),
                "w": item.get("w", 6),
                "h": item.get("h", 4)
            }
            
            crud.crud_dashboard_widget.update_position(
                db,
                widget_id=widget_id,
                position_config=position
            )
        
        # 更新Dashboard的layout_config
        dashboard = crud.crud_dashboard.get(db, id=dashboard_id)
        if dashboard:
            dashboard.layout_config = layout
            db.commit()
        
        return True


# 创建全局实例
dashboard_service = DashboardService()
