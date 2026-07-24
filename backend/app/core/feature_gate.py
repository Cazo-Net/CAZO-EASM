"""Feature gating and usage enforcement middleware.

Provides FastAPI dependencies that check subscription plan entitlements
and usage limits before allowing access to protected endpoints.
"""

from typing import Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.services.subscription_service import SubscriptionService
from app.services.usage_service import UsageService


def require_feature(feature: str) -> Callable:
    """Dependency factory that checks if the organization's plan includes a feature.

    Usage:
        @router.get("/reports", dependencies=[Depends(require_feature("basic_reports"))])
        async def list_reports(...):
            ...
    """
    async def feature_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization required for this feature",
            )

        sub_service = SubscriptionService(db)

        if not sub_service.is_feature_enabled_for_org(
            current_user.organization_id, feature
        ):
            plan = sub_service.get_current_plan(current_user.organization_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' is not available on the '{plan}' plan. Please upgrade.",
                headers={"X-Required-Feature": feature, "X-Current-Plan": plan},
            )

        return current_user

    return feature_checker


def require_usage(metric: str, quantity: int = 1) -> Callable:
    """Dependency factory that checks if the organization has remaining capacity.

    Usage:
        @router.post("/scans", dependencies=[Depends(require_usage("scans"))])
        async def create_scan(...):
            ...

        @router.post("/scans", dependencies=[Depends(require_usage("scans", 1))])
        async def create_scan(...):
            ...
    """
    async def usage_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization required",
            )

        sub_service = SubscriptionService(db)
        result = sub_service.check_usage_limit_for_org(
            current_user.organization_id, metric
        )

        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": f"Usage limit exceeded for '{metric}'",
                    "current": result["current"],
                    "limit": result["limit"],
                    "plan": sub_service.get_current_plan(current_user.organization_id),
                },
                headers={
                    "X-RateLimit-Limit": str(result["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Used": str(result["current"]),
                },
            )

        if result["limit"] > 0 and result["remaining"] <= result["limit"] * 0.1:
            pass  # Near limit — headers will be set by caller if needed

        return current_user

    return usage_checker


def require_plan(*plans: str) -> Callable:
    """Dependency factory that checks if the org is on one of the specified plans.

    Usage:
        @router.get("/advanced-scan", dependencies=[Depends(require_plan("professional", "enterprise"))])
        async def advanced_scan(...):
            ...
    """
    async def plan_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization required",
            )

        sub_service = SubscriptionService(db)
        current_plan = sub_service.get_current_plan(current_user.organization_id)

        if current_plan not in plans:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires one of the following plans: {', '.join(plans)}",
            )

        return current_user

    return plan_checker


def record_usage_on_success(metric: str, quantity: int = 1) -> Callable:
    """Dependency that records usage AFTER a successful endpoint call.

    This is used as a post-execution hook. The actual recording happens
    in the endpoint's post-response logic. For simpler usage, call
    UsageService.record_usage() directly in your endpoint.

    Usage:
        @router.post("/scans")
        async def create_scan(
            ...,
            db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user),
        ):
            # ... create scan ...
            record_usage(db, current_user.organization_id, "scans", 1)
            return scan
    """
    def record(db: Session, org_id: str, qty: int = quantity):
        usage_service = UsageService(db)
        usage_service.record_usage(org_id, metric, qty)

    return record


def get_usage_headers(
    db: Session,
    org_id: str,
    metric: str,
) -> dict:
    """Get rate-limit-style headers for usage information.

    Returns headers like X-RateLimit-Limit, X-RateLimit-Remaining, etc.
    """
    sub_service = SubscriptionService(db)
    result = sub_service.check_usage_limit_for_org(org_id, metric)

    headers = {}
    if result["limit"] > 0:
        headers["X-RateLimit-Limit"] = str(result["limit"])
        headers["X-RateLimit-Remaining"] = str(result["remaining"])
        headers["X-RateLimit-Used"] = str(result["current"])

    return headers


def get_org_from_user(user: User, db: Session) -> Organization:
    """Get the organization from a user. Raises 404 if not found."""
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with an organization",
        )

    org = db.query(Organization).filter(
        Organization.id == user.organization_id
    ).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return org


def require_active_subscription() -> Callable:
    """Dependency that checks if the organization has an active (non-suspended) subscription."""
    async def subscription_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        org = get_org_from_user(current_user, db)

        if not org.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization account is suspended. Please contact support.",
            )

        return current_user

    return subscription_checker
