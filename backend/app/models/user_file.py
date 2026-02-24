"""
User File Model
Tracks all files uploaded by users for file management system.
"""
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class UserFile(Base):
    """
    Model for tracking user-uploaded files.
    Supports file management with soft delete and trash functionality.
    """
    __tablename__ = "user_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # File information
    file_path = Column(String, nullable=False)  # Full path relative to DATA_DIR
    file_name = Column(String, nullable=False)  # Original filename
    file_type = Column(String, nullable=False)  # "image" or "video"
    file_size = Column(BigInteger, nullable=False)  # Size in bytes
    
    # Folder organization
    folder_path = Column(String, nullable=False, default="shared")  # e.g., "shared", "shared/subfolder", "workflow", "trash"
    is_system_folder = Column(Boolean, default=False)  # True for workflow/shared/trash root folders
    
    # Soft delete for trash functionality
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="files")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_user_files_user_folder", "user_id", "folder_path"),
        Index("ix_user_files_deleted_cleanup", "is_deleted", "deleted_at"),
    )
    
    def __repr__(self):
        return f"<UserFile(id={self.id}, user_id={self.user_id}, name='{self.file_name}', path='{self.folder_path}')>"
