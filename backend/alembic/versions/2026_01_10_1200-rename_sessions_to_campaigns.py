"""rename_sessions_to_campaigns

Revision ID: rename_sessions_to_campaigns
Revises: 961025dcf96d
Create Date: 2026-01-10 12:00

This migration completes the campaign terminology normalization:
1. Renames table: prediction_sessions -> prediction_campaigns
2. Renames table: session_exports -> campaign_exports
3. Renames column: prediction_jobs.session_id -> campaign_id
4. Renames column: campaign_exports.session_id -> campaign_id
5. Updates all foreign key constraints
6. Renames all associated indexes (7 total)

This is a metadata-only change with no data transformation.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_sessions_to_campaigns'
down_revision = '961025dcf96d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Rename main table prediction_sessions -> prediction_campaigns
    op.rename_table('prediction_sessions', 'prediction_campaigns')
    
    # Step 2: Rename indexes for prediction_campaigns table
    op.execute('ALTER INDEX IF EXISTS ix_prediction_sessions_id RENAME TO ix_prediction_campaigns_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_sessions_playbook_id RENAME TO ix_prediction_campaigns_playbook_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_sessions_creator_id RENAME TO ix_prediction_campaigns_creator_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_sessions_status RENAME TO ix_prediction_campaigns_status')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_sessions_created_at RENAME TO ix_prediction_campaigns_created_at')
    
    # Step 3: Rename session_exports table -> campaign_exports
    op.rename_table('session_exports', 'campaign_exports')
    
    # Step 4: Rename column in campaign_exports: session_id -> campaign_id
    op.alter_column('campaign_exports', 'session_id', new_column_name='campaign_id')
    
    # Step 5: Rename indexes for campaign_exports table
    op.execute('ALTER INDEX IF EXISTS ix_session_exports_session_id RENAME TO ix_campaign_exports_campaign_id')
    op.execute('ALTER INDEX IF EXISTS ix_session_exports_status RENAME TO ix_campaign_exports_status')
    
    # Step 6: Rename column in prediction_jobs: session_id -> campaign_id
    op.alter_column('prediction_jobs', 'session_id', new_column_name='campaign_id')
    
    # Step 7: Rename index for prediction_jobs.campaign_id
    op.execute('ALTER INDEX IF EXISTS ix_prediction_jobs_session_id RENAME TO ix_prediction_jobs_campaign_id')
    
    # Note: Foreign key constraints are automatically updated by PostgreSQL when tables/columns are renamed
    # Constraint names may remain as-is or can be explicitly renamed if needed for clarity


def downgrade() -> None:
    # Reverse all changes in opposite order
    
    # Step 1: Rename index back
    op.execute('ALTER INDEX IF EXISTS ix_prediction_jobs_campaign_id RENAME TO ix_prediction_jobs_session_id')
    
    # Step 2: Rename column back in prediction_jobs
    op.alter_column('prediction_jobs', 'campaign_id', new_column_name='session_id')
    
    # Step 3: Rename indexes back for campaign_exports
    op.execute('ALTER INDEX IF EXISTS ix_campaign_exports_status RENAME TO ix_session_exports_status')
    op.execute('ALTER INDEX IF EXISTS ix_campaign_exports_campaign_id RENAME TO ix_session_exports_session_id')
    
    # Step 4: Rename column back in campaign_exports
    op.alter_column('campaign_exports', 'campaign_id', new_column_name='session_id')
    
    # Step 5: Rename table back
    op.rename_table('campaign_exports', 'session_exports')
    
    # Step 6: Rename indexes back for prediction_sessions
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_created_at RENAME TO ix_prediction_sessions_created_at')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_status RENAME TO ix_prediction_sessions_status')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_creator_id RENAME TO ix_prediction_sessions_creator_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_playbook_id RENAME TO ix_prediction_sessions_playbook_id')
    op.execute('ALTER INDEX IF EXISTS ix_prediction_campaigns_id RENAME TO ix_prediction_sessions_id')
    
    # Step 7: Rename main table back
    op.rename_table('prediction_campaigns', 'prediction_sessions')
