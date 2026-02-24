"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b67ecc969708'
down_revision = 'add_classification_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add error_message column to session_exports table
    op.add_column('session_exports', sa.Column('error_message', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    # Remove error_message column from session_exports table
    op.drop_column('session_exports', 'error_message')
