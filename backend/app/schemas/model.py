"""
Model Schemas
"""
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from typing import Optional, Dict, Any
from app.models.model import ModelStatus


class BaseModelInfo(BaseModel):
    """Schema for base YOLO model information."""
    name: str
    description: str
    parameters: str
    speed: str
    accuracy: str


class ModelCreate(BaseModel):
    """Schema for creating a new trained model."""
    name: str = Field(..., min_length=1, max_length=255)
    base_type: str = Field(..., pattern="^yolov8[nsmlx]$")
    task_type: str = Field(..., pattern="^(detect|classify|segment)$")
    inference_type: str = Field(default="yolo", pattern="^(yolo|sam3)$")
    requires_prompts: bool = Field(default=False)
    project_id: int


class ModelUpdate(BaseModel):
    """Schema for updating a model."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)


class ModelResponse(BaseModel):
    """Schema for model list response."""
    id: int
    name: str
    description: Optional[str]
    tags: Optional[str]
    base_type: str
    task_type: str
    inference_type: str
    requires_prompts: bool
    project_id: int
    project_name: str
    version: str
    is_system: bool = False
    status: ModelStatus
    metrics_json: Dict[str, Any]
    validation_error: Optional[str]
    api_key: Optional[UUID]
    created_at: datetime
    
    @field_serializer('api_key')
    def serialize_api_key(self, api_key: Optional[UUID], _info):
        """Convert UUID to string for JSON serialization."""
        return str(api_key) if api_key else None
    
    model_config = {"from_attributes": True}


class ModelDetail(ModelResponse):
    """Schema for detailed model response."""
    artifact_path: Optional[str]
    
    model_config = {"from_attributes": True}
