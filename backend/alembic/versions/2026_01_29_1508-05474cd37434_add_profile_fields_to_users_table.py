"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '05474cd37434'
down_revision = '7c81950af2cf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add profile fields to users table
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('profile_image', sa.String(length=512), nullable=True))


def downgrade() -> None:
    # Remove profile fields from users table
    op.drop_column('users', 'profile_image')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
