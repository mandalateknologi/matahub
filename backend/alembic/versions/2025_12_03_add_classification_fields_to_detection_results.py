"""add classification fields to detection results

Revision ID: add_classification_fields
Revises: 3553e0d1f869
Create Date: 2025-12-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_classification_fields'
down_revision = '3553e0d1f869'
branch_labels = None
depends_on = None


def upgrade():
    # Add classification-specific columns to detection_results table
    op.add_column('detection_results', sa.Column('top_class', sa.String(255), nullable=True))
    op.add_column('detection_results', sa.Column('top_confidence', sa.Float, nullable=True))
    op.add_column('detection_results', sa.Column('top_classes_json', sa.JSON, nullable=True))
    op.add_column('detection_results', sa.Column('probabilities_json', sa.JSON, nullable=True))
    op.add_column('detection_results', sa.Column('task_type', sa.String(50), nullable=True, server_default='detect'))


def downgrade():
    op.drop_column('detection_results', 'probabilities_json')
    op.drop_column('detection_results', 'top_classes_json')
    op.drop_column('detection_results', 'top_confidence')
    op.drop_column('detection_results', 'top_class')
    op.drop_column('detection_results', 'task_type')
