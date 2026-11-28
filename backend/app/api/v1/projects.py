from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.api.deps import get_current_user
from app.core.permissions import require_permission, require_any_permission, Permission

router = APIRouter()


def _require_project_access(project: Project, current_user: User) -> None:
    """Raise 403 if user does not have access to the project."""
    if current_user.organization_id and project.organization_id == current_user.organization_id:
        return
    if project.created_by == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this project"
    )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    organization_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List projects, optionally filtered by organization."""
    query = db.query(Project)

    if organization_id:
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization"
            )
        query = query.filter(Project.organization_id == organization_id)
    elif current_user.organization_id:
        query = query.filter(Project.organization_id == current_user.organization_id)
    else:
        query = query.filter(Project.created_by == current_user.id)

    projects = query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN))
):
    """Create a new project."""
    target_org_id = project_data.organization_id or current_user.organization_id

    if target_org_id and current_user.organization_id != target_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create projects in another organization"
        )

    project = Project(
        name=project_data.name,
        description=project_data.description,
        organization_id=target_org_id,
        created_by=current_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project details."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _require_project_access(project, current_user)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN))
):
    """Update a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _require_project_access(project, current_user)

    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ASSETS))
):
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _require_project_access(project, current_user)

    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}
