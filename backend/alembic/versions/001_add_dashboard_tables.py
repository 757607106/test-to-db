"""添加Dashboard相关表

Revision ID: 001_add_dashboard_tables
Revises: 
Create Date: 2024-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '001_add_dashboard_tables'
down_revision = '000_add_users_table'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建dashboards表
    op.create_table(
        'dashboards',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.BigInteger(), nullable=False),
        sa.Column('layout_config', sa.JSON(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_dashboards_owner'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_dashboards_owner_id', 'dashboards', ['owner_id'])
    op.create_index('idx_dashboards_created_at', 'dashboards', ['created_at'])
    op.create_index('idx_dashboards_deleted_at', 'dashboards', ['deleted_at'])

    # 2. 创建dashboard_widgets表
    op.create_table(
        'dashboard_widgets',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('dashboard_id', sa.BigInteger(), nullable=False),
        sa.Column('widget_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('connection_id', sa.BigInteger(), nullable=False),
        sa.Column('query_config', sa.JSON(), nullable=False),
        sa.Column('chart_config', sa.JSON(), nullable=True),
        sa.Column('position_config', sa.JSON(), nullable=False),
        sa.Column('refresh_interval', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_refresh_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('data_cache', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], name='fk_widgets_dashboard', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connection_id'], ['dbconnection.id'], name='fk_widgets_connection'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_widgets_dashboard_id', 'dashboard_widgets', ['dashboard_id'])
    op.create_index('idx_widgets_connection_id', 'dashboard_widgets', ['connection_id'])

    # 3. 创建dashboard_permissions表
    op.create_table(
        'dashboard_permissions',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('dashboard_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('permission_level', sa.String(20), nullable=False),
        sa.Column('granted_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], name='fk_permissions_dashboard', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_permissions_user'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], name='fk_permissions_granted_by'),
        sa.UniqueConstraint('dashboard_id', 'user_id', name='uq_dashboard_user'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_permissions_dashboard_id', 'dashboard_permissions', ['dashboard_id'])
    op.create_index('idx_permissions_user_id', 'dashboard_permissions', ['user_id'])


def downgrade():
    # 按照依赖关系的相反顺序删除表
    op.drop_table('dashboard_permissions')
    op.drop_table('dashboard_widgets')
    op.drop_table('dashboards')
