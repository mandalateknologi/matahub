"""add chats_json to prediction_results

Revision ID: 7c81950af2cf
Revises: add_config_json_only
Create Date: 2026-01-23 15:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c81950af2cf'
down_revision = 'add_config_json_only'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add chats_json column to prediction_results table
    op.add_column('prediction_results', sa.Column('chats_json', sa.JSON(), nullable=True, comment='LLM chat outputs and vision-language model responses (reserved for future use)'))


def downgrade() -> None:
    # Remove chats_json column from prediction_results table
    op.drop_column('prediction_results', 'chats_json')
