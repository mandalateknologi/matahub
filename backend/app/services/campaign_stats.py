"""
Campaign Statistics Service

Calculates and caches aggregate statistics across all prediction jobs within a campaign.
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.prediction_job import PredictionStatus, PredictionMode


def calculate_campaign_stats(campaign_id: int, db: Session) -> Dict[str, Any]:
    """
    Calculate aggregate statistics for a campaign from all its prediction jobs.
    
    Aggregates:
    - Total predictions across all jobs
    - Job counts by status and mode
    - Class distribution (merged from all jobs)
    - Confidence statistics
    - Temporal data (first/last prediction times)
    
    Args:
        campaign_id: Campaign ID to calculate stats for
        db: Database session
        
    Returns:
        Dictionary containing aggregate statistics
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {}
    
    jobs = campaign.prediction_jobs
    
    # Initialize stats
    stats = {
        "campaign_id": campaign_id,
        "total_predictions": 0,
        "total_jobs": len(jobs),
        "completed_jobs": 0,
        "running_jobs": 0,
        "failed_jobs": 0,
        "single_jobs": 0,
        "batch_jobs": 0,
        "video_jobs": 0,
        "rtsp_jobs": 0,
        "class_counts": {},
        "average_confidence": 0.0,
        "min_confidence": None,
        "max_confidence": None,
        "first_prediction": None,
        "last_prediction": None,
        "cached_at": datetime.utcnow().isoformat()
    }
    
    if not jobs:
        return stats
    
    # Aggregate statistics
    all_confidences = []
    earliest_time = None
    latest_time = None

    # Totals for different task types
    total_dets = 0
    total_classifications = 0
    total_detections = 0
    total_segmentations = 0
    
    for job in jobs:
        # Count by status
        if job.status == PredictionStatus.COMPLETED:
            stats["completed_jobs"] += 1
        elif job.status in (PredictionStatus.RUNNING, PredictionStatus.PENDING):
            stats["running_jobs"] += 1
        elif job.status == PredictionStatus.FAILED:
            stats["failed_jobs"] += 1
        
        # Count by mode
        if job.mode == PredictionMode.SINGLE:
            stats["single_jobs"] += 1
        elif job.mode == PredictionMode.BATCH:
            stats["batch_jobs"] += 1
        elif job.mode == PredictionMode.VIDEO:
            stats["video_jobs"] += 1
        elif job.mode == PredictionMode.RTSP:
            stats["rtsp_jobs"] += 1

        # Extract from summary_json
        summary = job.summary_json or {}
        
        # Total predictions
        task_type = job.model.task_type if job.model else None

        if task_type == "detect" and job.status == PredictionStatus.COMPLETED:
            total_dets += summary.get("total_predictions", 0)
            # Backward compatibility (some jobs may use 'total_detections')
            total_dets += summary.get("total_detections", 0)
            total_detections += (summary.get("total_predictions", 0) + summary.get("total_detections", 0))
            
        elif task_type == "segment" and job.status == PredictionStatus.COMPLETED:
            total_dets += summary.get("total_masks", 0)
            total_segmentations += summary.get("total_masks", 0)
        elif task_type == "classify" and job.status == PredictionStatus.COMPLETED:
            total_dets += summary.get("total_predictions", 0)
            # Backward compatibility (some jobs may use 'total_detections')
            total_dets += summary.get("total_detections", 0)
            total_classifications += (summary.get("total_predictions", 0) + summary.get("total_detections", 0))
        
        # Merge class counts
        class_counts = summary.get("class_counts", {})
        for class_name, count in class_counts.items():
            stats["class_counts"][class_name] = stats["class_counts"].get(class_name, 0) + count
        
        # Collect confidence values
        avg_conf = summary.get("average_confidence")
        if avg_conf is not None:
            all_confidences.append(avg_conf)
        
        # Track temporal bounds
        if job.created_at:
            if earliest_time is None or job.created_at < earliest_time:
                earliest_time = job.created_at
        
        if job.completed_at:
            if latest_time is None or job.completed_at > latest_time:
                latest_time = job.completed_at
        elif job.created_at:
            if latest_time is None or job.created_at > latest_time:
                latest_time = job.created_at
    
    # Calculate confidence statistics
    if all_confidences:
        stats["average_confidence"] = sum(all_confidences) / len(all_confidences)
        stats["min_confidence"] = min(all_confidences)
        stats["max_confidence"] = max(all_confidences)
    
    # Set total predictions results
    stats["total_predictions"] = total_dets
    stats["total_detections"] = total_detections
    stats["total_classifications"] = total_classifications
    stats["total_segmentations"] = total_segmentations
    
    # Set temporal bounds
    if earliest_time:
        stats["first_prediction"] = earliest_time.isoformat()
    if latest_time:
        stats["last_prediction"] = latest_time.isoformat()
    
    return stats


def cache_campaign_stats(campaign_id: int, db: Session) -> Dict[str, Any]:
    """
    Calculate campaign statistics and cache them in the campaign's summary_json field.
    Preserves existing custom_fields if present.
    
    Args:
        campaign_id: Campaign ID to calculate and cache stats for
        db: Database session
        
    Returns:
        Dictionary containing cached statistics
    """
    stats = calculate_campaign_stats(campaign_id, db)
    
    # Update campaign summary_json
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign:
        # Preserve custom_fields if they exist
        existing_custom_fields = campaign.summary_json.get("custom_fields") if campaign.summary_json else None
        if existing_custom_fields:
            stats["custom_fields"] = existing_custom_fields
        
        campaign.summary_json = stats
        db.commit()
        db.refresh(campaign)
    
    return stats


def get_cached_stats(campaign_id: int, db: Session, max_age_minutes: int = 5) -> Dict[str, Any]:
    """
    Get cached campaign statistics if available and fresh, otherwise recalculate.
    
    Args:
        campaign_id: Campaign ID to get stats for
        db: Database session
        max_age_minutes: Maximum age of cached stats in minutes (default 5)
        
    Returns:
        Dictionary containing campaign statistics
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {}
    
    # Check if cached stats exist and are recent
    cached_at_str = campaign.summary_json.get("cached_at")
    if cached_at_str:
        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            age_minutes = (datetime.utcnow() - cached_at).total_seconds() / 60
            
            if age_minutes < max_age_minutes:
                # Return cached stats
                return campaign.summary_json
        except (ValueError, TypeError):
            # Invalid cached_at format, recalculate
            pass
    
    # Recalculate and cache
    return cache_campaign_stats(campaign_id, db)
