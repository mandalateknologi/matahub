"""
API Key Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class ApiKey(Base):
    """API Key model for API authentication."""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)  # Bcrypt hash of the API key
    key_prefix = Column(String(12), nullable=False)  # First 8 chars after 'atv_' for display
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_key")
    
    def __repr__(self):
        return f"<ApiKey(id={self.id}, user_id={self.user_id}, prefix={self.key_prefix})>"
