"""
Workflow Models - Automation workflows for ATVISION
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class WorkflowStatus(str, enum.Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTriggerType(str, enum.Enum):
    """Workflow trigger types"""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    API = "api"  # External API calls with API key
    EVENT = "event"  # Internal workflow-to-workflow


class StepStatus(str, enum.Enum):
    """Individual step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Workflow(Base):
    """Workflow definition with nodes and edges."""
    
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    is_template = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    trigger_type = Column(
        Enum(WorkflowTriggerType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=WorkflowTriggerType.MANUAL,
        server_default="manual",
        index=True
    )
    trigger_config = Column(JSONB, nullable=False, default=dict, server_default='{}')  # {cron, event_filters}
    nodes = Column(JSONB, nullable=False, default=list, server_default='[]')  # [{id, type, data, position}]
    edges = Column(JSONB, nullable=False, default=list, server_default='[]')  # [{id, source, target}]
    scheduler_job_id = Column(String(255), nullable=True)  # APScheduler job ID for cleanup
    api_enabled = Column(Boolean, nullable=False, default=False, server_default="false")  # Enable API trigger access
    api_rate_limit_override = Column(Integer, nullable=True)  # Per-workflow rate limit (calls/min)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[creator_id])
    executions = relationship(
        "WorkflowExecution",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowExecution.created_at.desc()"
    )
    api_calls = relationship(
        "WorkflowApiCall",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowApiCall.called_at.desc()"
    )
    
    @property
    def last_execution(self):
        """Get most recent execution."""
        return self.executions[0] if self.executions else None


class WorkflowExecution(Base):
    """Workflow execution instance with runtime state."""
    
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum(WorkflowStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=WorkflowStatus.PENDING,
        server_default="pending",
        index=True
    )
    trigger_type = Column(
        Enum(WorkflowTriggerType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    trigger_data = Column(JSONB, nullable=False, default=dict, server_default='{}')  # Trigger-specific metadata
    context = Column(JSONB, nullable=False, default=dict, server_default='{}')  # Shared data between steps
    progress = Column(Integer, nullable=False, default=0, server_default='0')  # 0-100
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    step_executions = relationship(
        "WorkflowStepExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowStepExecution.created_at"
    )
    
    @property
    def duration(self):
        """Calculate execution duration."""
        if not self.started_at:
            return None
        end = self.completed_at or func.now()
        return (end - self.started_at).total_seconds()


class WorkflowStepExecution(Base):
    """Individual node execution within a workflow run."""
    
    __tablename__ = "workflow_step_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(255), nullable=False, index=True)  # From workflow.nodes[].id
    node_type = Column(String(100), nullable=False)  # e.g., "train_model", "send_email"
    status = Column(
        Enum(StepStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=StepStatus.PENDING,
        server_default="pending",
        index=True
    )
    input_data = Column(JSONB, nullable=False, default=dict, server_default='{}')  # Node config + context
    output_data = Column(JSONB, nullable=False, default=dict, server_default='{}')  # Results to pass to next nodes
    error_message = Column(Text, nullable=True)
    job_id = Column(Integer, nullable=True)  # Link to TrainingJob/DetectionJob/ExportJob
    job_type = Column(String(50), nullable=True)  # "training", "detection", "export"
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="step_executions")
    
    @property
    def duration(self):
        """Calculate step duration."""
        if not self.started_at:
            return None
        end = self.completed_at or func.now()
        return (end - self.started_at).total_seconds()


class WorkflowApiCall(Base):
    """Workflow API call tracking for rate limiting and analytics."""
    
    __tablename__ = "workflow_api_calls"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True)
    called_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="api_calls")
    user = relationship("User", foreign_keys=[user_id])
    execution = relationship("WorkflowExecution", foreign_keys=[execution_id])

