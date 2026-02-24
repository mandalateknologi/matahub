"""
Unified Inference API Router
Model-agnostic inference supporting YOLO, SAM3, and future models.
Prepares backend for Hybrid Inference architecture.
"""
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
import json
import uuid
import cv2
import base64
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import get_db
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.prediction_job import PredictionJob, PredictionMode, PredictionStatus
from app.models.prediction_result import PredictionResult
from app.schemas.prediction import (
    PredictionResponse,
    PredictionJobResponse,
    PredictionJobResponse,
    PaginatedPredictionJobsResponse
)
from app.models.model import Model
from app.utils.auth import get_current_active_user
from app.utils.permissions import check_project_team_access
from app.utils.file_handler import save_uploaded_image, save_uploaded_video
from app.services.inference_service import inference_service
from app.workers.prediction_worker import prediction_worker
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inference", tags=["Inference"])

@router.post("/single", response_model=PredictionResponse)
async def infer_single_image(
    model_id: int = Form(...),
    file: UploadFile = File(...),
    campaign_id: Optional[int] = Form(None),
    confidence: Optional[float] = Form(0.25),
    iou_threshold: Optional[float] = Form(0.45), # Currently unused, reserved for future use
    imgsz: Optional[int] = Form(640), # Image Size, Currently unused, reserved for future use
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),  # JSON string for SAM3 prompts
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Run inference on a single image.
    Automatically routes to appropriate model service (YOLO, SAM3, etc.).
    
    Args:
        model_id: Model ID to use for inference
        confidence: Confidence threshold (YOLO only, ignored for SAM3)
        campaign_id: Optional session ID to link result to
        class_filter: Comma-separated class names to filter (YOLO only)
        prompts: JSON array of SAM3 prompts (SAM3 only) - [] for automatic segmentation
        file: Image file
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Inference results with boxes, scores, classes, masks (depending on model)
    """
    # Verify model exists and get model info
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )

    if model.requires_prompts:
        # Prompt-capable model requires prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompts are required for '{model.name}' inference"
            )
    
    # Validate team access for operators
    check_project_team_access(model.project_id, current_user, db)
    
    # Parse prompts for SAM3
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
            if not isinstance(prompts_list, list):
                raise ValueError("Prompts must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Create prediction job
    job = PredictionJob(
        model_id=model_id,
        campaign_id=campaign_id,
        creator_id=current_user.id,
        mode=PredictionMode.SINGLE,
        source_type="image",
        source_ref=file.filename
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Initialize summary_json with new schema
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Save uploaded image
    image_path = await save_uploaded_image(file, job.id)
    
    # Parse class_filter for YOLO
    class_filter_list = None
    if class_filter:
        class_filter_list = [c.strip() for c in class_filter.split(",") if c.strip()]
    
    # Get BPE path from model metadata (SAM3)
    bpe_path = None
    if model.metrics_json and isinstance(model.metrics_json, dict):
        bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
    
    # Run inference using unified service
    try:
        result = inference_service.detect_image(
            model_path=model.artifact_path,
            inference_type=model.inference_type,
            image_path=image_path,
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            prompts=prompts_list,
            class_filter=class_filter_list,
            bpe_path=bpe_path,
        )
        
        # Store result in database with configuration tracking
        from app.schemas.prediction import ResultConfig
        result_config = ResultConfig(
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter_list,
            prompts=prompts_list,
            inference_type=model.inference_type
        ).model_dump()
        
        prediction_result = PredictionResult(
            prediction_job_id=job.id,
            file_name=file.filename,
            task_type=model.task_type,
            boxes_json=result.boxes or [],
            scores_json=result.scores or [],
            classes_json=result.classes or [],
            class_names_json=result.class_names or [],
            masks_json=result.masks or [],
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            config_json=result_config
        )
        db.add(prediction_result)
        
        # Update job status
        if model.task_type == "segment":
            job.update_stats(
                replace=True,
                total_masks=len(result.masks) if result.masks else 0,
                mask_count_per_class={},
                average_confidence=sum(result.scores) / len(result.scores) if result.scores else 0.0,
                inference_time_ms=result.inference_time_ms or 0.0,
                processing_time_ms=0.0
            )
        elif model.task_type == "classify":
            job.update_stats(
                replace=True,
                total_classifications=1,
                top_class_distribution={result.top_class: 1} if result.top_class else {},
                average_top_confidence=result.top_confidence or 0.0,
                top_classes_summary=[{"class": result.top_class, "confidence": result.top_confidence}] if result.top_class else [],
                inference_time_ms=result.inference_time_ms or 0.0,
                processing_time_ms=0.0
            )
        elif model.task_type == "detect":  # detect
            class_counts = {}
            if result.class_names:
                for class_name in result.class_names:
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1

            job.update_stats(
                replace=True,
                total_detections=len(result.boxes) if result.boxes else 0,
                class_counts=class_counts,
                average_confidence=sum(result.scores) / len(result.scores) if result.scores else 0.0,
                inference_time_ms=result.inference_time_ms or 0.0,
                processing_time_ms=0.0
            )
        else:
            logger.warning(f"Unknown task_type '{model.task_type}' for job {job.id}") # reminder for new task types, transformer models, etc.

        job.status = PredictionStatus.COMPLETED.value
        job.completed_at = datetime.now(timezone.utc)
        job.progress = 100

        db.commit()
        db.refresh(prediction_result)
        
        # Return unified response
        return PredictionResponse(
            job_id=job.id,
            file_name=file.filename,
            task_type=result.task_type,
            inference_time_ms=result.inference_time_ms,
            boxes=result.boxes,
            scores=result.scores,
            classes=result.classes,
            class_names=result.class_names,
            masks=result.masks,
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            top_classes=result.top_classes,
            probabilities=result.probabilities,
            result_id=prediction_result.id,
            config=result_config,
            chats=[]
        )
        
    except Exception as e:
        job.status = PredictionStatus.FAILED.value
        job.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {str(e)}"
        )

@router.post("/preview", response_model=PredictionResponse)
async def infer_preview(
    model_id: int = Form(...),
    confidence: float = Form(0.25),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Run inference for preview ONLY - no database records created.
    Used for live preview in video manual capture mode.
    Supports both YOLO and SAM3 models.
    
    Args:
        model_id: Model ID to use for inference
        confidence: Confidence threshold (YOLO only)
        class_filter: Comma-separated class names to filter (YOLO only)
        prompts: JSON array of SAM3 prompts (SAM3 only)
        file: Image file (temporary frame)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Inference results (no database records created)
    """
    # Verify model exists
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )
    
    if model.requires_prompts:
        # Prompt-capable model requires prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompts are required for '{model.name}' preview"
            )
    
    # Validate team access
    check_project_team_access(model.project_id, current_user, db)
    
    # Save temporary image
    temp_dir = Path(settings.predictions_dir) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_filename = f"preview_{uuid.uuid4().hex}.jpg"
    temp_path = temp_dir / temp_filename
    
    with open(temp_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Parse prompts for SAM3
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Parse class_filter for YOLO
    class_filter_list = None
    if class_filter:
        class_filter_list = [c.strip() for c in class_filter.split(",") if c.strip()]
    
    # Get BPE path
    bpe_path = None
    if model.metrics_json and isinstance(model.metrics_json, dict):
        bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
    
    try:
        result = inference_service.detect_image(
            model_path=model.artifact_path,
            inference_type=model.inference_type,
            image_path=str(temp_path),
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            prompts=prompts_list,
            bpe_path=bpe_path,
            class_filter=class_filter_list
        )
        
        # Clean up temp file
        temp_path.unlink(missing_ok=True)
        
        return PredictionResponse(
            job_id=0,
            file_name=file.filename,
            task_type=result.task_type,
            inference_time_ms=result.inference_time_ms,
            boxes=result.boxes,
            scores=result.scores,
            classes=result.classes,
            class_names=result.class_names,
            masks=result.masks,
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            top_classes=result.top_classes,
            probabilities=result.probabilities
        )
        
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview inference failed: {str(e)}"
        )

