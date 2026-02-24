"""
External Inference API Router
Public API endpoints for running inference with API key authentication.

This API is designed for external integrations (free users without workflows).
All endpoints require API key authentication and track usage for rate limiting.
"""
from typing import List, Optional, Dict, Any
import json
import logging
import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import get_db
from app.models.user import User
from app.models.model import Model
from app.models.inference_api_call import InferenceApiCall
from app.models.prediction_job import PredictionJob, PredictionMode, PredictionStatus
from app.models.prediction_result import PredictionResult
from app.schemas.prediction import PredictionResponse
from app.utils.api_key_auth import get_user_from_api_key
from app.utils.file_handler import save_uploaded_image
from app.services.inference_service import inference_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/external/inference", tags=["External Inference"])

# Rate limit: 100 calls per hour (configurable via .env)
RATE_LIMIT_PER_HOUR = getattr(settings, 'EXTERNAL_INFERENCE_RATE_LIMIT_PER_HOUR', 100)

def check_rate_limit(user_id: int, db: Session) -> None:
    """
    Check if user has exceeded rate limit for external inference API.
    
    Raises HTTPException 429 if limit exceeded.
    """
    # Count calls in the last hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    call_count = db.query(InferenceApiCall).filter(
        InferenceApiCall.user_id == user_id,
        InferenceApiCall.called_at >= one_hour_ago
    ).count()
    
    if call_count >= RATE_LIMIT_PER_HOUR:
        # Calculate retry-after (time until oldest call expires)
        oldest_call = db.query(InferenceApiCall).filter(
            InferenceApiCall.user_id == user_id,
            InferenceApiCall.called_at >= one_hour_ago
        ).order_by(InferenceApiCall.called_at).first()
        
        if oldest_call:
            retry_after_seconds = int(3600 - (datetime.now(timezone.utc) - oldest_call.called_at).total_seconds())
        else:
            retry_after_seconds = 3600
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_PER_HOUR} calls per hour. Try again in {retry_after_seconds} seconds.",
            headers={"Retry-After": str(retry_after_seconds)}
        )

def get_model_by_api_key(model_key: str, user_id: int, db: Session) -> Model:
    """
    Get model by API key and validate ownership.
    
    All models are private - user must own the model to use it.
    """
    model = db.query(Model).filter(Model.api_key == model_key).first()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Validate ownership (all models are private)
    if model.project.creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only use models you own."
        )
    
    if model.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model is not ready for inference. Current status: {model.status}"
        )
    
    return model

@router.get("/models/{model_key}/info")
async def get_model_info(
    model_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_api_key)
):
    """
    Get model capabilities and schema for external API usage.
    
    Returns:
        - task_type: detect, classify, or segment
        - requires_prompts: whether model needs prompts (SAM3, etc.)
        - prompt_schema: available prompt types if applicable
        - example_request: sample request body
    """
    model = get_model_by_api_key(model_key, current_user.id, db)
    
    response = {
        "model_key": str(model.api_key),
        "model_name": model.name,
        "task_type": model.task_type,
        "inference_type": model.inference_type,
        "requires_prompts": model.requires_prompts,
        "prompt_schema": None,
        "example_request": {}
    }
    
    # Add prompt schema if model requires prompts
    if model.requires_prompts:
        response["prompt_schema"] = {
            "text": True if model.inference_type == "sam3" else False,
            "point": True if model.inference_type == "sam3" else False,
            "box": True if model.inference_type == "sam3" else False
        }
        response["example_request"] = {
            "confidence": 0.25,
            "prompts": [
                {"type": "text", "value": "bicycle"},
                {"type": "point", "coords": [100, 200], "label": 1},
                {"type": "box", "coords": [50, 50, 150, 150]}
            ]
        }
    else:
        response["example_request"] = {
            "confidence": 0.25
        }
    
    return response

