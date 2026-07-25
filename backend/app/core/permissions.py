"""Role-Based Access Control (RBAC) system.

Expanded from 3 roles to 6 system roles + custom roles.
Enforces authorization on all API endpoints.
"""

from enum import Enum
from typing import List, Callable, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.user import User
from app.models.role import Role


class Permission(str, Enum):
    # Scans
    CREATE_SCAN = "create_scan"
    VIEW_SCAN = "view_scan"
    DELETE_SCAN = "delete_scan"
    RERUN_SCAN = "rerun_scan"

    # Assets
    VIEW_ASSETS = "view_assets"
    MANAGE_ASSETS = "manage_assets"

    # Reports
    GENERATE_REPORT = "generate_report"
    EXPORT_REPORTS = "export_reports"

    # Organization
    MANAGE_ORG = "manage_org"
    VIEW_ORG = "view_org"

    # Members
    MANAGE_MEMBERS = "manage_members"
    INVITE_USERS = "invite_users"
    REMOVE_USERS = "remove_users"
    MANAGE_ROLES = "manage_roles"

    # API Keys
    MANAGE_API_KEYS = "manage_api_keys"

    # AI
    CONFIGURE_AI = "configure_ai"
    VIEW_AI = "view_ai"
    USE_AI = "use_ai"

    # Security
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SECURITY = "manage_security"

    # Settings
    MANAGE_SETTINGS = "manage_settings"
    VIEW_SETTINGS = "view_settings"

    # Scopes
    MANAGE_SCOPES = "manage_scopes"

    # Webhooks
    MANAGE_WEBHOOKS = "manage_webhooks"


# System role definitions (owner is not user-assignable, only transferable)
SYSTEM_ROLES = {
    "owner": {
        "name": "Owner",
        "description": "Full platform access. Organization owner.",
        "permissions": [p.value for p in Permission],
        "is_default": False,
    },
    "admin": {
        "name": "Administrator",
        "description": "Full access except org deletion.",
        "permissions": [
            Permission.CREATE_SCAN.value,
            Permission.VIEW_SCAN.value,
            Permission.DELETE_SCAN.value,
            Permission.RERUN_SCAN.value,
            Permission.VIEW_ASSETS.value,
            Permission.MANAGE_ASSETS.value,
            Permission.GENERATE_REPORT.value,
            Permission.EXPORT_REPORTS.value,
            Permission.MANAGE_ORG.value,
            Permission.VIEW_ORG.value,
            Permission.MANAGE_MEMBERS.value,
            Permission.INVITE_USERS.value,
            Permission.REMOVE_USERS.value,
            Permission.MANAGE_ROLES.value,
            Permission.MANAGE_API_KEYS.value,
            Permission.VIEW_AI.value,
            Permission.USE_AI.value,
            Permission.CONFIGURE_AI.value,
            Permission.VIEW_AUDIT_LOGS.value,
            Permission.MANAGE_SECURITY.value,
            Permission.MANAGE_SETTINGS.value,
            Permission.VIEW_SETTINGS.value,
            Permission.MANAGE_SCOPES.value,
            Permission.MANAGE_WEBHOOKS.value,
        ],
        "is_default": False,
    },
    "security_manager": {
        "name": "Security Manager",
        "description": "Can manage scans, reports, AI, and security settings.",
        "permissions": [
            Permission.CREATE_SCAN.value,
            Permission.VIEW_SCAN.value,
            Permission.DELETE_SCAN.value,
            Permission.RERUN_SCAN.value,
            Permission.VIEW_ASSETS.value,
            Permission.MANAGE_ASSETS.value,
            Permission.GENERATE_REPORT.value,
            Permission.EXPORT_REPORTS.value,
            Permission.VIEW_ORG.value,
            Permission.VIEW_AI.value,
            Permission.USE_AI.value,
            Permission.CONFIGURE_AI.value,
            Permission.VIEW_AUDIT_LOGS.value,
            Permission.MANAGE_SECURITY.value,
            Permission.MANAGE_SCOPES.value,
            Permission.VIEW_SETTINGS.value,
        ],
        "is_default": False,
    },
    "analyst": {
        "name": "Analyst",
        "description": "Can create scans, view assets, and generate reports.",
        "permissions": [
            Permission.CREATE_SCAN.value,
            Permission.VIEW_SCAN.value,
            Permission.RERUN_SCAN.value,
            Permission.VIEW_ASSETS.value,
            Permission.GENERATE_REPORT.value,
            Permission.EXPORT_REPORTS.value,
            Permission.VIEW_ORG.value,
            Permission.VIEW_AI.value,
            Permission.USE_AI.value,
            Permission.VIEW_SETTINGS.value,
        ],
        "is_default": False,
    },
    "member": {
        "name": "Member",
        "description": "Standard team member with view and basic AI access.",
        "permissions": [
            Permission.VIEW_SCAN.value,
            Permission.VIEW_ASSETS.value,
            Permission.VIEW_ORG.value,
            Permission.VIEW_AI.value,
            Permission.USE_AI.value,
            Permission.VIEW_SETTINGS.value,
        ],
        "is_default": True,
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to all platform data.",
        "permissions": [
            Permission.VIEW_SCAN.value,
            Permission.VIEW_ASSETS.value,
            Permission.VIEW_ORG.value,
            Permission.VIEW_AI.value,
            Permission.VIEW_SETTINGS.value,
        ],
        "is_default": False,
    },
}