@router.post("/batch", response_model=PredictionJobResponse, status_code=status.HTTP_201_CREATED)
async def infer_batch_images(
    model_id: int = Form(...),
    files: List[UploadFile] = File(...),
    campaign_id: Optional[int] = Form(None),
    confidence: Optional[float] = Form(0.25),
    iou_threshold: Optional[float] = Form(0.45), # Currently unused, reserved for future use
    imgsz: Optional[int] = Form(640), # Image Size, Currently unused, reserved for future use
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    mode: Optional[str] = Form("batch"),  # batch / continuous
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Run inference on multiple images.
    Background worker processes images asynchronously.
    
    Args:
        model_id: Model ID to use for inference
        confidence: Confidence threshold (YOLO only)
        campaign_id: Optional session ID to link results to
        class_filter: Comma-separated class names to filter (YOLO only)
        prompts: JSON array of SAM3 prompts (SAM3 only) - same prompts applied to all images
        files: List of image files
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Job information for batch processing
    """
    # Verify model exists
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )
    
    if model.requires_prompts:
        # Prompt-capable model requires prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompts are required for '{model.name}' batch inference"
            )
    
    # Validate team access
    check_project_team_access(model.project_id, current_user, db)
    
    # Parse prompts for SAM3
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
            if not isinstance(prompts_list, list):
                raise ValueError("Prompts must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Create prediction job
    total_images = len(files)
    job = PredictionJob(
        model_id=model_id,
        creator_id=current_user.id,
        campaign_id=campaign_id,
        mode=PredictionMode.BATCH,
        source_type="batch",
        source_ref=f"{total_images} images"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Initialize summary_json
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list,
        )
        # Add batch metadata
        job.update_metadata(
            total_images=total_images, #total images in batch
            frames_processed=0 #frames processed so far (0 at start)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for batch job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Save uploaded images
    image_paths = []
    file_names = []
    for file in files:
        image_path = await save_uploaded_image(file, job.id)
        image_paths.append(image_path)
        file_names.append(file.filename)
    
    # Parse class_filter for YOLO
    class_filter_list = None
    if class_filter:
        class_filter_list = [c.strip() for c in class_filter.split(",") if c.strip()]
    
    # Start batch processing based on inference type
    if model.inference_type == "sam3":
        # Get BPE path for SAM3
        bpe_path = None
        if model.metrics_json and isinstance(model.metrics_json, dict):
            bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")

        prediction_worker.start_sam3_batch_detection(
            job_id=job.id,
            model_path=model.artifact_path,
            image_paths=image_paths,
            file_names=file_names,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter_list,
            prompts=prompts_list or [],
            bpe_path=bpe_path
        )
    else:  # YOLO
        prediction_worker.start_batch_prediction(
            job_id=job.id,
            model_path=model.artifact_path,
            image_paths=image_paths,
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter_list
        )
    
    return job

@router.post("/video", response_model=PredictionJobResponse, status_code=status.HTTP_201_CREATED)
async def infer_video(
    model_id: int = Form(...),
    campaign_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    capture_mode: str = Form("manual"),  # "continuous" or "manual"
    confidence: float = Form(0.25),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    skip_frames: int = Form(5),
    limit_frames: Optional[int] = Form(None),
    video_duration: Optional[float] = Form(None), # From frontend video info
    video_fps: Optional[float] = Form(None), # From frontend video info
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Run inference on a video file.
    Background worker processes frames asynchronously.
    
    Args:
        model_id: Model ID to use for inference
        confidence: Confidence threshold (YOLO only)
        skip_frames: Process every Nth frame (1-30)
        campaign_id: Optional session ID to link results to
        class_filter: Comma-separated class names to filter (YOLO only)
        prompts: JSON array of prompts (for models that use prompts) - same prompts applied to all frames
        limit_frames: Optional limit to process only first N frames
        file: Video file
        db: Database session
        current_user: Current authenticated user
        video_duration: Optional[float] = Form(None), # From frontend video info
        video_fps: Optional[float] = Form(None), # From frontend video info
        capture_mode: str = Form("manual"),  # "continuous" or "manual"
    Returns:
        Job information for video processing
    """
    # Verify model exists
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )

    if model.requires_prompts:
        # Prompt-capable model requires prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompts are required for '{model.name}' inference"
            )
        
    if capture_mode not in ["manual", "continuous"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="capture_mode must be either 'manual' or 'continuous'"
        )
    
    # Validate team access
    check_project_team_access(model.project_id, current_user, db)
    
    # Validate skip_frames range
    if skip_frames < 1 or skip_frames > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="skip_frames must be between 1 and 30"
        )
    
    # Parse prompts for models that use prompts
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
            if not isinstance(prompts_list, list):
                raise ValueError("Prompts must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    job_status = PredictionStatus.PENDING
    if capture_mode == "manual":
        job_status = PredictionStatus.RUNNING # Manual capture jobs start as RUNNING

    # Create prediction job
    job = PredictionJob(
        model_id=model_id,
        creator_id=current_user.id,
        campaign_id=campaign_id,
        mode=PredictionMode.VIDEO,
        source_type="video",
        source_ref=file.filename,
        status=job_status,
        progress=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Initialize summary_json
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list,
            capture_mode=capture_mode,
            skip_frames=skip_frames,
            limit_frames=limit_frames
        )
        # Add video metadata
        job.update_metadata(
            video_filename=file.filename,
            video_duration=video_duration, # capture_mode == "continuous" will fill after processing
            fps=video_fps,       # capture_mode == "continuous" will fill after processing
            frames_processed=0,  # frames processed so far (0 at start)
            frames_captured=0  # frames captured so far (0 at start)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for video job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")

    if capture_mode == "continuous":
        # Save uploaded video
        video_path = await save_uploaded_video(file, job.id)
        
        # Parse class_filter for YOLO
        class_filter_list = None
        if class_filter:
            class_filter_list = [c.strip() for c in class_filter.split(",") if c.strip()]
        
        # Start video processing based on inference type
        if model.inference_type == "sam3":
            # Get BPE path for SAM3
            bpe_path = None
            if model.metrics_json and isinstance(model.metrics_json, dict):
                bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")

            prediction_worker.start_sam3_video_segmentation(
                job_id=job.id,
                model_path=model.artifact_path,
                video_path=video_path,
                prompts=prompts_list or [],
                skip_frames=skip_frames,
                limit_frames=limit_frames,
                bpe_path=bpe_path
            )
        else:  # YOLO
            prediction_worker.start_video_prediction(
                job_id=job.id,
                model_path=model.artifact_path,
                video_path=video_path,
                task_type=model.task_type,
                confidence=confidence,
                skip_frames=skip_frames,
                limit_frames=limit_frames,
                class_filter=class_filter_list
            )
    
    return job

@router.post("/webcam", response_model=PredictionJobResponse, status_code=status.HTTP_201_CREATED)
async def infer_webcam(
    model_id: int = Form(...),
    campaign_id: Optional[int] = Form(None),
    capture_mode: str = Form("manual"),  # "continuous" or "manual"
    confidence: Optional[float] = Form(0.25),
    iou_threshold: Optional[float] = Form(0.45),
    imgsz: Optional[int] = Form(640),
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Start webcam inference session.
    Supports both manual capture (user clicks capture) and continuous recording.
    
    Args:
        model_id: Model ID to use for inference
        campaign_id: Optional session ID to link results to
        capture_mode: "manual" for user-triggered captures, "continuous" for auto-recording
        confidence: Confidence threshold
        class_filter: Comma-separated class names to filter
        prompts: JSON array of prompts for models requiring prompts
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Job information for webcam session
    """
    # Verify model exists
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )
    
    if model.requires_prompts and capture_mode != "manual":
        # Auto mode validation for models requiring prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompts are required for this model in continuous mode"
            )
    
    # Validate team access for operators
    check_project_team_access(model.project_id, current_user, db)
    
    # Parse prompts
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
            if not isinstance(prompts_list, list):
                raise ValueError("Prompts must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Validate capture mode
    if capture_mode not in ["manual", "continuous"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="capture_mode must be 'manual' or 'continuous'"
        )
    
    # Check for existing active webcam session
    existing_session = db.query(PredictionJob).filter(
        PredictionJob.creator_id == current_user.id,
        PredictionJob.status == PredictionStatus.RUNNING,
        PredictionJob.source_type == "webcam"
    ).first()
    
    if existing_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have an active webcam session (Job #{existing_session.id}). Please stop it before starting a new one."
        )
    
    # Create prediction job
    job = PredictionJob(
        model_id=model_id,
        creator_id=current_user.id,
        campaign_id=campaign_id,
        mode=PredictionMode.VIDEO,  # Webcam uses VIDEO mode (live capture)
        source_type="webcam",
        source_ref="webcam_stream",
        status=PredictionStatus.RUNNING.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Initialize summary_json
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list,
            capture_mode=capture_mode,
        )
        
        # Add webcam metadata
        job.update_metadata(
            frames_processed=0,
            frames_captured=0
        )
        
        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for webcam job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    return job

@router.post("/webcam/{job_id}/capture", response_model=PredictionResponse)
async def capture_webcam_frame(
    job_id: int,
    file: UploadFile = File(...),
    frame_number: Optional[int] = Form(None),
    confidence: Optional[float] = Form(0.25),
    iou_threshold: Optional[float] = Form(0.45),
    imgsz: Optional[int] = Form(640),
    class_filter: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Capture and detect a single frame from an active webcam session.
    Adds prediction result to existing webcam job.
    
    Args:
        job_id: Active webcam session job ID
        file: Frame image file
        frame_number: Optional frame counter
        confidence: Confidence threshold
        class_filter: Comma-separated class names to filter
        prompts: JSON array of prompts for models requiring prompts
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Prediction results for the captured frame
    """
    # Verify job exists and is active
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webcam session not found"
        )
    
    # Verify it's the same user who created the session or admin
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only capture frames in your own sessions"
        )
    
    # Verify job is a webcam session
    if job.source_type != "webcam":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for webcam capture sessions"
        )
    
    # Verify job is still running
    if job.status != PredictionStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webcam session is not active (status: {job.status.value})"
        )
    
    # Get model
    model = db.query(Model).filter(Model.id == job.model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not trained"
        )
    
    # Parse class filter
    class_filter_list = None
    if class_filter:
        class_filter_list = [c.strip() for c in class_filter.split(",")]
    
    # Get existing prompts from job summary
    existing_prompts = job.summary_json.get("prompts", []) if job.summary_json else []
    prompts_to_use = existing_prompts.copy()
    
    # Parse and merge new prompts from frontend
    if prompts:
        try:
            new_prompts = json.loads(prompts)
            if not isinstance(new_prompts, list):
                raise ValueError("Prompts must be a JSON array")
            
            # Check for duplicates and merge
            for new_prompt in new_prompts:
                if new_prompt not in prompts_to_use:
                    prompts_to_use.append(new_prompt)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Save frame image to job directory
    prediction_dir = Path(settings.predictions_dir) / str(job_id)
    prediction_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    frame_filename = f"webcam_frame_{frame_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg" if frame_number else f"webcam_frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = prediction_dir / frame_filename
    
    # Read file content once
    content = await file.read()
    
    # Save uploaded frame to disk
    with open(image_path, "wb") as f:
        f.write(content)
    
    # Get BPE path for SAM3
    bpe_path = None
    if model.metrics_json and isinstance(model.metrics_json, dict):
        bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
    
    # Validate confidence
    if confidence <= 0:
        confidence = (job.summary_json.get("confidence") if job.summary_json else None) or 0.25
        if confidence <= 0:
            confidence = 0.25
    
    try:
        result = inference_service.detect_image(
            model_path=model.artifact_path,
            inference_type=model.inference_type,
            image_path=str(image_path),
            task_type=model.task_type,
            confidence=confidence,
            class_filter=class_filter_list,
            prompts=prompts_to_use,
            bpe_path=bpe_path,
        )
        
        # Store result in database
        from app.schemas.prediction import ResultConfig
        result_config = ResultConfig(
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter_list,
            prompts=prompts_to_use,
            inference_type=model.inference_type
        ).model_dump()
        
        prediction_result = PredictionResult(
            prediction_job_id=job.id,
            file_name=str(image_path),
            frame_number=frame_number,
            task_type=model.task_type,
            boxes_json=result.boxes or [],
            scores_json=result.scores or [],
            classes_json=result.classes or [],
            class_names_json=result.class_names or [],
            masks_json=result.masks or [],
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            config_json=result_config
        )
        db.add(prediction_result)
        
        # Update job metadata
        current_count = job.source_metadata.frames_captured if job.source_metadata else 0
        job.update_metadata(
            last_activity=datetime.now(timezone.utc).isoformat(),
            frames_captured=current_count + 1
        )
        db.commit()
        
        # Return unified prediction response
        return PredictionResponse(
            job_id=job.id,
            result_id=prediction_result.id,
            file_name=prediction_result.file_name,
            task_type=result.task_type,
            boxes=result.boxes or [],
            scores=result.scores or [],
            classes=result.classes or [],
            class_names=result.class_names or [],
            masks=result.masks or [],
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            frame_number=frame_number,
        )
        
    except Exception as e:
        logger.error(f"Webcam frame detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}"
        )

