"""
ProjectCampaignForm Model
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class ProjectCampaignForm(Base):
    """Custom form configuration for project campaigns."""
    
    __tablename__ = "project_session_forms"  # Keep table name for now
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    form_config_json = Column(JSONB, nullable=False, server_default='[]')
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="campaign_form")
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<ProjectCampaignForm(id={self.id}, project_id={self.project_id})>"
