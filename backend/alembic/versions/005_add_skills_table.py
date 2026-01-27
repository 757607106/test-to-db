"""add skills table

Revision ID: 005_add_skills_table
Revises: 004_add_system_config
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '005_add_skills_table'
down_revision = '004_add_system_config'
branch_labels = None
depends_on = None


def upgrade():
    # Create skills table
    op.create_table(
        'skills',
        # 主键
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        
        # 基础信息
        sa.Column('name', sa.String(length=50), nullable=False, comment='Skill 标识'),
        sa.Column('display_name', sa.String(length=100), nullable=False, comment='显示名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='Skill 描述'),
        
        # 路由配置
        sa.Column('keywords', sa.JSON(), nullable=True, comment='关键词列表'),
        sa.Column('intent_examples', sa.JSON(), nullable=True, comment='意图示例'),
        
        # Schema 关联
        sa.Column('table_patterns', sa.JSON(), nullable=True, comment='表名匹配模式'),
        sa.Column('table_names', sa.JSON(), nullable=True, comment='关联表名列表'),
        
        # 业务配置
        sa.Column('business_rules', sa.Text(), nullable=True, comment='业务规则'),
        sa.Column('common_patterns', sa.JSON(), nullable=True, comment='常用查询模式'),
        
        # 配置
        sa.Column('priority', sa.Integer(), nullable=False, default=0, comment='优先级'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否启用'),
        sa.Column('icon', sa.String(length=50), nullable=True, comment='图标'),
        sa.Column('color', sa.String(length=20), nullable=True, comment='主题色'),
        
        # 统计
        sa.Column('usage_count', sa.Integer(), nullable=False, default=0, comment='使用次数'),
        sa.Column('hit_rate', sa.Float(), nullable=False, default=0.0, comment='命中率'),
        
        # 来源
        sa.Column('is_auto_generated', sa.Boolean(), nullable=False, default=False, comment='是否自动生成'),
        
        # 多租户
        sa.Column('connection_id', sa.BigInteger(), sa.ForeignKey('dbconnection.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        
        # 时间戳
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        
        # 主键约束
        sa.PrimaryKeyConstraint('id'),
        
        # 唯一约束：同一连接下 name 唯一
        sa.UniqueConstraint('name', 'connection_id', name='uq_skill_name_connection'),
        
        # 字符集
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    
    # 创建索引
    op.create_index('ix_skills_id', 'skills', ['id'])
    op.create_index('ix_skills_name', 'skills', ['name'])
    op.create_index('ix_skills_connection_id', 'skills', ['connection_id'])
    op.create_index('ix_skills_tenant_id', 'skills', ['tenant_id'])
    op.create_index('ix_skills_is_active', 'skills', ['is_active'])


def downgrade():
    # 删除索引
    op.drop_index('ix_skills_is_active', table_name='skills')
    op.drop_index('ix_skills_tenant_id', table_name='skills')
    op.drop_index('ix_skills_connection_id', table_name='skills')
    op.drop_index('ix_skills_name', table_name='skills')
    op.drop_index('ix_skills_id', table_name='skills')
    
    # 删除表
    op.drop_table('skills')
