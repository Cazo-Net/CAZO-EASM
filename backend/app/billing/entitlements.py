"""What an organization's plan allows, what it uses, and the checks that enforce it.

Enforced limits:

* ``root_domains``: distinct root domains the org has scanned. Scanning a new
  root domain is refused once the allowance is used. Re-scanning a domain the
  org already monitors is always allowed.
* ``hosts``: distinct hostnames discovered across the org's scans. Over the
  allowance, no new root domains can be added (existing ones keep scanning).
* ``scans_per_month``: scans created since the first of the month (UTC).
* ``users``: active members plus pending invitations.

Scheduled scans are also held to the plan's scan frequency (weekly or daily).
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing.plans import (
    FREE_PLAN_ID,
    FREQUENCY_MIN_HOURS,
    Plan,
    get_plan,
    plan_limits,
)
from app.config import settings

# Second-level labels under which a registrable domain has three labels
# (example.com.my, example.co.uk). Kept short on purpose; extend as markets open.
_MULTI_LABEL_SUFFIXES = {
    "com.my", "net.my", "org.my", "edu.my", "gov.my", "name.my", "biz.my", "mil.my",
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "com.sg", "edu.sg", "gov.sg", "org.sg", "net.sg",
    "co.id", "or.id", "ac.id", "go.id", "web.id",
    "com.ph", "gov.ph", "edu.ph",
    "co.th", "ac.th", "go.th", "in.th", "or.th",
    "com.vn", "gov.vn", "edu.vn",
    "co.nz", "org.nz", "govt.nz",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
    "co.in", "net.in", "org.in", "gov.in", "ac.in",
    "com.br", "com.cn", "com.hk", "com.tw", "co.kr", "co.za", "com.mx", "com.tr",
}

ACTIVE_STATUSES = {"active", "trialing", "past_due"}


class PlanLimitExceeded(Exception):
    """Raised when an action would go over the organization's plan.

    Turned into HTTP 402 by the handler registered in app.main.
    """

    def __init__(self, metric: str, limit: int | None, used: int, plan: Plan, message: str):
        super().__init__(message)
        self.metric = metric
        self.limit = limit
        self.used = used
        self.plan = plan
        self.message = message

    def as_detail(self) -> dict:
        return {
            "code": "plan_limit_reached",
            "metric": self.metric,
            "limit": self.limit,
            "used": self.used,
            "plan": self.plan.id,
            "plan_name": self.plan.name,
            "message": self.message,
            "upgrade_url": "/pricing",
        }


def root_domain(target: str) -> str:
    """Registrable root of a hostname or URL (``a.b.example.com.my`` -> ``example.com.my``)."""
    host = (target or "").strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0].split("?", 1)[0]
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    host = host.strip(".").lstrip("*.")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = [label for label in host.split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in _MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


@dataclass
class Entitlement:
    plan: Plan
    status: str
    quantity: int
    extra_domains: int
    limits: dict[str, int | None]
    period_end: datetime | None
    subscription: object | None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def get_subscription(db: Session, organization_id: str):
    from app.models.billing import BillingSubscription

    return (
        db.query(BillingSubscription)
        .filter(BillingSubscription.organization_id == organization_id)
        .first()
    )


def subscription_is_current(sub, now: datetime | None = None) -> bool:
    """True when ``sub`` still grants its plan (including the grace period)."""
    if sub is None or sub.status not in ACTIVE_STATUSES:
        return False
    end = _aware(sub.current_period_end)
    if end is None:
        return True
    now = now or _utcnow()
    return now <= end + timedelta(days=settings.BILLING_GRACE_DAYS)


def get_entitlement(db: Session, organization_id: str | None) -> Entitlement:
    sub = get_subscription(db, organization_id) if organization_id else None
    if subscription_is_current(sub):
        plan = get_plan(sub.plan)
        quantity = sub.quantity or 1
        extra = sub.extra_domains or 0
        status = sub.status
    else:
        plan = get_plan(FREE_PLAN_ID)
        quantity, extra = 1, 0
        status = "expired" if sub is not None and sub.plan != FREE_PLAN_ID else "none"
    return Entitlement(
        plan=plan,
        status=status,
        quantity=quantity,
        extra_domains=extra,
        limits=plan_limits(plan, quantity, extra),
        period_end=_aware(sub.current_period_end) if sub else None,
        subscription=sub,
    )


# ── Usage ────────────────────────────────────────────────────────────────


def _month_start(now: datetime | None = None) -> datetime:
    now = now or _utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monitored_root_domains(db: Session, organization_id: str) -> set[str]:
    from app.models.scan import Scan

    rows = (
        db.query(Scan.domain)
        .filter(Scan.organization_id == organization_id)
        .distinct()
        .all()
    )
    return {root_domain(r[0]) for r in rows if r[0]}


def count_hosts(db: Session, organization_id: str) -> int:
    """Hosts that count toward the plan.

    The deduplicated inventory is the source of truth: every host that has not
    gone missing. Organizations whose inventory has not been built yet fall
    back to distinct hostnames across their scans.
    """
    from app.models.asset import Subdomain
    from app.models.asset_inventory import Asset
    from app.models.scan import Scan

    has_inventory = (
        db.query(Asset.id)
        .filter(Asset.organization_id == organization_id, Asset.asset_type == "domain")
        .first()
    )
    if has_inventory:
        return (
            db.query(func.count(Asset.id))
            .filter(
                Asset.organization_id == organization_id,
                Asset.asset_type == "host",
                Asset.state != "missing",
            )
            .scalar()
            or 0
        )

    return (
        db.query(func.count(func.distinct(Subdomain.hostname)))
        .join(Scan, Subdomain.scan_id == Scan.id)
        .filter(Scan.organization_id == organization_id)
        .scalar()
        or 0
    )


def count_scans_this_month(db: Session, organization_id: str) -> int:
    from app.models.scan import Scan

    return (
        db.query(func.count(Scan.id))
        .filter(Scan.organization_id == organization_id, Scan.created_at >= _month_start())
        .scalar()
        or 0
    )


def count_seats(db: Session, organization_id: str) -> int:
    from app.models.auth_models import Invitation
    from app.models.user import User

    members = (
        db.query(func.count(User.id))
        .filter(User.organization_id == organization_id, User.is_active.is_(True))
        .scalar()
        or 0
    )
    pending = (
        db.query(func.count(Invitation.id))
        .filter(
            Invitation.organization_id == organization_id,
            Invitation.status == "pending",
            Invitation.expires_at > _utcnow(),
        )
        .scalar()
        or 0
    )
    return members + pending


def usage(db: Session, organization_id: str) -> dict[str, int]:
    return {
        "root_domains": len(monitored_root_domains(db, organization_id)),
        "hosts": count_hosts(db, organization_id),
        "users": count_seats(db, organization_id),
        "scans_per_month": count_scans_this_month(db, organization_id),
    }


# ── Checks ───────────────────────────────────────────────────────────────


def _over(limit: int | None, used: int) -> bool:
    return limit is not None and used >= limit


def check_scan_allowed(
    db: Session,
    organization_id: str | None,
    domain: str,
    *,
    counts_toward_quota: bool = True,
) -> None:
    """Raise PlanLimitExceeded if the org may not scan ``domain`` now."""
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return
    ent = get_entitlement(db, organization_id)
    limits = ent.limits
    root = root_domain(domain)

    domains = monitored_root_domains(db, organization_id)
    if root not in domains:
        if _over(limits["root_domains"], len(domains)):
            raise PlanLimitExceeded(
                "root_domains", limits["root_domains"], len(domains), ent.plan,
                f"Your {ent.plan.name} plan covers {limits['root_domains']} root "
                f"domain(s) and all are in use, so {root} cannot be added. "
                "Upgrade or buy extra root domains to monitor it.",
            )
        hosts = count_hosts(db, organization_id)
        if _over(limits["hosts"], hosts):
            raise PlanLimitExceeded(
                "hosts", limits["hosts"], hosts, ent.plan,
                f"Your organization already monitors {hosts} hosts, the "
                f"{ent.plan.name} plan allowance is {limits['hosts']}. "
                "Upgrade to add new root domains.",
            )

    if counts_toward_quota:
        scans = count_scans_this_month(db, organization_id)
        if _over(limits["scans_per_month"], scans):
            raise PlanLimitExceeded(
                "scans_per_month", limits["scans_per_month"], scans, ent.plan,
                f"You have used all {limits['scans_per_month']} scans in your "
                f"{ent.plan.name} plan this month. The count resets on the 1st.",
            )


def check_schedule_allowed(db: Session, organization_id: str | None, domain: str, interval_hours: int) -> None:
    """Scheduled scans: root-domain allowance plus the plan's scan frequency."""
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return
    check_scan_allowed(db, organization_id, domain, counts_toward_quota=False)
    ent = get_entitlement(db, organization_id)
    min_hours = FREQUENCY_MIN_HOURS.get(ent.plan.scan_frequency, 24)
    if interval_hours < min_hours:
        raise PlanLimitExceeded(
            "scan_frequency", min_hours, interval_hours, ent.plan,
            f"The {ent.plan.name} plan schedules scans {ent.plan.scan_frequency} "
            f"at most (every {min_hours} hours). Upgrade for more frequent scans.",
        )


def check_seat_available(db: Session, organization_id: str | None, *, joining: bool = False) -> None:
    """Raise if the org has no free user seat.

    ``joining`` is for accepting an invitation: that invitation already holds a
    seat, so only active members are counted.
    """
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return
    ent = get_entitlement(db, organization_id)
    limit = ent.limits["users"]
    if limit is None:
        return
    if joining:
        from app.models.user import User

        used = (
            db.query(func.count(User.id))
            .filter(User.organization_id == organization_id, User.is_active.is_(True))
            .scalar()
            or 0
        )
    else:
        used = count_seats(db, organization_id)
    if used >= limit:
        raise PlanLimitExceeded(
            "users", limit, used, ent.plan,
            f"Your {ent.plan.name} plan includes {limit} user seat(s) and all are "
            "taken (pending invitations count). Remove a member or upgrade.",
        )
