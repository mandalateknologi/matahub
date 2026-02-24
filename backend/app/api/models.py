"""
Models API Router
"""
from typing import List
from pathlib import Path
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.user import User, UserRole
from app.models.model import Model, ModelStatus
from app.models.project import Project
from app.schemas.model import ModelCreate, ModelUpdate, ModelResponse, ModelDetail, BaseModelInfo
from app.utils.auth import get_current_active_user
from app.utils.permissions import require_project_admin_or_admin, check_project_ownership, get_user_accessible_project_ids
from app.services.yolo_service import yolo_service
from app.workers.model_validation_worker import model_validation_worker
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["Models"])


@router.get("/base", response_model=List[BaseModelInfo])
async def list_base_models(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of available base YOLO models.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of base model information
    """
    return yolo_service.get_base_models()


@router.get("", response_model=List[ModelResponse])
async def list_models(
    skip: int = 0,
    limit: int = 100,
    project_id: int = None,
    task_type: str = None,
    accessible: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of trained models.
    If accessible=True, filters by projects user can access (for operators).
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        project_id: Optional filter by project ID
        task_type: Optional filter by task type (detect/classify/segment)
        accessible: If true, filter by accessible projects (for operators)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of models
    """
    query = db.query(Model).options(joinedload(Model.project))
    
    # Filter by accessible projects if requested (for operators)
    if accessible:
        accessible_ids = get_user_accessible_project_ids(current_user, db)
        query = query.filter(Model.project_id.in_(accessible_ids))
    
    if project_id:
        query = query.filter(Model.project_id == project_id)
    
    if task_type:
        query = query.filter(Model.task_type == task_type)
    
    models = query.offset(skip).limit(limit).all()
    return models


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_data: ModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Create a new model (prepares for training).
    Requires PROJECT_ADMIN or ADMIN role.
    Validates project ownership.
    
    Args:
        model_data: Model creation data
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Created model
    """
    # Verify project exists and validate ownership
    project = check_project_ownership(model_data.project_id, current_user, db)
    
    # Create new model
    new_model = Model(
        name=model_data.name,
        base_type=model_data.base_type,
        task_type=model_data.task_type,
        inference_type=model_data.inference_type,
        project_id=model_data.project_id
    )
    
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    
    # Load project relationship
    new_model = db.query(Model).options(joinedload(Model.project)).filter(Model.id == new_model.id).first()
    
    return new_model


@router.get("/{model_id}", response_model=ModelDetail)
async def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get detailed information about a specific model.
    Allows access if user owns project or it's a system project.
    
    Args:
        model_id: Model ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Model details
    """
    model = db.query(Model).options(joinedload(Model.project)).filter(Model.id == model_id).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Check access: allow if admin, project owner, or system project
    if current_user.role != UserRole.ADMIN:
        project = model.project
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        if not project.is_system and project.creator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: not your project"
            )
    
    return model


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: int,
    model_data: ModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Update a model's metadata (name only).
    Requires PROJECT_ADMIN or ADMIN role.
    Validates project ownership.
    
    Args:
        model_id: Model ID
        model_data: Model update data
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Updated model
    """
    model = db.query(Model).filter(Model.id == model_id).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Validate project ownership
    check_project_ownership(model.project_id, current_user, db)
    
    # Update model fields
    model.name = model_data.name
    if model_data.description is not None:
        model.description = model_data.description
    if model_data.tags is not None:
        model.tags = model_data.tags
    
    db.commit()
    db.refresh(model)
    
    # Load project relationship
    model = db.query(Model).options(joinedload(Model.project)).filter(Model.id == model.id).first()
    
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Delete a model.
    Base models (in system projects): ADMIN only
    Non-system projects: Cannot delete, only rename
    
    Args:
        model_id: Model ID
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
    """
    model = db.query(Model).filter(Model.id == model_id).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Get the project to check if it's a system project
    project = db.query(Project).filter(Project.id == model.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Only allow deletion for models in system projects
    if not project.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete models from non-system projects. Only rename is allowed."
        )
    
    # Base models can only be deleted by ADMIN
    if project.is_system and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete base models"
        )
    
    db.delete(model)
    db.commit()
    
    # TODO: Delete model files from storage
    # if model.artifact_path and os.path.exists(model.artifact_path):
    #     os.remove(model.artifact_path)


