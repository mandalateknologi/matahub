"""
Remove project_id from workflows table

Revision ID: f89090070cdc
Revises: 7e22c8c5ab33
Create Date: 2026-01-17 15:17

Workflows are now creator-based only. Project references removed entirely.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f89090070cdc'
down_revision = '7e22c8c5ab33'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop foreign key constraint first
    op.drop_constraint('workflows_project_id_fkey', 'workflows', type_='foreignkey')
    
    # Drop the project_id column
    op.drop_column('workflows', 'project_id')


def downgrade() -> None:
    # Add back project_id column
    op.add_column('workflows', sa.Column('project_id', sa.Integer(), nullable=True))
    
    # Recreate foreign key constraint
    op.create_foreign_key('workflows_project_id_fkey', 'workflows', 'projects', ['project_id'], ['id'], ondelete='CASCADE')
    
    # Note: Cannot restore NOT NULL constraint as data would be null after downgrade
