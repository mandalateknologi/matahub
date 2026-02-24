"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c5d7256c64'
down_revision = '05474cd37434'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add description and tags columns to models table
    op.add_column('models', sa.Column('description', sa.String(length=1000), nullable=True))
    op.add_column('models', sa.Column('tags', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove description and tags columns from models table
    op.drop_column('models', 'tags')
    op.drop_column('models', 'description')
