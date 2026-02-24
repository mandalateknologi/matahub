"""
User Schemas
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from app.models.user import UserRole


class UserCreate(BaseModel):
    """Schema for creating a new user (admin only)."""
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: UserRole = Field(..., description="User role: project_admin or operator")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")


class UserUpdate(BaseModel):
    """Schema for updating a user (admin only)."""
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image: Optional[str] = None
    
    model_config = {"from_attributes": True}


class UserWithResourceCounts(UserResponse):
    """Schema for user response with resource counts."""
    datasets_count: Optional[int] = 0
    projects_count: Optional[int] = 0
    prediction_jobs_count: Optional[int] = 0
    
    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    """Schema for project member response."""
    user_id: int
    email: str
    role: UserRole
    added_at: datetime
    added_by: int
    
    model_config = {"from_attributes": True}


class ProjectMemberAdd(BaseModel):
    """Schema for adding a project member."""
    user_id: int = Field(..., description="User ID of the operator to add")


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: Optional[int] = None
    email: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """Schema for updating user profile."""
    first_name: str = Field(..., min_length=1, max_length=100, description="First name (required)")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name (optional)")


class ChangePasswordRequest(BaseModel):
    """Schema for changing user password."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class PasswordStrengthResponse(BaseModel):
    """Schema for password strength check response."""
    is_valid: bool
    message: str
    strength_score: int = Field(..., ge=0, le=4, description="Strength score 0-4")
    strength_label: str = Field(..., description="Strength label: Very Weak, Weak, Medium, Strong, Very Strong")