@router.post("/single", response_model=PredictionResponse)
async def infer_single_image(
    model_key: str = Form(..., description="Model API key (UUID)"),
    file: UploadFile = File(..., description="Image file to process"),
    confidence: Optional[float] = Form(0.25, description="Confidence threshold"),
    prompts: Optional[str] = Form(None, description="JSON array of prompts for prompt-capable models"),
    iou_threshold: Optional[float] = Form(0.45, description="IOU threshold"),
    imgsz: Optional[int] = Form(640, description="Image size"),
    class_filter: Optional[str] = Form(None, description="Filter results by class"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_api_key)
):
    """
    Run inference on a single image using external API key.
    
    **Authentication**: API key required (X-API-Key header)
    **Rate Limit**: 100 calls per hour
    **Model Access**: You can only use models you own
    
    Args:
        model_key: Model's unique API key (UUID format)
        file: Image file to process
        confidence: Confidence threshold (0.0-1.0)
        prompts: JSON string of prompts for SAM3/prompt-capable models
            Example: [{"type": "text", "value": "bicycle"}]
        class_filter: Optional[str] = Form(None, description="Filter results by class"),
    Returns:
        PredictionResponse with detections/classifications
    """
    start_time = time.time()
    api_call_record = None
    
    try:
        # Check rate limit
        check_rate_limit(current_user.id, db)
        
        # Get and validate model
        model = get_model_by_api_key(model_key, current_user.id, db)
        
        # Parse prompts if provided
        parsed_prompts = None
        if prompts:
            try:
                parsed_prompts = json.loads(prompts)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid prompts JSON format"
                )
        
        # Validate prompts requirement
        if model.requires_prompts and not parsed_prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{model.name}' requires prompts. Please provide prompts parameter."
            )
        
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
        
        # Parse class_filter if provided
        class_filter_list = None
        if class_filter:
            class_filter_list = [c.strip() for c in class_filter.split(',')]
        
        # Create prediction job
        job = PredictionJob(
            model_id=model.id,
            creator_id=current_user.id,
            mode=PredictionMode.SINGLE,
            source_type="external_api",
            source_ref=file.filename,
            status=PredictionStatus.PENDING,
            progress=0,
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
        
        # Get BPE path from model metadata (SAM3)
        bpe_path = None
        if model.metrics_json and isinstance(model.metrics_json, dict):
            bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
        
        # Run inference using unified service
        result = inference_service.detect_image(
            model_path=model.artifact_path,
            inference_type=model.inference_type,
            image_path=str(image_path),
            task_type=model.task_type,
            confidence=confidence,
            prompts=parsed_prompts,
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
            prompts=parsed_prompts,
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
        
        # Update job status
        job.status = PredictionStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(prediction_result)
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log successful API call
        api_call_record = InferenceApiCall(
            user_id=current_user.id,
            model_id=model.id,
            prediction_job_id=job.id,
            called_at=datetime.now(timezone.utc),
            response_time_ms=response_time_ms,
            status_code=200,
            file_count=1
        )
        db.add(api_call_record)
        db.commit()
        
        return PredictionResponse(
            id=prediction_result.id,
            result_id=prediction_result.id,
            job_id=job.id,
            file_name=file.filename,
            task_type=result.task_type,
            inference_time_ms=result.inference_time_ms,
            response_time_ms=response_time_ms,
            boxes=result.boxes,
            scores=result.scores,
            classes=result.classes,
            class_names=result.class_names,
            masks=result.masks,
            top_class=result.top_class,
            top_confidence=result.top_confidence,
            top_classes=result.top_classes,
            probabilities=result.probabilities,
            config=result_config,
            chats=[]
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (rate limit, not found, etc.)
        raise
    except Exception as e:
        logger.error(f"External inference error: {str(e)}")
        
        # Log failed API call
        response_time_ms = (time.time() - start_time) * 1000
        api_call_record = InferenceApiCall(
            user_id=current_user.id,
            model_id=model.id if 'model' in locals() else None,
            called_at=datetime.now(timezone.utc),
            response_time_ms=response_time_ms,
            status_code=500,
            file_count=1,
            error_message=str(e)[:512]
        )
        db.add(api_call_record)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {str(e)}"
        )

@router.post("/batch")
async def infer_batch_images(
    model_key: str = Form(..., description="Model API key (UUID)"),
    files: List[UploadFile] = File(..., description="Image files to process"),
    confidence: float = Form(0.25, description="Confidence threshold"),
    iou_threshold: Optional[float] = Form(0.45, description="IOU threshold"),
    imgsz: Optional[int] = Form(640, description="Image size"),
    class_filter: Optional[str] = Form(None, description="Filter results by class"),
    prompts: str = Form(None, description="JSON array of prompts for prompt-capable models"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_api_key)
):
    """
    Run inference on multiple images using external API key.
    
    **Note**: Batch inference does NOT support prompt-capable models.
    Use /single endpoint for SAM3 or other prompt-based models.
    
    **Authentication**: API key required (X-API-Key header)
    **Rate Limit**: 100 calls per hour (counts as 1 call regardless of file count)
    **Model Access**: You can only use models you own
    
    Args:
        model_key: Model's unique API key (UUID format)
        files: List of image files to process
        confidence: Confidence threshold (0.0-1.0)
    
    Returns:
        Job ID for tracking batch processing status
    """
    start_time = time.time()
    api_call_record = None
    
    try:
        # Check rate limit
        check_rate_limit(current_user.id, db)
        
        # Get and validate model
        model = get_model_by_api_key(model_key, current_user.id, db)
        
        # Parse prompts if provided
        parsed_prompts = None
        if prompts:
            try:
                parsed_prompts = json.loads(prompts)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid prompts JSON format"
                )
        
        # Validate prompts requirement
        if model.requires_prompts and not parsed_prompts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{model.name}' requires prompts. Please provide prompts parameter."
            )
        
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
    
        # Parse class_filter if provided
        class_filter_list = None
        if class_filter:
            class_filter_list = [c.strip() for c in class_filter.split(',')]
        
        # Get BPE path from model metadata (SAM3)
        bpe_path = None
        if model.metrics_json and isinstance(model.metrics_json, dict):
            bpe_path = model.metrics_json.get("bpe_path") or model.metrics_json.get("bpe_vocab_path")
        
        total_images = len(files)
        job = PredictionJob(
            model_id=model.id,
            creator_id=current_user.id,
            mode=PredictionMode.BATCH,
            source_type="external_api",
            source_ref=f"{total_images} images via API",
            status=PredictionStatus.PENDING,
            progress=0,
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

        # Save uploaded images and run inference
        job_response_list: List[PredictionResponse] = []
        failed_files = []

        for file in files:
            try:
                image_path = await save_uploaded_image(file, job.id)

                # Run inference using unified service
                result = inference_service.detect_image(
                    model_path=model.artifact_path,
                    inference_type=model.inference_type,
                    image_path=str(image_path),
                    task_type=model.task_type,
                    confidence=confidence,
                    prompts=parsed_prompts,
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
                    prompts=parsed_prompts,
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

                job_response_list.append(PredictionResponse(
                    id=prediction_result.id,
                    result_id=prediction_result.id,
                    job_id=job.id,
                    file_name=file.filename,
                    task_type=result.task_type,
                    inference_time_ms=result.inference_time_ms,
                    response_time_ms=0,  # Will be calculated after loop
                    boxes=result.boxes,
                    scores=result.scores,
                    classes=result.classes,
                    class_names=result.class_names,
                    masks=result.masks,
                    top_class=result.top_class,
                    top_confidence=result.top_confidence,
                    top_classes=result.top_classes,
                    probabilities=result.probabilities,
                    config=result_config,
                    chats=[]
                ))
            except Exception as e:
                logger.error(f"Failed to process {file.filename}: {str(e)}")
                failed_files.append({"filename": file.filename, "error": str(e)})
                continue

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Update response_time_ms in all responses
        for response in job_response_list:
            response.response_time_ms = response_time_ms

        # Calculate final statistics based on task type
        total_detections = 0
        total_masks = 0
        total_classifications = 0
        class_counts = {}
        total_confidence = 0.0
        confidence_count = 0
        
        for result in job_response_list:
            # Count based on task type
            if result.boxes:  # Detection or Segmentation with boxes
                total_detections += len(result.boxes)
            
            if result.masks:  # Segmentation
                total_masks += len(result.masks)
            
            if result.top_class:  # Classification
                total_classifications += 1
            
            # Aggregate class counts (count each class once per result)
            if result.class_names:
                for class_name in result.class_names:
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            # Aggregate confidence scores (count each score once)
            if result.scores:
                for score in result.scores:
                    total_confidence += score
                    confidence_count += 1
        
        # Build summary with task-specific metrics
        summary_update = {
            "frames_captured": len(job_response_list),
            "total_files": len(files),
            "failed_files": len(failed_files),
            "class_counts": class_counts,
            "average_confidence": total_confidence / confidence_count if confidence_count > 0 else 0,
            "session_end_time": datetime.now(timezone.utc).isoformat()
        }
        
        # Add task-specific metrics only if they exist
        if total_detections > 0:
            summary_update["total_detections"] = total_detections
        if total_masks > 0:
            summary_update["total_masks"] = total_masks
        if total_classifications > 0:
            summary_update["total_classifications"] = total_classifications
        
        # Add failed files info if any
        if failed_files:
            summary_update["errors"] = failed_files
        
        # Update job summary
        job.summary_json.update(summary_update)
        flag_modified(job, "summary_json")

        # Update job status
        job.status = PredictionStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        
        # Log successful API call
        api_call_record = InferenceApiCall(
            user_id=current_user.id,
            model_id=model.id,
            prediction_job_id=job.id,
            called_at=datetime.now(timezone.utc),
            response_time_ms=response_time_ms,
            status_code=200,  # OK (synchronous batch processing)
            file_count=len(files)
        )
        db.add(api_call_record)
        db.commit()
        
        return job_response_list
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"External batch inference error: {str(e)}")
        
        # Log failed API call
        response_time_ms = (time.time() - start_time) * 1000
        api_call_record = InferenceApiCall(
            user_id=current_user.id,
            model_id=model.id if 'model' in locals() else None,
            called_at=datetime.now(timezone.utc),
            response_time_ms=response_time_ms,
            status_code=500,
            file_count=len(files) if 'files' in locals() else 0,
            error_message=str(e)[:512]
        )
        db.add(api_call_record)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch inference failed: {str(e)}"
        )


