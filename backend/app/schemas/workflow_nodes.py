"""
Workflow Node Configuration Schemas
Defines validation schemas for each node type's configuration
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


# ============================================================================
# Shared Enums
# ============================================================================

class InputMode(str, Enum):
    """Input modes for detection."""
    SINGLE = "single"
    BATCH = "batch"
    FOLDER_IMAGES = "folder_images"
    FOLDER_VIDEOS = "folder_videos"
    WEBCAM = "webcam"
    RTSP = "rtsp"


class DetectionTaskType(str, Enum):
    """YOLO task types."""
    DETECT = "detect"
    CLASSIFY = "classify"
    SEGMENT = "segment"
    POSE = "pose"


class ExportFormat(str, Enum):
    """Export output formats."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    ZIP = "zip"


class ConditionalOperator(str, Enum):
    """Operators for conditional logic."""
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="
    GTE = ">="
    LTE = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


# ============================================================================
# Trigger Node Configs
# ============================================================================

class ManualTriggerConfig(BaseModel):
    """Manual trigger - no configuration needed."""
    pass


class ScheduleTriggerConfig(BaseModel):
    """Schedule trigger with cron expression."""
    cron_expression: str = Field(
        ...,
        description="Cron expression (e.g., '0 0 * * *' for daily at midnight)"
    )
    timezone: str = Field(default="UTC", description="Timezone for schedule")
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Basic cron validation."""
        parts = v.strip().split()
        if len(parts) not in [5, 6]:
            raise ValueError("Cron expression must have 5 or 6 parts")
        return v


class EventTriggerConfig(BaseModel):
    """Event trigger for training/detection completion."""
    event_type: Literal["training_complete", "detection_complete"]
    filter_project_id: Optional[int] = Field(None, description="Filter by specific project")
    filter_model_id: Optional[int] = Field(None, description="Filter by specific model")


# ============================================================================
# Input Node Config
# ============================================================================

class NewCampaignConfig(BaseModel):
    """New campaign node configuration."""
    campaign_mode: str = Field(default="new", description="Campaign mode: 'new' to create or 'existing' to use existing")
    campaign_id: Optional[int] = Field(None, gt=0, description="Existing campaign ID when campaign_mode='existing'")
    playbook_id: Optional[int] = Field(None, gt=0, description="Playbook ID - required when campaign_mode='new', retrieved from DB when 'existing'")
    campaign_name: Optional[str] = Field(None, max_length=255, description="Name for the new campaign when campaign_mode='new'")
    campaign_description: Optional[str] = Field(None, description="Optional description for the campaign")
    form_fields: Optional[Dict[str, Any]] = Field(None, description="Custom form field values")
    
    @field_validator('campaign_name')
    @classmethod
    def validate_campaign_name(cls, v):
        """Convert empty string to None."""
        if v is not None and v.strip() == '':
            return None
        return v
    
    @field_validator('campaign_id')
    @classmethod
    def validate_campaign_id(cls, v, info):
        """Ensure campaign_id is provided when mode is 'existing'."""
        campaign_mode = info.data.get('campaign_mode')
        if campaign_mode == 'existing' and not v:
            raise ValueError("campaign_id is required when campaign_mode is 'existing'")
        return v
    
    @field_validator('playbook_id')
    @classmethod
    def validate_playbook_id(cls, v, info):
        """Ensure playbook_id is provided when mode is 'new'."""
        campaign_mode = info.data.get('campaign_mode')
        if campaign_mode == 'new' and not v:
            raise ValueError("playbook_id is required when campaign_mode is 'new'")
        return v


class InputNodeConfig(BaseModel):
    """Input node for specifying detection sources."""
    mode: InputMode
    
    # Single/Batch mode
    file_paths: Optional[List[str]] = Field(None, description="List of file paths for batch mode")
    
    # Folder mode
    folder_path: Optional[str] = Field(None, description="Folder path for folder mode")
    recursive: bool = Field(default=False, description="Scan subfolders recursively")
    
    # Post-processing for folder modes
    post_process_action: Optional[str] = Field(None, description="Action after processing: 'move_to_output', 'delete', or 'keep'")
    output_folder: Optional[str] = Field(None, description="Output folder path for move_to_output action (File Management relative path)")
    
    # Webcam mode
    camera_index: Optional[int] = Field(0, ge=0, description="Camera device index")
    
    # RTSP mode
    rtsp_url: Optional[str] = Field(None, description="RTSP stream URL")
    
    @field_validator('file_paths')
    @classmethod
    def validate_file_paths(cls, v: Optional[List[str]], info) -> Optional[List[str]]:
        """Validate file_paths for batch mode (allow empty for runtime population)."""
        # Note: file_paths can be empty at config time if files are uploaded at execution time
        # Actual validation happens in the executor
        return v
    
    @field_validator('folder_path')
    @classmethod
    def validate_folder_path(cls, v: Optional[str], info) -> Optional[str]:
        """Validate folder_path required for folder modes."""
        mode = info.data.get('mode')
        if mode in [InputMode.FOLDER_IMAGES, InputMode.FOLDER_VIDEOS] and not v:
            raise ValueError("folder_path required for folder modes")
        return v
    
    @field_validator('rtsp_url')
    @classmethod
    def validate_rtsp_url(cls, v: Optional[str], info) -> Optional[str]:
        """Validate rtsp_url required for RTSP mode."""
        mode = info.data.get('mode')
        if mode == InputMode.RTSP and not v:
            raise ValueError("rtsp_url required for RTSP mode")
        return v


# ============================================================================
# Operation Node Configs
# ============================================================================

class TrainModelNodeConfig(BaseModel):
    """Train model node configuration."""
    model_name: str = Field(..., min_length=1, max_length=255)
    base_model_id: int = Field(..., gt=0, description="Base YOLO model to use")
    dataset_id: int = Field(..., gt=0, description="Dataset for training")
    epochs: int = Field(default=100, ge=1, le=1000)
    batch_size: int = Field(default=16, ge=1, le=128)
    image_size: int = Field(default=640, ge=32, le=1280)
    learning_rate: float = Field(default=0.01, gt=0, le=1)
    patience: int = Field(default=50, ge=1, description="Early stopping patience")
    device: Optional[str] = Field(None, description="cuda:0, cpu, or None for auto")


class DetectionNodeConfig(BaseModel):
    """Detection node configuration."""
    model_id: int = Field(..., gt=0, description="Trained model to use")
    task_type: DetectionTaskType = DetectionTaskType.DETECT
    confidence_threshold: float = Field(default=0.25, ge=0, le=1)
    iou_threshold: float = Field(default=0.45, ge=0, le=1)
    max_detections: int = Field(default=300, ge=1, le=1000)
    device: Optional[str] = Field(None, description="cuda:0, cpu, or None for auto")
    save_results: bool = Field(default=True, description="Save detection results to database")
    class_filter: Optional[List[str]] = Field(None, description="Filter detections by specific class names (e.g., ['person', 'car'])")
    # Campaign configuration
    campaign_mode: str = Field(default="none", description="Campaign mode: 'new', 'existing', or 'none' (inherit from parent)")
    campaign_id: Optional[int] = Field(None, description="Existing campaign ID when campaign_mode='existing'")
    campaign_name: Optional[str] = Field(None, description="Campaign name when campaign_mode='new'")
    campaign_description: Optional[str] = Field(None, description="Campaign description when campaign_mode='new'")
    # Deprecated fields (kept for backward compatibility)
    create_session: bool = Field(default=False, description="[Deprecated] Use campaign_mode instead")
    campaign_form_data: Optional[Dict[str, Any]] = Field(default=None, description="Custom campaign form data")


class ExportResultsNodeConfig(BaseModel):
    """Export results node configuration."""
    format: ExportFormat = ExportFormat.JSON
    include_images: bool = Field(default=True, description="Include annotated images")
    include_metadata: bool = Field(default=True, description="Include detection metadata")
    output_path: Optional[str] = Field(None, description="Custom output path (optional)")


class ConditionalBranchNodeConfig(BaseModel):
    """Conditional branching logic."""
    conditions: List[Dict[str, Any]] = Field(
        ...,
        description="List of conditions to evaluate",
        min_length=1
    )
    # Condition format: {"variable": "detection_count", "operator": ">", "value": 10}
    
    @field_validator('conditions')
    @classmethod
    def validate_conditions(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate condition structure."""
        for cond in v:
            if 'variable' not in cond or 'operator' not in cond or 'value' not in cond:
                raise ValueError("Each condition must have 'variable', 'operator', and 'value'")
            
            if cond['operator'] not in [op.value for op in ConditionalOperator]:
                raise ValueError(f"Invalid operator: {cond['operator']}")
        
        return v


