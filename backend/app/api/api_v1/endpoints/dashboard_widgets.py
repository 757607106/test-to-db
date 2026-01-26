"""Dashboard Widget API端点"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.dashboard_widget import (
    WidgetCreate, WidgetUpdate, WidgetResponse,
    WidgetRefreshResponse, WidgetRegenerateRequest,
    AIChartRecommendRequest, AIChartRecommendResponse
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


@router.post("/widgets/{widget_id}/ai-recommend", response_model=AIChartRecommendResponse)
async def ai_recommend_chart(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    request: AIChartRecommendRequest,
) -> Any:
    """AI智能推荐图表类型"""
    from app.models.dashboard_widget import DashboardWidget
    
    # 获取 Widget
    widget = db.query(DashboardWidget).filter(DashboardWidget.id == widget_id).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    # 获取数据样本（优先使用请求中的，否则从缓存获取）
    data_sample = request.data_sample
    if not data_sample and widget.data_cache:
        # 取前10条作为样本
        cache_data = widget.data_cache
        if isinstance(cache_data, dict) and "rows" in cache_data:
            data_sample = {
                "columns": cache_data.get("columns", []),
                "rows": cache_data.get("rows", [])[:10]
            }
        elif isinstance(cache_data, list):
            data_sample = cache_data[:10]
    
    # 分析数据特征，推荐图表类型
    recommended_type = "bar"
    confidence = 0.8
    reasoning = "基于数据特征分析"
    alternatives = []
    
    if data_sample:
        columns = []
        if isinstance(data_sample, dict):
            columns = data_sample.get("columns", [])
            rows = data_sample.get("rows", [])
        elif isinstance(data_sample, list) and len(data_sample) > 0:
            columns = list(data_sample[0].keys()) if isinstance(data_sample[0], dict) else []
            rows = data_sample
        
        # 简单规则推荐
        has_time_col = any(c for c in columns if any(t in str(c).lower() for t in ['date', 'time', '日期', '时间', 'month', 'year']))
        has_category = any(c for c in columns if any(t in str(c).lower() for t in ['name', 'type', 'category', '名称', '类型', '分类']))
        num_rows = len(rows) if rows else 0
        
        if has_time_col:
            recommended_type = "line"
            confidence = 0.9
            reasoning = "检测到时间维度字段，推荐使用折线图展示趋势变化"
            alternatives = [
                {"type": "area", "confidence": 0.8, "description": "面积图可以更好地展示累积效果"},
                {"type": "bar", "confidence": 0.7, "description": "柱状图适合对比不同时间点的数值"}
            ]
        elif has_category and num_rows <= 10:
            recommended_type = "pie"
            confidence = 0.85
            reasoning = "检测到分类字段且数据量较少，推荐使用饼图展示占比"
            alternatives = [
                {"type": "bar", "confidence": 0.75, "description": "柱状图适合对比不同类别的数值"},
                {"type": "table", "confidence": 0.6, "description": "表格可以展示更详细的信息"}
            ]
        elif has_category:
            recommended_type = "bar"
            confidence = 0.85
            reasoning = "检测到分类字段，推荐使用柱状图对比各类别"
            alternatives = [
                {"type": "line", "confidence": 0.6, "description": "折线图可以展示类别间的变化趋势"},
                {"type": "table", "confidence": 0.5, "description": "表格适合展示详细数据"}
            ]
        else:
            recommended_type = "table"
            confidence = 0.7
            reasoning = "数据结构较为复杂，推荐使用表格展示完整信息"
            alternatives = [
                {"type": "bar", "confidence": 0.6, "description": "柱状图适合数值对比"},
                {"type": "scatter", "confidence": 0.5, "description": "散点图适合展示数据分布"}
            ]
    
    # 构建推荐的图表配置
    chart_config = {
        "type": recommended_type,
        "title": widget.title,
    }
    
    return AIChartRecommendResponse(
        recommended_type=recommended_type,
        confidence=confidence,
        reasoning=reasoning,
        chart_config=chart_config,
        alternatives=alternatives
    )
