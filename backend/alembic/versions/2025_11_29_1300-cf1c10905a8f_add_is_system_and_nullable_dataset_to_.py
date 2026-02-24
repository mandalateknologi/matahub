"""
Add is_system column and make dataset_id nullable in projects table
Also add CASCADE delete to model and training_job foreign keys
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf1c10905a8f'
down_revision = 'e866c3008a65'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_system column to projects table
    op.add_column('projects', sa.Column('is_system', sa.Boolean(), nullable=True))
    
    # Set default value for existing rows
    op.execute("UPDATE projects SET is_system = FALSE WHERE is_system IS NULL")
    
    # Make is_system NOT NULL
    op.alter_column('projects', 'is_system', nullable=False)
    
    # Make dataset_id nullable in projects table
    op.alter_column('projects', 'dataset_id', nullable=True)
    
    # Drop existing foreign key constraints and recreate with CASCADE
    # Models table
    op.drop_constraint('models_project_id_fkey', 'models', type_='foreignkey')
    op.create_foreign_key(
        'models_project_id_fkey', 
        'models', 'projects', 
        ['project_id'], ['id'], 
        ondelete='CASCADE'
    )
    
    # Training jobs table
    op.drop_constraint('training_jobs_project_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key(
        'training_jobs_project_id_fkey', 
        'training_jobs', 'projects', 
        ['project_id'], ['id'], 
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Remove CASCADE from foreign keys
    op.drop_constraint('training_jobs_project_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key(
        'training_jobs_project_id_fkey', 
        'training_jobs', 'projects', 
        ['project_id'], ['id']
    )
    
    op.drop_constraint('models_project_id_fkey', 'models', type_='foreignkey')
    op.create_foreign_key(
        'models_project_id_fkey', 
        'models', 'projects', 
        ['project_id'], ['id']
    )
    
    # Make dataset_id NOT NULL again
    op.alter_column('projects', 'dataset_id', nullable=False)
    
    # Drop is_system column
    op.drop_column('projects', 'is_system')
