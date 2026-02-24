"""
Permission and Authorization Utilities

This module provides dependency injection functions and helpers for enforcing
role-based access control (RBAC) across the ATVISION API.
"""
from typing import List
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.dataset import Dataset
from app.models.project import Project
from app.models.prediction_job import PredictionJob as DetectionJob
from app.models.project_member import ProjectMember
from app.models.recognition import RecognitionCatalog
from app.utils.auth import get_current_active_user


# ============================================================================
# Role-Based Dependencies
# ============================================================================


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency that requires ADMIN role.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        User object if authorized
        
    Raises:
        HTTPException: 403 if user is not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_project_admin_or_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency that requires PROJECT_ADMIN or ADMIN role.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        User object if authorized
        
    Raises:
        HTTPException: 403 if user is not project admin or admin
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.PROJECT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project Admin or Admin access required"
        )
    return current_user


async def require_operator_or_above(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency that requires any authenticated user (OPERATOR, PROJECT_ADMIN, or ADMIN).
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        User object if authenticated
    """
    # All authenticated users can access
    return current_user


# ============================================================================
# Resource Ownership Validators
# ============================================================================

def check_dataset_ownership(
    dataset_id: int,
    user: User,
    db: Session
) -> Dataset:
    """
    Validate that user owns the dataset or is an admin.
    
    Args:
        dataset_id: Dataset ID to check
        user: Current user
        db: Database session
        
    Returns:
        Dataset object if authorized
        
    Raises:
        HTTPException: 404 if dataset not found, 403 if not authorized
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Admin can access all datasets
    if user.role == UserRole.ADMIN:
        return dataset
    
    # Project Admin can only access their own datasets
    if dataset.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this dataset"
        )
    
    return dataset


def check_project_ownership(
    project_id: int,
    user: User,
    db: Session
) -> Project:
    """
    Validate that user owns the project or is an admin.
    
    Args:
        project_id: Project ID to check
        user: Current user
        db: Database session
        
    Returns:
        Project object if authorized
        
    Raises:
        HTTPException: 404 if project not found, 403 if not authorized
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Admin can access all projects
    if user.role == UserRole.ADMIN:
        return project
    
    # System projects are accessible to all Project Admins (for base models)
    if project.is_system and user.role == UserRole.PROJECT_ADMIN:
        return project
    
    # Project Admin can only access their own projects
    if project.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this project"
        )
    
    return project


def check_detection_ownership(
    detection_job_id: int,
    user: User,
    db: Session
) -> DetectionJob:
    """
    Validate that user owns the detection job or is an admin.
    
    Args:
        detection_job_id: DetectionJob ID to check
        user: Current user
        db: Database session
        
    Returns:
        DetectionJob object if authorized
        
    Raises:
        HTTPException: 404 if detection job not found, 403 if not authorized
    """
    job = db.query(DetectionJob).filter(DetectionJob.id == detection_job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection job not found"
        )
    
    # Admin can access all detection jobs
    if user.role == UserRole.ADMIN:
        return job
    
    # User can only access their own detection jobs
    if job.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this detection job"
        )
    
    return job


def check_catalog_ownership(
    catalog: RecognitionCatalog,
    user: User
) -> None:
    """
    Validate that user owns the catalog or is an admin.
    
    Args:
        catalog: RecognitionCatalog object to check
        user: Current user
        
    Raises:
        HTTPException: 403 if not authorized
    """
    # Admin can access all catalogs
    if user.role == UserRole.ADMIN:
        return
    
    # User can only access their own catalogs
    if catalog.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this recognition catalog"
        )


# ============================================================================
# Team Access Validators
# ============================================================================

def check_project_team_access(
    project_id: int,
    user: User,
    db: Session
) -> Project:
    """
    Validate that user has access to the project (owner, team member, or admin).
    
    Args:
        project_id: Project ID to check
        user: Current user
        db: Database session
        
    Returns:
        Project object if authorized
        
    Raises:
        HTTPException: 404 if project not found, 403 if not authorized
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Admin can access all projects
    if user.role == UserRole.ADMIN:
        return project
    
    # Project owner has access
    if project.creator_id == user.id:
        return project
    
    # Check if user is a team member
    is_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id
    ).first()
    
    if is_member:
        return project
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this project"
    )


# ============================================================================
# Query Helpers
# ============================================================================

def get_user_accessible_project_ids(user: User, db: Session) -> List[int]:
    """
    Get list of project IDs that user can access based on ownership and team membership.
    
    For ADMIN: Returns all project IDs
    For PROJECT_ADMIN: Returns owned project IDs
    For OPERATOR: Returns project IDs where user is a team member
    
    Args:
        user: Current user
        db: Database session
        
    Returns:
        List of project IDs user can access
    """
    if user.role == UserRole.ADMIN:
        # Admin can access all projects
        project_ids = db.query(Project.id).all()
        return [p[0] for p in project_ids]
    
    elif user.role == UserRole.PROJECT_ADMIN:
        # Project Admin can access their own projects
        project_ids = db.query(Project.id).filter(
            Project.creator_id == user.id
        ).all()
        return [p[0] for p in project_ids]
    
    else:  # OPERATOR
        # Operator can access projects where they are team members
        project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == user.id
        ).all()
        return [p[0] for p in project_ids]


