"""添加 Schema 管理表

Revision ID: 003_add_schema_tables
Revises: 002_add_llm_and_agent_tables
Create Date: 2026-01-18 13:00:00.000000

表名与模型定义保持一致（类名小写）：
- SchemaTable -> schematable
- SchemaColumn -> schemacolumn
- SchemaRelationship -> schemarelationship
- ValueMapping -> valuemapping
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '003_add_schema_tables'
down_revision = '002_add_llm_and_agent_tables'
branch_labels = None
depends_on = None


def upgrade():
    # 创建 schematable 表（对应 SchemaTable 模型）
    # 注意：使用 BigInteger 以匹配 dbconnection.id 的数据类型
    op.create_table(
        'schematable',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('connection_id', sa.BigInteger(), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ui_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['connection_id'], ['dbconnection.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_schematable_connection', 'schematable', ['connection_id'])
    op.create_index('uq_schematable_conn_name', 'schematable', ['connection_id', 'table_name'], unique=True)
    
    # 创建 schemacolumn 表（对应 SchemaColumn 模型）
    op.create_table(
        'schemacolumn',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('table_id', sa.BigInteger(), nullable=False),
        sa.Column('column_name', sa.String(255), nullable=False),
        sa.Column('data_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_primary_key', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_foreign_key', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_unique', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['table_id'], ['schematable.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_schemacolumn_table', 'schemacolumn', ['table_id'])
    op.create_index('uq_schemacolumn_table_name', 'schemacolumn', ['table_id', 'column_name'], unique=True)
    
    # 创建 schemarelationship 表（对应 SchemaRelationship 模型）
    op.create_table(
        'schemarelationship',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('connection_id', sa.BigInteger(), nullable=False),
        sa.Column('source_table_id', sa.BigInteger(), nullable=False),
        sa.Column('source_column_id', sa.BigInteger(), nullable=False),
        sa.Column('target_table_id', sa.BigInteger(), nullable=False),
        sa.Column('target_column_id', sa.BigInteger(), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['connection_id'], ['dbconnection.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_table_id'], ['schematable.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_column_id'], ['schemacolumn.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_table_id'], ['schematable.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_column_id'], ['schemacolumn.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_schemarelationship_connection', 'schemarelationship', ['connection_id'])
    op.create_index('idx_schemarelationship_source_table', 'schemarelationship', ['source_table_id'])
    op.create_index('idx_schemarelationship_target_table', 'schemarelationship', ['target_table_id'])
    
    # 创建 valuemapping 表（对应 ValueMapping 模型）
    op.create_table(
        'valuemapping',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('column_id', sa.BigInteger(), nullable=False),
        sa.Column('nl_term', sa.String(255), nullable=False),
        sa.Column('db_value', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['column_id'], ['schemacolumn.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_valuemapping_column', 'valuemapping', ['column_id'])
    op.create_index('idx_valuemapping_nl_term', 'valuemapping', ['nl_term'])


def downgrade():
    op.drop_table('valuemapping')
    op.drop_table('schemarelationship')
    op.drop_table('schemacolumn')
    op.drop_table('schematable')