def check_permission(user_role: str, required_permission: Permission) -> bool:
    """Check if a system role has the required permission."""
    role_perms = SYSTEM_ROLES.get(user_role, {})
    perms = role_perms.get("permissions", [])
    return required_permission.value in perms


def check_custom_permission(
    user_role: str,
    required_permission: Permission,
    db: Session,
    organization_id: Optional[str] = None,
) -> bool:
    """Check permission against custom role if user has one, otherwise system role."""
    if organization_id:
        role = db.query(Role).filter(
            Role.slug == user_role,
            Role.organization_id == organization_id,
            not Role.is_system,
        ).first()

        if role:
            return required_permission.value in (role.permissions or [])

    return check_permission(user_role, required_permission)


def require_permission(permission: Permission) -> Callable:
    """Dependency factory to require a specific permission."""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(_get_db),
    ):
        if not check_custom_permission(
            current_user.role,
            permission,
            db,
            current_user.organization_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
        return current_user
    return permission_checker


def require_any_permission(*permissions: Permission) -> Callable:
    """Dependency factory to require any one of the specified permissions."""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(_get_db),
    ):
        for perm in permissions:
            if check_custom_permission(
                current_user.role,
                perm,
                db,
                current_user.organization_id,
            ):
                return current_user

        perm_names = [p.value for p in permissions]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: one of {perm_names} required",
        )
    return permission_checker


def require_role(*roles: str) -> Callable:
    """Dependency factory to require one of the specified roles."""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: one of {list(roles)} required",
            )
        return current_user
    return role_checker


def get_user_permissions(user_role: str, db: Session, organization_id: Optional[str] = None) -> List[str]:
    """Get all permissions for a user role."""
    if organization_id:
        role = db.query(Role).filter(
            Role.slug == user_role,
            Role.organization_id == organization_id,
            not Role.is_system,
        ).first()

        if role:
            return role.permissions or []

    return SYSTEM_ROLES.get(user_role, {}).get("permissions", [])


def list_system_roles():
    """List all system roles with their details."""
    return [
        {
            "slug": slug,
            "name": info["name"],
            "description": info["description"],
            "permissions": info["permissions"],
            "is_system": True,
            "is_default": info["is_default"],
        }
        for slug, info in SYSTEM_ROLES.items()
    ]


def _get_db():
    """Get database session (imported to avoid circular imports)."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
