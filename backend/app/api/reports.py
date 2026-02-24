"""
Reports API Router
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.models.training_job import TrainingJob, TrainingStatus
from app.models.prediction_job import PredictionJob, PredictionStatus
from app.models.prediction_result import PredictionResult
from app.models.model import Model
from app.schemas.reports import TrainingSummary, PredictionSummary, ClassCount, ClassificationMetrics
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/training/summary", response_model=TrainingSummary)
async def get_training_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get training summary report.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Training summary with statistics
    """
    # Build query
    query = db.query(TrainingJob)
    
    if start_date:
        query = query.filter(TrainingJob.created_at >= start_date)
    if end_date:
        query = query.filter(TrainingJob.created_at <= end_date)
    
    # Get counts by status
    total_jobs = query.count()
    completed_jobs = query.filter(TrainingJob.status == TrainingStatus.COMPLETED).count()
    failed_jobs = query.filter(TrainingJob.status == TrainingStatus.FAILED).count()
    running_jobs = query.filter(TrainingJob.status == TrainingStatus.RUNNING).count()
    
    # Calculate average epochs
    completed = query.filter(TrainingJob.status == TrainingStatus.COMPLETED).all()
    average_epochs = sum(j.total_epochs for j in completed) / len(completed) if completed else 0
    
    # Get best model (highest mAP)
    best_model = None
    models_with_metrics = db.query(Model).filter(
        Model.metrics_json.isnot(None),
        Model.status == "ready"
    ).all()
    
    if models_with_metrics:
        best = max(
            models_with_metrics,
            key=lambda m: m.metrics_json.get("mAP50-95", 0) if m.metrics_json else 0
        )
        best_model = {
            "id": best.id,
            "name": best.name,
            "mAP": best.metrics_json.get("mAP50-95", 0) if best.metrics_json else 0
        }
    
    # Get recent jobs
    recent = query.order_by(TrainingJob.created_at.desc()).limit(10).all()
    recent_jobs = [
        {
            "id": j.id,
            "project_id": j.project_id,
            "status": j.status.value,
            "progress": j.progress,
            "created_at": j.created_at.isoformat()
        }
        for j in recent
    ]
    
    # Get metrics over time
    metrics_over_time = []
    for job in completed[:20]:  # Last 20 completed jobs
        if job.metrics_json:
            metrics_over_time.append({
                "job_id": job.id,
                "created_at": job.created_at.isoformat(),
                "mAP50": job.metrics_json.get("mAP50", 0),
                "mAP50_95": job.metrics_json.get("mAP50-95", 0)
            })
    
    return TrainingSummary(
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        running_jobs=running_jobs,
        average_epochs=average_epochs,
        best_model=best_model,
        recent_jobs=recent_jobs,
        metrics_over_time=metrics_over_time
    )


@router.get("/prediction/summary", response_model=PredictionSummary)
async def get_Prediction_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get Prediction summary report.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Prediction summary with statistics
    """
    # Build query
    query = db.query(PredictionJob)
    
    if start_date:
        query = query.filter(PredictionJob.created_at >= start_date)
    if end_date:
        query = query.filter(PredictionJob.created_at <= end_date)
    
    # Get counts by status
    total_jobs = query.count()
    completed_jobs = query.filter(PredictionJob.status == PredictionStatus.COMPLETED).count()
    failed_jobs = query.filter(PredictionJob.status == PredictionStatus.FAILED).count()
    
    # Get all Prediction results
    results = db.query(PredictionResult).join(PredictionJob).filter(
        PredictionJob.status == PredictionStatus.COMPLETED
    )
    
    if start_date:
        results = results.filter(PredictionJob.created_at >= start_date)
    if end_date:
        results = results.filter(PredictionJob.created_at <= end_date)
    
    results = results.all()
    
    # Calculate statistics
    total_Predictions = 0
    class_counts = {}
    total_confidence = 0.0
    confidence_count = 0
    
    for result in results:
        if result.boxes_json:
            total_Predictions += len(result.boxes_json)
        
        if result.class_names_json:
            for class_name in result.class_names_json:
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        if result.scores_json:
            for score in result.scores_json:
                total_confidence += score
                confidence_count += 1
    
    # Create class distribution
    class_distribution = [
        ClassCount(class_name=name, count=count)
        for name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    # Get recent jobs
    recent = query.order_by(PredictionJob.created_at.desc()).limit(10).all()
    recent_jobs = [
        {
            "id": j.id,
            "model_id": j.model_id,
            "mode": j.mode.value,
            "status": j.status.value,
            "created_at": j.created_at.isoformat()
        }
        for j in recent
    ]
    
    # Prediction frequency over time (last 30 days)
    Prediction_frequency = []
    if start_date is None:
        start_date = datetime.now() - timedelta(days=30)
    
    completed = query.filter(PredictionJob.status == PredictionStatus.COMPLETED).all()
    for job in completed[-30:]:
        if job.summary_json:
            Prediction_frequency.append({
                "date": job.created_at.date().isoformat(),
                "count": job.summary_json.get("total_Predictions", 0)
            })
    
    # Task type breakdown
    task_type_breakdown = {}
    for job in query.all():
        if job.model and job.model.task_type:
            task_type = job.model.task_type
            task_type_breakdown[task_type] = task_type_breakdown.get(task_type, 0) + 1
    
    # Classification-specific metrics
    classification_metrics = None
    classification_results = [r for r in results if r.task_type == "classify"]
    
    if classification_results:
        total_classifications = len(classification_results)
        class_counts_classify = {}
        top_confidences = []
        
        for result in classification_results:
            # Count predicted classes
            if result.top_class:
                class_counts_classify[result.top_class] = class_counts_classify.get(result.top_class, 0) + 1
            
            # Collect top confidences
            if result.top_confidence:
                top_confidences.append(result.top_confidence)
        
        # Create classification class distribution
        classify_class_distribution = [
            ClassCount(class_name=name, count=count)
            for name, count in sorted(class_counts_classify.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        classification_metrics = ClassificationMetrics(
            total_classifications=total_classifications,
            average_top_confidence=sum(top_confidences) / len(top_confidences) if top_confidences else 0,
            class_distribution=classify_class_distribution,
            top_k_accuracy=None,  # Would need ground truth labels
            per_class_accuracy=None,  # Would need ground truth labels
            confusion_matrix=None  # Would need ground truth labels
        )
    
    return PredictionSummary(
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        total_Predictions=total_Predictions,
        class_distribution=class_distribution,
        Prediction_frequency=Prediction_frequency,
        average_confidence=total_confidence / confidence_count if confidence_count > 0 else 0,
        recent_jobs=recent_jobs,
        task_type_breakdown=task_type_breakdown,
        classification_metrics=classification_metrics
    )
