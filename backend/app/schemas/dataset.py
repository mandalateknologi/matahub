"""
Dataset Schemas
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Any, Dict


class DatasetCreate(BaseModel):
    """Schema for creating a new dataset."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    task_type: str = Field(default="detect", pattern="^(detect|segment|classify)$")


class DatasetResponse(BaseModel):
    """Schema for dataset list response."""
    id: int
    name: str
    description: Optional[str]
    task_type: str
    status: str  # Will be DatasetStatus enum value
    images_count: int
    labels_count: int
    classes_json: Dict[str, str]  # Dict mapping class IDs to names
    creator_id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
    
    @field_validator('classes_json', mode='before')
    @classmethod
    def validate_classes_json(cls, v: Any) -> Dict[str, str]:
        """Convert classes_json to dict mapping IDs to names."""
        if v is None:
            return {}
        
        # If it's already a dict with string keys, return it
        if isinstance(v, dict):
            # Ensure all keys are strings
            return {str(k): str(v) for k, v in v.items()}
        
        # If it's a list, convert to dict with indices as keys
        if isinstance(v, list):
            result = {}
            for idx, item in enumerate(v):
                if isinstance(item, str):
                    result[str(idx)] = item
                elif isinstance(item, dict):
                    # Handle nested dict items
                    result.update({str(k): str(v) for k, v in item.items()})
            return result
        
        # Default: return empty dict
        return {}


class DatasetDetail(DatasetResponse):
    """Schema for detailed dataset response."""
    yaml_path: Optional[str]
    
    model_config = {"from_attributes": True}


class DatasetUpdate(BaseModel):
    """Schema for updating a dataset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    classes_json: Optional[Dict[str, str]] = None  # Dict mapping class IDs to names


class SegmentationPolygon(BaseModel):
    """Schema for a single segmentation polygon."""
    class_id: int = Field(..., description="Class ID for the polygon")
    points: List[float] = Field(..., description="Flat list of normalized coordinates [x1, y1, x2, y2, ...]")
    
    model_config = {"extra": "forbid"}
    
    @field_validator('points')
    @classmethod
    def validate_points(cls, v: List[float]) -> List[float]:
        """Validate polygon points."""
        if len(v) < 6:
            raise ValueError("Polygon must have at least 3 points (6 coordinates)")
        if len(v) % 2 != 0:
            raise ValueError("Points must have even number of coordinates (x,y pairs)")
        return v


class SegmentationLabelRequest(BaseModel):
    """Schema for segmentation label save request."""
    polygons: List[SegmentationPolygon] = Field(..., description="List of polygons to save")
