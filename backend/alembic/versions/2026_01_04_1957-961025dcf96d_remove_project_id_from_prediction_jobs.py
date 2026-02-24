"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '961025dcf96d'
down_revision = 'ae3b2ea96a78'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop foreign key constraint first (using original detection_jobs naming)
    op.drop_constraint('fk_detection_jobs_project_id', 'prediction_jobs', type_='foreignkey')
    
    # Drop index on project_id (use prediction_jobs naming for index)
    op.drop_index('ix_prediction_jobs_project_id', table_name='prediction_jobs')
    
    # Drop the project_id column
    op.drop_column('prediction_jobs', 'project_id')


def downgrade() -> None:
    # Re-add the project_id column
    op.add_column('prediction_jobs', sa.Column('project_id', sa.Integer(), nullable=False))
    
    # Re-create index (use prediction_jobs naming for index)
    op.create_index('ix_prediction_jobs_project_id', 'prediction_jobs', ['project_id'])
    
    # Re-create foreign key constraint (using original detection_jobs naming)
    op.create_foreign_key('fk_detection_jobs_project_id', 'prediction_jobs', 'projects', ['project_id'], ['id'], ondelete='CASCADE')
