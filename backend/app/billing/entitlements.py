"""What an organization's plan allows, what it uses, and the checks that enforce it.

Enforced limits:

* ``root_domains``: distinct root domains the org monitors: domains it has
  scanned, domain/wildcard scopes it has registered, and domains it ran an
  ad-hoc Scanner v2 scan on in the last 30 days. Adding a new root domain (a
  scan, a schedule or a scope) is refused once the allowance is used. When an
  org has more root domains than its plan allows (after a downgrade or an
  expired term), the oldest ones up to the allowance keep working and the
  rest are paused until the org upgrades or removes some.
* ``hosts``: distinct hostnames discovered across the org's scans. Over the
  allowance, no new root domains can be added (existing ones keep scanning).
* ``scans_per_month``: scans created since the first of the month (UTC),
  including ad-hoc Scanner v2 scans. Scheduled runs count but are never
  stopped by the quota (monitoring must not silently stop).
* ``users``: active members plus pending invitations.

Scheduled scans are also held to the plan's scan frequency (weekly or daily),
summed over every schedule on the same root domain.
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


ADHOC_TRIGGER = "adhoc"
ADHOC_ROOT_WINDOW_DAYS = 30
_SCOPE_DOMAIN_TYPES = ("domain", "wildcard")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def root_domain_inventory(db: Session, organization_id: str) -> list[tuple[str, datetime]]:
    """Every root domain the org monitors, oldest first, with when it was first added.

    Sources: scans (any status), domain/wildcard authorized scopes, and ad-hoc
    Scanner v2 scans in the last 30 days. The order decides which domains stay
    active when the org is over its allowance: the oldest ones win.
    """
    from app.models.scan import Scan
    from app.models.scope import AuthorizedScope
    from app.models.v2_scanner import ScanHistory

    first_seen: dict[str, datetime] = {}

    def add(target: str | None, when: datetime | None) -> None:
        root = root_domain(target or "")
        if not root:
            return
        when = _aware(when) or _EPOCH
        if root not in first_seen or when < first_seen[root]:
            first_seen[root] = when

    for domain, when in (
        db.query(Scan.domain, func.min(Scan.created_at))
        .filter(Scan.organization_id == organization_id)
        .group_by(Scan.domain)
        .all()
    ):
        add(domain, when)
    for value, when in (
        db.query(AuthorizedScope.value, AuthorizedScope.created_at)
        .filter(
            AuthorizedScope.organization_id == organization_id,
            AuthorizedScope.scope_type.in_(_SCOPE_DOMAIN_TYPES),
        )
        .all()
    ):
        add(value, when)
    since = _utcnow() - timedelta(days=ADHOC_ROOT_WINDOW_DAYS)
    for domain, when in (
        db.query(ScanHistory.domain, func.min(ScanHistory.created_at))
        .filter(
            ScanHistory.organization_id == organization_id,
            ScanHistory.triggered_by == ADHOC_TRIGGER,
            ScanHistory.created_at >= since,
        )
        .group_by(ScanHistory.domain)
        .all()
    ):
        add(domain, when)
    return sorted(first_seen.items(), key=lambda item: (item[1], item[0]))


def monitored_root_domains(db: Session, organization_id: str) -> set[str]:
    return {root for root, _ in root_domain_inventory(db, organization_id)}


def root_domain_status(db: Session, organization_id: str, limit: int | None) -> list[dict]:
    """Root domains with whether each one is inside the plan allowance."""
    return [
        {
            "domain": root,
            "first_seen": None if when == _EPOCH else when,
            "active": limit is None or index < limit,
        }
        for index, (root, when) in enumerate(root_domain_inventory(db, organization_id))
    ]


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
    """Scans created this month, plus ad-hoc Scanner v2 scans (which have no Scan row)."""
    from app.models.scan import Scan
    from app.models.v2_scanner import ScanHistory

    start = _month_start()
    scans = (
        db.query(func.count(Scan.id))
        .filter(Scan.organization_id == organization_id, Scan.created_at >= start)
        .scalar()
        or 0
    )
    adhoc = (
        db.query(func.count(ScanHistory.id))
        .filter(
            ScanHistory.organization_id == organization_id,
            ScanHistory.triggered_by == ADHOC_TRIGGER,
            ScanHistory.created_at >= start,
        )
        .scalar()
        or 0
    )
    return scans + adhoc


def record_adhoc_scan(db: Session, organization_id: str | None, user_id: str | None,
                      domain: str, scan_type: str) -> None:
    """Log an ad-hoc Scanner v2 scan so it counts toward the plan (no Scan row is made)."""
    if not organization_id:
        return
    import uuid

    from app.models.v2_scanner import ScanHistory

    now = _utcnow()
    db.add(ScanHistory(
        id=str(uuid.uuid4()),
        domain=domain,
        scan_type=(scan_type or "full")[:20],
        scan_engine="v2",
        status="started",
        triggered_by=ADHOC_TRIGGER,
        user_id=user_id,
        organization_id=organization_id,
        started_at=now,
        created_at=now,
    ))
    db.commit()


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


def _upgrade_hint(ent: Entitlement) -> str:
    if ent.plan.id in ("free",):
        return "Choose a plan to add more."
    return "Upgrade your plan or add extra root domains on the Billing page."


def check_root_domain_allowed(
    db: Session,
    organization_id: str | None,
    target: str,
    *,
    allow_paused: bool = False,
    ent: Entitlement | None = None,
) -> None:
    """Raise PlanLimitExceeded if ``target``'s root domain cannot be used now.

    A new root domain needs a free slot. A root domain the org already has but
    that sits beyond the allowance (after a downgrade) is paused, unless
    ``allow_paused`` (used when adding a scope for it, which costs nothing).
    """
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return
    ent = ent or get_entitlement(db, organization_id)
    limit = ent.limits["root_domains"]
    if limit is None:
        return
    root = root_domain(target)
    inventory = [r for r, _ in root_domain_inventory(db, organization_id)]
    if root in inventory:
        if allow_paused or inventory.index(root) < limit:
            return
        raise PlanLimitExceeded(
            "root_domains", limit, len(inventory), ent.plan,
            f"{root} is paused: your organization has {len(inventory)} root domains and the "
            f"{ent.plan.name} plan covers {limit}. The {limit} oldest keep working. "
            "Upgrade, buy extra root domains, or remove domains you no longer need.",
        )
    if len(inventory) >= limit:
        raise PlanLimitExceeded(
            "root_domains", limit, len(inventory), ent.plan,
            f"Your {ent.plan.name} plan covers {limit} root domain{'s' if limit != 1 else ''} "
            f"and {'all are' if limit != 1 else 'it is'} in use, so {root} cannot be added. "
            + _upgrade_hint(ent),
        )


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
    check_root_domain_allowed(db, organization_id, domain, ent=ent)
    if root not in domains:
        hosts = count_hosts(db, organization_id)
        if _over(limits["hosts"], hosts):
            raise PlanLimitExceeded(
                "hosts", limits["hosts"], hosts, ent.plan,
                f"Your organization already monitors {hosts:,} hosts, the "
                f"{ent.plan.name} plan allowance is {limits['hosts']:,}. "
                "Upgrade to add new root domains.",
            )

    if counts_toward_quota:
        scans = count_scans_this_month(db, organization_id)
        if _over(limits["scans_per_month"], scans):
            raise PlanLimitExceeded(
                "scans_per_month", limits["scans_per_month"], scans, ent.plan,
                f"You have used all {limits['scans_per_month']:,} scans in your "
                f"{ent.plan.name} plan this month. The count resets on the 1st (UTC). "
                "Upgrade for a higher monthly allowance.",
            )


def _schedules_per_hour(db: Session, organization_id: str, root: str, exclude_id: str | None) -> float:
    """How many scheduled runs per hour the org already has on ``root``."""
    from app.models.v2_scanner import MonitorSchedule

    rate = 0.0
    rows = (
        db.query(MonitorSchedule.id, MonitorSchedule.domain, MonitorSchedule.interval_hours)
        .filter(MonitorSchedule.organization_id == organization_id, MonitorSchedule.enabled.is_(True))
        .all()
    )
    for sched_id, domain, hours in rows:
        if sched_id != exclude_id and root_domain(domain) == root:
            rate += 1.0 / max(1, int(hours or 24))
    return rate


def check_schedule_allowed(
    db: Session,
    organization_id: str | None,
    domain: str,
    interval_hours: int,
    *,
    exclude_schedule_id: str | None = None,
) -> None:
    """Scheduled scans: root-domain allowance plus the plan's scan frequency.

    The frequency is checked across every enabled schedule on the same root
    domain, so several weekly schedules cannot add up to a daily one.
    """
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return
    check_scan_allowed(db, organization_id, domain, counts_toward_quota=False)
    ent = get_entitlement(db, organization_id)
    min_hours = FREQUENCY_MIN_HOURS.get(ent.plan.scan_frequency, 24)
    label = "weekly" if min_hours >= 168 else "daily"
    if interval_hours < min_hours:
        raise PlanLimitExceeded(
            "scan_frequency", min_hours, interval_hours, ent.plan,
            f"The {ent.plan.name} plan runs scheduled scans {label} at most (every "
            f"{min_hours} hours). Pick a longer interval or upgrade for more frequent scans.",
        )
    root = root_domain(domain)
    existing = _schedules_per_hour(db, organization_id, root, exclude_schedule_id)
    # Small tolerance so e.g. two schedules of exactly 2x the minimum fit.
    if existing + 1.0 / max(1, interval_hours) > 1.0 / min_hours + 1e-9:
        raise PlanLimitExceeded(
            "scan_frequency", min_hours, interval_hours, ent.plan,
            f"{root} already has a schedule that uses the {ent.plan.name} plan's "
            f"{label} scan allowance. Edit or remove that schedule, or upgrade for more "
            "frequent scans.",
        )


def scheduled_run_blocker(db: Session, organization_id: str | None, domain: str,
                          interval_hours: int) -> str | None:
    """Why a due schedule should not run now (plan-wise), or None.

    Used by the scheduler so a downgrade or an expired term takes effect on
    existing schedules too. The monthly scan quota is deliberately not applied.
    """
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return None
    try:
        check_root_domain_allowed(db, organization_id, domain)
    except PlanLimitExceeded as exc:
        return exc.message
    return None


def schedule_min_hours(db: Session, organization_id: str | None) -> int:
    """Shortest interval the org's plan allows between scheduled runs."""
    if not settings.BILLING_ENFORCE_LIMITS or not organization_id:
        return 1
    ent = get_entitlement(db, organization_id)
    return FREQUENCY_MIN_HOURS.get(ent.plan.scan_frequency, 24)


def plan_change_conflicts(db: Session, organization_id: str, new_limits: dict[str, int | None]) -> list[dict]:
    """Allowances the org already uses more of than ``new_limits`` would give."""
    used = usage(db, organization_id)
    out = []
    for key in ("root_domains", "users", "hosts"):
        limit = new_limits.get(key)
        if limit is not None and used[key] > limit:
            out.append({"metric": key, "used": used[key], "limit": limit})
    return out


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
