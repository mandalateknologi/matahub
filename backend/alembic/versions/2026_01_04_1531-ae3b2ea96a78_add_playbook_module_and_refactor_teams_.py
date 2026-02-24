"""add_playbook_module_and_refactor_teams_forms

Revision ID: ae3b2ea96a78
Revises: add_cancelled_to_status
Create Date: 2026-01-04 15:31

This migration:
1. Adds SUPER_ADMIN role to user roles enum - DEFERRED use admin
2. Creates playbooks table
3. Renames project_members -> playbook_members (with playbook_id FK)
4. Renames project_session_forms -> playbook_session_forms (with playbook_id FK)
5. Creates playbook_models join table
6. Updates prediction_sessions to use playbook_id instead of project_id
7. Migrates data: Creates one Playbook per Project, copies teams and forms

WARNING: This is a ONE-WAY migration. Backup database before running!
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'ae3b2ea96a78'
down_revision = 'add_cancelled_to_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add SUPER_ADMIN to UserRole enum - DEFERRED use admin instead.
    # 2. Create playbooks table
    op.create_table(
        'playbooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='RESTRICT')
    )
    op.create_index('ix_playbooks_id', 'playbooks', ['id'])
    op.create_index('ix_playbooks_name', 'playbooks', ['name'])
    op.create_index('ix_playbooks_creator_id', 'playbooks', ['creator_id'])
    
    # 3. Create playbook_members table (new structure)
    op.create_table(
        'playbook_members',
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('playbook_id', 'user_id'),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'])
    )
    op.create_index('ix_playbook_members_user_id', 'playbook_members', ['user_id'])
    
    # 4. Create playbook_session_forms table (new structure)
    op.create_table(
        'playbook_session_forms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('form_config_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT')
    )
    op.create_index('ix_playbook_session_forms_id', 'playbook_session_forms', ['id'])
    op.create_index('ix_playbook_session_forms_playbook_id', 'playbook_session_forms', ['playbook_id'], unique=True)
    
    # 5. Create playbook_models join table
    op.create_table(
        'playbook_models',
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('playbook_id', 'model_id'),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'])
    )
    op.create_index('ix_playbook_models_model_id', 'playbook_models', ['model_id'])
    
    # 6. DATA MIGRATION: Create one Playbook per Project
    op.execute("""
        INSERT INTO playbooks (name, description, creator_id, created_at, updated_at)
        SELECT 
            name || ' Playbook' as name,
            'Auto-migrated from project: ' || name as description,
            creator_id,
            created_at,
            created_at as updated_at
        FROM projects
    """)
    
    # 7. DATA MIGRATION: Copy project_members to playbook_members
    op.execute("""
        INSERT INTO playbook_members (playbook_id, user_id, added_by, added_at)
        SELECT 
            p.id as playbook_id,
            pm.user_id,
            pm.added_by,
            pm.added_at
        FROM project_members pm
        JOIN projects proj ON pm.project_id = proj.id
        JOIN playbooks p ON p.name = proj.name || ' Playbook'
    """)
    
    # 8. DATA MIGRATION: Copy project_session_forms to playbook_session_forms
    op.execute("""
        INSERT INTO playbook_session_forms (playbook_id, form_config_json, created_by, created_at, updated_at)
        SELECT 
            p.id as playbook_id,
            psf.form_config_json::text,
            psf.created_by,
            psf.created_at,
            psf.updated_at
        FROM project_session_forms psf
        JOIN projects proj ON psf.project_id = proj.id
        JOIN playbooks p ON p.name = proj.name || ' Playbook'
    """)
    
    # 9. DATA MIGRATION: Copy project models to playbook_models
    op.execute("""
        INSERT INTO playbook_models (playbook_id, model_id, added_by, added_at)
        SELECT 
            p.id as playbook_id,
            m.id as model_id,
            proj.creator_id as added_by,
            m.created_at as added_at
        FROM models m
        JOIN projects proj ON m.project_id = proj.id
        JOIN playbooks p ON p.name = proj.name || ' Playbook'
    """)
    
    # 10. Add playbook_id column to prediction_sessions
    op.add_column('prediction_sessions', sa.Column('playbook_id', sa.Integer(), nullable=True))
    
    # 11. DATA MIGRATION: Set playbook_id based on project_id
    op.execute("""
        UPDATE prediction_sessions ps
        SET playbook_id = p.id
        FROM projects proj
        JOIN playbooks p ON p.name = proj.name || ' Playbook'
        WHERE ps.project_id = proj.id
    """)
    
    # 12. Make playbook_id NOT NULL and add FK constraint
    op.alter_column('prediction_sessions', 'playbook_id', nullable=False)
    op.create_foreign_key('fk_prediction_sessions_playbook_id', 'prediction_sessions', 'playbooks', ['playbook_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_prediction_sessions_playbook_id', 'prediction_sessions', ['playbook_id'])
    
    # 13. Drop old project_id from prediction_sessions
    # Try both possible constraint names (detection_sessions and prediction_sessions)
    try:
        op.drop_constraint('detection_sessions_project_id_fkey', 'prediction_sessions', type_='foreignkey')
    except:
        op.drop_constraint('prediction_sessions_project_id_fkey', 'prediction_sessions', type_='foreignkey')
    op.drop_index('ix_prediction_sessions_project_id', table_name='prediction_sessions')
    op.drop_column('prediction_sessions', 'project_id')
    
    # 14. Drop old project_members and project_session_forms tables
    op.drop_table('project_members')
    op.drop_table('project_session_forms')


def downgrade() -> None:
    # This migration is ONE-WAY only due to data transformation complexity
    # Restore from backup if rollback is needed
    raise NotImplementedError("This migration is one-way only. Restore from database backup to rollback.")
