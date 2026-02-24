"""
Export Job Model
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.db import Base


class ExportType(str, enum.Enum):
    """Export type enumeration."""
    IMAGES_ZIP = "images_zip"
    DATA_JSON = "data_json"
    DATA_CSV = "data_csv"
    REPORT_PDF = "report_pdf"


class ExportStatus(str, enum.Enum):
    """Export status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(Base):
    """Export job for prediction results."""
    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, index=True)
    prediction_job_id = Column(Integer, ForeignKey("prediction_jobs.id"), nullable=False)
    export_type = Column(
        SQLEnum(ExportType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    status = Column(
        SQLEnum(ExportStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ExportStatus.PENDING,
        nullable=False
    )
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    file_path = Column(String, nullable=True)  # Path to generated export file
    options_json = Column(JSON, nullable=True)  # Export options (annotated, result_ids, etc.)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)

    # Relationships
    prediction_job = relationship("PredictionJob", back_populates="export_jobs")
    creator = relationship("User")

    def __repr__(self):
        return f"<ExportJob(id={self.id}, type={self.export_type}, status={self.status})>"
