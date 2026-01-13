"""Dashboard Widget API端点"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.dashboard_widget import (
    WidgetCreate, WidgetUpdate, WidgetResponse,
    WidgetRefreshResponse, WidgetRegenerateRequest
)
from app.services.dashboard_widget_service import dashboard_widget_service
from app import crud

router = APIRouter()


@router.post("/dashboards/{dashboard_id}/widgets", response_model=WidgetResponse)
def create_widget(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    widget_in: WidgetCreate,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """添加Widget到Dashboard"""
    widget = dashboard_widget_service.create_widget(
        db,
        dashboard_id=dashboard_id,
        obj_in=widget_in,
        user_id=current_user_id
    )
    
    if not widget:
        raise HTTPException(status_code=403, detail="No permission to add widget")
    
    return widget


@router.put("/widgets/{widget_id}", response_model=WidgetResponse)
def update_widget(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    widget_in: WidgetUpdate,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """更新Widget配置"""
    widget = dashboard_widget_service.update_widget(
        db,
        widget_id=widget_id,
        obj_in=widget_in,
        user_id=current_user_id
    )
    
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found or no permission")
    
    return widget


@router.delete("/widgets/{widget_id}")
def delete_widget(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """删除Widget"""
    success = dashboard_widget_service.delete_widget(
        db,
        widget_id=widget_id,
        user_id=current_user_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Widget not found or no permission")
    
    return {"message": "Widget deleted successfully"}


@router.post("/widgets/{widget_id}/refresh", response_model=WidgetRefreshResponse)
def refresh_widget(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """手动刷新Widget数据"""
    result = dashboard_widget_service.refresh_widget(
        db,
        widget_id=widget_id,
        user_id=current_user_id
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Widget not found or no permission")
    
    return result


@router.post("/widgets/{widget_id}/regenerate", response_model=WidgetResponse)
def regenerate_widget_query(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    regenerate_request: WidgetRegenerateRequest,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """重新生成Widget查询"""
    widget = dashboard_widget_service.regenerate_widget_query(
        db,
        widget_id=widget_id,
        mode=regenerate_request.mode,
        updated_query=regenerate_request.updated_query,
        parameters=regenerate_request.parameters,
        user_id=current_user_id
    )
    
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found or no permission")
    
    return widget
