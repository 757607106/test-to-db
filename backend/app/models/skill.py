"""
Skill 模型定义

业务领域技能 - SaaS 多租户模型

设计原则：
1. 每个数据库连接独立配置 Skill
2. 支持自动发现和手动配置
3. 无 Skill 配置时系统仍可工作（零配置可用）
4. 同步到 Neo4j 建立语义层关系
"""
from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, Boolean, 
    DateTime, ForeignKey, JSON, Float, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Skill(Base):
    """
    业务领域技能
    
    用于在复杂业务场景下实现领域隔离和按需加载。
    每个 Skill 定义一个业务领域，关联特定的表、指标和 JOIN 规则。
    """
    __tablename__ = "skills"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    # 基础信息
    name = Column(String(50), nullable=False, index=True, 
                  comment="Skill 标识，如：sales, inventory")
    display_name = Column(String(100), nullable=False, 
                          comment="显示名称，如：销售管理")
    description = Column(Text, nullable=True, 
                         comment="Skill 描述，用于 LLM 理解")
    
    # 路由配置
    keywords = Column(JSON, default=list, 
                      comment="关键词列表，用于路由匹配")
    intent_examples = Column(JSON, default=list, 
                             comment="意图示例，帮助 LLM 理解适用场景")
    
    # Schema 关联
    table_patterns = Column(JSON, default=list, 
                            comment="表名匹配模式，支持通配符如 order_*")
    table_names = Column(JSON, default=list, 
                         comment="精确关联的表名列表")
    
    # 业务配置
    business_rules = Column(Text, nullable=True, 
                            comment="业务规则说明，注入到 SQL Generator")
    common_patterns = Column(JSON, default=list, 
                             comment="常用查询模式")
    
    # JOIN 规则（内嵌，替代独立的 JoinRule 表）
    # nullable=True 以兼容迁移前的数据库
    join_rules = Column(JSON, default=list, nullable=True,
                        comment="JOIN 规则列表，格式: [{left_table, left_column, right_table, right_column, join_type}]")
    
    # 配置
    priority = Column(Integer, default=0, 
                      comment="路由优先级，数字越大越优先")
    is_active = Column(Boolean, default=True, 
                       comment="是否启用")
    icon = Column(String(50), nullable=True, 
                  comment="图标（用于前端展示）")
    color = Column(String(20), nullable=True, 
                   comment="主题色")
    
    # 统计
    usage_count = Column(Integer, default=0, 
                         comment="使用次数")
    hit_rate = Column(Float, default=0.0, 
                      comment="命中率")
    
    # 来源
    is_auto_generated = Column(Boolean, default=False, 
                               comment="是否为自动生成")
    
    # 多租户
    connection_id = Column(BigInteger, ForeignKey("dbconnection.id", ondelete="CASCADE"), 
                           nullable=False, index=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id", ondelete="SET NULL"), 
                       nullable=True, index=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 约束：同一连接下 name 唯一
    __table_args__ = (
        UniqueConstraint('name', 'connection_id', name='uq_skill_name_connection'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

    # Relationships
    connection = relationship("DBConnection", backref="skills")
    tenant = relationship("Tenant", backref="skills")

    def __repr__(self):
        return f"<Skill(id={self.id}, name='{self.name}', connection_id={self.connection_id})>"
