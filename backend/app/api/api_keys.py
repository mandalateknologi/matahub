"""
API Keys Management Router
Endpoints for managing user API keys for authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.api_key import (
    ApiKeyResponse,
    ApiKeyCreateResponse
)
from app.utils.auth import get_current_active_user
from app.utils.security import get_password_hash
from app.utils.api_key_auth import generate_api_key

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a new API key for the current user.
    
    **Important:** Each user can only have ONE API key at a time.
    If an API key already exists, you must revoke it first.
    
    **Warning:** The full API key is only shown ONCE in this response.
    Store it securely - it cannot be retrieved again!
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        API key metadata with the full key (only shown once)
        
    Raises:
        HTTPException 409: If user already has an API key
    """
    # Check if user already has an API key
    existing_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key already exists. Please revoke the existing key before creating a new one."
        )
    
    # Generate new API key
    full_key, key_prefix = generate_api_key()
    
    # Hash the key for storage (same as password hashing)
    key_hash = get_password_hash(full_key)
    
    # Create API key record
    api_key = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    # Return response with full key (only time it's shown)
    return ApiKeyCreateResponse(
        id=api_key.id,
        user_id=api_key.user_id,
        key=full_key,  # ⚠️ Only shown once!
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at
    )


@router.get("/current", response_model=ApiKeyResponse)
async def get_current_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get metadata about the current user's API key.
    
    **Note:** This returns only metadata (prefix, dates).
    The full API key is never retrievable after creation.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        API key metadata (without the full key)
        
    Raises:
        HTTPException 404: If no API key exists
    """
    api_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API key found for current user"
        )
    
    return api_key


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Revoke (delete) the current user's API key.
    
    This action is immediate and irreversible.
    Any applications using this key will be unable to authenticate.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Raises:
        HTTPException 404: If no API key exists
    """
    api_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API key found for current user"
        )
    
    db.delete(api_key)
    db.commit()
    
    return None