class RecognitionNodeConfig(BaseModel):
    """Recognition node configuration for CLIP-based similarity search."""
    catalog_id: int = Field(..., gt=0, description="Recognition catalog to search")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of top matches to return")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum similarity score")
    label_filter: Optional[List[int]] = Field(None, description="Filter by specific label IDs")
    min_detection_confidence: float = Field(
        default=0.25, 
        ge=0.0, 
        le=1.0, 
        description="Minimum detection confidence to process"
    )
    class_filter: Optional[List[str]] = Field(
        None, 
        description="Only recognize specific detection classes"
    )
    bbox_padding_percent: float = Field(
        default=0.15, 
        ge=0.0, 
        le=0.5, 
        description="Padding percentage for bbox cropping (0.0-0.5)"
    )


# ============================================================================
# Output Node Configs
# ============================================================================

class OutputNodeConfig(BaseModel):
    """Output node for displaying results."""
    output_type: Literal[
        "show_images",
        "show_video",
        "generate_detection_report",
        "generate_session_report"
    ]
    include_statistics: bool = Field(default=True)
    include_visualizations: bool = Field(default=True)
    format: ExportFormat = Field(default=ExportFormat.PDF)


# ============================================================================
# Notification Node Configs
# ============================================================================

class SendEmailNodeConfig(BaseModel):
    """Send email notification."""
    recipients: List[str] = Field(..., min_length=1, description="List of email addresses")
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, description="Email body (supports template variables)")
    include_attachments: bool = Field(default=False)
    attachment_formats: List[ExportFormat] = Field(default_factory=list)
    
    @field_validator('recipients')
    @classmethod
    def validate_emails(cls, v: List[str]) -> List[str]:
        """Basic email validation."""
        for email in v:
            if '@' not in email or '.' not in email.split('@')[1]:
                raise ValueError(f"Invalid email address: {email}")
        return v


