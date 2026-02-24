"""
Training Schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.training_job import TrainingStatus


class TrainingStart(BaseModel):
    """Schema for starting a training job."""
    project_id: int
    model_name: str = Field(..., min_length=1, max_length=255)
    base_model_id: int = Field(..., gt=0)
    epochs: int = Field(default=100, ge=1, le=1000)
    batch_size: int = Field(default=16, ge=1, le=128)
    image_size: int = Field(default=640, ge=32, le=1280)
    learning_rate: float = Field(default=0.01, gt=0, le=1)


class TrainingJobResponse(BaseModel):
    """Schema for training job response."""
    id: int
    project_id: int
    model_id: int
    status: TrainingStatus
    progress: float
    current_epoch: int
    total_epochs: int
    metrics_json: Dict[str, Any]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TrainingLogs(BaseModel):
    """Schema for training logs response."""
    job_id: int
    logs: List[str]
    current_epoch: int
    total_epochs: int
