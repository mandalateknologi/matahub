"""
System API Router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db import get_db
from app.models.user import User
from app.utils.auth import get_current_active_user
from app.utils.file_handler import cleanup_old_predictions
from app.workers.training_worker import training_worker
from app.workers.prediction_worker import prediction_worker
from app.config import settings

router = APIRouter(prefix="/api/system", tags=["System"])


def get_gpu_info() -> Dict[str, Any]:
    """
    Get GPU/device information.
    
    Returns:
        Dictionary with GPU availability and details
    """
    try:
        import torch
        
        if torch.cuda.is_available():
            return {
                "available": True,
                "device_count": torch.cuda.device_count(),
                "device_name": torch.cuda.get_device_name(0),
                "cuda_version": torch.version.cuda,
                "current_device": torch.cuda.current_device(),
                "memory_allocated_gb": round(torch.cuda.memory_allocated(0) / 1024**3, 2),
                "memory_reserved_gb": round(torch.cuda.memory_reserved(0) / 1024**3, 2),
            }
        else:
            return {
                "available": False,
                "message": "CUDA not available. Using CPU for training and inference."
            }
    except ImportError:
        return {
            "available": False,
            "message": "PyTorch not installed or configured properly."
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        System health status
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@router.get("/status")
async def system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get system status information.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        System status with active jobs and configuration
    """
    active_training_jobs = training_worker.get_active_jobs()
    active_prediction_jobs = prediction_worker.get_active_jobs()
    
    # Get GPU info
    gpu_info = get_gpu_info()
    
    return {
        "status": "operational",
        "active_training_jobs": len(active_training_jobs),
        "active_prediction_jobs": len(active_prediction_jobs),
        "training_job_ids": active_training_jobs,
        "prediction_job_ids": active_prediction_jobs,
        "gpu": gpu_info,
        "config": {
            "max_dataset_size_mb": settings.MAX_DATASET_SIZE / (1024 * 1024),
            "max_image_size_mb": settings.MAX_IMAGE_SIZE / (1024 * 1024),
            "max_video_size_mb": settings.MAX_VIDEO_SIZE / (1024 * 1024),
            "prediction_retention_days": settings.PREDICTION_RETENTION_DAYS,
            "yolo_device": settings.get_device()
        }
    }


@router.post("/cleanup")
async def cleanup_system(
    retention_days: int = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Cleanup old prediction data.
    
    Args:
        retention_days: Optional custom retention period
        current_user: Current authenticated user
        
    Returns:
        Cleanup result
    """
    cleaned = cleanup_old_predictions(retention_days)
    
    return {
        "status": "success",
        "directories_cleaned": cleaned,
        "retention_days": retention_days or settings.prediction_RETENTION_DAYS
    }
