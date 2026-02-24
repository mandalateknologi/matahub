"""
Export Job Schemas
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ExportJobRequest(BaseModel):
    """Request to create an export job."""
    annotated: bool = Field(True, description="Include bounding boxes on images (for images_zip and pdf)")
    result_ids: Optional[List[int]] = Field(None, description="Specific result IDs to export (None = all)")
    format: Optional[str] = Field("json", description="Format for data export (json or csv)")


class ExportJobResponse(BaseModel):
    """Export job response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_job_id: int
    export_type: str
    status: str
    progress: float
    file_path: Optional[str] = None
    options_json: Optional[dict] = None
    creator_id: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
