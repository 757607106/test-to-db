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


@router.post("/dashboards/{dashboard_id}/mining/suggestions", response_model=schemas.MiningResponse)
async def generate_mining_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    dashboard_id: int,
    request: schemas.MiningRequest,
) -> Any:
    """生成智能挖掘建议（增强版：支持个性化上下文）"""
    try:
        from app import crud
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission to view this dashboard")
        
        # ✨ 传递 dashboard_id 和 user_id 以支持个性化
        return await dashboard_insight_service.generate_mining_suggestions(
            db, 
            request,
            dashboard_id=dashboard_id,  # 新增：Dashboard上下文
            user_id=current_user.id  # 新增：用户画像
        )
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
