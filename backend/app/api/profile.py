"""
Profile API Router
Endpoints for user profile management (self-service).
"""
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Body
from sqlalchemy.orm import Session
from PIL import Image
from typing import Optional

from app.db import get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    ProfileUpdateRequest,
    ChangePasswordRequest,
    PasswordStrengthResponse
)
from app.utils.auth import get_current_active_user
from app.utils.security import get_password_hash, verify_password
from app.utils.password_validator import validate_password_strength, get_password_strength_label


router = APIRouter(prefix="/api/profile", tags=["Profile"])

# Profile images directory
PROFILE_IMAGES_DIR = "data/profile_images"
os.makedirs(PROFILE_IMAGES_DIR, exist_ok=True)

# Allowed image extensions and max size
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
PROFILE_IMAGE_SIZE = (200, 200)  # Profile image dimensions


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update current user's profile (first name, last name)."""
    # Update profile fields
    current_user.first_name = profile_data.first_name
    current_user.last_name = profile_data.last_name
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Change current user's password."""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    is_valid, error_msg, _ = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Hash and update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(password: str):
    """Check password strength without saving."""
    is_valid, message, score = validate_password_strength(password)
    label = get_password_strength_label(score)
    
    return PasswordStrengthResponse(
        is_valid=is_valid,
        message=message if message else "Password meets all requirements",
        strength_score=score,
        strength_label=label
    )


@router.post("/upload-image", response_model=UserResponse)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload and set user's profile image (with resize/crop)."""
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE / 1024 / 1024}MB"
        )
    
    # Create user's profile images directory
    user_image_dir = os.path.join(PROFILE_IMAGES_DIR, str(current_user.id))
    os.makedirs(user_image_dir, exist_ok=True)
    
    # Process image with PIL (resize and crop to square)
    try:
        image = Image.open(file.file)
        
        # Convert to RGB if necessary (handles PNG with transparency)
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
            image = background
        
        # Crop to square (center crop)
        width, height = image.size
        if width != height:
            min_dim = min(width, height)
            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            right = (width + min_dim) / 2
            bottom = (height + min_dim) / 2
            image = image.crop((left, top, right, bottom))
        
        # Resize to target dimensions
        image = image.resize(PROFILE_IMAGE_SIZE, Image.Resampling.LANCZOS)
        
        # Save as JPEG
        image_filename = "avatar.jpg"
        image_path = os.path.join(user_image_dir, image_filename)
        image.save(image_path, "JPEG", quality=90, optimize=True)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing image: {str(e)}"
        )
    
    # Update user's profile_image path (relative path)
    relative_path = f"profile_images/{current_user.id}/{image_filename}"
    current_user.profile_image = relative_path
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.delete("/image")
async def delete_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete current user's profile image."""
    if not current_user.profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image to delete"
        )
    
    # Delete file from filesystem
    user_image_dir = os.path.join(PROFILE_IMAGES_DIR, str(current_user.id))
    if os.path.exists(user_image_dir):
        try:
            shutil.rmtree(user_image_dir)
        except Exception as e:
            print(f"Error deleting profile image directory: {e}")
    
    # Clear profile_image field
    current_user.profile_image = None
    db.commit()
    
    return {"message": "Profile image deleted successfully"}
