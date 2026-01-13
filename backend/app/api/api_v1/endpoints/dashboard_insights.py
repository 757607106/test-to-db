"""Dashboard洞察分析API端点"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app import schemas
from app.services.dashboard_insight_service import dashboard_insight_service

router = APIRouter()


@router.post("/dashboards/{dashboard_id}/insights", response_model=schemas.DashboardInsightResponse)
def generate_dashboard_insights(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    request: schemas.DashboardInsightRequest,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """生成看板洞察分析"""
    try:
        response = dashboard_insight_service.generate_dashboard_insights(
            db,
            dashboard_id=dashboard_id,
            user_id=current_user_id,
            request=request
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成洞察失败: {str(e)}")


@router.get("/dashboards/{dashboard_id}/insights")
def get_dashboard_insights(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """获取看板的洞察Widget"""
    try:
        from app import crud
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=current_user_id,
            required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to view this dashboard")
        
        # 获取Dashboard的所有Widgets
        widgets = crud.crud_dashboard_widget.get_by_dashboard(db, dashboard_id=dashboard_id)
        
        # 筛选insight_analysis类型
        insight_widgets = [w for w in widgets if w.widget_type == "insight_analysis"]
        
        return {
            "insights": [
                {
                    "id": w.id,
                    "title": w.title,
                    "data_cache": w.data_cache,
                    "query_config": w.query_config,
                    "last_refresh_at": w.last_refresh_at
                }
                for w in insight_widgets
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取洞察失败: {str(e)}")


@router.put("/widgets/{widget_id}/refresh-insights")
def refresh_insight_widget(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    request: schemas.InsightRefreshRequest,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """刷新洞察Widget（支持条件更新）"""
    try:
        from app import crud
        
        # 获取Widget
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            raise HTTPException(status_code=404, detail="Widget not found")
        
        if widget.widget_type != "insight_analysis":
            raise HTTPException(status_code=400, detail="Widget is not an insight widget")
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=current_user_id,
            required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to refresh this widget")
        
        # 构建新的洞察请求
        insight_request = schemas.DashboardInsightRequest(
            conditions=request.updated_conditions,
            force_refresh=True
        )
        
        # 重新生成洞察
        response = dashboard_insight_service.generate_dashboard_insights(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=current_user_id,
            request=insight_request
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"刷新洞察失败: {str(e)}")
