"""Dashboard洞察分析API端点"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.api import deps
from app.models.user import User
from app import schemas, crud
from app.services.dashboard_insight_service import dashboard_insight_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboards/{dashboard_id}/insights/detail")
def get_insight_detail(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    widget_id: Optional[int] = None,
) -> Any:
    """获取洞察详情（含数据溯源）- P0功能"""
    try:
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to view this dashboard")
        
        # 获取洞察Widget
        widgets = crud.crud_dashboard_widget.get_by_dashboard(db, dashboard_id=dashboard_id)
        insight_widgets = [w for w in widgets if w.widget_type == "insight_analysis"]
        
        if widget_id:
            insight_widgets = [w for w in insight_widgets if w.id == widget_id]
        
        if not insight_widgets:
            raise HTTPException(status_code=404, detail="Insight widget not found")
        
        widget = insight_widgets[0]
        data_cache = widget.data_cache or {}
        query_config = widget.query_config or {}
        
        # 构建溯源信息
        lineage = {
            "source_tables": query_config.get("source_tables", []),
            "generated_sql": query_config.get("generated_sql"),
            "sql_generation_trace": {
                "user_intent": query_config.get("user_intent"),
                "schema_tables_used": query_config.get("source_tables", []),
                "few_shot_samples_count": query_config.get("few_shot_samples_count", 0),
                "generation_method": query_config.get("generation_method", "standard"),
            },
            "execution_metadata": {
                "execution_time_ms": query_config.get("execution_time_ms", 0),
                "from_cache": query_config.get("from_cache", False),
                "row_count": query_config.get("row_count", 0),
                "db_type": query_config.get("db_type"),
                "connection_id": widget.connection_id,
            },
            "data_transformations": query_config.get("data_transformations", []),
            "schema_context": query_config.get("schema_context"),
        }
        
        return {
            "widget_id": widget.id,
            "insights": data_cache,
            "lineage": lineage,
            "confidence_score": query_config.get("confidence_score", 0.8),
            "analysis_method": query_config.get("analysis_method", "auto"),
            "analyzed_widget_count": query_config.get("analyzed_widget_count", 0),
            "relationship_count": query_config.get("relationship_count", 0),
            "generated_at": widget.last_refresh_at,
            "status": query_config.get("status", "completed"),
        }
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("获取洞察详情失败")
        raise HTTPException(status_code=500, detail="获取洞察详情失败")


@router.post("/dashboards/{dashboard_id}/insights", response_model=schemas.DashboardInsightResponse)
def generate_dashboard_insights(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    request: schemas.DashboardInsightRequest,
    background_tasks: BackgroundTasks
) -> Any:
    """生成看板洞察分析 (异步后台处理)"""
    try:
        # 1. 触发生成（创建占位Widget）
        response = dashboard_insight_service.trigger_dashboard_insights(
            db,
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            request=request
        )
        
        # 2. 添加后台任务
        background_tasks.add_task(
            dashboard_insight_service.process_dashboard_insights_task,
            dashboard_id=dashboard_id,
            user_id=current_user.id,
            request=request,
            widget_id=response.widget_id
        )
        
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception:
        logger.exception("生成洞察失败: dashboard_id=%s", dashboard_id)
        raise HTTPException(status_code=500, detail="生成洞察失败")


@router.get("/dashboards/{dashboard_id}/insights")
def get_dashboard_insights(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
) -> Any:
    """获取看板的洞察Widget"""
    try:
        from app import crud
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db,
            dashboard_id=dashboard_id,
            user_id=current_user.id,
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
    except Exception:
        logger.exception("获取洞察失败: dashboard_id=%s", dashboard_id)
        raise HTTPException(status_code=500, detail="获取洞察失败")


@router.put("/widgets/{widget_id}/refresh-insights")
def refresh_insight_widget(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    widget_id: int,
    request: schemas.InsightRefreshRequest,
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
            user_id=current_user.id,
            required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to refresh this widget")
        
        # 构建新的洞察请求
        insight_request = schemas.DashboardInsightRequest(
            conditions=request.updated_conditions,
            force_refresh=True,
            force_requery=request.force_requery
        )
        
        # 重新触发生成
        response = dashboard_insight_service.trigger_dashboard_insights(
            db,
            dashboard_id=widget.dashboard_id,
            user_id=current_user.id,
            request=insight_request
        )
        
        # 添加后台任务
        background_tasks.add_task(
            dashboard_insight_service.process_dashboard_insights_task,
            dashboard_id=widget.dashboard_id,
            user_id=current_user.id,
            request=insight_request,
            widget_id=response.widget_id
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("刷新洞察失败: widget_id=%s", widget_id)
        raise HTTPException(status_code=500, detail="刷新洞察失败")


@router.post("/dashboards/{dashboard_id}/mining/suggestions", response_model=schemas.MiningResponse)
async def generate_mining_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    request: schemas.MiningRequest,
) -> Any:
    """生成智能挖掘建议"""
    try:
        from app import crud
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to view this dashboard")
        
        return await dashboard_insight_service.generate_mining_suggestions(db, request)
    except Exception as e:
        logger.exception(f"生成挖掘建议失败: dashboard_id={dashboard_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dashboards/{dashboard_id}/mining/apply")
def apply_mining_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    request: schemas.ApplyMiningRequest,
) -> Any:
    """应用推荐，创建Widget"""
    try:
        from app import crud
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="editor"
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
    except Exception:
        logger.exception("应用推荐失败: dashboard_id=%s", dashboard_id)
        raise HTTPException(status_code=500, detail="应用推荐失败")
