"""
Add progress field to detection_jobs table

Revision ID: 2025_11_30_progress
Revises: 2025_11_29_rbac
Create Date: 2025-11-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2025_11_30_progress'
down_revision = '2025_11_29_rbac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add progress column to detection_jobs table."""
    op.add_column('detection_jobs', sa.Column('progress', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    """Remove progress column from detection_jobs table."""
    op.drop_column('detection_jobs', 'progress')
