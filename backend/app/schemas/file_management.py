"""
File Management Schemas
Pydantic models for file management API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class FileItemResponse(BaseModel):
    """Response model for a single file item."""
    id: int
    name: str
    type: str  # "image", "video", "folder"
    size: int  # bytes
    path: str  # full path relative to DATA_DIR
    folder_path: str  # folder organization path
    is_system_folder: bool
    is_deleted: bool
    uploaded_at: datetime
    deleted_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class FolderTreeResponse(BaseModel):
    """Response model for folder tree structure."""
    tree: Dict[str, Any]  # Nested dictionary representing folder hierarchy


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    used_bytes: int
    total_bytes: int
    file_count: int
    used_percentage: float = Field(..., ge=0, le=100)


class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    id: int
    name: str
    type: str
    size: int
    path: str
    folder_path: str
    uploaded_at: datetime
    message: str


class FolderCreateRequest(BaseModel):
    """Request model for creating a folder."""
    name: str = Field(..., min_length=1, max_length=255)
    parent_path: str = Field(default="shared")


class FolderCreateResponse(BaseModel):
    """Response model for folder creation."""
    id: int
    name: str
    path: str
    message: str


class MigrationStatsResponse(BaseModel):
    """Response model for file migration statistics."""
    files_found: int
    files_migrated: int
    files_skipped: int
    folders_migrated: int = 0


class BatchFileOperation(BaseModel):
    """Request model for batch file operations."""
    file_ids: list[int] = Field(..., min_length=1)


class BatchRestoreRequest(BaseModel):
    """Request model for batch restore operations."""
    file_ids: List[int] = Field(..., min_length=1)
    restore_to: str = Field(default="shared")


class MoveFileRequest(BaseModel):
    """Request model for moving a file."""
    new_folder_path: str = Field(..., min_length=1)


class RenameFileRequest(BaseModel):
    """Request model for renaming a file."""
    new_name: str = Field(..., min_length=1, max_length=255)
