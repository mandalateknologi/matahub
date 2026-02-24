"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '18b9a39f6956'
down_revision = '053f9f651b66'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add requires_prompts column with default False
    op.add_column('models', sa.Column('requires_prompts', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    
    # Backfill: Set requires_prompts = TRUE for all SAM3 models
    op.execute("UPDATE models SET requires_prompts = TRUE WHERE inference_type = 'sam3'")


def downgrade() -> None:
    # Drop requires_prompts column
    op.drop_column('models', 'requires_prompts')
