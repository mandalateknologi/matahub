"""
Prediction Schemas
"""
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Literal
from app.models.prediction_job import PredictionMode, PredictionStatus


# ==================== SUMMARY JSON SCHEMA MODELS (v1) ====================

class InitialConfig(BaseModel):
    """Initial configuration parameters for inference job (set at job creation)."""
    confidence: float = Field(default=0.25, ge=0.0, le=1.0, description="Confidence threshold for predictions")
    iou_threshold: Optional[float] = Field(default=0.45, ge=0.0, le=1.0, description="IoU threshold for NMS")
    imgsz: Optional[int] = Field(default=640, ge=32, description="Input image size")
    class_filter: Optional[List[str]] = Field(default=None, description="Filter predictions to specific classes")
    prompts: Optional[List[Dict[str, Any]]] = Field(default=None, description="SAM3 prompts for segmentation")
    capture_mode: Optional[str] = Field(default=None, description="Capture mode for video/webcam/RTSP (manual, continuous)")
    skip_frames: Optional[int] = Field(default=None, ge=1, le=30, description="Process every Nth frame for video/RTSP")
    limit_frames: Optional[int] = Field(default=None, ge=1, description="Limit total frames processed")
    
    model_config = ConfigDict(extra="forbid")


class ResultConfig(BaseModel):
    """Configuration parameters used for a specific inference result (runtime per-frame config)."""
    confidence: float = Field(default=0.25, ge=0.0, le=1.0, description="Confidence threshold for predictions")
    iou_threshold: Optional[float] = Field(default=0.45, ge=0.0, le=1.0, description="IoU threshold for NMS")
    imgsz: Optional[int] = Field(default=640, ge=32, description="Input image size")
    class_filter: Optional[List[str]] = Field(default=None, description="Filter predictions to specific classes")
    prompts: Optional[List[Dict[str, Any]]] = Field(default=None, description="SAM3 prompts for segmentation")
    inference_type: Optional[str] = Field(default=None, description="Inference engine used (yolo, sam3)")
    
    model_config = ConfigDict(extra="forbid")


class DetectionStats(BaseModel):
    """Statistics for object detection tasks."""
    total_detections: int = Field(default=0, ge=0, description="Total number of detections across all results")
    class_counts: Dict[str, int] = Field(default_factory=dict, description="Detection count per class name")
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Average confidence score")
    inference_time_ms: float = Field(default=0.0, ge=0.0, description="Total model inference time in milliseconds")
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Total wall-clock processing time in milliseconds")
    
    model_config = ConfigDict(extra="forbid")


class ClassificationStats(BaseModel):
    """Statistics for image classification tasks."""
    total_classifications: int = Field(default=0, ge=0, description="Total number of images classified")
    top_class_distribution: Dict[str, int] = Field(default_factory=dict, description="Raw count of top class occurrences")
    average_top_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Average confidence of top class predictions")
    top_classes_summary: List[Dict[str, Union[str, float]]] = Field(
        default_factory=list,
        description="Top classes with confidence scores, format: [{'class': 'cat', 'confidence': 0.95}, ...]"
    )
    inference_time_ms: float = Field(default=0.0, ge=0.0, description="Total model inference time in milliseconds")
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Total wall-clock processing time in milliseconds")
    
    @field_validator('top_classes_summary')
    @classmethod
    def validate_top_classes_format(cls, v):
        """Ensure top_classes_summary has correct structure."""
        for item in v:
            if not isinstance(item, dict) or 'class' not in item or 'confidence' not in item:
                raise ValueError("Each item must have 'class' and 'confidence' keys")
        return v
    
    model_config = ConfigDict(extra="forbid")


class SegmentationStats(BaseModel):
    """Statistics for segmentation tasks (YOLO segment, SAM3)."""
    total_masks: int = Field(default=0, ge=0, description="Total number of segmentation masks generated")
    mask_count_per_class: Dict[str, int] = Field(default_factory=dict, description="Mask count per class name")
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Average confidence score for masks")
    inference_time_ms: float = Field(default=0.0, ge=0.0, description="Total model inference time in milliseconds")
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="Total wall-clock processing time in milliseconds")
    
    model_config = ConfigDict(extra="forbid")


class SourceMetadata(BaseModel):
    """Source-specific metadata for tracking job execution."""
    #BATCH IMAGES
    total_images: Optional[int] = Field(default=None, ge=0, description="Total images in batch source")
    #VIDEO/RTSP
    fps: Optional[float] = Field(default=None, description="Frames per second for video/RTSP sources")
    total_frames: Optional[int] = Field(default=None, ge=0, description="Total frames in video source")
    #VIDEO
    video_duration: Optional[float] = Field(default=None, ge=0.0, description="Video duration in seconds")
    video_filename: Optional[str] = Field(default=None, description="Original video filename")
    #BATCH/VIDEO/RTSP/WEBCAM
    frames_processed: int = Field(default=0, ge=0, description="Number of frames processed so far")
    frames_captured: int = Field(default=0, ge=0, description="Number of frames manually captured (manual mode)")
    #ACTIVE SESSION TRACKING
    last_activity: Optional[str] = Field(default=None, description="ISO timestamp of last user activity (manual sessions)")
    inactive_since: Optional[str] = Field(default=None, description="ISO timestamp when session became inactive")
    
    model_config = ConfigDict(extra="forbid")


# Union type for all stats variants
SummaryStats = Union[DetectionStats, ClassificationStats, SegmentationStats]


class SingleImageSummary(BaseModel):
    """Summary schema for single image inference."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    
    model_config = ConfigDict(extra="forbid")


class BatchImageSummary(BaseModel):
    """Summary schema for batch image inference."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    
    model_config = ConfigDict(extra="forbid")


