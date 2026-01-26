"""
JOIN 规则 Schema 定义

用于预定义表之间的JOIN关系，减少LLM生成SQL时的错误。
支持多种JOIN类型和条件，存储在 Neo4j 图数据库中。
"""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


# JOIN 类型
JoinType = Literal["INNER", "LEFT", "RIGHT", "FULL"]


class JoinRuleBase(BaseModel):
    """JOIN规则基础属性"""
    name: str = Field(..., description="规则名称，如：订单-用户关联")
    description: Optional[str] = Field(None, description="规则描述")
    
    # 左表信息
    left_table: str = Field(..., description="左表名")
    left_column: str = Field(..., description="左表关联字段")
    
    # 右表信息
    right_table: str = Field(..., description="右表名")
    right_column: str = Field(..., description="右表关联字段")
    
    # JOIN配置
    join_type: JoinType = Field("INNER", description="JOIN类型")
    priority: int = Field(1, ge=1, le=10, description="优先级(1-10)，LLM优先使用高优先级规则")
    
    # 附加条件
    extra_conditions: Optional[str] = Field(None, description="附加JOIN条件，如：AND a.status = 'active'")
    
    # 业务标签
    tags: List[str] = Field(default_factory=list, description="业务标签")
    is_active: bool = Field(True, description="是否启用")


class JoinRuleCreate(JoinRuleBase):
    """创建JOIN规则请求"""
    connection_id: int = Field(..., description="数据库连接ID")


class JoinRuleUpdate(BaseModel):
    """更新JOIN规则请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    left_column: Optional[str] = None
    right_column: Optional[str] = None
    join_type: Optional[JoinType] = None
    priority: Optional[int] = None
    extra_conditions: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class JoinRule(JoinRuleBase):
    """JOIN规则响应模型"""
    id: str = Field(..., description="规则ID")
    connection_id: int = Field(..., description="数据库连接ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    usage_count: int = Field(0, description="使用次数")
    
    class Config:
        from_attributes = True


class JoinRuleContext(BaseModel):
    """JOIN规则上下文（用于LLM提示）"""
    rule_id: str
    join_clause: str = Field(..., description="完整的JOIN子句")
    priority: int
    description: Optional[str] = None
