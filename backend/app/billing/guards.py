"""FastAPI dependencies that apply plan limits to existing routes."""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.billing.entitlements import check_schedule_allowed
from app.database import get_db
from app.models.user import User


async def schedule_plan_guard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Scheduled scans: root-domain allowance and the plan's scan frequency."""
    try:
        body = await request.json()
    except ValueError:
        return  # the route's own validation reports the bad body
    if not isinstance(body, dict):
        return
    domain = body.get("domain")
    try:
        interval_hours = int(body.get("interval_hours", 24))
    except (TypeError, ValueError):
        return
    if isinstance(domain, str) and domain:
        check_schedule_allowed(db, current_user.organization_id, domain, interval_hours)
