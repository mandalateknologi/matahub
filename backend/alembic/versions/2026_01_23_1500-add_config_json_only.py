"""add config_json to prediction_results

Revision ID: add_config_json_only
Revises: 8e189e03c757
Create Date: 2026-01-23 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_config_json_only'
down_revision = '8e189e03c757'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add config_json column to prediction_results table
    op.add_column('prediction_results', sa.Column('config_json', sa.JSON(), nullable=True, comment='Inference configuration used for this result'))


def downgrade() -> None:
    # Remove config_json column from prediction_results table
    op.drop_column('prediction_results', 'config_json')
