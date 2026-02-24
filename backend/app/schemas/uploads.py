"""
Upload Schemas
Pydantic schemas for file upload responses
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class FileUploadResponse(BaseModel):
    """Response after successful file upload."""
    file_path: str = Field(..., description="Relative server path to uploaded file")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    
    model_config = {"from_attributes": True}


class FileDeleteResponse(BaseModel):
    """Response after file deletion."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Result message")
