"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3553e0d1f869'
down_revision = '4b9a0d3e2f6c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add task_type column with default 'detect' for existing models
    op.add_column('models', sa.Column('task_type', sa.String(50), nullable=False, server_default='detect'))
    
    # Remove server default after column creation (keep nullable=False)
    op.alter_column('models', 'task_type', server_default=None)


def downgrade() -> None:
    op.drop_column('models', 'task_type')