class VideoManualSummary(BaseModel):
    """Summary schema for manual video capture (frame-by-frame)."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata
    
    model_config = ConfigDict(extra="forbid")


class VideoContinuousSummary(BaseModel):
    """Summary schema for continuous video processing."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata
    
    model_config = ConfigDict(extra="forbid")


class RTSPManualSummary(BaseModel):
    """Summary schema for manual RTSP capture (preview mode)."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata
    
    model_config = ConfigDict(extra="forbid")


class RTSPContinuousSummary(BaseModel):
    """Summary schema for continuous RTSP processing."""
    config: InitialConfig
    stats: SummaryStats
    metadata: SourceMetadata
    
    model_config = ConfigDict(extra="forbid")


# ==================== END SUMMARY JSON SCHEMA MODELS ====================


class PredictionRequest(BaseModel):
    """Schema for single prediction request."""
    model_id: int
    confidence: float = Field(default=0.25, ge=0, le=1)


class BatchPredictionRequest(BaseModel):
    """Schema for batch prediction request."""
    model_id: int
    confidence: float = Field(default=0.25, ge=0, le=1)


class PredictionResponse(BaseModel):
    """
    Unified schema for prediction results.
    Handles both real-time inference responses and stored database records.
    
    Usage patterns:
    - Real-time: PredictionResponse.from_inference(...) or direct construction
    - Database: PredictionResponse.from_orm_with_json(db_obj) for batch retrieval
    """
    # Identity fields (context-dependent)
    id: Optional[int] = None  # Database ID (present when retrieved from DB)
    job_id: Optional[int] = None  # Job ID (present in real-time responses and DB records)
    result_id: Optional[int] = None  # Alias for id in real-time context (links to stored result)
    
    # File/frame metadata
    file_name: str
    frame_number: Optional[int] = None  # Frame index for video/RTSP processing
    frame_timestamp: Optional[str] = None  # Video position like "00:10:01.5"
    frame_base64: Optional[str] = None  # Base64-encoded frame image (real-time only)
    task_type: str = "detect"  # detect, classify, segment
    
    # Performance metric (real-time only, not stored in DB)
    inference_time_ms: Optional[float] = None
    response_time_ms: Optional[float] = None
    
    # Detection fields
    boxes: Optional[List[List[float]]] = []  # [[x1, y1, x2, y2], ...]
    scores: Optional[List[float]] = []
    classes: Optional[List[int]] = []
    class_names: Optional[List[str]] = []
    
    # Classification fields
    top_class: Optional[str] = None
    top_confidence: Optional[float] = None
    top_classes: Optional[List[str]] = None
    probabilities: Optional[List[float]] = None
    
    # Segmentation fields
    masks: Optional[List[Dict[str, Any]]] = []  # [{"instance_id": 0, "class_id": 1, "polygon": [[x,y], ...], ...}, ...]
    
    # Per-result configuration (tracks inference params used for this specific result)
    config: Optional[ResultConfig] = Field(default=None, description="Inference configuration used for this result")
    
    # LLM/chat outputs (reserved for future use)
    chats: Optional[List[Dict[str, Any]]] = Field(default=None, description="LLM chat outputs and vision-language model responses")
    
    model_config = {"from_attributes": True}
    
    @classmethod
    def from_orm_with_json(cls, obj):
        """
        Construct from database ORM model (PredictionResult).
        Maps *_json columns to clean field names.
        """
        return cls(
            id=obj.id,
            job_id=obj.prediction_job_id,
            result_id=obj.id,
            file_name=obj.file_name,
            frame_number=obj.frame_number,
            frame_timestamp=obj.frame_timestamp,
            task_type=obj.task_type or "detect",
            boxes=obj.boxes_json or [],
            scores=obj.scores_json or [],
            classes=obj.classes_json or [],
            class_names=obj.class_names_json or [],
            top_class=obj.top_class,
            top_confidence=obj.top_confidence,
            top_classes=obj.top_classes_json or None,
            probabilities=obj.probabilities_json or None,
            masks=obj.masks_json or [],
            config=ResultConfig(**obj.config_json) if obj.config_json else None,
            chats=obj.chats_json or None
        )
    
    @classmethod
    def from_inference(
        cls,
        job_id: int,
        file_name: str,
        result,  # InferenceResult from service
        result_id: Optional[int] = None,
        frame_number: Optional[int] = None,
        frame_timestamp: Optional[str] = None
    ):
        """
        Construct from inference service result (real-time).
        Convenience method for standardized construction.
        """
        return cls(
            job_id=job_id,
            result_id=result_id,
            file_name=file_name,
            task_type=result.task_type,
            inference_time_ms=result.inference_time_ms,
            frame_number=frame_number,
            frame_timestamp=frame_timestamp,
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

class PredictionJobResponse(BaseModel):
    """Schema for prediction job response."""
    id: int
    model_id: int
    campaign_id: Optional[int] = None
    model_name: Optional[str] = None
    campaign_name: Optional[str] = None
    task_type: Optional[str] = None  # detect, classify, segment (from model)
    mode: PredictionMode
    source_type: str
    source_ref: str
    status: PredictionStatus
    summary_json: Dict[str, Any]
    error_message: Optional[str]
    progress: Optional[int] = 0
    creator_id: int
    created_at: datetime
    completed_at: Optional[datetime]
    results_count: Optional[int] = None
    total_images: Optional[int] = None
    
    model_config = {"from_attributes": True}


class PaginatedPredictionJobsResponse(BaseModel):
    """Schema for paginated prediction jobs response."""
    jobs: List[PredictionJobResponse]
    total: int
    skip: int
    limit: int
