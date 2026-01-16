"""add llm and agent tables

Revision ID: 002_add_llm_and_agent_tables
Revises: 001_add_dashboard_tables
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '002_add_llm_and_agent_tables'
down_revision = '001_add_dashboard_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create llm_configuration table
    op.create_table(
        'llm_configuration',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_type', sa.String(length=20), nullable=False, server_default='chat'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_llm_configuration_id', 'id'),
        sa.Index('ix_llm_configuration_provider', 'provider'),
        sa.Index('ix_llm_configuration_model_type', 'model_type'),
        sa.Index('ix_llm_configuration_is_active', 'is_active'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    
    # Create agent_profile table
    op.create_table(
        'agent_profile',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('role_description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('tools', sa.JSON(), nullable=True),
        sa.Column('llm_config_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('is_system', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['llm_config_id'], ['llm_configuration.id'], name='fk_agent_profile_llm_config', ondelete='SET NULL'),
        sa.UniqueConstraint('name', name='uq_agent_profile_name'),
        sa.Index('ix_agent_profile_id', 'id'),
        sa.Index('ix_agent_profile_name', 'name'),
        sa.Index('ix_agent_profile_is_system', 'is_system'),
        sa.Index('ix_agent_profile_is_active', 'is_active'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )


def downgrade():
    op.drop_table('agent_profile')
    op.drop_table('llm_configuration')
