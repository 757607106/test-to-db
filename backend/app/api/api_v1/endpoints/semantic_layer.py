"""
语义层 API 端点 (Semantic Layer Endpoints)

提供值域预检索的 REST API：
- 字段 Profile 分析
- 枚举值检索
- 日期范围检索

注意：
- 指标库功能已废弃（2026-01）
- JOIN 规则已迁移到 Skill.join_rules
"""
from typing import Any, List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app import crud
from app.schemas.metric import ColumnProfile, TableProfile
from app.services.value_profiling_service import value_profiling_service

router = APIRouter()


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
