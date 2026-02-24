"""
Recognition Catalog Schemas
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


# ===== Recognition Catalog Schemas =====

class RecognitionCatalogCreate(BaseModel):
    """Schema for creating a new recognition catalog."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., min_length=1, max_length=100)  # e.g., "Office Faces", "VVIP Database"


class RecognitionCatalogResponse(BaseModel):
    """Schema for recognition catalog list response."""
    id: int
    name: str
    description: Optional[str]
    category: str
    image_count: int
    label_count: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class RecognitionCatalogDetail(RecognitionCatalogResponse):
    """Schema for detailed recognition catalog response with labels."""
    labels: List["RecognitionLabelResponse"] = []
    
    model_config = {"from_attributes": True}


class RecognitionCatalogUpdate(BaseModel):
    """Schema for updating a recognition catalog."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, min_length=1, max_length=100)


# ===== Recognition Label Schemas =====

class RecognitionLabelCreate(BaseModel):
    """Schema for creating a new label in a catalog."""
    label_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class RecognitionLabelResponse(BaseModel):
    """Schema for recognition label response."""
    id: int
    catalog_id: int
    label_name: str
    description: Optional[str]
    image_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class RecognitionLabelDetail(RecognitionLabelResponse):
    """Schema for detailed label response with images."""
    images: List["RecognitionImageResponse"] = []
    
    model_config = {"from_attributes": True}


class RecognitionLabelUpdate(BaseModel):
    """Schema for updating a label."""
    label_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


# ===== Recognition Image Schemas =====

class RecognitionImageResponse(BaseModel):
    """Schema for recognition image response."""
    id: int
    label_id: int
    image_path: str
    thumbnail_path: Optional[str]
    is_processed: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class RecognitionImageDetail(RecognitionImageResponse):
    """Schema for detailed image response with embedding."""
    embedding: Optional[List[float]]  # 512-dimensional CLIP embedding
    
    model_config = {"from_attributes": True}


# ===== Recognition Job Schemas =====

class RecognitionJobResponse(BaseModel):
    """Schema for recognition job response."""
    id: int
    catalog_id: int
    label_id: Optional[int]
    total_images: int
    processed_images: int
    failed_images: int
    status: str  # pending, processing, completed, failed
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    model_config = {"from_attributes": True}


# ===== Similarity Search Schemas =====

class SimilaritySearchRequest(BaseModel):
    """Schema for similarity search request."""
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    label_filter: Optional[List[int]] = None  # Filter by specific label IDs


class SimilarityMatchResponse(BaseModel):
    """Schema for a single similarity match result."""
    label_id: int
    label_name: str
    image_id: int
    image_path: str
    thumbnail_path: Optional[str]
    similarity_score: float
    distance_metric: str = "cosine"


class SimilaritySearchResponse(BaseModel):
    """Schema for similarity search response."""
    query_image_path: str
    matches: List[SimilarityMatchResponse]
    inference_time_ms: float
    total_candidates: int


# ===== Statistics Schemas =====

class RecognitionCatalogStats(BaseModel):
    """Schema for catalog statistics."""
    catalog_id: int
    catalog_name: str
    category: str
    total_labels: int
    total_images: int
    processed_images: int
    unprocessed_images: int
    average_images_per_label: float
