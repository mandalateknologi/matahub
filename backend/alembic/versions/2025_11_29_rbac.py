"""
Add RBAC: UserRole enum extension, creator_id columns, project_members table, is_active column

Revision ID: 2025_11_29_rbac
Revises: 2025_11_29_1433-8bf5756081bc
Create Date: 2025-11-29 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_11_29_rbac'
down_revision = 'fix_modelstatus_enum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade database schema for RBAC implementation:
    1. Add new UserRole enum values (project_admin, operator)
    2. Add is_active column to users table
    3. Add creator_id columns to datasets, projects, detection_jobs
    4. Add project_id column to detection_jobs
    5. Create project_members association table
    6. Create indexes for performance
    """
    
    # Step 1: Add new enum values using raw SQL (PostgreSQL enum extension)
    # Note: This is a forward-only migration - cannot be rolled back automatically
    op.execute("ALTER TYPE userrole ADD VALUE 'project_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE 'operator'")
    
    # Step 2: Add is_active column to users table
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # Step 3: Add creator_id to datasets table (with default to admin user id=1)
    op.add_column('datasets', sa.Column('creator_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_foreign_key('fk_datasets_creator_id', 'datasets', 'users', ['creator_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_datasets_creator_id', 'datasets', ['creator_id'])
    # Remove server_default after backfill
    op.alter_column('datasets', 'creator_id', server_default=None)
    
    # Step 4: Add creator_id to projects table (with default to admin user id=1)
    op.add_column('projects', sa.Column('creator_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_foreign_key('fk_projects_creator_id', 'projects', 'users', ['creator_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_projects_creator_id', 'projects', ['creator_id'])
    # Remove server_default after backfill
    op.alter_column('projects', 'creator_id', server_default=None)
    
    # Step 5: Add project_id to detection_jobs table (populate from model.project_id)
    # First add as nullable, then populate, then make non-nullable
    op.add_column('detection_jobs', sa.Column('project_id', sa.Integer(), nullable=True))
    
    # Populate project_id from models table
    op.execute("""
        UPDATE detection_jobs 
        SET project_id = models.project_id 
        FROM models 
        WHERE detection_jobs.model_id = models.id
    """)
    
    # Make project_id non-nullable and add foreign key
    op.alter_column('detection_jobs', 'project_id', nullable=False)
    op.create_foreign_key('fk_detection_jobs_project_id', 'detection_jobs', 'projects', ['project_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_detection_jobs_project_id', 'detection_jobs', ['project_id'])
    
    # Step 6: Add creator_id to detection_jobs table (with default to admin user id=1)
    op.add_column('detection_jobs', sa.Column('creator_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_foreign_key('fk_detection_jobs_creator_id', 'detection_jobs', 'users', ['creator_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_detection_jobs_creator_id', 'detection_jobs', ['creator_id'])
    # Remove server_default after backfill
    op.alter_column('detection_jobs', 'creator_id', server_default=None)
    
    # Step 7: Create project_members association table
    op.create_table(
        'project_members',
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('project_id', 'user_id')
    )
    op.create_index('ix_project_members_user_id', 'project_members', ['user_id'])


def downgrade() -> None:
    """
    Downgrade database schema (partial - enum values cannot be automatically removed).
    
    WARNING: PostgreSQL enum values (project_admin, operator) cannot be removed automatically.
    Manual steps required:
    1. Drop foreign keys referencing users table
    2. Drop affected tables
    3. Recreate enum without new values
    4. Restore tables
    """
    
    # Drop project_members table
    op.drop_index('ix_project_members_user_id', 'project_members')
    op.drop_table('project_members')
    
    # Drop creator_id and project_id from detection_jobs
    op.drop_index('ix_detection_jobs_creator_id', 'detection_jobs')
    op.drop_constraint('fk_detection_jobs_creator_id', 'detection_jobs', type_='foreignkey')
    op.drop_column('detection_jobs', 'creator_id')
    
    op.drop_index('ix_detection_jobs_project_id', 'detection_jobs')
    op.drop_constraint('fk_detection_jobs_project_id', 'detection_jobs', type_='foreignkey')
    op.drop_column('detection_jobs', 'project_id')
    
    # Drop creator_id from projects
    op.drop_index('ix_projects_creator_id', 'projects')
    op.drop_constraint('fk_projects_creator_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'creator_id')
    
    # Drop creator_id from datasets
    op.drop_index('ix_datasets_creator_id', 'datasets')
    op.drop_constraint('fk_datasets_creator_id', 'datasets', type_='foreignkey')
    op.drop_column('datasets', 'creator_id')
    
    # Drop is_active from users
    op.drop_column('users', 'is_active')
    
    # Note: Cannot automatically remove enum values 'project_admin' and 'operator'
    # This requires manual database intervention if rollback is needed
