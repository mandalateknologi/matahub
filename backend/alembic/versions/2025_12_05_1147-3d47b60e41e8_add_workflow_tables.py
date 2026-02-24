"""Add workflow tables

Revision ID: 3d47b60e41e8
Revises: b67ecc969708
Create Date: 2025-12-05 11:47:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3d47b60e41e8'
down_revision = 'b67ecc969708'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create WorkflowStatus enum
    workflow_status_enum = postgresql.ENUM(
        'pending', 'running', 'paused', 'completed', 'failed', 'cancelled',
        name='workflowstatus', create_type=False
    )
    workflow_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create WorkflowTriggerType enum
    workflow_trigger_enum = postgresql.ENUM(
        'manual', 'schedule', 'event',
        name='workflowtriggertype', create_type=False
    )
    workflow_trigger_enum.create(op.get_bind(), checkfirst=True)
    
    # Create StepStatus enum
    step_status_enum = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'skipped',
        name='stepstatus', create_type=False
    )
    step_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create workflows table
    op.create_table(
        'workflows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trigger_type', workflow_trigger_enum, nullable=False, server_default='manual'),
        sa.Column('trigger_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('nodes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('edges', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('scheduler_job_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflows_project_id'), 'workflows', ['project_id'], unique=False)
    op.create_index(op.f('ix_workflows_creator_id'), 'workflows', ['creator_id'], unique=False)
    op.create_index(op.f('ix_workflows_trigger_type'), 'workflows', ['trigger_type'], unique=False)
    op.create_index(op.f('ix_workflows_is_active'), 'workflows', ['is_active'], unique=False)
    op.create_index(op.f('ix_workflows_is_template'), 'workflows', ['is_template'], unique=False)
    op.create_index(op.f('ix_workflows_created_at'), 'workflows', ['created_at'], unique=False)
    
    # Create workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('status', workflow_status_enum, nullable=False, server_default='pending'),
        sa.Column('trigger_type', workflow_trigger_enum, nullable=False),
        sa.Column('trigger_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_executions_workflow_id'), 'workflow_executions', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_workflow_executions_status'), 'workflow_executions', ['status'], unique=False)
    op.create_index(op.f('ix_workflow_executions_created_at'), 'workflow_executions', ['created_at'], unique=False)
    
    # Create workflow_step_executions table
    op.create_table(
        'workflow_step_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(length=255), nullable=False),
        sa.Column('node_type', sa.String(length=100), nullable=False),
        sa.Column('status', step_status_enum, nullable=False, server_default='pending'),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_step_executions_execution_id'), 'workflow_step_executions', ['execution_id'], unique=False)
    op.create_index(op.f('ix_workflow_step_executions_node_id'), 'workflow_step_executions', ['node_id'], unique=False)
    op.create_index(op.f('ix_workflow_step_executions_status'), 'workflow_step_executions', ['status'], unique=False)


def downgrade() -> None:
    # Drop workflow_step_executions table
    op.drop_index(op.f('ix_workflow_step_executions_status'), table_name='workflow_step_executions')
    op.drop_index(op.f('ix_workflow_step_executions_node_id'), table_name='workflow_step_executions')
    op.drop_index(op.f('ix_workflow_step_executions_execution_id'), table_name='workflow_step_executions')
    op.drop_table('workflow_step_executions')
    
    # Drop workflow_executions table
    op.drop_index(op.f('ix_workflow_executions_created_at'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_status'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_workflow_id'), table_name='workflow_executions')
    op.drop_table('workflow_executions')
    
    # Drop workflows table
    op.drop_index(op.f('ix_workflows_created_at'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_is_template'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_is_active'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_trigger_type'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_creator_id'), table_name='workflows')
    op.drop_index(op.f('ix_workflows_project_id'), table_name='workflows')
    op.drop_table('workflows')
    
    # Drop enums
    sa.Enum(name='stepstatus').drop(op.get_bind())
    sa.Enum(name='workflowtriggertype').drop(op.get_bind())
    sa.Enum(name='workflowstatus').drop(op.get_bind())
