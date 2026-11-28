"""Change alerts for the asset inventory: settings and delivery.

``inventory.sync_scan`` decides *what* changed. This module decides *who is
told and how*, from the organization's ``AlertSettings``:

* one notification per alert type per scan (a scan that finds 40 new hosts
  sends one "40 new assets" alert, not 40);
* in-app and email are switched per alert type by the organization, and each
  member can still mute a type for themselves in notification preferences;
* optional extra mailboxes (a SOC inbox, an MSSP client contact) get the email.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.alert_settings import AlertSettings
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_EXTRA_EMAILS = 10
ITEMS_PER_ALERT = 10
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# alert_type -> presentation, defaults and the notification type it maps to.
ALERT_TYPES: Dict[str, Dict[str, Any]] = {
    "new_asset": {
        "label": "New asset discovered",
        "description": "A host that was not in your inventory appeared, or a missing one came back.",
        "notification_type": "inventory_new_asset",
        "defaults": {"in_app": True, "email": True},
        "tone": "warning",
        "noun": ("new asset", "new assets"),
    },
    "new_service": {
        "label": "New open port or service",
        "description": "A port that was closed is now reachable from the internet.",
        "notification_type": "inventory_new_service",
        "defaults": {"in_app": True, "email": True},
        "tone": "warning",
        "noun": ("new open port", "new open ports"),
    },
    "new_critical_finding": {
        "label": "New critical finding",
        "description": "A finding at or above the chosen severity that you have not had before.",
        "notification_type": "inventory_new_finding",
        "defaults": {"in_app": True, "email": True},
        "tone": "danger",
        "noun": ("new finding", "new findings"),
    },
    "certificate_expiring": {
        "label": "Certificate expiring",
        "description": "A certificate is inside the warning window or has expired.",
        "notification_type": "inventory_cert_expiring",
        "defaults": {"in_app": True, "email": True},
        "tone": "warning",
        "noun": ("certificate expiring", "certificates expiring"),
    },
    "certificate_changed": {
        "label": "Certificate changed",
        "description": "A host started serving a different certificate.",
        "notification_type": "inventory_cert_changed",
        "defaults": {"in_app": True, "email": False},
        "tone": "warning",
        "noun": ("certificate replaced", "certificates replaced"),
    },
    "asset_disappeared": {
        "label": "Asset disappeared",
        "description": "A host was not found by two scans in a row.",
        "notification_type": "inventory_asset_missing",
        "defaults": {"in_app": True, "email": False},
        "tone": "warning",
        "noun": ("asset disappeared", "assets disappeared"),
    },
}

FINDING_SEVERITIES = ("critical", "high", "medium")
RECIPIENT_MODES = ("admins", "all")
ADMIN_ROLES = ("owner", "admin")


def default_settings() -> Dict[str, Any]:
    return {
        "enabled": True,
        "rules": {k: dict(v["defaults"]) for k, v in ALERT_TYPES.items()},
        "cert_expiry_days": 30,
        "finding_min_severity": "critical",
        "recipients": "admins",
        "extra_emails": [],
    }


def get_settings(db: Session, organization_id: str) -> Dict[str, Any]:
    """The organization's alert settings merged over the defaults."""
    out = default_settings()
    row = db.query(AlertSettings).filter(AlertSettings.organization_id == organization_id).first()
    if not row:
        return out
    out["enabled"] = bool(row.enabled)
    for key, rule in (row.rules or {}).items():
        if key in out["rules"] and isinstance(rule, dict):
            out["rules"][key] = {
                "in_app": bool(rule.get("in_app", out["rules"][key]["in_app"])),
                "email": bool(rule.get("email", out["rules"][key]["email"])),
            }
    out["cert_expiry_days"] = int(row.cert_expiry_days or 30)
    if row.finding_min_severity in FINDING_SEVERITIES:
        out["finding_min_severity"] = row.finding_min_severity
    if row.recipients in RECIPIENT_MODES:
        out["recipients"] = row.recipients
    out["extra_emails"] = list(row.extra_emails or [])
    return out


