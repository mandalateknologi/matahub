"""
Campaign Schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.campaign import CampaignStatus, CampaignExportType, CampaignExportStatus


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign."""
    name: str = Field(..., min_length=1, max_length=255)
    playbook_id: int
    description: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None


class CampaignUpdate(BaseModel):
    """Schema for updating campaign details."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignResponse(BaseModel):
    """Schema for campaign response."""
    id: int
    name: str
    description: Optional[str]
    playbook_id: int
    playbook_name: Optional[str] = None
    creator_id: int
    creator_name: Optional[str] = None
    status: CampaignStatus
    summary_json: Dict[str, Any]
    created_at: datetime
    ended_at: Optional[datetime]
    
    # Calculated fields
    jobs_count: int = 0
    last_activity: Optional[datetime] = None
    running_jobs_count: int = 0
    
    model_config = {"from_attributes": True}


class CampaignStatsResponse(BaseModel):
    """Schema for campaign aggregate statistics."""
    campaign_id: int
    total_predictions: int = 0
    total_jobs: int = 0
    completed_jobs: int = 0
    running_jobs: int = 0
    failed_jobs: int = 0
    
    # Mode breakdown
    single_jobs: int = 0
    batch_jobs: int = 0
    video_jobs: int = 0
    rtsp_jobs: int = 0
    
    # prediction statistics
    class_counts: Dict[str, int] = Field(default_factory=dict)
    average_confidence: float = 0.0
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None

    # prediction totals by task type
    total_classifications: int = 0
    total_detections: int = 0
    total_segmentations: int = 0
    
    # Temporal data
    first_prediction: Optional[datetime] = None
    last_prediction: Optional[datetime] = None
    
    # Cache metadata
    cached_at: Optional[datetime] = None


class CampaignExportCreate(BaseModel):
    """Schema for creating campaign export."""
    export_type: CampaignExportType
    config: Dict[str, Any] = Field(default_factory=dict)


class CampaignExportResponse(BaseModel):
    """Schema for campaign export response."""
    id: int
    campaign_id: int
    export_type: CampaignExportType
    status: CampaignExportStatus
    file_path: Optional[str]
    progress: int
    config_json: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]
    
    model_config = {"from_attributes": True}


class CampaignListFilters(BaseModel):
    """Schema for campaign list filters."""
    playbook_id: Optional[int] = None
    status: Optional[CampaignStatus] = None
    search: Optional[str] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
