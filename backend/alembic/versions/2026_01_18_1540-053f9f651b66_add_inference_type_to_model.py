"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '053f9f651b66'
down_revision = 'f89090070cdc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add inference_type column with default value 'yolo'
    op.add_column('models', sa.Column('inference_type', sa.String(length=50), nullable=False, server_default='yolo'))
    
    # Update existing SAM3 models to have inference_type='sam3'
    op.execute("UPDATE models SET inference_type = 'sam3' WHERE base_type = 'sam3'")


def downgrade() -> None:
    # Remove inference_type column
    op.drop_column('models', 'inference_type')
