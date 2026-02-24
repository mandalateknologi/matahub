"""Add detection sessions and session exports

Revision ID: 3a8f9c2d1e5b
Revises: 2fe7d1bbf3b3
Create Date: 2025-12-01 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a8f9c2d1e5b'
down_revision = '2fe7d1bbf3b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create SessionStatus enum (check if exists first)
    session_status_enum = postgresql.ENUM('active', 'ended', name='sessionstatus', create_type=False)
    session_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create ExportType enum for session exports
    session_export_type_enum = postgresql.ENUM('mega_report_pdf', 'mega_data_zip', name='sessionexporttype', create_type=False)
    session_export_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create ExportStatus enum for session exports (reuse naming pattern)
    session_export_status_enum = postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='sessionexportstatus', create_type=False)
    session_export_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create detection_sessions table
    op.create_table(
        'detection_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('status', session_status_enum, nullable=False, server_default='active'),
        sa.Column('summary_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_detection_sessions_project_id'), 'detection_sessions', ['project_id'], unique=False)
    op.create_index(op.f('ix_detection_sessions_creator_id'), 'detection_sessions', ['creator_id'], unique=False)
    op.create_index(op.f('ix_detection_sessions_status'), 'detection_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_detection_sessions_created_at'), 'detection_sessions', ['created_at'], unique=False)
    
    # Create session_exports table
    op.create_table(
        'session_exports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('export_type', session_export_type_enum, nullable=False),
        sa.Column('status', session_export_status_enum, nullable=False, server_default='pending'),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['detection_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_exports_session_id'), 'session_exports', ['session_id'], unique=False)
    op.create_index(op.f('ix_session_exports_status'), 'session_exports', ['status'], unique=False)
    
    # Add session_id column to detection_jobs
    op.add_column('detection_jobs', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_detection_jobs_session_id', 'detection_jobs', 'detection_sessions', ['session_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_detection_jobs_session_id'), 'detection_jobs', ['session_id'], unique=False)


def downgrade() -> None:
    # Drop foreign key and index from detection_jobs
    op.drop_index(op.f('ix_detection_jobs_session_id'), table_name='detection_jobs')
    op.drop_constraint('fk_detection_jobs_session_id', 'detection_jobs', type_='foreignkey')
    op.drop_column('detection_jobs', 'session_id')
    
    # Drop session_exports table
    op.drop_index(op.f('ix_session_exports_status'), table_name='session_exports')
    op.drop_index(op.f('ix_session_exports_session_id'), table_name='session_exports')
    op.drop_table('session_exports')
    
    # Drop detection_sessions table
    op.drop_index(op.f('ix_detection_sessions_created_at'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_status'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_creator_id'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_project_id'), table_name='detection_sessions')
    op.drop_table('detection_sessions')
    
    # Drop enums
    sa.Enum(name='sessionexportstatus').drop(op.get_bind())
    sa.Enum(name='sessionexporttype').drop(op.get_bind())
    sa.Enum(name='sessionstatus').drop(op.get_bind())