def clean_extra_emails(values: List[str]) -> List[str]:
    """Normalize, validate and cap the extra recipient list. Raises ValueError."""
    cleaned: List[str] = []
    for raw in values or []:
        email = str(raw).strip().lower()
        if not email:
            continue
        if len(email) > 254 or not _EMAIL_RE.match(email) or any(c in email for c in "\r\n,;<>\""):
            raise ValueError(f"'{raw}' is not a valid email address")
        if email not in cleaned:
            cleaned.append(email)
    if len(cleaned) > MAX_EXTRA_EMAILS:
        raise ValueError(f"At most {MAX_EXTRA_EMAILS} extra email addresses are allowed")
    return cleaned


def save_settings(db: Session, organization_id: str, payload: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    """Validate and store a (partial) settings update. Raises ValueError."""
    current = get_settings(db, organization_id)
    row = db.query(AlertSettings).filter(AlertSettings.organization_id == organization_id).first()
    if not row:
        row = AlertSettings(organization_id=organization_id)
        db.add(row)

    if payload.get("enabled") is not None:
        current["enabled"] = bool(payload["enabled"])
    for key, rule in (payload.get("rules") or {}).items():
        if key not in ALERT_TYPES:
            raise ValueError(f"Unknown alert type '{key}'")
        if not isinstance(rule, dict):
            raise ValueError(f"Rule for '{key}' must be an object")
        for channel in ("in_app", "email"):
            if rule.get(channel) is not None:
                current["rules"][key][channel] = bool(rule[channel])
    if payload.get("cert_expiry_days") is not None:
        days = int(payload["cert_expiry_days"])
        if not 1 <= days <= 365:
            raise ValueError("Certificate warning window must be between 1 and 365 days")
        current["cert_expiry_days"] = days
    if payload.get("finding_min_severity") is not None:
        if payload["finding_min_severity"] not in FINDING_SEVERITIES:
            raise ValueError("Finding severity must be critical, high or medium")
        current["finding_min_severity"] = payload["finding_min_severity"]
    if payload.get("recipients") is not None:
        if payload["recipients"] not in RECIPIENT_MODES:
            raise ValueError("Recipients must be 'admins' or 'all'")
        current["recipients"] = payload["recipients"]
    if payload.get("extra_emails") is not None:
        current["extra_emails"] = clean_extra_emails(payload["extra_emails"])

    row.enabled = current["enabled"]
    row.rules = current["rules"]
    row.cert_expiry_days = current["cert_expiry_days"]
    row.finding_min_severity = current["finding_min_severity"]
    row.recipients = current["recipients"]
    row.extra_emails = current["extra_emails"]
    row.updated_by = user_id
    db.commit()
    return current


def email_delivery_status() -> Dict[str, Any]:
    """Whether email can actually leave the platform (for the settings page)."""
    from app.config import settings

    provider = (getattr(settings, "EMAIL_PROVIDER", "log") or "log").lower()
    configured = (
        (provider == "resend" and bool(getattr(settings, "RESEND_API_KEY", "")))
        or (provider == "smtp" and bool(getattr(settings, "SMTP_HOST", "")) and settings.SMTP_HOST != "localhost")
    )
    return {"provider": provider, "configured": configured}


def _recipients(db: Session, organization_id: str, mode: str) -> List[User]:
    q = db.query(User).filter(User.organization_id == organization_id, User.is_active == True)  # noqa: E712
    if mode != "all":
        q = q.filter(User.role.in_(ADMIN_ROLES))
    return q.order_by(User.created_at.asc()).all()


def _compose(alert_type: str, items: List[Dict[str, Any]], root: str) -> Dict[str, Any]:
    meta = ALERT_TYPES[alert_type]
    n = len(items)
    singular, plural = meta["noun"]
    where = f" on {root}" if root else ""
    if n == 1:
        title = f"{meta['label']}{where}"
    else:
        title = f"{n} {plural}{where}"
    lines = [i["summary"] for i in items[:ITEMS_PER_ALERT]]
    more = max(0, n - ITEMS_PER_ALERT)
    message = "; ".join(lines[:4]) + (f"; and {n - 4} more" if n > 4 else "")
    intro = f"{n} {singular if n == 1 else plural}{where} since the previous scan."
    return {"title": title[:255], "message": message, "intro": intro, "lines": lines, "more": more}


def dispatch_alerts(db: Session, result, scan=None) -> int:
    """Deliver the alerts a sync produced. Returns notifications created."""
    org_id = result.organization_id
    if not org_id or not (result.alerts or result.hosts_over_limit):
        return 0
    from app.services.notification_service import dispatch_notification

    cfg = get_settings(db, org_id)
    sent = 0

    if result.hosts_over_limit:
        sent += _notify_plan_limit(db, org_id, result)

    if not cfg["enabled"] or not result.alerts:
        return sent

    users = _recipients(db, org_id, cfg["recipients"])
    scan_id = getattr(scan, "id", None)
    for alert_type, items in result.alerts.items():
        meta = ALERT_TYPES.get(alert_type)
        rule = cfg["rules"].get(alert_type)
        if not meta or not rule or not items:
            continue
        text = _compose(alert_type, items, result.root)
        url = f"/inventory?tab=changes&alert={alert_type}"
        data = {
            "alert_type": alert_type, "domain": result.root, "scan_id": scan_id,
            "count": len(items), "items": text["lines"], "more": text["more"],
            "intro": text["intro"], "url": url, "tone": meta["tone"],
            "asset_ids": [i["asset_id"] for i in items[:ITEMS_PER_ALERT] if i.get("asset_id")],
        }
        webhook_pending = True
        for user in users:
            note = dispatch_notification(
                db=db, organization_id=org_id, user_id=user.id,
                notification_type=meta["notification_type"],
                title=text["title"], message=text["message"],
                related_entity_type="scan" if scan_id else "organization",
                related_entity_id=scan_id or org_id,
                data=data,
                skip_dedup=not scan_id,
                allow_in_app=rule["in_app"], allow_email=rule["email"],
                fire_webhooks=webhook_pending,
            )
            webhook_pending = False
            if note is not None:
                sent += 1
        if not users:
            logger.info("No recipients for %s alert in org %s", alert_type, org_id)

        if rule["email"] and cfg["extra_emails"]:
            _email_extra(cfg["extra_emails"], {u.email.lower() for u in users if u.email},
                         meta["notification_type"], text, data)
    return sent


def _email_extra(addresses: List[str], already: set, notification_type: str, text: Dict[str, Any],
                 data: Dict[str, Any]) -> None:
    from app.config import frontend_url
    from app.services.email.sender import get_email_service
    from app.services.notification_service import _build_email_content

    payload = dict(data)
    payload["url"] = frontend_url(data.get("url") or "/inventory")
    subject, html = _build_email_content(
        notification_type=notification_type, title=text["title"], message=text["message"],
        data=payload, user_name="there",
    )
    if not subject:
        return
    service = get_email_service()
    for address in addresses:
        if address in already:
            continue
        try:
            service.send_async(to=address, subject=subject, html_body=html)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not queue inventory alert email: %s", exc)


def _notify_plan_limit(db: Session, org_id: str, result) -> int:
    """Tell admins (in-app, once a day) that new hosts did not fit the plan."""
    from app.services.notification_service import dispatch_notification

    sent = 0
    n = result.hosts_over_limit
    for user in _recipients(db, org_id, "admins"):
        note = dispatch_notification(
            db=db, organization_id=org_id, user_id=user.id,
            notification_type="inventory_plan_limit",
            title="Host limit reached on your plan",
            message=(
                f"{n} newly discovered host(s) on {result.root} were not added to the inventory "
                f"because your plan covers {result.host_limit} hosts. Upgrade to monitor them."
            ),
            related_entity_type="organization", related_entity_id=org_id,
            data={"domain": result.root, "skipped": n, "limit": result.host_limit, "url": "/billing"},
            allow_email=False, fire_webhooks=False,
        )
        if note is not None:
            sent += 1
    return sent


def run_certificate_expiry_check(db: Session) -> int:
    """Daily job: alert on certificates that crossed a warning step between scans."""
    from app.services.inventory import check_certificate_expiry

    sent = 0
    for _org_id, result in check_certificate_expiry(db).items():
        try:
            sent += dispatch_alerts(db, result)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Certificate expiry alerts failed: %s", exc)
    return sent
