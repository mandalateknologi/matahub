"""
Projects API Router
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.dataset import Dataset
from app.models.model import Model
from app.models.training_job import TrainingJob
from app.models.project_member import ProjectMember
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectDetail
from app.schemas.user import ProjectMemberResponse, ProjectMemberAdd
from app.utils.permissions import (
    require_project_admin_or_admin,
    check_project_ownership,
    check_project_team_access
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectDetail])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    dataset_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get list of projects.
    PROJECT_ADMIN sees their own projects + system projects (for base models).
    ADMIN sees all projects.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        dataset_id: Optional dataset ID to filter projects
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        List of projects with models
    """
    query = db.query(Project)
    
    # Apply ownership filter (includes system projects for PROJECT_ADMIN)
    if current_user.role == UserRole.PROJECT_ADMIN:
        # PROJECT_ADMIN sees own projects OR system projects
        query = query.filter(
            (Project.creator_id == current_user.id) | (Project.is_system == True)
        )
    # ADMIN sees all projects (no filter needed)
    
    # Filter by dataset_id if provided
    if dataset_id is not None:
        query = query.filter(Project.dataset_id == dataset_id)
    
    projects = query.offset(skip).limit(limit).all()
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Create a new project.
    Requires PROJECT_ADMIN or ADMIN role.
    
    Args:
        project_data: Project creation data
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Created project
    """
    # Prevent users from creating system projects
    if project_data.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create system projects through API"
        )
    
    # Verify dataset exists if provided
    if project_data.dataset_id is not None:
        dataset = db.query(Dataset).filter(Dataset.id == project_data.dataset_id).first()
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
    
    # Create new project with creator
    new_project = Project(
        name=project_data.name,
        dataset_id=project_data.dataset_id,
        task_type=project_data.task_type,
        creator_id=current_user.id,
        is_system=False  # Always False for user-created projects
    )
    
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return new_project


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get detailed information about a specific project.
    Validates ownership or system project access (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        project_id: Project ID
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Project details with related dataset and models
    """
    project = check_project_ownership(project_id, current_user, db)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    confirmed: bool = Query(False, description="Confirm cascade deletion of related records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Delete a project.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        project_id: Project ID
        confirmed: Whether user confirmed cascade deletion
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
    """
    project = check_project_ownership(project_id, current_user, db)
    
    # Protect system projects from deletion
    if project.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System projects cannot be deleted"
        )
    
    # Check for related records and require confirmation
    if not confirmed:
        models_count = db.query(Model).filter(Model.project_id == project_id).count()
        jobs_count = db.query(TrainingJob).filter(TrainingJob.project_id == project_id).count()
        
        if models_count > 0 or jobs_count > 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": f"Project has {models_count} model(s) and {jobs_count} training job(s). Confirm to delete all.",
                    "models_count": models_count,
                    "jobs_count": jobs_count,
                    "requires_confirmation": True
                }
            )
    
    # Proceed with deletion (CASCADE will handle related records)
    db.delete(project)
    db.commit()


# ============================================================================
# Team Member Management Endpoints
# ============================================================================

@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
async def get_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get list of team members for a project.
    Accessible by project owner, team members, or admins.
    
    Args:
        project_id: Project ID
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        List of project members with user details
    """
    # Validate team access (owner, member, or admin)
    project = check_project_team_access(project_id, current_user, db)
    
    # Get all team members with user details
    members = db.query(
        ProjectMember.user_id,
        User.email,
        User.role,
        ProjectMember.added_at,
        ProjectMember.added_by
    ).join(
        User, ProjectMember.user_id == User.id
    ).filter(
        ProjectMember.project_id == project_id
    ).all()
    
    return [
        ProjectMemberResponse(
            user_id=m.user_id,
            email=m.email,
            role=m.role,
            added_at=m.added_at,
            added_by=m.added_by
        )
        for m in members
    ]


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: int,
    member_data: ProjectMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Add an operator to the project team.
    Only project owner or admin can add members.
    
    Args:
        project_id: Project ID
        member_data: Member addition data (user_id)
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Success message
    """
    # Validate project ownership
    project = check_project_ownership(project_id, current_user, db)
    
    # Verify target user exists and is an OPERATOR
    target_user = db.query(User).filter(User.id == member_data.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if target_user.role != UserRole.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only operators can be added to project teams"
        )
    
    # Check if already a member
    existing_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_data.user_id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a team member"
        )
    
    # Add member
    new_member = ProjectMember(
        project_id=project_id,
        user_id=member_data.user_id,
        added_by=current_user.id
    )
    db.add(new_member)
    db.commit()
    
    return {"message": "Team member added successfully", "user_id": member_data.user_id}


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Remove a member from the project team.
    Only project owner or admin can remove members.
    
    Args:
        project_id: Project ID
        user_id: User ID to remove
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
    """
    # Validate project ownership
    project = check_project_ownership(project_id, current_user, db)
    
    # Find and delete membership
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found"
        )
    
    db.delete(member)
    db.commit()
