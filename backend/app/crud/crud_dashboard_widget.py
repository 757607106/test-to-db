"""Dashboard Widget CRUD操作"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from datetime import datetime
import time

from app.crud.base import CRUDBase
from app.models.dashboard_widget import DashboardWidget
from app.schemas.dashboard_widget import WidgetCreate, WidgetUpdate


class CRUDDashboardWidget(CRUDBase[DashboardWidget, WidgetCreate, WidgetUpdate]):
    """Dashboard Widget CRUD操作类"""

    def get_by_dashboard(
        self,
        db: Session,
        *,
        dashboard_id: int
    ) -> List[DashboardWidget]:
        """获取Dashboard的所有Widget
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            Widget列表
        """
        return db.query(DashboardWidget).filter(
            DashboardWidget.dashboard_id == dashboard_id
        ).order_by(DashboardWidget.created_at).all()

    def create_widget(
        self,
        db: Session,
        *,
        obj_in: WidgetCreate,
        dashboard_id: int
    ) -> DashboardWidget:
        """创建Widget并自动分配位置
        
        Args:
            obj_in: Widget创建数据
            dashboard_id: Dashboard ID
            
        Returns:
            创建的Widget对象
        """
        widget_data = obj_in.model_dump()
        widget_data["dashboard_id"] = dashboard_id
        
        # 如果没有提供position_config,自动分配位置
        if "position_config" not in widget_data or not widget_data["position_config"]:
            widget_data["position_config"] = self._allocate_position(db, dashboard_id)
        
        widget = DashboardWidget(**widget_data)
        db.add(widget)
        db.commit()
        db.refresh(widget)
        
        return widget

    def _allocate_position(self, db: Session, dashboard_id: int) -> dict:
        """自动分配Widget位置
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            position_config字典
        """
        # 获取现有的所有Widget
        existing_widgets = self.get_by_dashboard(db, dashboard_id=dashboard_id)
        
        if not existing_widgets:
            # 第一个Widget,放在左上角
            return {"x": 0, "y": 0, "w": 6, "h": 4, "minW": 2, "minH": 2}
        
        # 找到最大的y值
        max_y = 0
        for widget in existing_widgets:
            pos = widget.position_config
            widget_bottom = pos.get("y", 0) + pos.get("h", 4)
            max_y = max(max_y, widget_bottom)
        
        # 放置在最底部
        return {"x": 0, "y": max_y, "w": 6, "h": 4, "minW": 2, "minH": 2}

    def update_position(
        self,
        db: Session,
        *,
        widget_id: int,
        position_config: dict
    ) -> Optional[DashboardWidget]:
        """更新Widget位置
        
        Args:
            widget_id: Widget ID
            position_config: 新的位置配置
            
        Returns:
            更新后的Widget对象
        """
        widget = db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return None
        
        widget.position_config = position_config
        db.commit()
        db.refresh(widget)
        
        return widget

    def refresh_data(
        self,
        db: Session,
        *,
        widget_id: int,
        data_cache: dict
    ) -> tuple[Optional[DashboardWidget], int]:
        """刷新Widget数据
        
        Args:
            widget_id: Widget ID
            data_cache: 新的缓存数据
            
        Returns:
            (更新后的Widget对象, 刷新耗时毫秒)
        """
        start_time = time.time()
        
        widget = db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return None, 0
        
        widget.data_cache = data_cache
        widget.last_refresh_at = datetime.utcnow()
        db.commit()
        db.refresh(widget)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return widget, duration_ms

    def get_widgets_need_refresh(
        self,
        db: Session,
        *,
        limit: int = 100
    ) -> List[DashboardWidget]:
        """获取需要刷新的Widget列表
        
        Args:
            limit: 最大数量
            
        Returns:
            需要刷新的Widget列表
        """
        from sqlalchemy import func, case
        
        now = datetime.utcnow()
        
        # 查询需要刷新的Widget
        # 条件: refresh_interval > 0 且 (last_refresh_at为空 或 当前时间-last_refresh_at >= refresh_interval)
        widgets = db.query(DashboardWidget).filter(
            DashboardWidget.refresh_interval > 0,
            or_(
                DashboardWidget.last_refresh_at.is_(None),
                func.timestampdiff(
                    'SECOND',
                    DashboardWidget.last_refresh_at,
                    now
                ) >= DashboardWidget.refresh_interval
            )
        ).limit(limit).all()
        
        return widgets

    def update_query_config(
        self,
        db: Session,
        *,
        widget_id: int,
        query_config: dict
    ) -> Optional[DashboardWidget]:
        """更新Widget的查询配置
        
        Args:
            widget_id: Widget ID
            query_config: 新的查询配置
            
        Returns:
            更新后的Widget对象
        """
        widget = db.query(DashboardWidget).filter(
            DashboardWidget.id == widget_id
        ).first()
        
        if not widget:
            return None
        
        # 添加编辑历史
        if "edit_history" not in query_config:
            query_config["edit_history"] = []
        
        if widget.query_config:
            query_config["edit_history"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "previous_query": widget.query_config.get("original_query"),
                "new_query": query_config.get("original_query")
            })
        
        widget.query_config = query_config
        # 清除缓存,因为查询已改变
        widget.data_cache = None
        db.commit()
        db.refresh(widget)
        
        return widget


# 创建全局实例
crud_dashboard_widget = CRUDDashboardWidget(DashboardWidget)
