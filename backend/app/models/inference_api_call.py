"""
InferenceApiCall Model
Tracks external API inference calls for usage monitoring and rate limiting
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class InferenceApiCall(Base):
    """Track external inference API calls."""
    
    __tablename__ = "inference_api_calls"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_job_id = Column(Integer, ForeignKey("prediction_jobs.id", ondelete="SET NULL"), nullable=True)
    
    # Call metadata
    called_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds
    status_code = Column(Integer, nullable=False)  # HTTP status code (200, 400, 429, etc.)
    file_count = Column(Integer, default=1)  # Number of files processed (1 for single, N for batch)
    error_message = Column(String(512), nullable=True)  # Error message if failed
    
    # Relationships
    user = relationship("User")
    model = relationship("Model")
    prediction_job = relationship("PredictionJob")
