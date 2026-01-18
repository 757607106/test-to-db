"""添加用户表

Revision ID: 000_add_users_table
Revises: 
Create Date: 2024-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '000_add_users_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 创建dbconnection表（必须在其他表之前创建，因为其他表会引用它）
    op.create_table(
        'dbconnection',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('db_type', sa.String(50), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('password_encrypted', sa.String(255), nullable=False),
        sa.Column('database_name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_dbconnection_name', 'dbconnection', ['name'], unique=True)
    
    # 创建users表
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_users_username', 'users', ['username'], unique=True)
    op.create_index('idx_users_email', 'users', ['email'], unique=True)


def downgrade():
    op.drop_table('users')
    op.drop_table('dbconnection')
