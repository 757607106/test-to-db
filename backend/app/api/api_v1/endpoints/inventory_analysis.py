"""
库存分析 API 端点
商业级库存分析引擎：ABC-XYZ分类、周转率分析、安全库存计算、供应商评估
"""
import time
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.inventory_analysis import (
    ABCXYZRequest, ABCXYZResult,
    TurnoverRequest, TurnoverResult,
    SafetyStockRequest, SafetyStockResult,
    SupplierEvaluationRequest, SupplierResult,
    InventoryAnalysisResponse
)
from app.services.inventory_analysis_service import inventory_analysis_service
from app import crud
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def get_data_from_request(
    db: Session, 
    widget_id: Optional[int], 
    connection_id: Optional[int], 
    sql: Optional[str]
) -> list:
    """
    从请求中获取分析数据
    
    优先级: widget_id > sql + connection_id
    """
    if widget_id:
        # 从 Widget 获取数据
        widget = crud.crud_dashboard_widget.get(db, id=widget_id)
        if not widget:
            raise HTTPException(status_code=404, detail=f"Widget {widget_id} 不存在")
        
        data_cache = widget.data_cache or {}
        # 兼容多种数据格式
        data = data_cache.get("data") or data_cache.get("rows") or []
        
        if isinstance(data_cache, list):
            data = data_cache
            
        if not data:
            raise HTTPException(status_code=400, detail="Widget 数据为空，请先刷新 Widget")
        
        return data
    
    elif sql and connection_id:
        # 执行自定义 SQL
        from app.tools.execute_sql_query import execute_sql_query
        
        try:
            result = execute_sql_query.invoke({
                "sql": sql,
                "connection_id": connection_id,
                "force_execute": True
            })
            
            import json
            result_data = json.loads(result) if isinstance(result, str) else result
            
            if result_data.get("success"):
                return result_data.get("data", [])
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"SQL 执行失败: {result_data.get('error', '未知错误')}"
                )
        except Exception as e:
            logger.error(f"SQL 执行异常: {e}")
            raise HTTPException(status_code=500, detail=f"SQL 执行异常: {str(e)}")
    
    else:
        raise HTTPException(
            status_code=400, 
            detail="请提供 widget_id 或 (sql + connection_id)"
        )


@router.post("/inventory/abc-xyz", response_model=InventoryAnalysisResponse)
def analyze_abc_xyz(
    request: ABCXYZRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    ABC-XYZ 库存分类分析
    
    - ABC分类：帕累托分析（70/20/10规则），按价值贡献分类
    - XYZ分类：变异系数分析，按需求稳定性分类
    
    返回：汇总统计、9宫格矩阵、帕累托图数据、详细分类列表
    """
    start_time = time.time()
    
    try:
        # 获取数据
        data = get_data_from_request(
            db, request.widget_id, request.connection_id, request.sql
        )
        
        # 执行分析
        result = inventory_analysis_service.abc_xyz_analysis(
            data=data,
            product_column=request.product_column,
            value_column=request.value_column,
            quantity_column=request.quantity_column,
            abc_thresholds=request.abc_thresholds,
            xyz_thresholds=request.xyz_thresholds
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return InventoryAnalysisResponse(
            success=True,
            analysis_type="abc_xyz",
            result=result,
            execution_time_ms=execution_time,
            data_rows=len(data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ABC-XYZ 分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/inventory/turnover", response_model=InventoryAnalysisResponse)
def analyze_turnover(
    request: TurnoverRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    库存周转率分析
    
    - 周转率 = 销售成本 / 平均库存
    - 库存天数 = 365 / 周转率
    
    返回：汇总统计、健康度评估、详细列表
    """
    start_time = time.time()
    
    try:
        data = get_data_from_request(
            db, request.widget_id, request.connection_id, request.sql
        )
        
        result = inventory_analysis_service.inventory_turnover(
            data=data,
            product_column=request.product_column,
            cogs_column=request.cogs_column,
            inventory_column=request.inventory_column
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return InventoryAnalysisResponse(
            success=True,
            analysis_type="turnover",
            result=result,
            execution_time_ms=execution_time,
            data_rows=len(data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"周转率分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/inventory/safety-stock", response_model=InventoryAnalysisResponse)
def calculate_safety_stock(
    request: SafetyStockRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    安全库存计算
    
    公式：安全库存 = Z × σ_demand × √(LT)
    - Z: 服务水平对应的标准正态分位数
    - σ_demand: 需求标准差
    - LT: 前置时间（天）
    
    返回：安全库存、再订货点、统计依据
    """
    start_time = time.time()
    
    try:
        data = get_data_from_request(
            db, request.widget_id, request.connection_id, request.sql
        )
        
        result = inventory_analysis_service.safety_stock(
            data=data,
            product_column=request.product_column,
            demand_column=request.demand_column,
            lead_time=request.lead_time,
            service_level=request.service_level
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return InventoryAnalysisResponse(
            success=True,
            analysis_type="safety_stock",
            result=result,
            execution_time_ms=execution_time,
            data_rows=len(data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"安全库存计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/inventory/supplier-eval", response_model=InventoryAnalysisResponse)
def evaluate_suppliers(
    request: SupplierEvaluationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    供应商评估
    
    - 加权评分法：多指标综合评分
    - K-means 聚类：供应商分组
    
    返回：加权得分、排名、聚类分组
    """
    start_time = time.time()
    
    try:
        data = get_data_from_request(
            db, request.widget_id, request.connection_id, request.sql
        )
        
        result = inventory_analysis_service.supplier_evaluation(
            data=data,
            supplier_column=request.supplier_column,
            metrics_columns=request.metrics_columns,
            weights=request.weights
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return InventoryAnalysisResponse(
            success=True,
            analysis_type="supplier_evaluation",
            result=result,
            execution_time_ms=execution_time,
            data_rows=len(data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"供应商评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")
