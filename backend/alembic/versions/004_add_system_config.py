"""add system_config table

Revision ID: 004_add_system_config
Revises: 003_add_schema_tables
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '004_add_system_config'
down_revision = '003_add_schema_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key', name='uq_system_config_key'),
        sa.Index('ix_system_config_id', 'id'),
        sa.Index('ix_system_config_key', 'config_key'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    
    # Insert default configuration for embedding model
    op.execute(
        """
        INSERT INTO system_config (config_key, config_value, description) 
        VALUES ('default_embedding_model_id', NULL, '默认Embedding模型的LLM配置ID')
        """
    )


def downgrade():
    op.drop_table('system_config')
