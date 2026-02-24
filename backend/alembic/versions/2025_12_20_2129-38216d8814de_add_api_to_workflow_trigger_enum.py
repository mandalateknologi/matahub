"""add_api_to_workflow_trigger_enum

Revision ID: 38216d8814de
Revises: acd4d88a1c50
Create Date: 2025-12-20 21:29:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '38216d8814de'
down_revision = 'acd4d88a1c50'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'api' value to WorkflowTriggerType enum
    op.execute("ALTER TYPE workflowtriggertype ADD VALUE IF NOT EXISTS 'api'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type which is complex
    # For now, we'll leave the enum value in place on downgrade
    pass