@router.get("/usage/stats")
async def get_usage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_api_key)
):
    """
    Get current user's external API usage statistics.
    
    Returns:
        - calls_last_hour: Number of calls in last 60 minutes
        - calls_today: Total calls today
        - rate_limit: Maximum calls per hour
        - remaining_quota: Remaining calls this hour
        - quota_resets_at: When the quota resets (ISO timestamp)
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Count calls in last hour
    calls_last_hour = db.query(InferenceApiCall).filter(
        InferenceApiCall.user_id == current_user.id,
        InferenceApiCall.called_at >= one_hour_ago
    ).count()
    
    # Count calls today
    calls_today = db.query(InferenceApiCall).filter(
        InferenceApiCall.user_id == current_user.id,
        InferenceApiCall.called_at >= today_start
    ).count()
    
    # Find oldest call in current window for reset time
    oldest_call = db.query(InferenceApiCall).filter(
        InferenceApiCall.user_id == current_user.id,
        InferenceApiCall.called_at >= one_hour_ago
    ).order_by(InferenceApiCall.called_at).first()
    
    quota_resets_at = (oldest_call.called_at + timedelta(hours=1)) if oldest_call else now + timedelta(hours=1)
    
    return {
        "calls_last_hour": calls_last_hour,
        "calls_today": calls_today,
        "rate_limit": RATE_LIMIT_PER_HOUR,
        "remaining_quota": max(0, RATE_LIMIT_PER_HOUR - calls_last_hour),
        "quota_resets_at": quota_resets_at.isoformat()
    }

@router.get("/usage/history")
async def get_usage_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_api_key)
):
    """
    Get current user's external API call history.
    
    Returns list of recent API calls with timestamps and response times.
    """
    calls = db.query(InferenceApiCall).filter(
        InferenceApiCall.user_id == current_user.id
    ).order_by(InferenceApiCall.called_at.desc()).limit(limit).all()
    
    return [
        {
            "id": call.id,
            "model_id": call.model_id,
            "called_at": call.called_at.isoformat(),
            "response_time_ms": call.response_time_ms,
            "status_code": call.status_code,
            "file_count": call.file_count,
            "error_message": call.error_message
        }
        for call in calls
    ]