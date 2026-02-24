"""
Project Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class ProjectStatus(str, enum.Enum):
    CREATED = "created"
    TRAINING = "training"
    TRAINED = "trained"
    FAILED = "failed"


class Project(Base):
    """Project model linking datasets and models."""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    task_type = Column(String(50), default="detect", nullable=False)
    status = Column(Enum(ProjectStatus, values_callable=lambda obj: [e.value for e in obj]), default=ProjectStatus.CREATED.value, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="owned_projects", foreign_keys=[creator_id])
    dataset = relationship("Dataset", back_populates="projects")
    models = relationship("Model", back_populates="project")
    training_jobs = relationship("TrainingJob", back_populates="project")
    campaign_form = relationship("ProjectCampaignForm", back_populates="project", uselist=False)
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"
