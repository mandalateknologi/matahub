"""
Initial database schema

Revision ID: 001
Create Date: 2025-11-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'user', name='userrole'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    
    # Create datasets table
    op.create_table(
        'datasets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('storage_path', sa.String(512), nullable=False),
        sa.Column('images_count', sa.Integer(), nullable=True),
        sa.Column('labels_count', sa.Integer(), nullable=True),
        sa.Column('classes_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_datasets_id'), 'datasets', ['id'], unique=False)
    op.create_index(op.f('ix_datasets_name'), 'datasets', ['name'], unique=False)
    
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('status', sa.Enum('created', 'training', 'trained', 'failed', name='projectstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)
    
    # Create models table
    op.create_table(
        'models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_type', sa.String(50), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'training', 'ready', 'failed', name='modelstatus'), nullable=False),
        sa.Column('artifact_path', sa.String(512), nullable=True),
        sa.Column('metrics_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_models_id'), 'models', ['id'], unique=False)
    op.create_index(op.f('ix_models_name'), 'models', ['name'], unique=False)
    
    # Create training_jobs table
    op.create_table(
        'training_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='trainingstatus'), nullable=False),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('current_epoch', sa.Integer(), nullable=True),
        sa.Column('total_epochs', sa.Integer(), nullable=True),
        sa.Column('logs_path', sa.String(512), nullable=True),
        sa.Column('metrics_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(1024), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_jobs_id'), 'training_jobs', ['id'], unique=False)
    
    # Create detection_jobs table
    op.create_table(
        'detection_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.Enum('single', 'batch', 'video', 'rtsp', name='detectionmode'), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_ref', sa.String(512), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', name='detectionstatus'), nullable=False),
        sa.Column('summary_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_detection_jobs_id'), 'detection_jobs', ['id'], unique=False)
    
    # Create detection_results table
    op.create_table(
        'detection_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('detection_job_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=True),
        sa.Column('boxes_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('scores_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('classes_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('class_names_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['detection_job_id'], ['detection_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_detection_results_id'), 'detection_results', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('detection_results')
    op.drop_table('detection_jobs')
    op.drop_table('training_jobs')
    op.drop_table('models')
    op.drop_table('projects')
    op.drop_table('datasets')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS detectionstatus')
    op.execute('DROP TYPE IF EXISTS detectionmode')
    op.execute('DROP TYPE IF EXISTS trainingstatus')
    op.execute('DROP TYPE IF EXISTS modelstatus')
    op.execute('DROP TYPE IF EXISTS projectstatus')
    op.execute('DROP TYPE IF EXISTS userrole')
