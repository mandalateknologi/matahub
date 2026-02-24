"""
ProjectCampaignForm Schemas
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional, Any, Literal


class CampaignFormFieldConfig(BaseModel):
    """Schema for a single form field configuration."""
    field_name: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    label: str = Field(..., min_length=1, max_length=255)
    field_type: Literal['text', 'textarea', 'number', 'email', 'date', 'select'] = Field(...)
    data_type: Literal['string', 'number', 'date', 'email'] = Field(default='string')
    required: bool = Field(default=False)
    placeholder: Optional[str] = Field(default=None, max_length=255)
    options: Optional[List[str]] = Field(default=None)
    order: int = Field(default=0, ge=0)
    
    @field_validator('options')
    def validate_options(cls, v, info):
        """Validate that options are provided for select field type."""
        field_type = info.data.get('field_type')
        if field_type == 'select':
            if not v or len(v) == 0:
                raise ValueError('Options are required for select field type')
        return v


class CampaignFormCreate(BaseModel):
    """Schema for creating/updating campaign form configuration."""
    form_config: List[CampaignFormFieldConfig] = Field(default_factory=list)
    
    @field_validator('form_config')
    def validate_unique_field_names(cls, v):
        """Ensure all field names are unique."""
        field_names = [field.field_name for field in v]
        if len(field_names) != len(set(field_names)):
            raise ValueError('Field names must be unique')
        return v


class CampaignFormResponse(BaseModel):
    """Schema for campaign form configuration response."""
    id: int
    project_id: int
    form_config: List[CampaignFormFieldConfig]
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
    
    @field_validator('form_config', mode='before')
    def parse_form_config(cls, v):
        """Parse form_config_json from database."""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
