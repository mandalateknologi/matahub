"""
Campaign and CampaignExport Models
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class CampaignStatus(str, enum.Enum):
    """Campaign lifecycle status"""
    ACTIVE = "active"
    ENDED = "ended"


class CampaignExportType(str, enum.Enum):
    """Types of campaign exports"""
    MEGA_REPORT_PDF = "mega_report_pdf"
    MEGA_DATA_ZIP = "mega_data_zip"


class CampaignExportStatus(str, enum.Enum):
    """Export job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Campaign(Base):
    """Campaign grouping multiple prediction jobs."""
    
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum(CampaignStatus, values_callable=lambda obj: [e.value for e in obj]), 
        nullable=False, 
        default=CampaignStatus.ACTIVE,
        server_default="active",
        index=True
    )
    summary_json = Column(JSONB, nullable=False, default=dict, server_default='{}')  # Cached statistics
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    creator = relationship("User", foreign_keys=[creator_id])
    playbook = relationship("Playbook", back_populates="campaigns", foreign_keys=[playbook_id])
    prediction_jobs = relationship(
        "PredictionJob", 
        back_populates="campaign",
        foreign_keys="PredictionJob.campaign_id"
    )
    campaign_exports = relationship(
        "CampaignExport", 
        back_populates="campaign",
        cascade="all, delete-orphan"
    )
    
    @property
    def team(self):
        """Inherit team access from playbook."""
        return self.playbook.team_members if self.playbook else []
    
    @property
    def last_activity(self):
        """Calculate last activity timestamp from jobs."""
        if not self.prediction_jobs:
            return self.created_at
        
        latest_job = max(
            self.prediction_jobs,
            key=lambda j: j.completed_at or j.created_at,
            default=None
        )
        
        if latest_job:
            return latest_job.completed_at or latest_job.created_at
        return self.created_at
    
    @property
    def running_jobs_count(self):
        """Count jobs currently running or pending."""
        from app.models.prediction_job import PredictionStatus
        return sum(
            1 for job in self.prediction_jobs 
            if job.status in (PredictionStatus.PENDING, PredictionStatus.RUNNING)
        )


class CampaignExport(Base):
    """Export jobs for campaigns (mega-reports)."""
    
    __tablename__ = "campaign_exports"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(
        Enum(CampaignExportType, values_callable=lambda obj: [e.value for e in obj]), 
        nullable=False
    )
    status = Column(
        Enum(CampaignExportStatus, values_callable=lambda obj: [e.value for e in obj]), 
        nullable=False,
        default=CampaignExportStatus.PENDING,
        server_default="pending",
        index=True
    )
    file_path = Column(String(500), nullable=True)
    progress = Column(Integer, nullable=False, default=0, server_default='0')  # 0-100
    config_json = Column(JSONB, nullable=False, default=dict, server_default='{}')
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_exports")
