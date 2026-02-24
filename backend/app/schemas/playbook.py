"""
Playbook Pydantic Schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# Playbook Schemas
class PlaybookBase(BaseModel):
    """Base playbook schema."""
    name: str
    description: Optional[str] = None


class PlaybookCreate(PlaybookBase):
    """Schema for creating a playbook."""
    pass


class PlaybookUpdate(BaseModel):
    """Schema for updating a playbook."""
    name: Optional[str] = None
    description: Optional[str] = None


class PlaybookResponse(PlaybookBase):
    """Basic playbook response."""
    id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Playbook Member Schemas
class PlaybookMemberAdd(BaseModel):
    """Schema for adding a member to playbook."""
    user_id: int


class PlaybookMemberResponse(BaseModel):
    """Playbook member response."""
    user_id: int
    added_by: int
    added_at: datetime
    # User details (populated from join)
    email: Optional[str] = None
    role: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# Playbook Model Schemas
class PlaybookModelAdd(BaseModel):
    """Schema for adding a model to playbook."""
    model_id: int


class PlaybookModelResponse(BaseModel):
    """Playbook model response."""
    model_id: int
    added_by: int
    added_at: datetime
    # Model details (populated from join)
    model_name: Optional[str] = None
    model_version: Optional[int] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    newer_version_available: bool = False
    
    model_config = ConfigDict(from_attributes=True)


# Playbook Campaign Form Schemas
class CampaignFormFieldConfig(BaseModel):
    """Single form field configuration."""
    field_name: str
    label: str
    field_type: str
    required: bool = False
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    default_value: Optional[str] = None
    validation_regex: Optional[str] = None
    help_text: Optional[str] = None


class PlaybookCampaignFormCreate(BaseModel):
    """Schema for creating/updating playbook campaign form."""
    fields: List[CampaignFormFieldConfig]


class PlaybookCampaignFormResponse(BaseModel):
    """Playbook campaign form response."""
    id: int
    playbook_id: int
    fields: List[CampaignFormFieldConfig]
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Detailed Playbook Response
class PlaybookDetail(PlaybookResponse):
    """Detailed playbook response with relationships."""
    team_members: List[PlaybookMemberResponse] = []
    models: List[PlaybookModelResponse] = []
    campaign_form: Optional[PlaybookCampaignFormResponse] = None
    
    model_config = ConfigDict(from_attributes=True)
