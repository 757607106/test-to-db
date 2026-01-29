"""
预测分析API端点
P2功能：数据预测相关的API接口
"""
from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app import crud
from app.models.user import User
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResult,
    PredictionColumnsResponse,
    CategoricalAnalysisRequest,
    CategoricalAnalysisResult
)
from app.services.prediction_service import prediction_service, categorical_analysis_service

router = APIRouter()


@router.post("/dashboards/{dashboard_id}/predict", response_model=PredictionResult)
async def create_prediction(
    *,
    db: Session = Depends(deps.get_db),
    dashboard_id: int,
    request: PredictionRequest,
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    创建预测分析
    
    基于Widget的历史数据进行时间序列预测
    """
    try:
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=dashboard_id, user_id=current_user.id, required_level="viewer"
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
    current_user: User = Depends(deps.get_current_active_user)
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
            db, dashboard_id=widget.dashboard_id, user_id=current_user.id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission")
        
        # 获取数据 - 兼容data和rows两种格式
        data_cache = widget.data_cache or {}
        data = data_cache.get("data") or data_cache.get("rows") or []
        
        # 如果data_cache本身就是列表，直接使用
        if isinstance(data_cache, list) and data_cache:
            data = data_cache
        
        # 调试信息
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Widget {widget_id} data_cache type: {type(data_cache)}, data length: {len(data) if data else 0}")
        if data and len(data) > 0:
            logger.info(f"Sample row keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}")
        
        if not data:
            return PredictionColumnsResponse(
                date_columns=[],
                value_columns=[],
                sample_data=[]
            )
        
        # 增强版列类型检测 - 检查多行数据
        date_columns = []
        value_columns = []
        category_columns = []
        
        # 扩展的日期关键词（中英文）
        date_keywords = [
            "date", "time", "day", "month", "year", "week", "quarter",
            "created", "updated", "timestamp", "period",
            "日期", "时间", "年", "月", "周", "季度", "天", "期间",
            "创建", "更新", "记录", "下单", "支付", "发货"
        ]
        
        # 获取所有列名
        all_columns = list(data[0].keys()) if data else []
        
        # 检查每一列
        for col in all_columns:
            col_lower = col.lower()
            
            # 检测该列的多个值（最多检查10行）
            sample_values = []
            for row in data[:10]:
                val = row.get(col)
                if val is not None:
                    sample_values.append(val)
            
            if not sample_values:
                continue
            
            # 调试日志
            logger.info(f"Checking column '{col}': sample_values={sample_values[:3]}")
            
            # 1. 检测日期列
            is_date_col = False
            
            # 方法a: 列名包含日期关键词
            if any(kw in col_lower for kw in date_keywords):
                is_date_col = True
                logger.info(f"Column '{col}' detected as DATE by keyword match")
            
            # 方法b: 检查值是否像日期
            if not is_date_col:
                date_like_count = sum(1 for v in sample_values if _looks_like_date_enhanced(v))
                logger.info(f"Column '{col}' date_like_count={date_like_count}/{len(sample_values)}")
                if date_like_count >= len(sample_values) * 0.5:  # 超过50%像日期
                    is_date_col = True
                    logger.info(f"Column '{col}' detected as DATE by value pattern")
            
            if is_date_col:
                date_columns.append(col)
            
            # 2. 检测数值列（排除已识别为日期的列）
            if not is_date_col:
                numeric_count = 0
                for v in sample_values:
                    if isinstance(v, (int, float)):
                        numeric_count += 1
                    elif isinstance(v, str):
                        try:
                            float(v.replace(",", "").replace("￥", "").replace("$", ""))
                            numeric_count += 1
                        except (ValueError, AttributeError):
                            pass
                
                logger.info(f"Column '{col}' numeric_count={numeric_count}/{len(sample_values)}")
                # 超过50%是数值则认为是数值列
                if numeric_count >= len(sample_values) * 0.5:
                    value_columns.append(col)
                    logger.info(f"Column '{col}' detected as VALUE")
                else:
                    # 剩余的非日期、非数值列视为分类列
                    category_columns.append(col)
                    logger.info(f"Column '{col}' detected as CATEGORY")
        
        logger.info(f"Final result: date_columns={date_columns}, value_columns={value_columns}, category_columns={category_columns}")
        
        # 确定建议的分析类型
        if date_columns and value_columns:
            suggested = "time_series"
        elif category_columns and value_columns:
            suggested = "categorical"
        else:
            suggested = "none"
        
        return PredictionColumnsResponse(
            date_columns=date_columns,
            value_columns=value_columns,
            category_columns=category_columns,
            sample_data=data[:5],
            suggested_analysis=suggested
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取列信息失败: {str(e)}")


def _looks_like_date_enhanced(value: Any) -> bool:
    """增强版日期检测 - 支持更多格式"""
    if value is None:
        return False
    
    # 如果是 datetime 对象
    if isinstance(value, datetime):
        return True
    
    if not isinstance(value, str):
        # 检查是否是时间戳（大于2000年的数字）
        if isinstance(value, (int, float)) and 946684800 < value < 4102444800:
            return True  # 2000-2100年的Unix时间戳
        return False
    
    import re
    value_str = str(value).strip()
    
    # 常见日期格式模式
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}",           # 2024-01-26
        r"^\d{4}/\d{2}/\d{2}",           # 2024/01/26
        r"^\d{2}-\d{2}-\d{4}",           # 26-01-2024
        r"^\d{2}/\d{2}/\d{4}",           # 26/01/2024
        r"^\d{4}-\d{2}$",                 # 2024-01 (年月)
        r"^\d{4}/\d{2}$",                 # 2024/01
        r"^\d{6}$",                        # 202401
        r"^\d{8}$",                        # 20240126
        r"^\d{4}年",                       # 2024年...
        r"^\d{1,2}月$",                    # 1月, 12月
        r"^Q[1-4]",                        # Q1, Q2...
        r"^\d{4}Q[1-4]",                  # 2024Q1
        r"^\d{4}-Q[1-4]",                 # 2024-Q1
        r"^\d{4}年\d{1,2}月",             # 2024年1月
        r"^\d{4}年\d{1,2}月\d{1,2}日",  # 2024年1月26日
    ]
    
    for pattern in date_patterns:
        if re.match(pattern, value_str):
            return True
    
    return False


# ==================== 分类统计分析 ====================

@router.post("/widgets/{widget_id}/categorical-analysis", response_model=CategoricalAnalysisResult)
def analyze_categorical(
    *,
    db: Session = Depends(deps.get_db),
    widget_id: int,
    request: CategoricalAnalysisRequest,
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    分类数据统计分析
    
    适用于没有时间维度的分类数据，提供：
    - 各分类统计指标（均值、标准差、中位数等）
    - 分布分析（偏度、峰度、正态性检验）
    - 分类比较（ANOVA检验）
    - 异常值检测（Z-score）
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 获取Widget
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            raise HTTPException(status_code=404, detail="Widget not found")
        
        # 检查权限
        has_permission = crud.crud_dashboard.check_permission(
            db, dashboard_id=widget.dashboard_id, user_id=current_user.id, required_level="viewer"
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail="No permission")
        
        # 获取数据
        data_cache = widget.data_cache or {}
        data = data_cache.get("data") or data_cache.get("rows") or []
        
        if isinstance(data_cache, list) and data_cache:
            data = data_cache
        
        if not data:
            raise HTTPException(status_code=400, detail="Widget没有可用数据")
        
        # 验证列存在
        first_row = data[0]
        if request.category_column not in first_row:
            raise HTTPException(status_code=400, detail=f"分类列 '{request.category_column}' 不存在")
        if request.value_column not in first_row:
            raise HTTPException(status_code=400, detail=f"数值列 '{request.value_column}' 不存在")
        
        logger.info(f"Starting categorical analysis for widget {widget_id}")
        
        # 执行分析
        result = categorical_analysis_service.analyze(
            data=data,
            category_column=request.category_column,
            value_column=request.value_column,
            include_outliers=request.include_outliers
        )
        
        logger.info(f"Categorical analysis completed: {result.get('category_count')} categories")
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分类分析失败: {str(e)}")