@router.get("/{model_id}/artifacts/{filename}")
async def get_model_artifact(
    model_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Get a training artifact file for a specific model.
    Security: Validates model exists and prevents directory traversal.
    Note: Public endpoint to allow browser image loading without auth headers.
    
    Args:
        model_id: Model ID
        filename: Artifact filename (e.g., 'confusion_matrix.png')
        db: Database session
        
    Returns:
        FileResponse with the artifact image
    """
    # Verify model exists
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Verify project exists (basic validation)
    project = db.query(Project).filter(Project.id == model.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Security: Prevent directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )
    
    # Allowed artifact files only
    allowed_files = {
        "confusion_matrix.png",
        "confusion_matrix_normalized.png", 
        "results.png",
        "BoxF1_curve.png",
        "BoxPR_curve.png",
        "BoxP_curve.png",
        "BoxR_curve.png"
    }
    
    if filename not in allowed_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artifact filename"
        )
    
    # Construct file path
    artifact_path = Path(settings.models_dir) / str(model_id) / "train" / filename
    
    if not artifact_path.exists() or not artifact_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    # Return file with aggressive caching (artifacts never change after training)
    return FileResponse(
        path=str(artifact_path),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{model_id}-{filename}"'
        }
    )


@router.post("/upload", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def upload_model(
    project_id: int = Form(...),
    name: str = Form(...),
    base_type: str = Form(...),
    task_type: str = Form(...),
    file: UploadFile = File(...),
    bpe_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a trained model file (.pt/.safetensors) directly to a project.
    Primarily used for system projects to bypass training.
    For SegmentAnything models, also accepts BPE vocabulary file.
    
    Args:
        project_id: Project ID to associate model with
        name: Model name
        base_type: Base model type (yolov8n, yolov8s, sam3, etc.)
        task_type: Task type (detect, classify, segment, segment_anything)
        file: Model file (.pt/.safetensors format)
        bpe_file: Optional BPE vocabulary file (required for segment_anything)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created model record
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Validate task_type
    if task_type not in ['detect', 'classify', 'segment', 'segment_anything']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_type. Must be 'detect', 'classify', 'segment', or 'segment_anything'"
        )
    
    # Validate BPE file for segment_anything
    if task_type == 'segment_anything' and not bpe_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BPE vocabulary file is required for SegmentAnything models"
        )
    
    # Force base_type to 'sam3' for segment_anything models
    original_base_type = base_type
    if task_type == 'segment_anything':
        base_type = 'sam3'
        if original_base_type != 'sam3':
            logger.info(
                f"Auto-correcting base_type from '{original_base_type}' to 'sam3' "
                f"for segment_anything model '{name}' (user: {current_user.email})"
            )
    
    # Validate file extension
    valid_extensions = ['.pt', '.safetensors']
    if not file.filename or not any(file.filename.endswith(ext) for ext in valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .pt (PyTorch) or .safetensors model file"
        )
    
    # Determine file type
    is_safetensors = file.filename.endswith('.safetensors')
    is_pytorch = file.filename.endswith('.pt')
    
    # Validate file size (max 100MB for YOLO, 5GB for SAM3) - check first 8KB for format validation
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024 if task_type == 'segment_anything' else 100 * 1024 * 1024
    
    # Read first chunk for format validation (8KB)
    first_chunk = await file.read(8192)
    
    # Basic validation: Check file format (only for PyTorch files)
    if is_pytorch and not first_chunk.startswith(b'PK'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model file format. Must be a valid PyTorch (.pt) file"
        )
    
    # Read BPE file if provided
    bpe_content = None
    if bpe_file and bpe_file.filename:
        bpe_content = await bpe_file.read()
        if len(bpe_content) > 10 * 1024 * 1024:  # Max 10MB for BPE
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="BPE file size exceeds maximum allowed size of 10MB"
            )
    
    try:
        # Determine if we can validate (requires dataset)
        # SAM3 models cannot be validated with standard datasets
        can_validate = project.dataset_id is not None and task_type != 'segment_anything'
        
        # Store task_type as 'segment' for segment_anything (database compatibility)
        db_task_type = 'segment' if task_type == 'segment_anything' else task_type
        
        # Create model record with appropriate initial status
        new_model = Model(
            name=name,
            base_type=base_type,
            task_type=db_task_type,
            project_id=project_id,
            status=ModelStatus.VALIDATING if can_validate else ModelStatus.READY
        )
        db.add(new_model)
        db.commit()
        db.refresh(new_model)
        
        # Prepare upload directory
        if task_type == 'segment_anything':
            # For SAM3, create dedicated folder with asset subfolder
            model_dir = Path(settings.models_dir) / str(new_model.id)
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Save model file using chunked streaming
            file_ext = '.safetensors' if is_safetensors else '.pt'
            file_path = model_dir / f"model_{new_model.id}{file_ext}"
            
            total_size = len(first_chunk)
            with open(file_path, 'wb') as f:
                # Write first chunk
                f.write(first_chunk)
                
                # Stream remaining chunks
                while chunk := await file.read(8192 * 1024):  # 8MB chunks
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        # Clean up partial file
                        f.close()
                        file_path.unlink(missing_ok=True)
                        max_size_gb = MAX_FILE_SIZE // (1024 * 1024 * 1024)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File size exceeds maximum allowed size of {max_size_gb}GB"
                        )
                    f.write(chunk)
            
            # Create asset folder and save BPE file
            asset_dir = model_dir / "asset"
            asset_dir.mkdir(parents=True, exist_ok=True)
            
            if bpe_content:
                bpe_path = asset_dir / (bpe_file.filename or "bpe_vocab.txt.gz")
                with open(bpe_path, 'wb') as f:
                    f.write(bpe_content)
                
                # Store BPE path in metrics
                new_model.metrics_json = {
                    "model_type": "SAM3",
                    "bpe_path": str(bpe_path),
                    "bpe_filename": bpe_file.filename
                }
        else:
            # Standard YOLO upload - use streaming for consistency
            upload_dir = Path(settings.models_dir) / str(project_id) / "uploaded"
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file with model ID in filename using chunked streaming
            file_path = upload_dir / f"model_{new_model.id}.pt"
            
            total_size = len(first_chunk)
            with open(file_path, 'wb') as f:
                # Write first chunk
                f.write(first_chunk)
                
                # Stream remaining chunks
                while chunk := await file.read(8192 * 1024):  # 8MB chunks
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        # Clean up partial file
                        f.close()
                        file_path.unlink(missing_ok=True)
                        max_size_mb = MAX_FILE_SIZE // (1024 * 1024)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
                        )
                    f.write(chunk)
        
        # Update model with artifact path
        new_model.artifact_path = str(file_path)
        db.commit()
        
        # Load project relationship for response
        new_model = db.query(Model).options(joinedload(Model.project)).filter(Model.id == new_model.id).first()
        
        # Trigger background validation if dataset exists
        if can_validate and project.dataset:
            dataset_path = Path(settings.datasets_dir) / str(project.dataset.id)
            model_validation_worker.start_validation(
                model_id=new_model.id,
                model_path=str(file_path),
                dataset_path=str(dataset_path)
            )
            logger.info(f"Started background validation for model {new_model.id}")
        elif not can_validate:
            logger.info(f"Skipping validation for model {new_model.id} - no dataset associated with project")
        
        # Log upload for system projects (audit trail)
        if project.is_system:
            logger.info(
                f"Model uploaded to system project '{project.name}' (ID: {project.id}): "
                f"Model '{name}' (ID: {new_model.id}, base_type: {base_type}, task_type: {task_type}) "
                f"by user {current_user.email}"
            )
        
        return new_model
        
    except Exception as e:
        # Rollback on error
        if new_model and new_model.id:
            db.delete(new_model)
            db.commit()
        
        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        
        logger.error(f"Model upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload model: {str(e)}"
        )


@router.post("/{model_id}/validate", response_model=ModelResponse)
async def validate_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually trigger validation for an uploaded model.
    Useful for models uploaded before validation feature or failed validations.
    
    Args:
        model_id: Model ID to validate
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated model record with VALIDATING status
    """
    # Get model
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Get project and verify dataset exists
    project = db.query(Project).filter(Project.id == model.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if not project.dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot validate model: project has no associated dataset"
        )
    
    # Verify model file exists
    if not model.artifact_path or not Path(model.artifact_path).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot validate model: model file not found"
        )
    
    # Check if already validating
    if model_validation_worker.is_validating(model_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model validation already in progress"
        )
    
    # Update status to validating
    model.status = ModelStatus.VALIDATING.value
    model.validation_error = None
    db.commit()
    
    # Load project relationship for response
    model = db.query(Model).options(joinedload(Model.project)).filter(Model.id == model.id).first()
    
    # Trigger background validation
    dataset_path = Path(settings.datasets_dir) / str(project.dataset.id)
    model_validation_worker.start_validation(
        model_id=model.id,
        model_path=model.artifact_path,
        dataset_path=str(dataset_path)
    )
    
    logger.info(f"Manual validation triggered for model {model_id} by user {current_user.email}")
    
    return model