@router.post("/video/{job_id}/capture", response_model=PredictionResponse)
async def capture_video_frame(
    job_id: int,
    file: UploadFile = File(...),
    frame_number: Optional[int] = Form(None),
    frame_timestamp: Optional[str] = Form(None),
    confidence: Optional[float] = Form(0.25),
    class_filter_list: Optional[List[str]] = Form(None),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    prompts: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Capture and detect a single frame from an active video session.
    Adds prediction result to existing VIDEO job.
    
    Args:
        job_id: Active video session job ID
        file: Frame image file
        frame_number: Frame number in video
        frame_timestamp: Video timestamp (e.g., "00:10:01.5" or "601.5")
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        prediction results for the captured frame
    """
    # Verify job exists and is active
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify it's the same user who created the session or admin
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only capture frames in your own sessions"
        )
    
    # Verify job is a manual video session
    if job.mode == PredictionMode.VIDEO:
        if (job.summary_json and job.config.capture_mode != "manual"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint is only for manual video capture sessions"
            )
    
    # Verify job is still running
    if job.status != PredictionStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video session is not active (status: {job.status.value})"
        )
    
    # Get model
    model = db.query(Model).filter(Model.id == job.model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not trained"
        )
    
    # Get existing prompts from job summary
    existing_prompts = job.summary_json.get("prompts", []) if job.summary_json else []
    prompts_to_use = existing_prompts.copy()
    
    # Parse and merge new prompts from frontend
    if prompts:
        try:
            new_prompts = json.loads(prompts)
            if not isinstance(new_prompts, list):
                raise ValueError("Prompts must be a JSON array")
            
            # Check for duplicates and merge
            for new_prompt in new_prompts:
                # Check if prompt already exists (exact match)
                if new_prompt not in prompts_to_use:
                    prompts_to_use.append(new_prompt)

        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Save frame image to job directory
    prediction_dir = Path(settings.predictions_dir) / str(job_id)
    prediction_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    frame_filename = f"frame_{frame_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg" if frame_number else f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = prediction_dir / frame_filename

    # Read file content once
    content = await file.read()
    
    # Save uploaded frame to disk
    with open(image_path, "wb") as f:
        f.write(content)
    
    # Encode frame to base64 from the same content (no re-read needed)
    frame_base64 = base64.b64encode(content).decode('utf-8')
    
    # Get BPE path for SAM3
    bpe_path = None
    if model.metrics_json and isinstance(model.metrics_json, dict):
        bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")

    # Validate confidence: use frontend value if valid (> 0), else fallback to job's saved value, default 0.25
    if confidence <= 0:
        confidence = (job.summary_json.get("confidence") if job.summary_json else None) or 0.25
        # Final safety check
        if confidence <= 0:
            confidence = 0.25
    
    try:
        result = inference_service.detect_image(
            model_path=model.artifact_path,
            inference_type=model.inference_type,
            image_path=str(image_path),
            task_type=model.task_type,
            confidence=confidence,
            class_filter=class_filter_list,
            prompts=prompts_to_use, #SAM3 prompts
            bpe_path=bpe_path, #SAM3 BPE
        )
        
        # Store result in database with configuration tracking
        from app.schemas.prediction import ResultConfig
        result_config = ResultConfig(
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter_list,
            prompts=prompts_to_use,
            inference_type=model.inference_type
        ).model_dump()
        
        prediction_result = PredictionResult(
            prediction_job_id=job.id,
            file_name=str(image_path),
            frame_number=frame_number,
            frame_timestamp=frame_timestamp,
            task_type=model.task_type,
            boxes_json=result.boxes or [],
            scores_json=result.scores or [],
            classes_json=result.classes or [],
            class_names_json=result.class_names or [],
            masks_json=result.masks or [],
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            config_json=result_config
        )
        db.add(prediction_result)
        
        current_count = job.source_metadata.frames_captured if job.source_metadata else 0
        job.update_metadata(
            last_activity=datetime.now(timezone.utc).isoformat(),
            frames_captured=current_count + 1
        )
        
        db.commit()
        db.refresh(prediction_result)
        
        return PredictionResponse(
            id=prediction_result.id,
            result_id=prediction_result.id,
            job_id=job_id,
            file_name=frame_filename,
            frame_base64=frame_base64,
            task_type=result.task_type,
            inference_time_ms=result.inference_time_ms,
            boxes=result.boxes,
            scores=result.scores,
            classes=result.classes,
            class_names=result.class_names,
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            top_classes=result.top_classes,
            probabilities=result.probabilities,
            masks=result.masks  # Include masks in response
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"prediction failed: {str(e)}"
        )

@router.post("/rtsp", response_model=PredictionJobResponse, status_code=status.HTTP_201_CREATED)
async def infer_rtsp(
    model_id: int = Form(...),
    rtsp_url: str = Form(...),
    prompts: Optional[str] = Form(None),
    capture_mode: str = Form("manual"),  # "continuous" or "manual"
    skip_frames: int = Form(10),
    limit_frames: Optional[int] = Form(None),
    campaign_id: Optional[int] = Form(None),
    confidence: float = Form(0.25),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    class_filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)   
):
    """
    Start RTSP stream inference.
    
    Args:
        model_id:  Model ID
        rtsp_url: RTSP stream URL (e.g., rtsp://camera.local:554/stream)
        prompts: JSON array of SAM3 prompts (text-only for RTSP) FOR SAM3
        capture_mode: "continuous" (auto-save all frames) or "manual" (preview only)
        skip_frames: Process every Nth frame (default 10 for SAM3 performance)
        campaign_id: Optional prediction session ID
        class_filter: Optional comma-separated class names to filter
        
    Returns:
        PredictionJob with job_id for polling
    """

    # Get model
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    if model.requires_prompts:
        # Prompt-capable model requires prompts
        if not prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompts are required for '{model.name}' inference"
            )
    
    # Validate team access
    check_project_team_access(model.project_id, current_user, db)
    
    # Validate skip_frames range
    if skip_frames < 1 or skip_frames > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="skip_frames must be between 1 and 30"
        )
    
    # Parse prompts for SAM3
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
            if not isinstance(prompts_list, list):
                raise ValueError("Prompts must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Create PredictionJob
    job = PredictionJob(
        creator_id=current_user.id,
        model_id=model_id,
        mode=PredictionMode.RTSP,
        source_type="rtsp",
        source_ref=rtsp_url,
        status=PredictionStatus.PENDING.value,
        campaign_id=campaign_id
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)

    # Initialize summary_json
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list,
            capture_mode=capture_mode,
            skip_frames=skip_frames,
            limit_frames=limit_frames
        )

        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for video job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Start RTSP worker
    if model.inference_type == "sam3":
        # Get BPE path for SAM3
        bpe_path = None
        if model.metrics_json and isinstance(model.metrics_json, dict):
            bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
        
        prediction_worker.start_rtsp_sam3_detection(
            job_id=job.id,
            model_path=model.artifact_path,
            bpe_path=bpe_path,
            rtsp_url=rtsp_url,
            prompts=prompts_list,
            skip_frames=skip_frames,
            capture_mode=capture_mode,
            class_filter=class_filter.split(",") if class_filter else None
        )
    else:  # YOLO
        prediction_worker.start_rtsp_prediction(
            job_id=job.id,
            model_path=model.artifact_path,
            rtsp_url=rtsp_url,
            task_type=model.task_type,
            confidence=0.25,
            skip_frames=skip_frames,
            capture_mode=capture_mode,
            class_filter=class_filter.split(",") if class_filter else None
        )
    
    return job

@router.post("/rtsp/{job_id}/capture", response_model=PredictionResponse)
async def capture_rtsp_frame(
    job_id: int,
    confidence: Optional[float] = Form(0.25),
    class_filter_list: Optional[List[str]] = Form(None),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    prompts: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Capture and save the current RTSP frame (manual mode). 
    The backend captures the frame from OpenCV worker memory and then runs inference on it.
    The frame and masks are saved to the database as a PredictionResult. 
    Its different from the video and webcam inference where frame captures in frontend and sent to backend for inference.
    
    Args:
        job_id: PredictionJob ID
        confidence: Confidence threshold
        prompts: Optional JSON array of new SAM3 prompts to add (will be merged with existing prompts)
        class_filter_list: Optional list of class names to filter
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Saved PredictionResult with frame and masks
    """
    import cv2
    from pathlib import Path
    
    # Get job
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get existing prompts from job summary
    existing_prompts = job.summary_json.get("prompts", []) if job.summary_json else []
    prompts_to_use = existing_prompts.copy()
    
    # Parse and merge new prompts from frontend
    if prompts:
        try:
            new_prompts = json.loads(prompts)
            if not isinstance(new_prompts, list):
                raise ValueError("Prompts must be a JSON array")
            
            # Check for duplicates and merge
            for new_prompt in new_prompts:
                # Check if prompt already exists (exact match)
                if new_prompt not in prompts_to_use:
                    prompts_to_use.append(new_prompt)
            
            # Update job summary with merged prompts
            if job.summary_json:
                job.summary_json["prompts"] = prompts_to_use
                job.summary_json["prompts_count"] = len(prompts_to_use)
            else:
                job.summary_json = {
                    "prompts": prompts_to_use,
                    "prompts_count": len(prompts_to_use)
                }
            db.commit()
            
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid prompts format: {str(e)}"
            )
    
    # Check permissions
    if job.creator_id != current_user.id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job"
        )
    
    # Get latest frame from worker memory
    if job_id not in prediction_worker._active_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not active"
        )
    
    job_data = prediction_worker._active_jobs[job_id]
    latest_frame = job_data.get('latest_frame')
    
    if latest_frame is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No frames captured yet"
        )
    
    # Get model info from job
    model = db.query(Model).filter(Model.id == job.model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Save frame to disk
    frames_saved = db.query(PredictionResult).filter(
        PredictionResult.prediction_job_id == job_id
    ).count()
    
    temp_path = Path(settings.predictions_dir) / str(job_id) / f"manual_frame_{frames_saved}.jpg"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(temp_path), latest_frame)
    
    # Get BPE path for SAM3
    bpe_path = None
    if model.metrics_json and isinstance(model.metrics_json, dict):
        bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
        
    result = inference_service.detect_image(
        model_path=model.artifact_path,
        inference_type=model.inference_type,
        image_path=str(temp_path),
        task_type=model.task_type,
        confidence=confidence,
        prompts=prompts_to_use,
        bpe_path=bpe_path,
        class_filter=class_filter_list
    )
    
    # Store result in database with configuration tracking
    from app.schemas.prediction import ResultConfig
    result_config = ResultConfig(
        confidence=confidence,
        iou_threshold=iou_threshold,
        imgsz=imgsz,
        class_filter=class_filter_list,
        prompts=prompts_to_use,
        inference_type=model.inference_type
    ).model_dump()
    
    prediction_result = PredictionResult(
        prediction_job_id=job.id,
        file_name=f"manual_frame_{frames_saved}.jpg",
        task_type=model.task_type,
        frame_number=frames_saved,
        boxes_json=result.boxes or [],
        scores_json=result.scores or [],
        classes_json=result.classes or [],
        class_names_json=result.class_names or [],
        masks_json=result.masks or [],
        top_class=result.top_class,
        top_confidence=result.top_confidence,
        config_json=result_config
    )
    db.add(prediction_result)
    db.commit()
    db.refresh(prediction_result)
    
    # Update manual session metadata
    try:
        current_count = job.source_metadata.frames_captured if job.source_metadata else 0
        job.update_metadata(
            last_activity=datetime.now(timezone.utc).isoformat(),
            frames_captured=current_count + 1
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to update metadata for job {job_id}: {e}")

    # Encode frame to base64
    _, buffer = cv2.imencode('.jpg', latest_frame)
    frame_base64 = base64.b64encode(buffer).decode('utf-8')

    # Return unified response
    return PredictionResponse(
        id=prediction_result.id,
        job_id=job.id,
        file_name=prediction_result.file_name,
        frame_number=prediction_result.frame_number,
        frame_base64=frame_base64,
        task_type=result.task_type,
        inference_time_ms=result.inference_time_ms,
        boxes=result.boxes,
        scores=result.scores,
        classes=result.classes,
        class_names=result.class_names,
        masks=result.masks,
        top_class=result.top_class,
        top_confidence=result.top_confidence,
        top_classes=result.top_classes,
        probabilities=result.probabilities,
        result_id=prediction_result.id
    )

@router.get("/rtsp/{job_id}/latest-frame")
async def get_latest_rtsp_frame(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get latest frame with prediction data for RTSP job.
    Used for manual capture mode to retrieve current frame and prediction results.
    
    Args:
        job_id: prediction job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with base64-encoded frame and prediction data
    """
    from app.workers.prediction_worker import prediction_worker
    import base64
    import cv2
    
    # Verify job exists and user has access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access permissions (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if job is active
    if job_id not in prediction_worker._active_jobs:
        raise HTTPException(status_code=404, detail="Job not active or no frames available yet")
    
    job_data = prediction_worker._active_jobs[job_id]
    frame = job_data.get('latest_frame')
    results = job_data.get('latest_results')
    
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame available yet")
    
    # Encode frame to base64
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return {
        "frame": f"data:image/jpeg;base64,{frame_base64}",
        "predictions": results if results else {
            "boxes": [],
            "scores": [],
            "classes": [],
            "class_names": [],
            "masks": []
        }
    }

# JOB AND RESULT ENDPOINTS
@router.get("/jobs", response_model=PaginatedPredictionJobsResponse)
async def list_prediction_jobs(
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    dataset_id: Optional[int] = None,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    task_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of prediction jobs with advanced filtering and pagination.
    Non-admin users see only their own jobs. Admins see all jobs.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        model_id: Optional filter by model ID
        dataset_id: Optional filter by dataset ID (via model -> project -> dataset)
        status: Optional filter by status (pending, running, completed, failed)
        mode: Optional filter by mode (single, batch, video, rtsp)
        task_type: Optional filter by task type (detect, classify, segment)
        start_date: Optional filter by created_at >= start_date (ISO format)
        end_date: Optional filter by created_at <= end_date (ISO format)
        search: Optional search by job ID or source reference
        sort_by: Sort column (id, mode, status, created_at, progress). Default: created_at
        sort_order: Sort order (asc, desc). Default: desc
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Paginated response with jobs, total count, skip, and limit
    """
    # Validate sort parameters
    valid_sort_columns = ["id", "mode", "status", "created_at", "progress"]
    if sort_by not in valid_sort_columns:
        sort_by = "created_at"
    if sort_order not in ["asc", "desc"]:
        sort_order = "desc"
    
    query = db.query(PredictionJob).join(Model)
    
    # Filter by user (non-admin users see only their own jobs)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(PredictionJob.creator_id == current_user.id)
    
    if model_id:
        query = query.filter(PredictionJob.model_id == model_id)
    
    if dataset_id:
        # Filter by dataset through model -> project -> dataset
        query = query.join(Project, Model.project_id == Project.id).filter(Project.dataset_id == dataset_id)
    
    if status:
        try:
            status_enum = PredictionStatus(status.lower())
            query = query.filter(PredictionJob.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    if mode:
        try:
            mode_enum = PredictionMode(mode.lower())
            query = query.filter(PredictionJob.mode == mode_enum)
        except ValueError:
            pass  # Invalid mode, ignore filter
    
    if task_type:
        # Filter by task_type through the model's task_type
        query = query.filter(Model.task_type == task_type.lower())
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(PredictionJob.created_at >= start_dt)
        except ValueError:
            pass  # Invalid date, ignore filter
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(PredictionJob.created_at <= end_dt)
        except ValueError:
            pass  # Invalid date, ignore filter
    
    if search:
        # Search by job ID (if numeric) or source_ref (case-insensitive)
        from sqlalchemy import or_
        search_filters = [PredictionJob.source_ref.ilike(f'%{search}%')]
        if search.isdigit():
            search_filters.append(PredictionJob.id == int(search))
        query = query.filter(or_(*search_filters))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply sorting
    sort_column_map = {
        "id": PredictionJob.id,
        "mode": PredictionJob.mode,
        "status": PredictionJob.status,
        "created_at": PredictionJob.created_at,
        "progress": PredictionJob.progress,
    }
    
    # Validate and apply sorting
    sort_column = sort_column_map.get(sort_by, PredictionJob.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Apply pagination
    jobs = query.offset(skip).limit(limit).all()
    
    # Add results count and convert to response models
    job_responses = []
    for job in jobs:
        job.results_count = db.query(PredictionResult).filter(
            PredictionResult.prediction_job_id == job.id
        ).count()
        # Add task_type from model relationship
        job.task_type = job.model.task_type if job.model else None
        # Convert to response model (model_name, project_name, session_name come from properties)
        job_responses.append(PredictionJobResponse.model_validate(job))
    
    return PaginatedPredictionJobsResponse(
        jobs=job_responses,
        total=total,
        skip=skip,
        limit=limit
    )

@router.post("/jobs/start", response_model=PredictionJobResponse, status_code=status.HTTP_201_CREATED, deprecated=True)
async def start_inference_job(
    model_id: int = Form(...),
    campaign_id: Optional[int] = Form(None),
    filename: str = Form(...),
    source_type: Optional[str] = Form(None),  # video for now
    confidence: Optional[float] = Form(0.25),
    class_filter: Optional[str] = Form(None),
    iou_threshold: float = Form(0.45), # Currently unused, reserved for future use
    imgsz: int = Form(640), # Image Size, Currently unused, reserved for future use
    prompts: Optional[str] = Form(None),  # JSON string for SAM3 prompts
    skip_frames: int = Form(5),
    limit_frames: Optional[int] = Form(None),
    video_duration: Optional[float] = Form(None), # From frontend video info
    video_fps: Optional[float] = Form(None), # From frontend video info
    mode: Optional[str] = Form(None),  # Deprecated: capture mode
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    **DEPRECATED**: Use dedicated source endpoints instead:
    - Webcam: POST /api/inference/webcam
    - Video: POST /api/inference/video
    - RTSP: POST /api/inference/rtsp
    
    This endpoint will be removed in a future version.
    
    Legacy endpoint for starting manual capture sessions.
    Creates a VIDEO mode job that will accumulate manual frame captures.
    
    Args:
        model_id: Model ID
        filename: Name of the video file being processed
        source_type: Source type (webcam, video, rtsp) - use dedicated endpoints instead
        prompts: JSON array of prompt objects
        campaign_id: Optional session ID to link to
        
    Returns:
        Job information for the manual capture session
    """
    logger.warning(f"DEPRECATED: User {current_user.id} called /jobs/start for {source_type}. Use dedicated endpoints instead.")
    # Verify model exists 
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or not configured"
        )
    
    # Check for existing active session by this user
    existing_session = db.query(PredictionJob).filter(
        PredictionJob.creator_id == current_user.id,
        PredictionJob.status == PredictionStatus.RUNNING,
        PredictionJob.mode == (PredictionMode.VIDEO or PredictionMode.RTSP)
    ).first()
    
    if existing_session and existing_session.summary_json and existing_session.summary_json.get('capture_mode') == 'manual':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have an active video or rtsp manual session (Job #{existing_session.id}). Please finish it before starting a new one."
        )
    
    prompts_list = []
    if model.inference_type == "sam3":
        if not prompts:
            raise ValueError("Prompts are required for SAM3 video session")
        else:
            # Parse prompts JSON
            try:
                prompts_list = json.loads(prompts)
                if not isinstance(prompts_list, list):
                    raise ValueError("Prompts must be a JSON array")
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid prompts format: {str(e)}"
                )
    
    # Validate team access for operators
    check_project_team_access(model.project_id, current_user, db)
    
    # Create prediction job for video manual session
    job = PredictionJob(
        model_id=model_id,
        creator_id=current_user.id,
        campaign_id=campaign_id,
        mode=PredictionMode.VIDEO,
        source_type=source_type,
        source_ref=filename,
        status=PredictionStatus.RUNNING.value,  # Session is active
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Initialize summary_json
    try:
        job.initialize_summary(
            task_type=model.task_type,
            confidence=confidence,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
            class_filter=class_filter.split(",") if class_filter else None,
            prompts=prompts_list,
            capture_mode="manual",
            skip_frames=skip_frames,
            limit_frames=limit_frames
        )

        # Add video metadata
        job.update_metadata(
            video_filename=filename,
            video_duration=video_duration,
            fps=video_fps,
            frames_processed=0,
            frames_captured=0
        )
        
        db.commit()
    except Exception as e:
        logger.error(f"Failed to initialize summary for video job {job.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    return job

@router.get("/jobs/stats", response_model=Dict[str, Any])
async def get_job_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get prediction jobs statistics.
    Returns counts for total, running, completed, failed jobs,
    and breakdowns by mode and total predictions.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Statistics dictionary
    """
    # Filter by user (non-admin users see only their own jobs)
    base_query = db.query(PredictionJob)
    if current_user.role != UserRole.ADMIN:
        base_query = base_query.filter(PredictionJob.creator_id == current_user.id)
    
    # Count by status
    total_jobs = base_query.count()
    running_jobs = base_query.filter(PredictionJob.status == PredictionStatus.RUNNING).count()
    completed_jobs = base_query.filter(PredictionJob.status == PredictionStatus.COMPLETED).count()
    failed_jobs = base_query.filter(PredictionJob.status == PredictionStatus.FAILED).count()
    
    # Count by mode
    single_jobs = base_query.filter(PredictionJob.mode == PredictionMode.SINGLE).count()
    batch_jobs = base_query.filter(PredictionJob.mode == PredictionMode.BATCH).count()
    video_jobs = base_query.filter(PredictionJob.mode == PredictionMode.VIDEO).count()
    rtsp_jobs = base_query.filter(PredictionJob.mode == PredictionMode.RTSP).count()
    
    # Calculate total predictions from completed jobs
    completed = base_query.filter(PredictionJob.status == PredictionStatus.COMPLETED).all()
    total_predictions = sum(job.summary_json.get('total_predictions', 0) for job in completed if job.summary_json)
    
    # Calculate average confidence
    confidences = [job.summary_json.get('average_confidence', 0) for job in completed if job.summary_json and job.summary_json.get('average_confidence')]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        "total_jobs": total_jobs,
        "running_jobs": running_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "single_jobs": single_jobs,
        "batch_jobs": batch_jobs,
        "video_jobs": video_jobs,
        "rtsp_jobs": rtsp_jobs,
        "total_predictions": total_predictions,
        "average_confidence": round(avg_confidence, 4)
    }


def __finalize_job_with_stats(
    job: PredictionJob,
    final_status: PredictionStatus,
    db: Session
) -> None:
    """
    Helper function to stop worker, calculate final statistics, and update job status.
    Uses the new summary JSON architecture with finalize_stats() method.
    Shared logic for cancel/stop operations.
    
    Args:
        job: PredictionJob to finalize
        final_status: Final status (CANCELLED or COMPLETED)
        db: Database session
    """
    # Stop the inference worker job
    prediction_worker.stop_job(job_id=job.id)

    # Get all results for final summary
    results = db.query(PredictionResult).filter(
        PredictionResult.prediction_job_id == job.id
    ).all()
    
    # Get task type from job config or model
    task_type = "detect"  # Default
    try:
        if job.config and hasattr(job.config, 'task_type'):
            task_type = getattr(job.config, 'task_type', 'detect')
        elif job.model:
            task_type = job.model.task_type
    except Exception as e:
        logger.warning(f"Could not determine task_type for job {job.id}, defaulting to 'detect': {e}")
    
    # Use finalize_stats method to calculate and update stats with task-specific schema
    try:
        job.finalize_stats(task_type=task_type, results=results)
    except Exception as e:
        logger.error(f"Failed to finalize stats for job {job.id}: {e}")
        # Fallback to basic stats update
        job.update_stats(
            replace=True,
            total_detections=sum(len(r.boxes_json or []) for r in results),
            class_counts={},
            average_confidence=0.0,
            inference_time_ms=0.0,
            processing_time_ms=0.0
        )
    
    # Update metadata with final session info
    try:
        job.update_metadata(
            frames_captured=len(results),
            inactive_since=datetime.now(timezone.utc).isoformat() if final_status == PredictionStatus.CANCELLED else None
        )
    except Exception as e:
        logger.error(f"Failed to update metadata for job {job.id}: {e}")

    # Update job status
    job.status = final_status.value
    job.completed_at = datetime.now(timezone.utc)
    job.progress = 100

@router.post("/jobs/{job_id}/cancel", response_model=PredictionJobResponse)
async def cancel_inference_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a running prediction job (aborted by user).
    
    Args:
        job_id: ID of the job to cancel
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated job information with CANCELLED status
    """
    from app.models.prediction_job import PredictionJob, PredictionStatus
    from app.schemas.prediction import PredictionJobResponse
    
    # Get job
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Check permissions (user must own the job or be admin)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this job"
        )
    
    # Only cancel if job is running or pending
    if job.status not in [PredictionStatus.RUNNING.value, PredictionStatus.PENDING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    # Finalize job with CANCELLED status
    __finalize_job_with_stats(job, PredictionStatus.CANCELLED, db)
    
    db.commit()
    # No refresh needed - we have the updated object in memory
    
    return PredictionJobResponse.model_validate(job)

@router.post("/jobs/{job_id}/stop", response_model=PredictionJobResponse)
async def stop_inference_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Stop a manual video/RTSP session (finished by user, not cancelled).
    
    Args:
        job_id: ID of the job to stop
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated job information with COMPLETED status
    """
    from app.models.prediction_job import PredictionJob, PredictionStatus
    from app.schemas.prediction import PredictionJobResponse
    
    # Get job
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Check permissions (user must own the job or be admin)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to stop this job"
        )
    
    # Only stop if job is running
    if job.status != PredictionStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop job with status: {job.status}. Use /cancel for pending jobs."
        )
    
    # Finalize job with COMPLETED status
    __finalize_job_with_stats(job, PredictionStatus.COMPLETED, db)
    
    db.commit()
    # No refresh needed - we have the updated object in memory
    
    return PredictionJobResponse.model_validate(job)

@router.get("/jobs/{job_id}", response_model=PredictionJobResponse)
async def get_inference_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get prediction job details.
    Validates team access.
    
    Args:
        job_id: prediction job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        prediction job details
    """
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Add results count
    job.results_count = db.query(PredictionResult).filter(
        PredictionResult.prediction_job_id == job.id
    ).count()
    
    # Convert to response model (model_name, session_name come from properties)
    return PredictionJobResponse.model_validate(job)

@router.post("/jobs/{job_id}/heartbeat")
async def video_session_heartbeat(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update last activity timestamp for job session to prevent timeout.
    
    Args:
        job_id: prediction job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message with session status
    """
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify it's the same user who created the session or admin
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send heartbeat to your own sessions"
        )
    
    # Update last activity
    if job.summary_json:
        job.summary_json["last_activity"] = datetime.now(timezone.utc).isoformat()
        job.summary_json["inactive_warning_shown"] = False  # Reset warning flag
        db.commit()
    
    return {
        "status": "ok",
        "job_id": job_id,
        "last_activity": job.summary_json.get("last_activity") if job.summary_json else None
    }

@router.get("/jobs/{job_id}/results", response_model=List[PredictionResponse])
async def get_inference_results(
    job_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get prediction results for a job.
    Validates team access.
    
    Args:
        job_id: prediction job ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of prediction results
    """
    # Verify job exists
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get results
    results = db.query(PredictionResult).filter(
        PredictionResult.prediction_job_id == job_id
    ).offset(skip).limit(limit).all()
    
    # Convert to response format (using unified PredictionResponse)
    return [PredictionResponse.from_orm_with_json(r) for r in results]

@router.get("/results/{result_id}/image")
async def get_result_image(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the source image for a prediction result.
    
    Args:
        result_id: prediction result ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Image file
    """
    # Get prediction result
    result = db.query(PredictionResult).filter(
        PredictionResult.id == result_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"prediction result {result_id} not found"
        )
    
    # Get job to find image path using lazy relationship
    job = result.prediction_job
    if not job: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated prediction job not found"
        )
    
    # Check access: admin or job creator
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource"
        )
    
    # Construct image path - handle both single file and frame extraction cases
    image_path = Path(settings.predictions_dir) / str(job.id) / result.file_name
    
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image file not found at {image_path}"
        )
    
    return FileResponse(image_path)

