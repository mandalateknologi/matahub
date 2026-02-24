"""
Recognition Catalog Models - Face/Object recognition with CLIP embeddings
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pathlib import Path
from pgvector.sqlalchemy import Vector
from app.db import Base


class RecognitionCatalog(Base):
    """Recognition catalog for storing labeled face/object embeddings."""
    
    __tablename__ = "recognition_catalogs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)  # e.g., "Office Faces", "VVIP Database"
    image_count = Column(Integer, default=0)
    label_count = Column(Integer, default=0)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="recognition_catalogs")
    labels = relationship("RecognitionLabel", back_populates="catalog", cascade="all, delete-orphan")
    
    def get_catalog_path(self) -> Path:
        """
        Get the absolute path to the catalog directory.
        Catalogs are stored at {DATA_DIR}/recognition_catalogs/{id}
        
        Returns:
            Path object to the catalog directory
        """
        from app.config import settings
        return Path(settings.DATA_DIR) / "recognition_catalogs" / str(self.id)


class RecognitionLabel(Base):
    """Labels within a recognition catalog (e.g., person name, object type)."""
    
    __tablename__ = "recognition_labels"
    
    id = Column(Integer, primary_key=True, index=True)
    catalog_id = Column(Integer, ForeignKey("recognition_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    label_name = Column(String(255), nullable=False)  # e.g., "John Doe", "Safety Helmet"
    description = Column(Text, nullable=True)
    image_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    catalog = relationship("RecognitionCatalog", back_populates="labels")
    images = relationship("RecognitionImage", back_populates="label", cascade="all, delete-orphan")
    
    # Unique constraint: label_name must be unique within catalog
    __table_args__ = (
        Index('ix_recognition_labels_catalog_name', 'catalog_id', 'label_name', unique=True),
    )


class RecognitionImage(Base):
    """Images associated with labels, storing CLIP embeddings for similarity search."""
    
    __tablename__ = "recognition_images"
    
    id = Column(Integer, primary_key=True, index=True)
    label_id = Column(Integer, ForeignKey("recognition_labels.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String(512), nullable=False)  # Relative to DATA_DIR
    thumbnail_path = Column(String(512), nullable=True)  # Optional thumbnail
    # CLIP ViT-B/32 produces 512-dimensional embeddings
    embedding = Column(Vector(512), nullable=True)  # pgvector for fast similarity search
    is_processed = Column(Boolean, default=False)  # True when embedding generated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    label = relationship("RecognitionLabel", back_populates="images")
    
    # Index for vector similarity search (cosine distance)
    __table_args__ = (
        Index('ix_recognition_images_embedding', 'embedding', postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )


class RecognitionJob(Base):
    """Background jobs for batch embedding generation."""
    
    __tablename__ = "recognition_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    catalog_id = Column(Integer, ForeignKey("recognition_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    label_id = Column(Integer, ForeignKey("recognition_labels.id", ondelete="CASCADE"), nullable=True, index=True)
    total_images = Column(Integer, default=0)
    processed_images = Column(Integer, default=0)
    failed_images = Column(Integer, default=0)
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    catalog = relationship("RecognitionCatalog")
    label = relationship("RecognitionLabel")
