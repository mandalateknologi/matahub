"""
Summary JSON Validation Utilities
Provides validation and default generation for PredictionJob summary_json structure.
"""
from typing import Dict, Any, Optional, Union
from pydantic import ValidationError
import logging

from app.schemas.prediction import (
    InitialConfig,
    DetectionStats,
    ClassificationStats,
    SegmentationStats,
    SourceMetadata,
    SummaryStats
)

logger = logging.getLogger(__name__)


def validate_config(config_dict: dict, task_type: str) -> Optional[InitialConfig]:
    """
    Validate configuration dictionary against InitialConfig schema.
    
    Args:
        config_dict: Configuration dictionary to validate
        task_type: Task type (detect, classify, segment)
        
    Returns:
        Validated InitialConfig object or None on error
    """
    try:
        return InitialConfig(**config_dict)
    except ValidationError as e:
        logger.error(f"Config validation failed for task_type={task_type}: {e}")
        return None


def validate_stats(stats_dict: dict, task_type: str) -> Optional[SummaryStats]:
    """
    Validate statistics dictionary against task-specific stats schema.
    
    Args:
        stats_dict: Statistics dictionary to validate
        task_type: Task type (detect, classify, segment)
        
    Returns:
        Validated stats object (DetectionStats/ClassificationStats/SegmentationStats) or None on error
    """
    try:
        if task_type == "classify":
            return ClassificationStats(**stats_dict)
        elif task_type == "segment":
            return SegmentationStats(**stats_dict)
        else:  # detect (default)
            return DetectionStats(**stats_dict)
    except ValidationError as e:
        logger.error(f"Stats validation failed for task_type={task_type}: {e}")
        return None


def validate_metadata(metadata_dict: dict) -> Optional[SourceMetadata]:
    """
    Validate metadata dictionary against SourceMetadata schema.
    
    Args:
        metadata_dict: Metadata dictionary to validate
        
    Returns:
        Validated SourceMetadata object or None on error
    """
    try:
        return SourceMetadata(**metadata_dict)
    except ValidationError as e:
        logger.error(f"Metadata validation failed: {e}")
        return None


def get_default_summary(task_type: str, source_type: str, mode: str) -> dict:
    """
    Generate minimal valid summary_json structure with default values.
    
    Args:
        task_type: Task type (detect, classify, segment)
        source_type: Source type (image, batch, video, rtsp)
        mode: Mode (manual, continuous, batch, capture)
        
    Returns:
        Dictionary with default config, stats, and metadata
    """
    # Default config
    config = InitialConfig(mode=mode)
    
    # Default stats based on task type
    if task_type == "classify":
        stats = ClassificationStats()
    elif task_type == "segment":
        stats = SegmentationStats()
    else:  # detect
        stats = DetectionStats()
    
    # Default metadata
    metadata = SourceMetadata()
    
    return {
        "config": config.model_dump(),
        "stats": stats.model_dump(),
        "metadata": metadata.model_dump()
    }


def safe_merge_stats(current_stats: dict, new_stats: dict, replace: bool) -> dict:
    """
    Safely merge statistics dictionaries with conflict resolution.
    
    Args:
        current_stats: Existing statistics dictionary
        new_stats: New statistics to merge or replace
        replace: If True, replace entirely. If False, merge.
        
    Returns:
        Merged statistics dictionary
    """
    if replace:
        return new_stats
    
    # Deep merge strategy
    merged = current_stats.copy()
    
    for key, value in new_stats.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # Deep merge for nested dicts (e.g., class_counts)
            merged[key] = {**merged[key], **value}
        else:
            # Direct replacement for primitives and lists
            merged[key] = value
    
    return merged


def safe_update_summary(
    job,  # PredictionJob instance
    section: str,
    data: dict
) -> bool:
    """
    Safely update a section of summary_json with validation and fallback.
    
    Args:
        job: PredictionJob instance
        section: Section to update ('config', 'stats', 'metadata')
        data: Data dictionary to set
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        if not job.summary_json or not isinstance(job.summary_json, dict):
            job.summary_json = {"config": {}, "stats": {}, "metadata": {}}
        
        # Validate based on section
        if section == "config":
            task_type = job.model.task_type if job.model else "detect"
            validated = validate_config(data, task_type)
            if validated:
                job.summary_json["config"] = validated.model_dump()
            else:
                logger.warning(f"Config validation failed for job {job.id}, using raw data")
                job.summary_json["config"] = data
        
        elif section == "stats":
            task_type = job.model.task_type if job.model else "detect"
            validated = validate_stats(data, task_type)
            if validated:
                job.summary_json["stats"] = validated.model_dump()
            else:
                logger.warning(f"Stats validation failed for job {job.id}, using raw data")
                job.summary_json["stats"] = data
        
        elif section == "metadata":
            validated = validate_metadata(data)
            if validated:
                job.summary_json["metadata"] = validated.model_dump()
            else:
                logger.warning(f"Metadata validation failed for job {job.id}, using raw data")
                job.summary_json["metadata"] = data
        
        else:
            logger.error(f"Unknown section '{section}' for job {job.id}")
            return False
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(job, "summary_json")
        return True
    
    except Exception as e:
        logger.error(f"Failed to update summary section '{section}' for job {job.id}: {e}")
        return False
