"""Add tenant_id to dashboards for data isolation

Revision ID: 008_add_tenant_isolation
Revises: 007_add_dashboard_refresh_config
Create Date: 2026-01-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_tenant_isolation'
down_revision: Union[str, None] = '007_add_dashboard_refresh_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tenant_id column to dashboards table for multi-tenant isolation"""
    
    # 1. Add tenant_id to dashboards
    op.add_column('dashboards', sa.Column(
        'tenant_id', 
        sa.BigInteger(), 
        sa.ForeignKey('tenants.id'),
        nullable=True,
        index=True
    ))
    
    # 2. Create index for better query performance
    op.create_index(
        'ix_dashboards_tenant_id',
        'dashboards',
        ['tenant_id']
    )
    
    # 3. Backfill existing dashboards: set tenant_id from owner's tenant_id
    # Using raw SQL for efficiency
    op.execute("""
        UPDATE dashboards d
        SET tenant_id = (
            SELECT u.tenant_id 
            FROM users u 
            WHERE u.id = d.owner_id
        )
        WHERE d.tenant_id IS NULL
    """)


def downgrade() -> None:
    """Remove tenant_id from dashboards"""
    
    op.drop_index('ix_dashboards_tenant_id', table_name='dashboards')
    op.drop_column('dashboards', 'tenant_id')
