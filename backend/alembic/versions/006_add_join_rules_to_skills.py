"""add join_rules column to skills table

Revision ID: 006_add_join_rules_to_skills
Revises: 005_add_skills_table
Create Date: 2026-01-27

Skill-Centric 架构重构:
- 将 JOIN 规则从独立的 Neo4j JoinRule 节点迁移到 Skill.join_rules 字段
- 简化数据模型，减少 Neo4j 依赖
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_join_rules_to_skills'
down_revision = '005_add_skills_table'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 join_rules JSON 列到 skills 表
    op.add_column(
        'skills',
        sa.Column(
            'join_rules', 
            sa.JSON(), 
            nullable=True, 
            comment='JOIN 规则列表，格式: [{left_table, left_column, right_table, right_column, join_type, description}]'
        )
    )


def downgrade():
    # 删除 join_rules 列
    op.drop_column('skills', 'join_rules')
