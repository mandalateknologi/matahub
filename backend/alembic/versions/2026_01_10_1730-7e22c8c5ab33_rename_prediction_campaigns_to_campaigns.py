"""rename_prediction_campaigns_to_campaigns

Revision ID: 7e22c8c5ab33
Revises: rename_sessions_to_campaigns
Create Date: 2026-01-10 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e22c8c5ab33'
down_revision = 'rename_sessions_to_campaigns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename table from prediction_campaigns to campaigns
    op.rename_table('prediction_campaigns', 'campaigns')
    
    # Rename indexes
    op.execute('ALTER INDEX IF EXISTS prediction_campaigns_pkey RENAME TO campaigns_pkey')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_creator_id RENAME TO ix_campaigns_creator_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_id RENAME TO ix_campaigns_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_playbook_id RENAME TO ix_campaigns_playbook_id')
    
    # Update foreign key constraints
    # Note: Foreign keys in prediction_jobs and campaign_exports will automatically reference the renamed table


def downgrade() -> None:
    # Rename table back
    op.rename_table('campaigns', 'prediction_campaigns')
    
    # Rename indexes back
    op.execute('ALTER INDEX IF EXISTS campaigns_pkey RENAME TO prediction_campaigns_pkey')
    op.execute('ALTER INDEX IF EXISTS ix_campaigns_creator_id RENAME TO ix_prediction_campaigns_creator_id')
    op.execute('ALTER INDEX IF EXISTS ix_campaigns_id RENAME TO ix_prediction_campaigns_id')
    op.execute('ALTER INDEX IF EXISTS ix_campaigns_playbook_id RENAME TO ix_prediction_campaigns_playbook_id')