def filter_query_by_ownership(query, model_class, user: User):
    """
    Apply ownership filter to a SQLAlchemy query based on user role.
    
    For ADMIN: No filter (see all)
    For PROJECT_ADMIN: Filter by creator_id
    For OPERATOR: Should not be used (operators don't have ownership access)
    
    Args:
        query: SQLAlchemy query object
        model_class: Model class (Dataset, Project, etc.)
        user: Current user
        
    Returns:
        Filtered query
    """
    if user.role == UserRole.ADMIN:
        # Admin sees all
        return query
    
    elif user.role == UserRole.PROJECT_ADMIN:
        # Project Admin sees only their own
        return query.filter(model_class.creator_id == user.id)
    
    else:
        # Operators should not use this function
        # They access resources through team membership
        raise ValueError("Operators should not filter by ownership directly")


# ============================================================================
# Campaign Validators
# ============================================================================

def validate_campaign_active(
    campaign_id: int,
    db: Session
) -> None:
    """
    Validate that campaign exists and is in ACTIVE status.
    
    Args:
        campaign_id: Campaign ID to validate
        db: Database session
        
    Raises:
        HTTPException: 404 if campaign not found, 400 if campaign is ENDED
    """
    from app.models.campaign import Campaign, CampaignStatus
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status == CampaignStatus.ENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add detections to an ended campaign"
        )


def check_campaign_access(
    campaign_id: int,
    user: User,
    db: Session
):
    """
    Validate that user has access to the campaign (via playbook team access).
    
    Args:
        campaign_id: Campaign ID to check
        user: Current user
        db: Database session
        
    Returns:
        Campaign object if authorized
    
    Raises:
        HTTPException: 404 if campaign not found, 403 if not authorized
    """
    from app.models.campaign import Campaign
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Check playbook access (campaigns inherit playbook team access)
    check_playbook_team_access(campaign.playbook_id, user, db)
    
    return campaign


# ============================================================================
# Playbook Validators
# ============================================================================

def check_playbook_ownership(
    playbook_id: int,
    user: User,
    db: Session
):
    """
    Validate that user owns the playbook or is admin.
    
    Args:
        playbook_id: Playbook ID to check
        user: Current user
        db: Database session
        
    Returns:
        Playbook object if authorized
        
    Raises:
        HTTPException: 404 if playbook not found, 403 if not authorized
    """
    from app.models.playbook import Playbook
    
    playbook = db.query(Playbook).filter(Playbook.id == playbook_id).first()
    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )
    
    # Super admin or admin can access all playbooks
    if user.role in [UserRole.ADMIN, UserRole.ADMIN]:
        return playbook
    
    # Creator can access own playbook
    if playbook.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this playbook"
        )
    
    return playbook


def check_playbook_team_access(
    playbook_id: int,
    user: User,
    db: Session
):
    """
    Validate that user has access to the playbook (owner, team member, or admin).
    
    Args:
        playbook_id: Playbook ID to check
        user: Current user
        db: Database session
        
    Returns:
        Playbook object if authorized
        
    Raises:
        HTTPException: 404 if playbook not found, 403 if not authorized
    """
    from app.models.playbook import Playbook, PlaybookMember
    
    playbook = db.query(Playbook).filter(Playbook.id == playbook_id).first()
    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )
    
    # Super admin or admin can access all playbooks
    if user.role in [UserRole.ADMIN, UserRole.ADMIN]:
        return playbook
    
    # Creator can access own playbook
    if playbook.creator_id == user.id:
        return playbook
    
    # Check if user is a team member
    is_member = db.query(PlaybookMember).filter(
        PlaybookMember.playbook_id == playbook_id,
        PlaybookMember.user_id == user.id
    ).first()
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this playbook"
        )
    
    return playbook


def get_user_accessible_playbook_ids(user: User, db: Session) -> List[int]:
    """
    Get list of playbook IDs accessible to the user.
    
    Args:
        user: Current user
        db: Database session
        
    Returns:
        List of playbook IDs the user can access
    """
    from app.models.playbook import Playbook, PlaybookMember
    
    # Super admin and admin can access all playbooks
    if user.role in [UserRole.ADMIN, UserRole.ADMIN]:
        return [p.id for p in db.query(Playbook.id).all()]
    
    # Get playbooks where user is creator or team member
    owned_ids = [p.id for p in db.query(Playbook.id).filter(Playbook.creator_id == user.id).all()]
    member_ids = [pm.playbook_id for pm in db.query(PlaybookMember.playbook_id).filter(PlaybookMember.user_id == user.id).all()]
    
    return list(set(owned_ids + member_ids))


