from enum import Enum
from typing import List, Callable
from fastapi import Depends, HTTPException, status
from app.api.deps import get_current_user
from app.models.user import User


class Permission(str, Enum):
    CREATE_SCAN = "create_scan"
    VIEW_SCAN = "view_scan"
    DELETE_SCAN = "delete_scan"
    GENERATE_REPORT = "generate_report"
    MANAGE_ORG = "manage_org"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_WEBHOOKS = "manage_webhooks"
    VIEW_ASSETS = "view_assets"


ROLE_PERMISSIONS = {
    "admin": [
        Permission.CREATE_SCAN,
        Permission.VIEW_SCAN,
        Permission.DELETE_SCAN,
        Permission.GENERATE_REPORT,
        Permission.MANAGE_ORG,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_WEBHOOKS,
        Permission.VIEW_ASSETS,
    ],
    "member": [
        Permission.CREATE_SCAN,
        Permission.VIEW_SCAN,
        Permission.GENERATE_REPORT,
        Permission.MANAGE_WEBHOOKS,
        Permission.VIEW_ASSETS,
    ],
    "viewer": [
        Permission.VIEW_SCAN,
        Permission.VIEW_ASSETS,
    ],
}


def check_permission(user_role: str, required_permission: Permission) -> bool:
    """Check if a role has the required permission."""
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return required_permission in permissions


def require_permission(permission: Permission) -> Callable:
    """Dependency factory to require a specific permission."""
    async def permission_checker(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required"
            )
        return current_user
    return permission_checker
