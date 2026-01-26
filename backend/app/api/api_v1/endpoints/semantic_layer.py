"""
语义层 API 端点 (Semantic Layer Endpoints)

提供指标库管理和值域预检索的 REST API：
- 指标 CRUD 操作
- 指标搜索和查询
- 字段 Profile 分析
- 语义层 SQL 生成
"""
from typing import Any, List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app import crud
from app.schemas.metric import (
    MetricCreate, MetricUpdate, Metric, MetricWithContext,
    ColumnProfile, TableProfile, SemanticQuery, SemanticQueryResult,
    MetricAlertCreate, MetricAlertUpdate, MetricAlert, AlertCheckResult
)
from app.schemas.join_rule import (
    JoinRuleCreate, JoinRuleUpdate, JoinRule, JoinRuleContext
)
from app.services.metric_service import metric_service
from app.services.value_profiling_service import value_profiling_service
from app.services.metric_alert_service import metric_alert_service
from app.services.join_rule_service import join_rule_service

router = APIRouter()


# ===== 指标管理 =====

@router.post("/metrics", response_model=Metric)
async def create_metric(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    metric_data: MetricCreate,
) -> Any:
    """
    创建业务指标
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric_data.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        metric = await metric_service.create_metric(metric_data)
        return metric
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create metric: {str(e)}")


@router.get("/metrics", response_model=List[Metric])
async def list_metrics(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    category: Optional[str] = Query(None, description="按分类筛选"),
    tags: Optional[str] = Query(None, description="按标签筛选（逗号分隔）"),
) -> Any:
    """
    获取指标列表
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        tag_list = tags.split(",") if tags else None
        metrics = await metric_service.get_metrics_by_connection(
            connection_id=connection_id,
            category=category,
            tags=tag_list
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list metrics: {str(e)}")


@router.get("/metrics/search", response_model=List[MetricWithContext])
async def search_metrics(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    query: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, description="返回数量限制"),
) -> Any:
    """
    搜索指标（支持名称、描述、标签模糊匹配）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        metrics = await metric_service.search_metrics(
            query=query,
            connection_id=connection_id,
            limit=limit
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search metrics: {str(e)}")


@router.get("/metrics/{metric_id}", response_model=Metric)
async def get_metric(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    metric_id: str,
) -> Any:
    """
    获取单个指标详情
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    try:
        metric = await metric_service.get_metric(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
        
        # 验证连接权限
        connection = crud.db_connection.get_by_tenant(
            db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Metric not found")
        
        return metric
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metric: {str(e)}")


@router.put("/metrics/{metric_id}", response_model=Metric)
async def update_metric(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    metric_id: str,
    update_data: MetricUpdate,
) -> Any:
    """
    更新指标
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 先获取指标以验证权限
    existing_metric = await metric_service.get_metric(metric_id)
    if not existing_metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    try:
        metric = await metric_service.update_metric(metric_id, update_data)
        return metric
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update metric: {str(e)}")


@router.delete("/metrics/{metric_id}")
async def delete_metric(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    metric_id: str,
) -> Any:
    """
    删除指标
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 先获取指标以验证权限
    existing_metric = await metric_service.get_metric(metric_id)
    if not existing_metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    try:
        deleted = await metric_service.delete_metric(metric_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Metric not found")
        return {"message": "Metric deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete metric: {str(e)}")


# ===== 值域预检索 =====

@router.post("/profile/column", response_model=ColumnProfile)
async def profile_column(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    table_name: str = Query(..., description="表名"),
    column_name: str = Query(..., description="字段名"),
    data_type: str = Query("varchar", description="数据类型"),
) -> Any:
    """
    对单个字段进行 Profile 分析
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        profile = await value_profiling_service.profile_column(
            connection_id=connection_id,
            table_name=table_name,
            column_name=column_name,
            data_type=data_type
        )
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to profile column: {str(e)}")


@router.post("/profile/table", response_model=TableProfile)
async def profile_table(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    table_name: str = Query(..., description="表名"),
) -> Any:
    """
    对整个表进行 Profile 分析
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        profile = await value_profiling_service.profile_table(
            connection_id=connection_id,
            table_name=table_name
        )
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to profile table: {str(e)}")


@router.post("/profile/all", response_model=List[TableProfile])
async def profile_all_tables(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    对连接的所有表进行 Profile 分析（耗时操作）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        profiles = await value_profiling_service.profile_all_tables(connection_id)
        return profiles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to profile tables: {str(e)}")


@router.get("/profile/enums", response_model=List[Dict[str, Any]])
async def get_enum_columns(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    table_name: Optional[str] = Query(None, description="表名（可选）"),
) -> Any:
    """
    获取枚举类型字段及其值
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        enums = await value_profiling_service.get_enum_columns(
            connection_id=connection_id,
            table_name=table_name
        )
        return enums
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get enum columns: {str(e)}")


@router.get("/profile/dates", response_model=List[Dict[str, Any]])
async def get_date_columns(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    table_name: Optional[str] = Query(None, description="表名（可选）"),
) -> Any:
    """
    获取日期字段及其范围
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        dates = await value_profiling_service.get_date_columns(
            connection_id=connection_id,
            table_name=table_name
        )
        return dates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get date columns: {str(e)}")


# ===== 语义层查询 =====

@router.post("/query", response_model=SemanticQueryResult)
async def semantic_query(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    query: SemanticQuery,
) -> Any:
    """
    根据指标和维度生成 SQL（语义层查询）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        sql = await metric_service.generate_sql_from_metrics(
            metrics=query.metrics,
            dimensions=query.dimensions,
            connection_id=connection_id,
            filters=query.filters,
            time_range=query.time_range
        )
        
        return SemanticQueryResult(
            sql=sql,
            metrics_used=query.metrics,
            dimensions_used=query.dimensions,
            explanation=f"Generated SQL using metrics: {', '.join(query.metrics)}"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL: {str(e)}")


@router.get("/metrics/for-query", response_model=List[MetricWithContext])
async def get_metrics_for_query(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    user_query: str = Query(..., description="用户查询"),
) -> Any:
    """
    根据用户查询获取相关指标（用于 Schema Agent）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        metrics = await metric_service.get_metrics_for_query(
            user_query=user_query,
            connection_id=connection_id
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics for query: {str(e)}")


# ===== 指标告警管理 =====

@router.get("/metrics/{metric_id}/alerts", response_model=List[MetricAlert])
async def get_metric_alerts(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    metric_id: str,
) -> Any:
    """获取指标的告警规则列表"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证指标存在
    metric = await metric_service.get_metric(metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    try:
        alerts = await metric_alert_service.get_alerts_by_metric(metric_id)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.post("/alerts", response_model=MetricAlert)
async def create_alert(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    alert_data: MetricAlertCreate,
) -> Any:
    """创建告警规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证指标存在
    metric = await metric_service.get_metric(alert_data.metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    try:
        alert = await metric_alert_service.create_alert(alert_data)
        return alert
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.put("/alerts/{alert_id}", response_model=MetricAlert)
async def update_alert(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    alert_id: str,
    update_data: MetricAlertUpdate,
) -> Any:
    """更新告警规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    existing_alert = await metric_alert_service.get_alert(alert_id)
    if not existing_alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # 验证指标权限
    metric = await metric_service.get_metric(existing_alert.metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    try:
        alert = await metric_alert_service.update_alert(alert_id, update_data)
        return alert
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    alert_id: str,
) -> Any:
    """删除告警规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    existing_alert = await metric_alert_service.get_alert(alert_id)
    if not existing_alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # 验证指标权限
    metric = await metric_service.get_metric(existing_alert.metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    try:
        deleted = await metric_alert_service.delete_alert(alert_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"message": "Alert deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")


@router.patch("/alerts/{alert_id}/toggle", response_model=MetricAlert)
async def toggle_alert(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    alert_id: str,
    enabled: bool = Query(..., description="是否启用"),
) -> Any:
    """启用/禁用告警"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    existing_alert = await metric_alert_service.get_alert(alert_id)
    if not existing_alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # 验证指标权限
    metric = await metric_service.get_metric(existing_alert.metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=metric.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    try:
        alert = await metric_alert_service.toggle_alert(alert_id, enabled)
        return alert
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle alert: {str(e)}")


# ===== JOIN 规则管理 =====

@router.get("/join-rules", response_model=List[JoinRule])
async def list_join_rules(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    is_active: Optional[bool] = Query(None, description="是否只返回启用的规则"),
) -> Any:
    """获取 JOIN 规则列表"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        rules = await join_rule_service.get_rules_by_connection(connection_id, is_active)
        return rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get join rules: {str(e)}")


@router.post("/join-rules", response_model=JoinRule)
async def create_join_rule(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    rule_data: JoinRuleCreate,
) -> Any:
    """创建 JOIN 规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=rule_data.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        rule = await join_rule_service.create_rule(rule_data)
        return rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create join rule: {str(e)}")


@router.get("/join-rules/{rule_id}", response_model=JoinRule)
async def get_join_rule(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    rule_id: str,
) -> Any:
    """获取单个 JOIN 规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    rule = await join_rule_service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=rule.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    return rule


@router.put("/join-rules/{rule_id}", response_model=JoinRule)
async def update_join_rule(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    rule_id: str,
    update_data: JoinRuleUpdate,
) -> Any:
    """更新 JOIN 规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    existing_rule = await join_rule_service.get_rule(rule_id)
    if not existing_rule:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_rule.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    try:
        rule = await join_rule_service.update_rule(rule_id, update_data)
        return rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update join rule: {str(e)}")


@router.delete("/join-rules/{rule_id}")
async def delete_join_rule(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    rule_id: str,
) -> Any:
    """删除 JOIN 规则"""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    existing_rule = await join_rule_service.get_rule(rule_id)
    if not existing_rule:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_rule.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Join rule not found")
    
    try:
        deleted = await join_rule_service.delete_rule(rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Join rule not found")
        return {"message": "Join rule deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete join rule: {str(e)}")


@router.get("/join-rules/for-tables", response_model=List[JoinRuleContext])
async def get_join_rules_for_tables(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    tables: str = Query(..., description="表名列表（逗号分隔）"),
) -> Any:
    """
    获取指定表之间的 JOIN 规则上下文（用于 LLM SQL 生成）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    
    try:
        contexts = await join_rule_service.get_rules_for_tables(connection_id, table_list)
        return contexts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get join rules: {str(e)}")
