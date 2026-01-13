"""Dashboard Widget业务服务"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import time

from app import crud
from app.schemas.dashboard_widget import (
    WidgetCreate, WidgetUpdate,
    WidgetResponse, WidgetRefreshResponse
)
from app.models.dashboard_widget import DashboardWidget


class DashboardWidgetService:
    """Dashboard Widget业务服务类"""

    def create_widget(
        self,
        db: Session,
        *,
        dashboard_id: int,
        obj_in: WidgetCreate,
        user_id: int
    ) -> Optional[DashboardWidget]:
        """创建Widget"""
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        return crud.crud_dashboard_widget.create_widget(
            db,
            obj_in=obj_in,
            dashboard_id=dashboard_id
        )

    def update_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        obj_in: WidgetUpdate,
        user_id: int
    ) -> Optional[DashboardWidget]:
        """更新Widget"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        return crud.crud_dashboard_widget.update(db, db_obj=widget, obj_in=obj_in)

    def delete_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        user_id: int
    ) -> bool:
        """删除Widget"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return False
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return False
        
        crud.crud_dashboard_widget.remove(db, id=widget_id)
        return True

    def refresh_widget(
        self,
        db: Session,
        *,
        widget_id: int,
        user_id: int
    ) -> Optional[WidgetRefreshResponse]:
        """手动刷新Widget数据"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限(viewer也可以刷新)
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="viewer"
        ):
            return None
        
        # TODO: 实际执行查询获取数据
        # 这里暂时使用占位数据
        start_time = time.time()
        data_cache = {
            "columns": ["col1", "col2"],
            "rows": [[1, 2], [3, 4]]
        }
        
        updated_widget, duration_ms = crud.crud_dashboard_widget.refresh_data(
            db,
            widget_id=widget_id,
            data_cache=data_cache
        )
        
        if not updated_widget:
            return None
        
        return WidgetRefreshResponse(
            id=updated_widget.id,
            data_cache=updated_widget.data_cache,
            last_refresh_at=updated_widget.last_refresh_at,
            refresh_duration_ms=duration_ms
        )

    def regenerate_widget_query(
        self,
        db: Session,
        *,
        widget_id: int,
        mode: str,
        updated_query: Optional[str],
        parameters: Optional[Dict[str, Any]],
        user_id: int
    ) -> Optional[DashboardWidget]:
        """重新生成Widget查询"""
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            return None
        
        # 检查权限
        if not crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=user_id,
            required_level="editor"
        ):
            return None
        
        # 构建新的query_config
        new_query_config = widget.query_config.copy()
        
        if mode == "params":
            # 只更新参数
            if parameters:
                new_query_config["parameters"] = parameters
        elif mode == "full":
            # 完全重新生成
            if updated_query:
                new_query_config["original_query"] = updated_query
            if parameters:
                new_query_config["parameters"] = parameters
            
            # TODO: 调用LangGraph重新生成SQL
            # 这里暂时保持原SQL
        
        return crud.crud_dashboard_widget.update_query_config(
            db,
            widget_id=widget_id,
            query_config=new_query_config
        )


# 创建全局实例
dashboard_widget_service = DashboardWidgetService()
