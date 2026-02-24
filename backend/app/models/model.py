"""
Model Model (Trained YOLO models)
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base
import enum
import uuid


class ModelStatus(str, enum.Enum):
    PENDING = "pending"
    TRAINING = "training"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"


class Model(Base):
    """Trained YOLO model metadata."""
    
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)  # Model description
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    api_key = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)  # Secure identifier for external API access
    base_type = Column(String(50), nullable=False)  # yolov8n, yolov8s, etc. (for training)
    inference_type = Column(String(50), nullable=False, default="yolo")  # yolo, sam3, etc. (for inference routing)
    task_type = Column(String(50), nullable=False)  # detect, classify, segment
    requires_prompts = Column(Boolean, nullable=False, server_default=text('false'))  # Whether model requires prompts (SAM3, future prompt-capable models)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ModelStatus, values_callable=lambda obj: [e.value for e in obj]), default=ModelStatus.PENDING, nullable=False)
    artifact_path = Column(String(512), nullable=True)  # Path to best.pt
    metrics_json = Column(JSON, default=dict)  # mAP, precision, recall, etc.
    validation_error = Column(String(512), nullable=True)  # Error message if validation fails
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="models")
    training_jobs = relationship("TrainingJob", back_populates="model")
    prediction_jobs = relationship("PredictionJob", back_populates="model")
    
    @property
    def is_system(self) -> bool:
        """Return whether this model belongs to a system project."""
        return self.project.is_system if self.project else False
    
    @property
    def project_name(self) -> str:
        """Return the name of the project this model belongs to."""
        return self.project.name if self.project else ""
    
    @property
    def version(self) -> str:
        """Return the version of the model."""
        return "0.1"  # Placeholder for actual versioning logic
    
    def __repr__(self):
        return f"<Model(id={self.id}, name={self.name}, status={self.status})>"
