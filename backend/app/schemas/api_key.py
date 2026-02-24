"""
API Key Schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key."""
    pass  # No input needed, key is generated server-side


class ApiKeyResponse(BaseModel):
    """Schema for API key metadata response (without the actual key)."""
    id: int
    user_id: int
    key_prefix: str = Field(..., description="First 8 characters of the key for identification")
    created_at: datetime
    last_used_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(BaseModel):
    """Schema for API key creation response (includes full key once)."""
    id: int
    user_id: int
    key: str = Field(..., description="Full API key - only shown once!")
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}