class WebhookNodeConfig(BaseModel):
    """Send webhook notification."""
    url: str = Field(..., description="Webhook URL")
    method: Literal["POST", "PUT", "PATCH"] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    include_execution_data: bool = Field(default=True)
    custom_payload: Optional[Dict[str, Any]] = Field(None, description="Custom JSON payload")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v


# ============================================================================
# Node Config Registry
# ============================================================================

NODE_CONFIG_REGISTRY: Dict[str, type[BaseModel]] = {
    # Triggers
    "manual_trigger": ManualTriggerConfig,
    "schedule_trigger": ScheduleTriggerConfig,
    "event_trigger": EventTriggerConfig,
    
    # Input
    "input": InputNodeConfig,
    "data_input": InputNodeConfig,  # Frontend uses data_input
    "new_campaign": NewCampaignConfig,  # Campaign node
    
    # Operations
    "train_model": TrainModelNodeConfig,
    "detection": DetectionNodeConfig,
    "classification": DetectionNodeConfig,  # Classification uses same config as detection
    "recognition": RecognitionNodeConfig,
    "export_results": ExportResultsNodeConfig,
    "conditional_branch": ConditionalBranchNodeConfig,
    
    # Output
    "output": OutputNodeConfig,
    "show_images": OutputNodeConfig,  # Show images output
    "show_image_results": OutputNodeConfig,  # Frontend uses this
    "show_video_results": OutputNodeConfig,  # Frontend uses this
    "generate_detection_report": OutputNodeConfig,  # Generate report
    "generate_campaign_report": OutputNodeConfig,  # Generate campaign report
    
    # Notifications
    "send_email": SendEmailNodeConfig,
    "webhook": WebhookNodeConfig,
}


def validate_node_config(node_type: str, config: Dict[str, Any]) -> BaseModel:
    """
    Validate node configuration against its schema.
    
    Args:
        node_type: Type of node (e.g., "train_model")
        config: Configuration dictionary
    
    Returns:
        Validated Pydantic model instance
    
    Raises:
        ValueError: If node_type not found or validation fails
    """
    if node_type not in NODE_CONFIG_REGISTRY:
        raise ValueError(f"Unknown node type: {node_type}")
    
    schema_class = NODE_CONFIG_REGISTRY[node_type]
    return schema_class(**config)
