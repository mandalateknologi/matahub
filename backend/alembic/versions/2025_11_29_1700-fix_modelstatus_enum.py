"""Add lowercase enum values to modelstatus

Revision ID: fix_modelstatus_enum
Revises: 8bf5756081bc
Create Date: 2025-11-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_modelstatus_enum'
down_revision = '8bf5756081bc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lowercase versions of all enum values
    op.execute("ALTER TYPE modelstatus ADD VALUE IF NOT EXISTS 'pending'")
    op.execute("ALTER TYPE modelstatus ADD VALUE IF NOT EXISTS 'training'")
    op.execute("ALTER TYPE modelstatus ADD VALUE IF NOT EXISTS 'ready'")
    op.execute("ALTER TYPE modelstatus ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL
    pass
