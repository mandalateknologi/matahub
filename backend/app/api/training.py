"""
Training API Router
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.models.training_job import TrainingJob
from app.models.model import Model
from app.models.dataset import Dataset
from app.schemas.training import TrainingStart, TrainingJobResponse, TrainingLogs
from app.utils.auth import get_current_active_user
from app.utils.permissions import require_project_admin_or_admin, check_project_ownership, require_admin
from app.workers.training_worker import training_worker
from app.services.yolo_service import yolo_service
from app.config import settings

router = APIRouter(prefix="/api/training", tags=["Training"])

@router.post("/start", response_model=TrainingJobResponse, status_code=status.HTTP_201_CREATED)
async def start_training(
    training_data: TrainingStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Start a new training job.
    Requires PROJECT_ADMIN or ADMIN role.
    Validates project ownership.
    
    Args:
        training_data: Training configuration
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Created training job
    """
    # Verify project exists and validate ownership
    project = check_project_ownership(training_data.project_id, current_user, db)
    
    # Protect system projects from training
    if project.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Training is disabled for system projects. Use model upload instead."
        )
    
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == project.dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get base model to use for training
    base_model = db.query(Model).filter(Model.id == training_data.base_model_id).first()
    if not base_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base model not found"
        )
    
    # Verify base model is ready
    if base_model.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Base model is not ready (status: {base_model.status})"
        )
    
    # Verify base model artifact file exists
    base_model_path = Path(base_model.artifact_path)
    if not base_model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base model file not found on disk"
        )
    
    # Validate task_type compatibility
    if base_model.task_type != dataset.task_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Base model task type '{base_model.task_type}' is incompatible with dataset task type '{dataset.task_type}'. Please select a base model matching the dataset's task type."
        )
    
    # Create model record for the new trained model
    new_model = Model(
        name=training_data.model_name,
        base_type=base_model.base_type,
        task_type=dataset.task_type,
        project_id=training_data.project_id
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    
    # Create training job
    new_job = TrainingJob(
        project_id=training_data.project_id,
        model_id=new_model.id,
        total_epochs=training_data.epochs
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Prepare output directory
    output_dir = Path(settings.models_dir) / str(new_model.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Start training in background with full path to base model
    training_worker.start_training(
        job_id=new_job.id,
        project_id=project.id,
        model_id=new_model.id,
        dataset_path=str(dataset.get_dataset_path()),
        output_dir=str(output_dir),
        task_type=dataset.task_type,
        base_model=str(base_model_path),
        epochs=training_data.epochs,
        batch_size=training_data.batch_size,
        image_size=training_data.image_size,
        learning_rate=training_data.learning_rate
    )
    
    return new_job

@router.get("/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get training job status and progress.
    Validates project ownership.
    
    Args:
        job_id: Training job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Training job details with progress
    """
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    
    # Validate project ownership
    check_project_ownership(job.project_id, current_user, db)
    
    return job

@router.get("/{job_id}/logs", response_model=TrainingLogs)
async def get_training_logs(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get training job logs.
    Validates project ownership.
    
    Args:
        job_id: Training job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Training logs
    """
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    
    # Validate project ownership
    check_project_ownership(job.project_id, current_user, db)
    
    # Read logs from file if available
    logs = []
    if job.logs_path and Path(job.logs_path).exists():
        try:
            with open(job.logs_path, 'r') as f:
                logs = f.readlines()
        except Exception:
            logs = ["Logs not available"]
    else:
        logs = [f"Training in progress: {job.progress:.1f}%"]
    
    return TrainingLogs(
        job_id=job.id,
        logs=logs,
        current_epoch=job.current_epoch,
        total_epochs=job.total_epochs
    )

@router.get("", response_model=List[TrainingJobResponse])
async def list_training_jobs(
    skip: int = 0,
    limit: int = 100,
    project_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of training jobs.
    Filters by accessible projects (ownership-based).
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        project_id: Optional filter by project ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of training jobs
    """
    from app.utils.permissions import get_user_accessible_project_ids
    
    query = db.query(TrainingJob)
    
    # Filter by accessible projects
    accessible_project_ids = get_user_accessible_project_ids(current_user, db)
    query = query.filter(TrainingJob.project_id.in_(accessible_project_ids))
    
    if project_id:
        query = query.filter(TrainingJob.project_id == project_id)
    
    jobs = query.order_by(TrainingJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

@router.post("/clear-cache", status_code=status.HTTP_200_OK)
async def clear_model_cache(
    current_user: User = Depends(require_admin)
):
    """
    Clear the inference model cache to free memory.
    Admin-only endpoint for memory management.
    
    Args:
        current_user: Current authenticated user (must be ADMIN)
        
    Returns:
        Number of models cleared from cache
    """
    cleared_count = yolo_service.clear_inference_cache()
    
    return {
        "success": True,
        "models_cleared": cleared_count,
        "message": f"Cleared {cleared_count} model(s) from cache"
    }
