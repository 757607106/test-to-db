"""Dashboard Widget业务服务"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date
import time

from app import crud
from app.schemas.dashboard_widget import (
    WidgetCreate, WidgetUpdate,
    WidgetResponse, WidgetRefreshResponse
)
from app.models.dashboard_widget import DashboardWidget


def convert_to_json_serializable(obj):
    """
    将数据库返回的对象转换为JSON可序列化的格式
    处理Decimal、datetime、date等特殊类型
    """
    if isinstance(obj, Decimal):
        # 将Decimal转换为float，保持精度
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        # 将日期时间转换为ISO格式字符串
        return obj.isoformat()
    elif isinstance(obj, bytes):
        # 将bytes转换为字符串
        try:
            return obj.decode('utf-8')
        except:
            return str(obj)
    elif obj is None:
        return None
    else:
        return obj


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
        
        # 实际执行SQL查询获取数据
        from app.services.db_service import get_db_connection_by_id, execute_query
        
        start_time = time.time()
        
        try:
            # 获取数据库连接
            connection = get_db_connection_by_id(widget.connection_id)
            if not connection:
                raise Exception(f"数据库连接 {widget.connection_id} 不存在")
            
            # 从query_config中获取SQL
            generated_sql = widget.query_config.get("generated_sql", "")
            if not generated_sql:
                raise Exception("Widget没有有效的SQL查询")
            
            # 执行查询
            result_data = execute_query(connection, generated_sql)
            
            # 转换数据格式为前端需要的格式
            if result_data:
                columns = list(result_data[0].keys()) if result_data else []
                # 转换每个值为JSON可序列化格式
                rows = [
                    [convert_to_json_serializable(row[col]) for col in columns] 
                    for row in result_data
                ]
                data_cache = {
                    "columns": columns,
                    "rows": rows
                }
            else:
                data_cache = {
                    "columns": [],
                    "rows": []
                }
            
        except Exception as e:
            print(f"刷新Widget数据失败: {str(e)}")
            # 如果查询失败，返回空数据，并附带错误信息
            data_cache = {
                "columns": [],
                "rows": [],
                "error": str(e)
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
