"""
Workflow Schemas - Request/Response models for workflow API
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.workflow import WorkflowStatus, WorkflowTriggerType, StepStatus


# ============================================================================
# Node & Edge Schemas
# ============================================================================

class NodePosition(BaseModel):
    """Position of node in visual editor."""
    x: float
    y: float


class NodeData(BaseModel):
    """Generic node data container."""
    label: str
    config: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "allow"}  # Allow additional fields


class WorkflowNode(BaseModel):
    """Workflow node definition."""
    id: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=100)
    data: NodeData
    position: NodePosition


class WorkflowEdge(BaseModel):
    """Workflow edge definition."""
    id: str = Field(..., min_length=1, max_length=255)
    source: str = Field(..., min_length=1, max_length=255)
    target: str = Field(..., min_length=1, max_length=255)
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


# ============================================================================
# Workflow CRUD Schemas
# ============================================================================

class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[WorkflowTriggerType] = None  # Deprecated: use trigger nodes instead
    trigger_config: Optional[Dict[str, Any]] = None  # Deprecated: use trigger node config instead
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    is_active: bool = True
    is_template: bool = False
    
    @field_validator('nodes')
    @classmethod
    def validate_nodes(cls, nodes: List[WorkflowNode]) -> List[WorkflowNode]:
        """Validate at least one trigger node exists."""
        if not nodes:
            return nodes
        
        trigger_types = {'manual_trigger', 'schedule_trigger', 'event_trigger', 'api_trigger'}
        has_trigger = any(node.type in trigger_types for node in nodes)
        
        if not has_trigger:
            raise ValueError("Workflow must have at least one trigger node")
        
        return nodes
    
    @field_validator('edges')
    @classmethod
    def validate_edges(cls, edges: List[WorkflowEdge]) -> List[WorkflowEdge]:
        """Validate edges reference valid nodes."""
        if not edges:
            return edges
        
        # Note: Full validation done in API layer with node access
        return edges


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[WorkflowTriggerType] = None
    trigger_config: Optional[Dict[str, Any]] = None
    nodes: Optional[List[WorkflowNode]] = None
    edges: Optional[List[WorkflowEdge]] = None
    is_active: Optional[bool] = None
    api_enabled: Optional[bool] = None
    api_rate_limit_override: Optional[int] = Field(None, gt=0, description="Override global rate limit (calls/minute)")


class WorkflowResponse(BaseModel):
    """Schema for workflow response."""
    id: int
    name: str
    description: Optional[str]
    creator_id: int
    is_active: bool
    is_template: bool
    trigger_type: Optional[WorkflowTriggerType] = None  # Deprecated: use trigger nodes instead
    trigger_config: Optional[Dict[str, Any]] = None  # Deprecated: use trigger node config instead
    nodes: List[Dict[str, Any]]  # Raw JSONB
    edges: List[Dict[str, Any]]  # Raw JSONB
    scheduler_job_id: Optional[str]
    api_enabled: bool = False
    api_rate_limit_override: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    """Schema for workflow list item."""
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    is_template: bool
    trigger_type: WorkflowTriggerType
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    nodes_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_execution_status: Optional[WorkflowStatus] = None
    last_execution_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


# ============================================================================
# Execution Schemas
# ============================================================================

class WorkflowTrigger(BaseModel):
    """Schema for manually triggering a workflow."""
    trigger_data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResponse(BaseModel):
    """Schema for workflow execution response."""
    id: int
    workflow_id: int
    status: WorkflowStatus
    trigger_type: WorkflowTriggerType
    trigger_data: Dict[str, Any]
    context: Dict[str, Any]
    progress: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class WorkflowStepExecutionResponse(BaseModel):
    """Schema for workflow step execution response."""
    id: int
    execution_id: int
    node_id: str
    node_type: str
    status: StepStatus
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str]
    job_id: Optional[int]
    job_type: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class WorkflowExecutionDetailResponse(BaseModel):
    """Schema for detailed execution with steps."""
    execution: WorkflowExecutionResponse
    steps: List[WorkflowStepExecutionResponse]
    workflow_name: str


# ============================================================================
# Template Schemas
# ============================================================================

class WorkflowTemplate(BaseModel):
    """Schema for workflow template."""
    id: int
    name: str
    description: Optional[str]
    trigger_type: WorkflowTriggerType
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class WorkflowTemplateCreate(BaseModel):
    """Schema for creating workflow from template."""
    template_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


# ============================================================================
# Statistics & Analytics
# ============================================================================

class WorkflowStats(BaseModel):
    """Workflow execution statistics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_duration_seconds: Optional[float]
    last_execution_at: Optional[datetime]
    success_rate: float


class WorkflowAnalytics(BaseModel):
    """Workflow analytics response."""
    workflow_id: int
    workflow_name: str
    stats: WorkflowStats
    recent_executions: List[WorkflowExecutionResponse]