# EXPORT JOBS ENDPOINTS -> For future the export job will be handled by a separate "export" service. This file only handles the AI inference related endpoints.
@router.post("/jobs/{job_id}/export/images", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def export_images(
    job_id: int,
    annotated: bool = True,
    result_ids: Optional[str] = None,  # Comma-separated IDs
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export prediction images as ZIP file.
    
    Args:
        job_id: prediction job ID
        annotated: Include bounding boxes on images
        result_ids: Comma-separated result IDs (optional, exports all if not provided)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Export job information
    """
    from app.models.export_job import ExportJob, ExportType
    from app.workers.export_worker import export_worker
    
    # Verify job exists and user has access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Parse result IDs
    result_id_list = None
    if result_ids:
        try:
            result_id_list = [int(id.strip()) for id in result_ids.split(',')]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid result_ids format"
            )
    
    # Create export job
    export_job = ExportJob(
        prediction_job_id=job_id,
        export_type=ExportType.IMAGES_ZIP,
        creator_id=current_user.id,
        options_json={
            'annotated': annotated,
            'result_ids': result_id_list
        }
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    
    # Start export in background
    export_worker.start_export(
        export_job.id,
        job_id,
        ExportType.IMAGES_ZIP,
        export_job.options_json
    )
    
    return {"export_job_id": export_job.id, "status": "processing"}

@router.post("/jobs/{job_id}/export/data", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def export_data(
    job_id: int,
    format: str = "json",  # json or csv
    result_ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export prediction data as JSON or CSV.
    
    Args:
        job_id: prediction job ID
        format: Export format (json or csv)
        result_ids: Comma-separated result IDs (optional)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Export job information
    """
    from app.models.export_job import ExportJob, ExportType
    from app.workers.export_worker import export_worker
    
    if format not in ['json', 'csv']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'json' or 'csv'"
        )
    
    # Verify job exists and user has access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Parse result IDs
    result_id_list = None
    if result_ids:
        try:
            result_id_list = [int(id.strip()) for id in result_ids.split(',')]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid result_ids format"
            )
    
    # Create export job
    export_type = ExportType.DATA_JSON if format == 'json' else ExportType.DATA_CSV
    export_job = ExportJob(
        prediction_job_id=job_id,
        export_type=export_type,
        creator_id=current_user.id,
        options_json={
            'result_ids': result_id_list
        }
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    
    # Start export in background
    export_worker.start_export(
        export_job.id,
        job_id,
        export_type,
        export_job.options_json
    )
    
    return {"export_job_id": export_job.id, "status": "processing"}

@router.post("/jobs/{job_id}/export/pdf", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def export_pdf(
    job_id: int,
    result_ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export prediction report as PDF.
    
    Args:
        job_id: prediction job ID
        result_ids: Comma-separated result IDs (optional, limited to 100)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Export job information
    """
    from app.models.export_job import ExportJob, ExportType
    from app.workers.export_worker import export_worker
    
    # Verify job exists and user has access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Parse result IDs
    result_id_list = None
    if result_ids:
        try:
            result_id_list = [int(id.strip()) for id in result_ids.split(',')]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid result_ids format"
            )
    
    # Create export job
    export_job = ExportJob(
        prediction_job_id=job_id,
        export_type=ExportType.REPORT_PDF,
        creator_id=current_user.id,
        options_json={
            'annotated': True,
            'result_ids': result_id_list
        }
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    
    # Start export in background
    export_worker.start_export(
        export_job.id,
        job_id,
        ExportType.REPORT_PDF,
        export_job.options_json
    )
    
    return {"export_job_id": export_job.id, "status": "processing"}

@router.get("/jobs/{job_id}/export/{export_id}/status")
async def get_export_status(
    job_id: int,
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get export job status.
    
    Args:
        job_id: prediction job ID
        export_id: Export job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Export job status
    """
    from app.models.export_job import ExportJob
    from app.schemas.export import ExportJobResponse
    
    # Verify prediction job access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get export job
    export_job = db.query(ExportJob).filter(
        ExportJob.id == export_id,
        ExportJob.prediction_job_id == job_id
    ).first()
    
    if not export_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found"
        )
    
    return ExportJobResponse.model_validate(export_job)

@router.get("/jobs/{job_id}/export/{export_id}/download")
async def download_export(
    job_id: int,
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Download export file.
    
    Args:
        job_id: prediction job ID
        export_id: Export job ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        File download
    """
    from app.models.export_job import ExportJob
    
    # Verify prediction job access
    job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get export job
    export_job = db.query(ExportJob).filter(
        ExportJob.id == export_id,
        ExportJob.prediction_job_id == job_id
    ).first()
    
    if not export_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found"
        )
    
    if export_job.status.value != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export is not ready. Current status: {export_job.status.value}"
        )
    
    if not export_job.file_path or not Path(export_job.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found"
        )
    
    # Determine media type based on file extension
    file_ext = Path(export_job.file_path).suffix.lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.zip': 'application/zip',
        '.json': 'application/json',
        '.csv': 'text/csv'
    }
    media_type = media_type_map.get(file_ext, 'application/octet-stream')
    
    # Get clean filename
    clean_filename = Path(export_job.file_path).name
    
    return FileResponse(
        export_job.file_path,
        media_type=media_type,
        filename=clean_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{clean_filename}"'
        }
    )

@router.post("/results/{result_id}/export/pdf", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def export_single_result_pdf(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export single prediction result as PDF with images and prediction details.
    
    Args:
        result_id: prediction result ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Export job information
    """
    from app.models.export_job import ExportJob, ExportType
    from app.workers.export_worker import export_worker
    
    # Get prediction result
    result = db.query(PredictionResult).filter(
        PredictionResult.id == result_id
    ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction result not found"
        )
    
    # Get prediction job
    job = db.query(PredictionJob).filter(
        PredictionJob.id == result.prediction_job_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prediction job not found"
        )
    
    # Verify access (user-scoped)
    if job.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Create export job
    export_job = ExportJob(
        prediction_job_id=job.id,
        export_type=ExportType.REPORT_PDF,
        creator_id=current_user.id,
        options_json={
            'result_id': result_id,
            'single_result': True
        }
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)
    
    # Start export in background
    export_worker.start_export(
        export_job.id,
        job.id,
        ExportType.REPORT_PDF,
        export_job.options_json
    )
    
    return {"export_job_id": export_job.id, "status": "processing", "result_id": result_id}

# Model and Capabilities Endpoints, this endpoints will be deprecated, use /models service instead. Make sure no one is using them before removing.
@router.get("/models", response_model=List[Dict[str, Any]])
async def list_inference_models(
    inference_type: Optional[str] = None,
    task_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of available inference models.
    
    Args:
        inference_type: Optional filter by inference type (yolo, sam3, etc.)
        task_type: Optional filter by task type (detection, segmentation, etc.)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of model info dictionaries
    """
    import warnings
    warnings.warn("This endpoints will be deprecated, use /models service instead.", DeprecationWarning, stacklevel=2)

    query = db.query(Model).filter(Model.artifact_path.isnot(None))
    
    if inference_type:
        query = query.filter(Model.inference_type == inference_type)
        
    if task_type:
        query = query.filter(Model.task_type == task_type)
    
    models = query.all()
    
    return [
        {
            "id": m.id,
            "name": m.name,
            "base_type": m.base_type,
            "inference_type": m.inference_type,
            "task_type": m.task_type,
            "project_id": m.project_id,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in models
    ]

@router.get("/capabilities")
async def get_inference_capabilities():
    """
    Get inference service capabilities and supported model types.
    
    Returns:
        Service info and capabilities
    """
    return {
        "service": "Unified Inference API",
        "version": "1.0.0",
        "inference_types": inference_service.get_supported_inference_types(),
        "endpoints": {
            "single": "POST /api/inference/single - Single image inference",
            "preview": "POST /api/inference/preview - Preview mode (no DB)",
            "batch": "POST /api/inference/batch - Batch image inference",
            "video": "POST /api/inference/video - Video file inference",
            "models": "GET /api/inference/models - List available models"
        },
        "features": [
            "Model-agnostic routing via inference_type field",
            "YOLO detection/classification/segmentation",
            "SAM3 prompt-based segmentation (text/point/box)",
            "Automatic inference service routing",
            "Unified response format",
            "Background processing for batch/video",
            "Hybrid Inference architecture ready"
        ]
    }

@router.post("/validate")
async def validate_inference_config(
    model_id: int = Form(...),
    task_type: Optional[str] = Form(None),
    prompts: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Validate inference configuration before running.
    
    Args:
        model_id: Model ID to validate
        task_type: Optional task type override
        prompts: Optional SAM3 prompts JSON
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Validation results with errors/warnings/recommendations
    """
    # Get model
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Parse prompts if provided
    prompts_list = None
    if prompts:
        try:
            prompts_list = json.loads(prompts)
        except (json.JSONDecodeError, ValueError) as e:
            return {
                "valid": False,
                "errors": [f"Invalid prompts JSON: {str(e)}"],
                "warnings": [],
                "recommendations": []
            }
    
    # Use model's task_type if not overridden
    effective_task_type = task_type or model.task_type
    
    # Validate using inference service
    validation = inference_service.validate_model_config(
        inference_type=model.inference_type,
        task_type=effective_task_type,
        prompts=prompts_list
    )
    
    return validation
