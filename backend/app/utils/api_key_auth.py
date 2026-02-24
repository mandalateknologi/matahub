"""
API Key Authentication Utilities
"""
import secrets
from typing import Optional
from datetime import datetime, timezone
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.db import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.utils.security import verify_password


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key with the format 'atv_' + random string.
    
    Returns:
        Tuple of (full_key, key_prefix) where:
        - full_key: The complete API key to be shown once
        - key_prefix: First 8 chars after 'atv_' for display
    """
    # Generate cryptographically secure random key
    random_part = secrets.token_urlsafe(32)  # Generates ~43 chars
    full_key = f"atv_{random_part}"
    
    # Extract prefix for display (first 8 chars after 'atv_')
    key_prefix = random_part[:8]
    
    return full_key, key_prefix


async def get_user_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticate user via API key from X-API-Key header.
    
    Args:
        x_api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        Authenticated User object
        
    Raises:
        HTTPException: If API key is invalid or user is inactive
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Validate key format
    if not x_api_key.startswith("atv_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Query all API keys and check hashes (since we can't query by hash directly)
    api_keys = db.query(ApiKey).all()
    
    matched_api_key = None
    for api_key_record in api_keys:
        # Use verify_password since we hash API keys the same way as passwords
        if verify_password(x_api_key, api_key_record.key_hash):
            matched_api_key = api_key_record
            break
    
    if not matched_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Get the user
    user = db.query(User).filter(User.id == matched_api_key.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Update last_used_at timestamp
    matched_api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    
    return user
