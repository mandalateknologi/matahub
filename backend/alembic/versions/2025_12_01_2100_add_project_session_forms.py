"""Add project_session_forms table

Revision ID: 4b9a0d3e2f6c
Revises: 3a8f9c2d1e5b
Create Date: 2025-12-01 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4b9a0d3e2f6c'
down_revision = '3a8f9c2d1e5b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create project_session_forms table
    op.create_table(
        'project_session_forms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('form_config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_project_session_forms_project_id')
    )
    op.create_index(op.f('ix_project_session_forms_id'), 'project_session_forms', ['id'], unique=False)
    op.create_index(op.f('ix_project_session_forms_project_id'), 'project_session_forms', ['project_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_project_session_forms_project_id'), table_name='project_session_forms')
    op.drop_index(op.f('ix_project_session_forms_id'), table_name='project_session_forms')
    op.drop_table('project_session_forms')
