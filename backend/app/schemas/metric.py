"""
值域 Profile Schema 定义

用于字段值域分析，支持：
- 枚举值检测
- 数值范围分析
- 日期范围分析
- 采样值获取

注意：指标库功能已废弃（2026-01），仅保留 Profile 相关定义
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """字段值域 Profile"""
    column_name: str = Field(..., description="字段名")
    table_name: str = Field(..., description="表名")
    data_type: str = Field(..., description="数据类型")
    
    # 值域信息
    distinct_count: int = Field(0, description="去重值数量")
    null_count: int = Field(0, description="空值数量")
    total_count: int = Field(0, description="总行数")
    
    # 枚举值（用于低基数字段）
    enum_values: List[str] = Field(default_factory=list, description="枚举值列表（前100个）")
    is_enum: bool = Field(False, description="是否为枚举类型字段")
    
    # 数值范围（用于数值字段）
    min_value: Optional[Any] = Field(None, description="最小值")
    max_value: Optional[Any] = Field(None, description="最大值")
    
    # 日期范围（用于日期字段）
    date_min: Optional[str] = Field(None, description="最早日期")
    date_max: Optional[str] = Field(None, description="最晚日期")
    
    # 采样值
    sample_values: List[Any] = Field(default_factory=list, description="采样值（前10个）")
    
    # Profile 时间
    profiled_at: Optional[datetime] = Field(None, description="Profile 时间")


class TableProfile(BaseModel):
    """表 Profile"""
    table_name: str = Field(..., description="表名")
    connection_id: int = Field(..., description="数据库连接ID")
    row_count: int = Field(0, description="行数")
    columns: List[ColumnProfile] = Field(default_factory=list, description="字段 Profile 列表")
    profiled_at: Optional[datetime] = Field(None, description="Profile 时间")
