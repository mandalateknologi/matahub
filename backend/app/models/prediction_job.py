"""
PredictionJob Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from app.db import Base
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import enum
import logging

if TYPE_CHECKING:
    from app.schemas.prediction import (
        InitialConfig, DetectionStats, ClassificationStats, 
        SegmentationStats, SourceMetadata, SummaryStats
    )
    from app.models.prediction_result import PredictionResult

logger = logging.getLogger(__name__)


class PredictionMode(str, enum.Enum):
    SINGLE = "single"
    BATCH = "batch"
    VIDEO = "video"
    RTSP = "rtsp"


class PredictionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PredictionJob(Base):
    """Prediction job for tracking inference tasks."""
    
    __tablename__ = "prediction_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    mode = Column(Enum(PredictionMode, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    source_type = Column(String(50), nullable=False)  # image, video, rtsp
    source_ref = Column(String(512), nullable=False)  # File path or URL
    status = Column(Enum(PredictionStatus, values_callable=lambda obj: [e.value for e in obj]), default=PredictionStatus.PENDING.value, nullable=False)
    summary_json = Column(JSON, default=dict)  # Prediction summary stats
    error_message = Column(String(1024), nullable=True)
    progress = Column(Integer, nullable=True, default=0)  # 0-100 for batch/video, frame count for RTSP
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    creator = relationship("User", back_populates="prediction_jobs", foreign_keys=[creator_id])
    model = relationship("Model", back_populates="prediction_jobs")
    campaign = relationship("Campaign", back_populates="prediction_jobs", foreign_keys=[campaign_id])
    results = relationship("PredictionResult", back_populates="prediction_job", cascade="all, delete-orphan")
    export_jobs = relationship("ExportJob", back_populates="prediction_job", cascade="all, delete-orphan")
    
    @property
    def model_name(self) -> str:
        """Get model name from relationship."""
        return self.model.name if self.model else None
    
    @property
    def campaign_name(self) -> str:
        """Get campaign name from relationship."""
        return self.campaign.name if self.campaign else None
    
    # ==================== SUMMARY JSON MANAGEMENT METHODS ====================
    
    @property
    def config(self) -> Optional['InitialConfig']:
        """Parse and return config section from summary_json."""
        from app.schemas.prediction import InitialConfig
        try:
            if self.summary_json and isinstance(self.summary_json, dict) and 'config' in self.summary_json:
                return InitialConfig(**self.summary_json['config'])
            return None
        except Exception as e:
            logger.warning(f"Failed to parse summary_json config for job {self.id}: {e}")
            return None
    
    @property
    def stats(self) -> Optional['SummaryStats']:
        """Parse and return stats section from summary_json (task-specific)."""
        from app.schemas.prediction import DetectionStats, ClassificationStats, SegmentationStats
        try:
            if not self.summary_json or not isinstance(self.summary_json, dict) or 'stats' not in self.summary_json:
                return None
            
            stats_data = self.summary_json['stats']
            task_type = self.model.task_type if self.model else "detect"
            
            if task_type == "classify":
                return ClassificationStats(**stats_data)
            elif task_type == "segment":
                return SegmentationStats(**stats_data)
            else:  # detect
                return DetectionStats(**stats_data)
        except Exception as e:
            logger.warning(f"Failed to parse summary_json stats for job {self.id}: {e}")
            return None
    
    @property
    def source_metadata(self) -> Optional['SourceMetadata']:
        """Parse and return metadata section from summary_json."""
        from app.schemas.prediction import SourceMetadata
        try:
            if self.summary_json and isinstance(self.summary_json, dict) and 'metadata' in self.summary_json:
                return SourceMetadata(**self.summary_json['metadata'])
            return None
        except Exception as e:
            logger.warning(f"Failed to parse summary_json metadata for job {self.id}: {e}")
            return None
    
    def initialize_summary(
        self,
        task_type: str,
        **config_kwargs
    ) -> None:
        """
        Initialize summary_json with config, empty stats, and empty metadata.
        
        Args:
            task_type: Task type (detect, classify, segment)
            **config_kwargs: Configuration parameters (confidence, prompts, etc.)
        """
        from app.schemas.prediction import (
            InitialConfig, DetectionStats, ClassificationStats, 
            SegmentationStats, SourceMetadata
        )
        
        try:
            # Create config
            config = InitialConfig(**config_kwargs)
            
            # Create empty stats based on task type
            if task_type == "classify":
                stats = ClassificationStats()
            elif task_type == "segment":
                stats = SegmentationStats()
            else:  # detect
                stats = DetectionStats()
            
            # Create empty metadata
            metadata = SourceMetadata()
            
            # Set summary_json
            self.summary_json = {
                "config": config.model_dump(),
                "stats": stats.model_dump(),
                "metadata": metadata.model_dump()
            }
            flag_modified(self, "summary_json")
            
        except Exception as e:
            logger.error(f"Failed to initialize summary_json for job {self.id}: {e}")
            # Fallback to basic structure
            self.summary_json = {
                "config": config_kwargs,
                "stats": {},
                "metadata": {}
            }
            flag_modified(self, "summary_json")
    
    def update_stats(self, replace: bool = False, **stats_kwargs) -> None:
        """
        Update stats section of summary_json.
        
        Args:
            replace: If True, replace entire stats section. If False, merge with existing.
            **stats_kwargs: Statistics to update (total_detections, class_counts, etc.)
        """
        try:
            if not self.summary_json or not isinstance(self.summary_json, dict):
                self.summary_json = {"config": {}, "stats": {}, "metadata": {}}
            
            if replace:
                # Replace entire stats section
                self.summary_json["stats"] = stats_kwargs
            else:
                # Merge with existing stats
                if "stats" not in self.summary_json:
                    self.summary_json["stats"] = {}
                self.summary_json["stats"].update(stats_kwargs)
            
            flag_modified(self, "summary_json")
            
        except Exception as e:
            logger.error(f"Failed to update stats for job {self.id}: {e}")
            # Graceful fallback - direct dict update
            if not self.summary_json:
                self.summary_json = {}
            if "stats" not in self.summary_json:
                self.summary_json["stats"] = {}
            self.summary_json["stats"].update(stats_kwargs)
            flag_modified(self, "summary_json")
    
    def update_metadata(self, **metadata_kwargs) -> None:
        """
        Update metadata section of summary_json.
        
        Args:
            **metadata_kwargs: Metadata fields to update (fps, frames_processed, last_activity, etc.)
        """
        try:
            if not self.summary_json or not isinstance(self.summary_json, dict):
                self.summary_json = {"config": {}, "stats": {}, "metadata": {}}
            
            if "metadata" not in self.summary_json:
                self.summary_json["metadata"] = {}
            
            self.summary_json["metadata"].update(metadata_kwargs)
            flag_modified(self, "summary_json")
            
        except Exception as e:
            logger.error(f"Failed to update metadata for job {self.id}: {e}")
    
    def finalize_stats(self, task_type: str, results: List['PredictionResult']) -> None:
        """
        Calculate and set final aggregated statistics from all results.
        
        Args:
            task_type: Task type (detect, classify, segment)
            results: List of PredictionResult records
        """
        try:
            total_detections = 0
            total_masks = 0
            total_classifications = 0
            class_counts = {}
            top_class_distribution = {}
            total_confidence = 0.0
            confidence_count = 0
            total_inference_time = 0.0
            
            for result in results:
                # Accumulate inference time
                # Note: inference_time_ms not stored in DB, will be 0 for historical results
                
                if task_type == "detect":
                    if result.boxes_json:
                        total_detections += len(result.boxes_json)
                    if result.class_names_json:
                        for class_name in result.class_names_json:
                            class_counts[class_name] = class_counts.get(class_name, 0) + 1
                    if result.scores_json:
                        total_confidence += sum(result.scores_json)
                        confidence_count += len(result.scores_json)
                
                elif task_type == "classify":
                    total_classifications += 1
                    if result.top_class:
                        top_class_distribution[result.top_class] = top_class_distribution.get(result.top_class, 0) + 1
                    if result.top_confidence:
                        total_confidence += result.top_confidence
                        confidence_count += 1
                
                elif task_type == "segment":
                    if result.masks_json:
                        total_masks += len(result.masks_json)
                        for mask in result.masks_json:
                            if 'class_name' in mask:
                                class_name = mask['class_name']
                                class_counts[class_name] = class_counts.get(class_name, 0) + 1
                    if result.scores_json:
                        total_confidence += sum(result.scores_json)
                        confidence_count += len(result.scores_json)
            
            # Calculate processing time (wall-clock)
            processing_time_ms = 0.0
            if self.completed_at and self.created_at:
                processing_time_ms = (self.completed_at - self.created_at).total_seconds() * 1000
            
            # Build final stats
            avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0.0
            
            if task_type == "classify":
                # Build top_classes_summary
                top_classes_summary = [
                    {"class": cls, "confidence": avg_confidence}
                    for cls in sorted(top_class_distribution.keys(), 
                                    key=lambda x: top_class_distribution[x], 
                                    reverse=True)[:10]  # Top 10 classes
                ]
                
                self.update_stats(
                    replace=True,
                    total_classifications=total_classifications,
                    top_class_distribution=top_class_distribution,
                    average_top_confidence=avg_confidence,
                    top_classes_summary=top_classes_summary,
                    inference_time_ms=total_inference_time,
                    processing_time_ms=processing_time_ms
                )
            
            elif task_type == "segment":
                self.update_stats(
                    replace=True,
                    total_masks=total_masks,
                    mask_count_per_class=class_counts,
                    average_confidence=avg_confidence,
                    inference_time_ms=total_inference_time,
                    processing_time_ms=processing_time_ms
                )
            
            else:  # detect
                self.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence,
                    inference_time_ms=total_inference_time,
                    processing_time_ms=processing_time_ms
                )
        
        except Exception as e:
            logger.error(f"Failed to finalize stats for job {self.id}: {e}")
    
    def is_session_inactive(self) -> bool:
        """
        Check if manual session has been inactive beyond timeout threshold.
        
        Returns:
            True if session is inactive, False otherwise
        """
        from app.config import settings
        
        try:
            source_metadata = self.source_metadata
            if not source_metadata or not source_metadata.last_activity:
                return False
            
            last_activity_dt = datetime.fromisoformat(source_metadata.last_activity)
            timeout_minutes = settings.MANUAL_SESSION_TIMEOUT_MINUTES
            elapsed_minutes = (datetime.now(timezone.utc) - last_activity_dt).total_seconds() / 60
            
            return elapsed_minutes > timeout_minutes
        
        except Exception as e:
            logger.warning(f"Failed to check session inactivity for job {self.id}: {e}")
            return False
    
    def mark_inactive(self) -> None:
        """Mark session as inactive by setting inactive_since timestamp."""
        try:
            self.update_metadata(inactive_since=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.error(f"Failed to mark job {self.id} as inactive: {e}")
    
    # ==================== END SUMMARY JSON MANAGEMENT ====================
    
    def __repr__(self):
        return f"<PredictionJob(id={self.id}, mode={self.mode}, status={self.status})>"
