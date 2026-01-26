"""
预测分析API端点
P2功能：数据预测相关的API接口
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app import crud
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResult,
    PredictionColumnsResponse
)
from app.services.prediction_service import prediction_service

router = APIRouter()


@router.post("/dashboards/{dashboard_id}/predict", response_model=PredictionResult)
async def create_prediction(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    request: PredictionRequest,
    current_user_id: int = 1
) -> Any:
    """
    创建预测分析
    
    基于Widget的历史数据进行时间序列预测
    """
    try:
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user_id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission")
        
        # 获取Widget
        widget = crud.crud_dashboard_widget.get(db, id=request.widget_id)
        if not widget:
            raise HTTPException(status_code=404, detail="Widget not found")
        
        if widget.dashboard_id != dashboard_id:
            raise HTTPException(status_code=400, detail="Widget does not belong to this dashboard")
        
        # 获取Widget数据
        data_cache = widget.data_cache or {}
        data = data_cache.get("data", [])
        
        if not data:
            raise HTTPException(status_code=400, detail="Widget没有可用数据")
        
        if len(data) < 3:
            raise HTTPException(status_code=400, detail="数据点数量不足，至少需要3个数据点")
        
        # 验证列存在
        first_row = data[0]
        if request.date_column not in first_row:
            raise HTTPException(status_code=400, detail=f"时间列 '{request.date_column}' 不存在")
        if request.value_column not in first_row:
            raise HTTPException(status_code=400, detail=f"数值列 '{request.value_column}' 不存在")
        
        # 执行预测
        result = await prediction_service.predict(
            data=data,
            date_column=request.date_column,
            value_column=request.value_column,
            periods=request.periods,
            method=request.method.value,
            confidence_level=request.confidence_level
        )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"预测分析失败: {str(e)}")


@router.get("/widgets/{widget_id}/prediction-columns", response_model=PredictionColumnsResponse)
def get_prediction_columns(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    current_user_id: int = 1
) -> Any:
    """
    获取可用于预测的列信息
    
    返回Widget数据中的时间类型列和数值类型列
    """
    try:
        # 获取Widget
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            raise HTTPException(status_code=404, detail="Widget not found")
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=widget.dashboard_id, user_id=current_user_id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission")
        
        # 获取数据
        data_cache = widget.data_cache or {}
        data = data_cache.get("data", [])
        
        if not data:
            return PredictionColumnsResponse(
                date_columns=[],
                value_columns=[],
                sample_data=[]
            )
        
        # 分析列类型
        first_row = data[0]
        date_columns = []
        value_columns = []
        
        date_keywords = ["date", "time", "day", "month", "year", "created", "updated", "日期", "时间"]
        
        for key, value in first_row.items():
            # 检测时间列
            is_date = any(kw in key.lower() for kw in date_keywords)
            if is_date or _looks_like_date(value):
                date_columns.append(key)
            
            # 检测数值列
            if isinstance(value, (int, float)):
                value_columns.append(key)
            elif isinstance(value, str):
                try:
                    float(value.replace(",", ""))
                    value_columns.append(key)
                except ValueError:
                    pass
        
        return PredictionColumnsResponse(
            date_columns=date_columns,
            value_columns=value_columns,
            sample_data=data[:5]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取列信息失败: {str(e)}")


def _looks_like_date(value: Any) -> bool:
    """判断值是否看起来像日期"""
    if not isinstance(value, str):
        return False
    
    # 常见日期格式模式
    import re
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}",  # 2024-01-26
        r"\d{4}/\d{2}/\d{2}",  # 2024/01/26
        r"\d{2}-\d{2}-\d{4}",  # 26-01-2024
        r"\d{2}/\d{2}/\d{4}",  # 26/01/2024
    ]
    
    for pattern in date_patterns:
        if re.match(pattern, value):
            return True
    
    return False
