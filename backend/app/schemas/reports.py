"""
Reports Schemas
"""
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime


class TrainingSummary(BaseModel):
    """Schema for training summary report."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    running_jobs: int
    average_epochs: float
    best_model: Optional[Dict[str, Any]]
    recent_jobs: List[Dict[str, Any]]
    metrics_over_time: List[Dict[str, Any]]


class ClassCount(BaseModel):
    """Schema for class detection count."""
    class_name: str
    count: int


class ClassificationMetrics(BaseModel):
    """Schema for classification-specific metrics."""
    total_classifications: int
    top_k_accuracy: Optional[float] = None  # Top-1, Top-3, Top-5 accuracy
    per_class_accuracy: Optional[Dict[str, float]] = None  # Accuracy per class
    confusion_matrix: Optional[List[List[int]]] = None  # Confusion matrix data
    average_top_confidence: float  # Average of top prediction confidence
    class_distribution: List[ClassCount]  # Distribution of predicted classes


class PredictionSummary(BaseModel):
    """Schema for prediction summary report."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_predictions: int
    class_distribution: List[ClassCount]
    prediction_frequency: List[Dict[str, Any]]  # Time-series data
    average_confidence: float
    recent_jobs: List[Dict[str, Any]]
    
    # Task type breakdown
    task_type_breakdown: Optional[Dict[str, int]] = None  # Count by detect/classify/segment
    
    # Classification-specific metrics (when applicable)
    classification_metrics: Optional[ClassificationMetrics] = None


class DateRangeFilter(BaseModel):
    """Schema for date range filter."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
