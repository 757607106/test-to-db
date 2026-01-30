"""Dashboard API端点"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.api import deps
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCreate, DashboardUpdate,
    DashboardListResponse, DashboardDetail,
    LayoutUpdateRequest,
    RefreshConfig, GlobalRefreshRequest, GlobalRefreshResponse
)
from app.services.dashboard_service import dashboard_service
from app.services.dashboard_refresh_service import dashboard_refresh_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=DashboardListResponse)
def get_dashboards(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    scope: str = Query("mine", description="范围: mine/shared/public/tenant/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None, description="搜索关键词"),
) -> Any:
    """获取Dashboard列表
    
    多租户隔离：自动按用户所属租户过滤
    """
    items, total = dashboard_service.get_dashboards_by_user(
        db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,  # 多租户隔离
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
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
) -> Any:
    """获取Dashboard详情"""
    dashboard = dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard_id,
        user_id=current_user.id
    )
    
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    return dashboard


@router.post("/", response_model=DashboardDetail)
def create_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_in: DashboardCreate,
) -> Any:
    """创建Dashboard
    
    多租户隔离：自动关联到用户所属租户
    """
    dashboard = dashboard_service.create_dashboard(
        db,
        obj_in=dashboard_in,
        owner_id=current_user.id,
        tenant_id=current_user.tenant_id  # 多租户隔离
    )
    
    # 返回详情
    return dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard.id,
        user_id=current_user.id
    )


@router.put("/{dashboard_id}", response_model=DashboardDetail)
def update_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    dashboard_in: DashboardUpdate,
) -> Any:
    """更新Dashboard基本信息"""
    dashboard = dashboard_service.update_dashboard(
        db,
        dashboard_id=dashboard_id,
        obj_in=dashboard_in,
        user_id=current_user.id
    )
    
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return dashboard_service.get_dashboard_detail(
        db,
        dashboard_id=dashboard.id,
        user_id=current_user.id
    )


@router.delete("/{dashboard_id}")
def delete_dashboard(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
) -> Any:
    """删除Dashboard"""
    success = dashboard_service.delete_dashboard(
        db,
        dashboard_id=dashboard_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return {"message": "Dashboard deleted successfully"}


@router.put("/{dashboard_id}/layout")
def update_dashboard_layout(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    layout_request: LayoutUpdateRequest,
) -> Any:
    """更新Dashboard布局"""
    success = dashboard_service.update_layout(
        db,
        dashboard_id=dashboard_id,
        layout=layout_request.layout,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Dashboard not found or no permission")
    
    return {"message": "Layout updated successfully"}


# ===== P1: 动态刷新机制API =====

@router.get("/{dashboard_id}/refresh/config", response_model=RefreshConfig)
def get_refresh_config(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
) -> Any:
    """获取Dashboard的刷新配置"""
    from app import crud
    
    # 检查权限
    has_permission = crud.crud_dashboard.check_permission(
        db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="No permission")
    
    return dashboard_refresh_service.get_refresh_config(db, dashboard_id)


@router.put("/{dashboard_id}/refresh/config", response_model=RefreshConfig)
def update_refresh_config(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    config: RefreshConfig,
) -> Any:
    """更新Dashboard的刷新配置"""
    from app import crud
    
    # 检查权限(需要编辑权限)
    has_permission = crud.crud_dashboard.check_permission(
        db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="editor"
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="No permission to edit")
    
    try:
        return dashboard_refresh_service.update_refresh_config(db, dashboard_id, config)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{dashboard_id}/refresh/global", response_model=GlobalRefreshResponse)
async def global_refresh(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    request: GlobalRefreshRequest,
) -> Any:
    """全局刷新Dashboard的所有Widget"""
    from app import crud
    
    # 检查权限
    has_permission = crud.crud_dashboard.check_permission(
        db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="No permission")
    
    try:
        result = await dashboard_refresh_service.global_refresh(
            db,
            dashboard_id=dashboard_id,
            force=request.force,
            widget_ids=request.widget_ids
        )
        return result
    except Exception as e:
        logger.exception(f"全局刷新失败: dashboard_id={dashboard_id}")
        raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")
