"""add_masks_json_to_prediction_results

Revision ID: add_masks_json_column
Revises: add_recognition_catalog_tables
Create Date: 2025-12-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_masks_json_column'
down_revision = 'add_recognition_catalog_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add masks_json column to prediction_results table for segmentation support."""
    op.add_column('prediction_results', sa.Column('masks_json', JSON, server_default='[]'))


def downgrade() -> None:
    """Remove masks_json column from prediction_results table."""
    op.drop_column('prediction_results', 'masks_json')
