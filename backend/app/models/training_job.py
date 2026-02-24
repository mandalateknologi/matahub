"""
TrainingJob Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class TrainingStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingJob(Base):
    """Training job for tracking YOLO model training progress."""
    
    __tablename__ = "training_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    status = Column(Enum(TrainingStatus, values_callable=lambda obj: [e.value for e in obj]), default=TrainingStatus.PENDING.value, nullable=False)
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=100)
    logs_path = Column(String(512), nullable=True)
    metrics_json = Column(JSON, default=dict)  # Current training metrics
    error_message = Column(String(1024), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="training_jobs")
    model = relationship("Model", back_populates="training_jobs")
    
    def __repr__(self):
        return f"<TrainingJob(id={self.id}, status={self.status}, progress={self.progress}%)>"
