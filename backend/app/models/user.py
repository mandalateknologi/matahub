"""
User Model
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class UserRole(str, enum.Enum):

    ADMIN = "admin"
    PROJECT_ADMIN = "project_admin"
    OPERATOR = "operator"


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, values_callable=lambda obj: [e.value for e in obj]), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Profile fields
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    profile_image = Column(String(512), nullable=True)
    
    # Relationships
    owned_datasets = relationship("Dataset", back_populates="creator", foreign_keys="Dataset.creator_id")
    owned_playbooks = relationship("Playbook", back_populates="creator", foreign_keys="Playbook.creator_id")
    owned_projects = relationship("Project", back_populates="creator", foreign_keys="Project.creator_id")
    prediction_jobs = relationship("PredictionJob", back_populates="creator", foreign_keys="PredictionJob.creator_id")
    files = relationship("UserFile", back_populates="user", cascade="all, delete-orphan")
    api_key = relationship("ApiKey", back_populates="user", uselist=False, cascade="all, delete-orphan")
    recognition_catalogs = relationship("RecognitionCatalog", back_populates="creator")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
