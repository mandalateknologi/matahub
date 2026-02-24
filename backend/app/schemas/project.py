"""
Project Schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.project import ProjectStatus
from app.schemas.dataset import DatasetResponse
from app.schemas.model import ModelResponse


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255)
    dataset_id: Optional[int] = None
    task_type: str = Field(default="detect", pattern="^(detect|segment|classify)$")
    is_system: bool = Field(default=False, description="System flag (cannot be set by users)")


class ProjectResponse(BaseModel):
    """Schema for project list response."""
    id: int
    name: str
    dataset_id: Optional[int] = None
    task_type: str
    status: ProjectStatus
    is_system: bool = False
    creator_id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ProjectDetail(ProjectResponse):
    """Schema for detailed project response."""
    dataset: Optional[DatasetResponse] = None
    models: List[ModelResponse] = []
    
    model_config = {"from_attributes": True}
