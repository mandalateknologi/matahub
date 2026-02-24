"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e866c3008a65'
down_revision = '7295a9595bf2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop storage_path column from datasets table
    # Datasets are now always stored at {DATA_DIR}/datasets/{id}
    op.drop_column('datasets', 'storage_path')


def downgrade() -> None:
    # Re-add storage_path column if rolling back
    op.add_column('datasets', sa.Column('storage_path', sa.String(512), nullable=True))
