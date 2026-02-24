"""
PredictionResult Model
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class PredictionResult(Base):
    """Individual prediction result for each processed file/frame."""
    
    __tablename__ = "prediction_results"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_job_id = Column(Integer, ForeignKey("prediction_jobs.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    frame_number = Column(Integer, nullable=True)  # For video frames
    frame_timestamp = Column(String(50), nullable=True)  # Video position: "00:10:01.5" or seconds "601.5"
    task_type = Column(String(50), nullable=True, default="detect")  # detect, classify, segment
    
    # Detection fields
    boxes_json = Column(JSON, default=list)  # [[x1, y1, x2, y2], ...]
    scores_json = Column(JSON, default=list)  # [0.95, 0.87, ...]
    classes_json = Column(JSON, default=list)  # [0, 1, 2, ...] class indices
    class_names_json = Column(JSON, default=list)  # ["person", "car", ...] class names
    
    # Classification fields
    top_class = Column(String(255), nullable=True)
    top_confidence = Column(Float, nullable=True)
    top_classes_json = Column(JSON, default=list)  # ["class1", "class2", ...]
    probabilities_json = Column(JSON, default=list)  # [0.95, 0.85, ...]
    
    # Segmentation fields
    masks_json = Column(JSON, default=list)  # [{"instance_id": 0, "class_id": 1, "mask_rle": "...", "bbox": [x1, y1, x2, y2]}, ...]
    
    # Per-result configuration (tracks inference params used for this specific result)
    config_json = Column(JSON, nullable=True, comment="Inference configuration used for this result")
    
    # LLM/chat outputs (reserved for future use)
    chats_json = Column(JSON, nullable=True, comment="LLM chat outputs and vision-language model responses (reserved for future use)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    prediction_job = relationship("PredictionJob", back_populates="results")
    
    @property
    def config(self):
        """Parse and return config from config_json."""
        from app.schemas.prediction import ResultConfig
        try:
            if self.config_json:
                return ResultConfig(**self.config_json)
            return None
        except Exception:
            return None
    
    def __repr__(self):
        return f"<PredictionResult(id={self.id}, file={self.file_name}, detections={len(self.boxes_json or [])})>"
