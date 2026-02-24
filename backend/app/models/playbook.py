"""
Playbook Model - Business Execution Container
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class Playbook(Base):
    """Playbook model - operational container for teams, forms, and campaigns."""
    
    __tablename__ = "playbooks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    creator = relationship("User", back_populates="owned_playbooks", foreign_keys=[creator_id])
    team_members = relationship("PlaybookMember", back_populates="playbook", cascade="all, delete-orphan")
    campaign_form = relationship("PlaybookCampaignForm", back_populates="playbook", uselist=False, cascade="all, delete-orphan")
    playbook_models = relationship("PlaybookModel", back_populates="playbook", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="playbook")
    
    def __repr__(self):
        return f"<Playbook(id={self.id}, name={self.name})>"


class PlaybookMember(Base):
    """Association table for playbook team members."""
    
    __tablename__ = "playbook_members"
    
    playbook_id = Column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    playbook = relationship("Playbook", back_populates="team_members")
    user = relationship("User", foreign_keys=[user_id])
    added_by_user = relationship("User", foreign_keys=[added_by])
    
    def __repr__(self):
        return f"<PlaybookMember(playbook_id={self.playbook_id}, user_id={self.user_id})>"


class PlaybookCampaignForm(Base):
    """Custom form configuration for playbook campaigns."""
    
    __tablename__ = "playbook_session_forms"
    
    id = Column(Integer, primary_key=True, index=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    form_config_json = Column("form_config_json", Text, nullable=False, server_default='[]')
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    playbook = relationship("Playbook", back_populates="campaign_form")
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<PlaybookCampaignForm(id={self.id}, playbook_id={self.playbook_id})>"


class PlaybookModel(Base):
    """Many-to-many association between playbooks and models."""
    
    __tablename__ = "playbook_models"
    
    playbook_id = Column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), primary_key=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), primary_key=True, index=True)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    playbook = relationship("Playbook", back_populates="playbook_models")
    model = relationship("Model")
    added_by_user = relationship("User", foreign_keys=[added_by])
    
    def __repr__(self):
        return f"<PlaybookModel(playbook_id={self.playbook_id}, model_id={self.model_id})>"
