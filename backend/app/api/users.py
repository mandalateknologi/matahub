"""
User Management API Router
Admin-only endpoints for managing users, roles, and permissions.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.user import User, UserRole
from app.models.dataset import Dataset
from app.models.project import Project
from app.models.prediction_job import PredictionJob as PredictionJob
from app.schemas.user import (
    UserResponse, 
    UserCreate, 
    UserUpdate, 
    UserWithResourceCounts
)
from app.utils.auth import get_current_active_user
from app.utils.security import get_password_hash
from app.utils.permissions import require_admin

router = APIRouter(prefix="/api/users", tags=["User Management"])


@router.get("", response_model=List[UserWithResourceCounts])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all users with optional filters.
    
    Permissions:
    - ADMIN: Can list all users
    - PROJECT_ADMIN: Can only list operators (for team management)
    - OPERATOR: Forbidden
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        role: Filter by user role (ADMIN, PROJECT_ADMIN, OPERATOR)
        is_active: Filter by active status (True/False)
        search: Search by username or email (case-insensitive)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of users with resource counts
    """
    # Permission check: PROJECT_ADMIN can only list operators
    if current_user.role == UserRole.PROJECT_ADMIN:
        if role and role != UserRole.OPERATOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project Admins can only list operators"
            )
        # Force role filter to OPERATOR for PROJECT_ADMIN
        role = UserRole.OPERATOR
    elif current_user.role == UserRole.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Project Admin access required"
        )
    query = db.query(User)
    
    # Apply filters
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_term)) | 
            (User.email.ilike(search_term))
        )
    
    # Get users
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    # Attach resource counts
    result = []
    for user in users:
        datasets_count = db.query(func.count(Dataset.id)).filter(
            Dataset.creator_id == user.id
        ).scalar()
        
        projects_count = db.query(func.count(Project.id)).filter(
            Project.creator_id == user.id
        ).scalar()
        
        prediction_jobs_count = db.query(func.count(PredictionJob.id)).filter(
            PredictionJob.creator_id == user.id
        ).scalar()
        
        user_dict = UserWithResourceCounts.model_validate(user)
        user_dict.datasets_count = datasets_count
        user_dict.projects_count = projects_count
        user_dict.prediction_jobs_count = prediction_jobs_count
        
        result.append(user_dict)
    
    return result


@router.get("/{user_id}", response_model=UserWithResourceCounts)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get user details with resource counts.
    Admin only.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        
    Returns:
        User details with resource counts
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get resource counts
    datasets_count = db.query(func.count(Dataset.id)).filter(
        Dataset.creator_id == user.id
    ).scalar()
    
    projects_count = db.query(func.count(Project.id)).filter(
        Project.creator_id == user.id
    ).scalar()
    
    prediction_jobs_count = db.query(func.count(PredictionJob.id)).filter(
        PredictionJob.creator_id == user.id
    ).scalar()
    
    user_dict = UserWithResourceCounts.model_validate(user)
    user_dict.datasets_count = datasets_count
    user_dict.projects_count = projects_count
    user_dict.prediction_jobs_count = prediction_jobs_count
    
    return user_dict


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new user.
    Admin only.
    
    Args:
        user_data: User creation data (email, password, role)
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        
    Returns:
        Created user
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        is_active=True,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update user details.
    Admin only.
    
    Protections:
    - Cannot change own role (self-demotion protection)
    - Cannot downgrade PROJECT_ADMIN to OPERATOR if they own resources
    - Can update email, is_active, and role (with validations)
    
    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        
    Returns:
        Updated user
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Self-demotion protection: cannot change own role
    if user.id == current_user.id and user_data.role and user_data.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change your own role"
        )
    
    # Role downgrade validation: PROJECT_ADMIN -> OPERATOR
    if user_data.role and user_data.role == UserRole.OPERATOR and user.role == UserRole.PROJECT_ADMIN:
        # Check if user owns resources
        datasets_count = db.query(func.count(Dataset.id)).filter(
            Dataset.creator_id == user.id
        ).scalar()
        
        projects_count = db.query(func.count(Project.id)).filter(
            Project.creator_id == user.id
        ).scalar()
        
        if datasets_count > 0 or projects_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot downgrade to OPERATOR: user owns {datasets_count} datasets and {projects_count} projects. Transfer or delete resources first."
            )
    
    # Update email if provided and different
    if user_data.email and user_data.email != user.email:
        # Check email uniqueness
        existing_email = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another user"
            )
        user.email = user_data.email
    
    # Update role if provided
    if user_data.role:
        user.role = user_data.role
    
    # Update is_active if provided
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # Update password if provided
    if user_data.password:
        user.hashed_password = get_password_hash(user_data.password)
    
    # Update first_name if provided
    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    
    # Update last_name if provided
    if user_data.last_name is not None:
        user.last_name = user_data.last_name
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    force: bool = Query(False, description="Force delete (hard delete) instead of soft delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a user (soft delete by default, hard delete with force=true).
    Admin only.
    
    Soft delete (default):
    - Sets is_active = False
    - User cannot login but data is preserved
    
    Hard delete (force=true):
    - Permanently deletes user
    - Only allowed if user has no owned resources (RESTRICT constraint)
    
    Protections:
    - Cannot delete yourself
    - Hard delete fails if user owns datasets/projects (foreign key RESTRICT)
    
    Args:
        user_id: User ID
        force: If True, perform hard delete; if False, soft delete
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Self-deletion protection
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete yourself"
        )
    
    if force:
        # Hard delete: will fail if user owns resources (foreign key RESTRICT)
        try:
            db.delete(user)
            db.commit()
        except Exception as e:
            db.rollback()
            # Check resource counts for better error message
            datasets_count = db.query(func.count(Dataset.id)).filter(
                Dataset.creator_id == user.id
            ).scalar()
            
            projects_count = db.query(func.count(Project.id)).filter(
                Project.creator_id == user.id
            ).scalar()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete user: owns {datasets_count} datasets and {projects_count} projects. Delete or transfer resources first, or use soft delete."
            )
    else:
        # Soft delete: just deactivate
        user.is_active = False
        db.commit()


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Reactivate a soft-deleted (deactivated) user.
    Admin only.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        
    Returns:
        Reactivated user
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )
    
    user.is_active = True
    db.commit()
    db.refresh(user)
    
    return user
