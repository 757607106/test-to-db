"""Dashboard洞察分析API端点"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
    current_user_id: int = 1,  # TODO: 从认证中获取
    background_tasks: BackgroundTasks
) -> Any:
    """生成看板洞察分析 (异步后台处理)"""
    try:
        # 1. 触发生成（创建占位Widget）
        response = dashboard_insight_service.trigger_dashboard_insights(
            db,
            dashboard_id=dashboard_id,
            user_id=current_user_id,
            request=request
        )
        
        # 2. 添加后台任务
        background_tasks.add_task(
            dashboard_insight_service.process_dashboard_insights_task,
            dashboard_id=dashboard_id,
            user_id=current_user_id,
            request=request,
            widget_id=response.widget_id
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
                    "last_refresh_at": w.last_refresh_at,
                    "status": w.query_config.get("status", "completed") if w.query_config else "completed"
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
    current_user_id: int = 1,  # TODO: 从认证中获取
    background_tasks: BackgroundTasks
) -> Any:
    """刷新洞察Widget（支持条件更新，异步）"""
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
        
        # 重新触发生成
        response = dashboard_insight_service.trigger_dashboard_insights(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=current_user_id,
            request=insight_request
        )
        
        # 添加后台任务
        background_tasks.add_task(
            dashboard_insight_service.process_dashboard_insights_task,
            dashboard_id=widget.dashboard_id,
            user_id=current_user_id,
            request=insight_request,
            widget_id=response.widget_id
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"刷新洞察失败: {str(e)}")


@router.post("/dashboards/{dashboard_id}/mining/suggestions", response_model=schemas.MiningResponse)
async def generate_mining_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    request: schemas.MiningRequest,
    current_user_id: int = 1  # TODO: 从认证中获取
) -> Any:
    """生成智能挖掘建议"""
    try:
        from app import crud
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user_id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to view this dashboard")
        
        return await dashboard_insight_service.generate_mining_suggestions(db, request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dashboards/{dashboard_id}/mining/apply")
def apply_mining_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    request: schemas.ApplyMiningRequest,
    current_user_id: int = 1
) -> Any:
    """应用推荐，创建Widget"""
    try:
        from app import crud
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user_id, required_level="editor"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to edit this dashboard")
        
        created_widgets = []
        for suggestion in request.suggestions:
            # 创建 Widget
            widget_create = schemas.WidgetCreate(
                title=suggestion.title,
                widget_type="chart",
                connection_id=request.connection_id,
                query_config={
                    "generated_sql": suggestion.sql,
                    "query_intent": suggestion.analysis_intent
                },
                chart_config={"chart_type": suggestion.chart_type},
                position_config={"x": 0, "y": 0, "w": 6, "h": 4}, # Default position
                refresh_interval=0
            )
            
            new_widget = crud.crud_dashboard_widget.create_widget(
                db,
                dashboard_id=dashboard_id,
                obj_in=widget_create
            )
            created_widgets.append(new_widget.id)
            
        return {"success": True, "count": len(created_widgets), "widget_ids": created_widgets}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
