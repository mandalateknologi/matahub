"""add cancelled to predictionstatus enum

Revision ID: add_cancelled_to_status
Revises: add_masks_json_column
Create Date: 2026-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_cancelled_to_status'
down_revision = 'add_masks_json_column'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'cancelled' value to predictionstatus enum if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'predictionstatus') THEN
                ALTER TYPE predictionstatus ADD VALUE IF NOT EXISTS 'cancelled';
            END IF;
        END $$;
    """)
    
    # Add 'cancelled' value to detectionstatus enum if it still exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'detectionstatus') THEN
                ALTER TYPE detectionstatus ADD VALUE IF NOT EXISTS 'cancelled';
            END IF;
        END $$;
    """)


def downgrade():
    # Cannot easily remove enum value in PostgreSQL
    # Would require recreating the enum and updating all references
    pass
