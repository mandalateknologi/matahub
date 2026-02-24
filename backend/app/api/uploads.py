"""
Uploads API Router
Handles file uploads for workflows with File Management integration
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
import os

from app.db import get_db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.project import Project
from app.schemas.uploads import FileUploadResponse, FileDeleteResponse
from app.utils.auth import get_current_active_user
from app.services.file_storage_service import FileStorageService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/workflows/{workflow_id}/upload", response_model=FileUploadResponse)
async def upload_workflow_file(
    workflow_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload file for workflow using File Management system.
    
    Stores file in: data/uploads/{user_id}/workflows/{workflow_id}/
    Enforces 50GB storage quota and creates UserFile database record.
    """
    # Verify workflow exists and user has access
    workflow = db.query(Workflow).join(Project).filter(
        Workflow.id == workflow_id,
        Project.creator_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or access denied"
        )
    
    # Use FileStorageService for upload (enforces quota, creates DB record)
    try:
        file_storage = FileStorageService(db)
        folder_path = f"workflows/{workflow_id}"
        
        user_file = file_storage.upload_file(
            user_id=current_user.id,
            file=file,
            folder_path=folder_path
        )
        
        logger.info(f"Workflow file uploaded: {user_file.file_path} ({user_file.file_size} bytes)")
        
        return FileUploadResponse(
            file_path=user_file.file_path,
            filename=user_file.file_name,
            size=user_file.file_size,
            uploaded_at=user_file.uploaded_at
        )
    except HTTPException:
        # Re-raise HTTPException from FileStorageService (quota exceeded, etc.)
        raise
    except Exception as e:
        logger.error(f"Error uploading workflow file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.delete("/workflows/{workflow_id}/file", response_model=FileDeleteResponse)
async def delete_workflow_file(
    workflow_id: int,
    file_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete specific uploaded file.
    """
    # Verify workflow exists and user has access
    workflow = db.query(Workflow).join(Project).filter(
        Workflow.id == workflow_id,
        Project.creator_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or access denied"
        )
    
    # Validate file path belongs to this workflow
    expected_prefix = f"data/uploads/{current_user.id}/workflows/{workflow_id}/"
    if not file_path.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete file from different workflow"
        )
    
    # Delete file
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return FileDeleteResponse(
                success=True,
                message="File deleted successfully"
            )
        else:
            return FileDeleteResponse(
                success=False,
                message="File not found"
            )
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting file"
        )


@router.delete("/workflows/{workflow_id}/all", response_model=FileDeleteResponse)
async def delete_all_workflow_files(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete all uploaded files for workflow.
    """
    # Verify workflow exists and user has access
    workflow = db.query(Workflow).join(Project).filter(
        Workflow.id == workflow_id,
        Project.creator_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found or access denied"
        )
    
    # Delete all files
    success = delete_workflow_uploads(current_user.id, workflow_id)
    
    if success:
        return FileDeleteResponse(
            success=True,
            message="All workflow files deleted successfully"
        )
    else:
        return FileDeleteResponse(
            success=False,
            message="Error deleting workflow files"
        )
