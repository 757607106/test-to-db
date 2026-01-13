"""Dashboard API端点"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate,
    DashboardListResponse, DashboardDetail,
    LayoutUpdateRequest
)
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get("/", response_model=DashboardListResponse)
def get_dashboards(
    *,
    db: Session = Depends(deps.get_db),
    scope: str = Query("mine", description="范围: mine/shared/public/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None, description="搜索关键词"),
    current_user_id: int = 1  # TODO: 从认证中获取当前用户ID
) -> Any:
    """获取Dashboard列表"""
    items, total = dashboard_service.get_dashboards_by_user(
        db,
        user_id=current_user_id,
        scope=scope,
        page=page,
        page_size=page_size,
        search=search
    )
    
    return DashboardListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@router.get("/{dashboard_id}", response_model=DashboardDetail)
def get_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """获取Dashboard详情"""
    dashboard = dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard_id,
        user_id=current_user_id
    )
    
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    return dashboard


@router.post("/", response_model=DashboardDetail)
def create_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_in: DashboardCreate,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """创建Dashboard"""
    dashboard = dashboard_service.create_dashboard(
        db,
        obj_in=dashboard_in,
        owner_id=current_user_id
    )
    
    # 返回详情
    return dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard.id,
        user_id=current_user_id
    )


@router.put("/{dashboard_id}", response_model=DashboardDetail)
def update_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    dashboard_in: DashboardUpdate,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """更新Dashboard基本信息"""
    dashboard = dashboard_service.update_dashboard(
        db,
        dashboard_id=dashboard_id,
        obj_in=dashboard_in,
        user_id=current_user_id
    )
    
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard.id,
        user_id=current_user_id
    )


@router.delete("/{dashboard_id}")
def delete_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """删除Dashboard"""
    success = dashboard_service.delete_dashboard(
        db,
        dashboard_id=dashboard_id,
        user_id=current_user_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return {"message": "Dashboard deleted successfully"}


@router.put("/{dashboard_id}/layout")
def update_dashboard_layout(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    layout_request: LayoutUpdateRequest,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """更新Dashboard布局"""
    success = dashboard_service.update_layout(
        db,
        dashboard_id=dashboard_id,
        layout=layout_request.layout,
        user_id=current_user_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return {"message": "Layout updated successfully"}
