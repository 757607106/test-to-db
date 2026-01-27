"""
Skill Schema 定义

用于 API 请求/响应的 Pydantic 模型
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class SkillBase(BaseModel):
    """
    Skill 基础属性
    
    设计为行业无关，通过配置适配任何业务场景
    """
    # 基础标识
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Skill 标识（小写字母+数字+下划线）"
    )
    display_name: str = Field(
        ..., 
        min_length=1, 
        max_length=100, 
        description="显示名称"
    )
    
    # 描述（用于 LLM 理解）
    description: Optional[str] = Field(
        None, 
        description="Skill 描述，告诉 LLM 这个领域处理什么类型的查询"
    )
    
    # 路由配置
    keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词，用于快速路由匹配"
    )
    intent_examples: List[str] = Field(
        default_factory=list,
        description="意图示例，帮助 LLM 理解适用场景"
    )
    
    # 关联 Schema
    table_patterns: List[str] = Field(
        default_factory=list,
        description="表名匹配模式，支持通配符如 'order*', 'sales_*'"
    )
    table_names: List[str] = Field(
        default_factory=list,
        description="精确关联的表名列表"
    )
    
    # 业务规则（用户自定义）
    business_rules: Optional[str] = Field(
        None, 
        description="业务规则说明，会注入到 SQL 生成的提示词中"
    )
    
    # 常用查询模式
    common_patterns: List[Dict[str, str]] = Field(
        default_factory=list,
        description="常用查询模式，如 {'pattern': '销售排名', 'hint': 'ORDER BY amount DESC'}"
    )
    
    # JOIN 规则（内嵌，替代独立的 JoinRule 管理）
    join_rules: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="JOIN 规则列表，格式: [{left_table, left_column, right_table, right_column, join_type, description}]"
    )
    
    # 配置
    priority: int = Field(0, description="路由优先级，数字越大越优先")
    is_active: bool = Field(True, description="是否启用")
    
    # 元数据
    icon: Optional[str] = Field(None, max_length=50, description="图标")
    color: Optional[str] = Field(None, max_length=20, description="主题色")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证 name 格式：小写字母开头，只能包含小写字母、数字、下划线"""
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError('name 必须以小写字母开头，只能包含小写字母、数字和下划线')
        return v

    @field_validator('join_rules', mode='before')
    @classmethod
    def validate_join_rules(cls, v):
        """处理 join_rules 为 None 的情况（数据库迁移前兼容）"""
        if v is None:
            return []
        return v


class SkillCreate(SkillBase):
    """创建 Skill 请求"""
    connection_id: int = Field(..., description="数据库连接 ID")


class SkillUpdate(BaseModel):
    """更新 Skill 请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    intent_examples: Optional[List[str]] = None
    table_patterns: Optional[List[str]] = None
    table_names: Optional[List[str]] = None
    business_rules: Optional[str] = None
    common_patterns: Optional[List[Dict[str, str]]] = None
    join_rules: Optional[List[Dict[str, Any]]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class Skill(SkillBase):
    """Skill 完整模型"""
    id: int
    connection_id: int
    tenant_id: Optional[int] = None
    
    # 统计信息
    usage_count: int = Field(0, description="使用次数")
    hit_rate: float = Field(0.0, description="命中率")
    
    # 时间戳
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # 自动发现来源
    is_auto_generated: bool = Field(False, description="是否为自动生成")
    
    class Config:
        from_attributes = True


class SkillLoadResult(BaseModel):
    """load_skill 工具返回结果"""
    skill_name: str
    display_name: str
    description: Optional[str] = None
    
    # Schema 信息（按需加载的核心内容）
    tables: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="表结构"
    )
    columns: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="列信息"
    )
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="表关系"
    )
    
    # 语义增强（与现有指标库整合）
    metrics: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="相关指标"
    )
    join_rules: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="JOIN 规则"
    )
    
    # 业务上下文
    business_rules: Optional[str] = Field(None, description="业务规则")
    common_patterns: List[Dict[str, str]] = Field(default_factory=list)
    
    # 值域信息
    enum_columns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="枚举字段"
    )


class SkillSuggestion(BaseModel):
    """Skill 自动发现建议"""
    name: str
    display_name: str
    description: str
    keywords: List[str]
    table_names: List[str]
    confidence: float = Field(description="置信度 0-1")
    reasoning: str = Field(description="建议原因")


class SkillListResponse(BaseModel):
    """Skill 列表响应"""
    skills: List[Skill]
    total: int
    has_skills_configured: bool = Field(
        description="是否已配置 Skills（用于前端判断模式）"
    )


class SkillStatusResponse(BaseModel):
    """Skills 状态响应（零配置检查）"""
    has_skills_configured: bool = Field(
        description="是否已配置 Skills"
    )
    skills_count: int = Field(
        description="已配置的 Skill 数量"
    )
    mode: str = Field(
        description="当前模式: 'skill' 或 'default'"
    )


class SkillDiscoverResponse(BaseModel):
    """Skill 自动发现响应"""
    suggestions: List[SkillSuggestion]
    total: int
