"""
Dataset Model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from pathlib import Path
from app.db import Base


class DatasetStatus(str, enum.Enum):
    """Dataset status enumeration."""
    EMPTY = "empty"          # Created but no files uploaded
    INCOMPLETE = "incomplete"  # Has files but validation failed or missing data
    VALID = "valid"           # Fully validated and ready for training


class Dataset(Base):
    """Dataset model for storing YOLO training data."""
    
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), default="detect", nullable=False)  # detect, segment, classify
    status = Column(Enum(DatasetStatus, values_callable=lambda obj: [e.value for e in obj]), default=DatasetStatus.EMPTY.value, nullable=False)
    yaml_path = Column(String(512), nullable=True)  # Path to data.yaml file
    images_count = Column(Integer, default=0)
    labels_count = Column(Integer, default=0)
    classes_json = Column(JSON, default=dict)  # Dict mapping class IDs to names: {'0': 'helmet', '1': 'vest'}
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="owned_datasets", foreign_keys=[creator_id])
    projects = relationship("Project", back_populates="dataset")
    
    def get_dataset_path(self) -> Path:
        """
        Get the absolute path to the dataset directory.
        Datasets are always stored at {DATA_DIR}/datasets/{id}
        
        Returns:
            Path object to the dataset directory
        """
        from app.config import settings
        return Path(settings.DATA_DIR) / "datasets" / str(self.id)
    
    def __repr__(self):
        return f"<Dataset(id={self.id}, name={self.name}, images={self.images_count})>"
