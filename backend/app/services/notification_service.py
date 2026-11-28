"""Centralized notification dispatch service.

Single entry point for all platform notifications. Handles:
- Preference checks (per-user, per-type, per-channel)
- In-app notification creation
- Email delivery (async, with deduplication)
- Organization scoping (security audit compliance)
- Deduplication via email_log table

Usage:
    from app.services.notification_service import dispatch_notification

    dispatch_notification(
        db=db,
        organization_id=user.organization_id,
        user_id=user.id,
        notification_type="scan_completed",
        title="Scan completed: example.com",
        message="Found 12 subdomains and 3 vulnerabilities.",
        related_entity_type="scan",
        related_entity_id=scan.id,
        priority="normal",
        data={"domain": "example.com", "scan_id": scan.id},
    )
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.notification_email_log import NotificationEmailLog
from app.models.user import User

logger = logging.getLogger(__name__)

# Notification type → default priority mapping
_TYPE_PRIORITY = {
    "scan_completed": "normal",
    "scan_failed": "normal",
    "new_shadow_asset": "high",
    "new_finding_critical": "critical",
    "new_finding_high": "high",
    "new_finding_medium": "normal",
    "ssl_expiring": "high",
    "new_cve_match": "high",
    "new_login": "high",
    "password_changed": "critical",
    "email_changed": "critical",
    "weekly_digest": "low",
    # Asset inventory change alerts (app/services/inventory_alerts.py)
    "inventory_new_asset": "high",
    "inventory_new_service": "high",
    "inventory_new_finding": "critical",
    "inventory_cert_expiring": "high",
    "inventory_cert_changed": "normal",
    "inventory_asset_missing": "normal",
    "inventory_plan_limit": "high",
}

INVENTORY_NOTIFICATION_TYPES = (
    "inventory_new_asset",
    "inventory_new_service",
    "inventory_new_finding",
    "inventory_cert_expiring",
    "inventory_cert_changed",
    "inventory_asset_missing",
)

# Types that should trigger email delivery when priority is high/critical
_EMAIL_ELIGIBLE_TYPES = {
    "scan_completed",
    "scan_failed",
    "new_shadow_asset",
    "new_finding_critical",
    "new_finding_high",
    "ssl_expiring",
    "new_cve_match",
    "new_login",
    "password_changed",
    "email_changed",
    "weekly_digest",
    *INVENTORY_NOTIFICATION_TYPES,
}

# Default preferences for new users (all channels enabled)
DEFAULT_PREFERENCES: Dict[str, Dict[str, bool]] = {
    "scan_completed":          {"in_app_enabled": True,  "email_enabled": True},
    "scan_failed":             {"in_app_enabled": True,  "email_enabled": True},
    "new_shadow_asset":        {"in_app_enabled": True,  "email_enabled": True},
    "new_finding_critical":    {"in_app_enabled": True,  "email_enabled": True},
    "new_finding_high":        {"in_app_enabled": True,  "email_enabled": True},
    "new_finding_medium":      {"in_app_enabled": True,  "email_enabled": False},
    "ssl_expiring":            {"in_app_enabled": True,  "email_enabled": True},
    "new_cve_match":           {"in_app_enabled": True,  "email_enabled": True},
    "new_login":               {"in_app_enabled": True,  "email_enabled": True},
    "password_changed":        {"in_app_enabled": True,  "email_enabled": True},
    "email_changed":           {"in_app_enabled": True,  "email_enabled": True},
    "weekly_digest":           {"in_app_enabled": False, "email_enabled": False},
    # Inventory alerts: on for both channels; the organization's alert
    # settings decide which of them are actually used.
    **{t: {"in_app_enabled": True, "email_enabled": True} for t in INVENTORY_NOTIFICATION_TYPES},
}


def ensure_default_preferences(db: Session, user_id: str) -> None:
    """Create default notification preferences for a user if none exist.

    Called during user registration to ensure preferences are always present.
    Safe to call multiple times — only creates missing rows.
    """
    existing = {
        pref.notification_type
        for pref in db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).all()
    }

    for notif_type, defaults in DEFAULT_PREFERENCES.items():
        if notif_type not in existing:
            db.add(NotificationPreference(
                user_id=user_id,
                notification_type=notif_type,
                in_app_enabled=defaults["in_app_enabled"],
                email_enabled=defaults["email_enabled"],
            ))
    db.commit()


def _get_preference(
    db: Session,
    user_id: str,
    notification_type: str,
) -> Optional[NotificationPreference]:
    """Get the user's preference for a notification type, or None if not configured."""
    return db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id,
        NotificationPreference.notification_type == notification_type,
    ).first()


def _should_send_email(
    db: Session,
    user_id: str,
    notification_type: str,
) -> bool:
    """Check if email should be sent for this notification type.

    Returns False if:
    - The type is not email-eligible
    - The user has email_enabled=False for this type
    - An email was already sent for this notification (dedup via email_log)
    """
    if notification_type not in _EMAIL_ELIGIBLE_TYPES:
        return False

    pref = _get_preference(db, user_id, notification_type)
    if pref and not pref.email_enabled:
        return False

    return True


def _check_deduplication(
    db: Session,
    user_id: str,
    notification_type: str,
    related_entity_type: Optional[str],
    related_entity_id: Optional[str],
    window_hours: int = 24,
) -> bool:
    """Check if a similar notification was already sent recently.

    Returns True if a duplicate exists (should be skipped).
    """
    if not related_entity_type or not related_entity_id:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    existing = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.type == notification_type,
        Notification.related_entity_type == related_entity_type,
        Notification.related_entity_id == related_entity_id,
        Notification.created_at >= cutoff,
    ).first()

    return existing is not None


def dispatch_notification(
    db: Session,
    organization_id: Optional[str],
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    priority: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    skip_dedup: bool = False,
    allow_in_app: bool = True,
    allow_email: bool = True,
    fire_webhooks: bool = True,
) -> Optional[Notification]:
    """Central notification dispatch — the single entry point for all notifications.

    1. Resolves priority from type if not provided
    2. Checks user preferences (in_app_enabled, email_enabled)
    3. Deduplicates within a 24h window for same entity
    4. Creates in-app notification row
    5. Sends email if eligible and enabled
    6. Returns the Notification or None if suppressed

    All exceptions are caught and logged — notifications must never crash
    the calling code path.
    """
    try:
        # Resolve priority
        if priority is None:
            priority = _TYPE_PRIORITY.get(notification_type, "normal")

        # Check user preferences
        pref = _get_preference(db, user_id, notification_type)
        in_app_enabled = True
        email_enabled = True
        if pref:
            in_app_enabled = pref.in_app_enabled
            email_enabled = pref.email_enabled
        # Organization-level channel switches (inventory alert settings).
        in_app_enabled = in_app_enabled and allow_in_app
        email_enabled = email_enabled and allow_email

        # If both channels disabled, skip entirely
        if not in_app_enabled and not email_enabled and not fire_webhooks:
            return None

        # Deduplication check (skip for security events and weekly digest)
        if not skip_dedup and notification_type not in ("new_login", "password_changed", "email_changed", "weekly_digest"):
            if _check_deduplication(db, user_id, notification_type, related_entity_type, related_entity_id):
                logger.debug(f"Skipping duplicate notification: {notification_type} for user {user_id}")
                return None

        # Create in-app notification
        notification = None
        if in_app_enabled:
            notification = Notification(
                organization_id=organization_id,
                user_id=user_id,
                type=notification_type,
                title=title,
                message=message,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                priority=priority,
                channel="in_app",
                data=data or {},
            )
            db.add(notification)
            db.flush()  # Get the ID without committing

        # Send email if eligible
        if email_enabled and notification_type in _EMAIL_ELIGIBLE_TYPES:
            _send_notification_email(
                db=db,
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                data=data,
                notification_id=notification.id if notification else None,
            )

        # Dispatch to webhooks (async, fire-and-forget)
        if organization_id and fire_webhooks:
            _dispatch_webhook_async(
                db=db,
                organization_id=organization_id,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                data=data,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            # The organization's own Slack / Teams / Jira / SIEM integrations.
            event_type = NOTIFICATION_EVENT_TYPES.get(notification_type)
            if event_type:
                from app.services.integration_delivery import dispatch_integrations

                dispatch_integrations(
                    db, organization_id, event_type, title, message, priority, data,
                    related_entity_type, related_entity_id,
                )

        if notification:
            db.commit()
            logger.info(f"Notification dispatched: {notification_type} to user {user_id}")
        else:
            db.commit()

        return notification

    except Exception as e:
        logger.error(f"Failed to dispatch notification ({notification_type} to {user_id}): {e}")
        db.rollback()
        return None


def _send_notification_email(
    db: Session,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str,
    related_entity_type: Optional[str],
    related_entity_id: Optional[str],
    data: Optional[Dict[str, Any]],
    notification_id: Optional[str],
) -> None:
    """Send email for a notification, with deduplication via email_log.

    Only sends for high/critical priority types. Uses async delivery.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.email:
            return

        # Check email_log for dedup (within 24h)
        if notification_id:
            existing_log = db.query(NotificationEmailLog).filter(
                NotificationEmailLog.notification_id == notification_id,
            ).first()
            if existing_log:
                return

        # Build email content based on notification type
        subject, html_body = _build_email_content(
            notification_type=notification_type,
            title=title,
            message=message,
            data=data or {},
            user_name=user.full_name or user.email.split("@")[0],
        )

        if not subject:
            return

        # Send via email service (async)
        from app.services.email.sender import get_email_service
        email_service = get_email_service()
        email_service.send_async(to=user.email, subject=subject, html_body=html_body)

        # Log the email send
        if notification_id:
            log_entry = NotificationEmailLog(
                notification_id=notification_id,
                user_id=user_id,
                email_type=notification_type,
            )
            db.add(log_entry)

    except Exception as e:
        logger.error(f"Failed to send notification email ({notification_type} to {user_id}): {e}")


# Notification type → outbound event name (webhooks and integrations).
NOTIFICATION_EVENT_TYPES = {
    "scan_completed": "scan.completed",
    "scan_failed": "scan.failed",
    "new_shadow_asset": "asset.shadow_asset",
    "new_finding_critical": "finding.critical",
    "new_finding_high": "finding.high",
    "new_finding_medium": "finding.medium",
    "ssl_expiring": "ssl.certificate_expiring",
    "new_cve_match": "cve.new_match",
    "inventory_new_asset": "asset.new_subdomain",
    "inventory_new_service": "asset.new_port",
    "inventory_new_finding": "finding.critical",
    "inventory_cert_expiring": "ssl.certificate_expiring",
    "inventory_cert_changed": "ssl.certificate_changed",
    "inventory_asset_missing": "asset.disappeared",
}


def _dispatch_webhook_async(
    db: Session,
    organization_id: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str,
    data: Optional[Dict[str, Any]],
    related_entity_type: Optional[str],
    related_entity_id: Optional[str],
) -> None:
    """Dispatch notification to matching webhooks for the organization.

    Maps notification types to webhook event types and fires async.
    """
    try:
        from app.models.webhook import Webhook

        event_type_map = NOTIFICATION_EVENT_TYPES

        event_type = event_type_map.get(notification_type)
        if not event_type:
            return  # No webhook event for this notification type

        # Get active webhooks for this org that match the event
        webhooks = (
            db.query(Webhook)
            .filter(
                Webhook.organization_id == organization_id,
                Webhook.is_active == True,
            )
            .all()
        )

        matching = [wh for wh in webhooks if wh.matches_event(event_type)]
        if not matching:
            return

        # Build webhook payload
        payload = {
            "title": title,
            "message": message,
            "priority": priority,
            "data": data or {},
        }
        if related_entity_type:
            payload["entity_type"] = related_entity_type
        if related_entity_id:
            payload["entity_id"] = related_entity_id

        # Fire webhooks asynchronously (fire-and-forget)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    _fire_webhooks(matching, event_type, payload)
                )
            else:
                loop.run_until_complete(
                    _fire_webhooks(matching, event_type, payload)
                )
        except RuntimeError:
            # No event loop, create one
            asyncio.run(_fire_webhooks(matching, event_type, payload))

    except Exception as e:
        logger.error(f"Failed to dispatch webhooks for org {organization_id}: {e}")


async def _fire_webhooks(
    webhooks: list,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Fire webhook dispatches concurrently."""
    from app.services.webhook_dispatch import dispatch_webhook
    import asyncio

    tasks = [dispatch_webhook(wh, event_type, payload) for wh in webhooks]
    await asyncio.gather(*tasks, return_exceptions=True)


def _build_email_content(
    notification_type: str,
    title: str,
    message: str,
    data: Dict[str, Any],
    user_name: str,
) -> tuple:
    """Build email subject and HTML body for a notification.

    Returns (subject, html_body) or (None, None) if no template exists.
    """
    from app.services.email.templates import (
        scan_completed_email,
        scan_failed_email,
        new_finding_email,
        ssl_expiring_email,
        new_shadow_asset_email,
        new_cve_email,
        security_event_email,
    )

    scan_id = data.get("scan_id")
    domain = data.get("domain", "")
    scan_url = f"/scan/{scan_id}" if scan_id else "/dashboard"

    if notification_type == "scan_completed":
        return scan_completed_email(
            name=user_name,
            domain=domain,
            subdomains=data.get("subdomains_count", 0),
            vulns=data.get("vulns_count", 0),
            scan_url=scan_url,
        )

    elif notification_type == "scan_failed":
        return scan_failed_email(
            name=user_name,
            domain=domain,
            error=data.get("error", "Unknown error"),
            scan_url=scan_url,
        )

    elif notification_type in ("new_finding_critical", "new_finding_high", "new_finding_medium"):
        return new_finding_email(
            name=user_name,
            domain=domain,
            vuln_name=data.get("vuln_name", title),
            severity=data.get("severity", notification_type.replace("new_finding_", "")),
            scan_url=scan_url,
        )

    elif notification_type == "ssl_expiring":
        return ssl_expiring_email(
            name=user_name,
            hostname=data.get("hostname", domain),
            days_left=data.get("days_left", 0),
            cert_url=scan_url,
        )

    elif notification_type == "new_shadow_asset":
        return new_shadow_asset_email(
            name=user_name,
            domain=domain,
            asset_count=data.get("asset_count", 1),
            shadow_url="/shadow",
        )

    elif notification_type == "new_cve_match":
        return new_cve_email(
            name=user_name,
            domain=domain,
            cve_id=data.get("cve_id", ""),
            severity=data.get("severity", "high"),
            tech_name=data.get("tech_name", ""),
            cve_url=scan_url,
        )

    elif notification_type in ("new_login", "password_changed", "email_changed"):
        event_labels = {
            "new_login": "New Login Detected",
            "password_changed": "Password Changed",
            "email_changed": "Email Changed",
        }
        return security_event_email(
            name=user_name,
            event_type=event_labels.get(notification_type, title),
            ip=data.get("ip_address", "Unknown"),
            browser=data.get("user_agent", "Unknown"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )

    elif notification_type.startswith("inventory_"):
        from app.services.email.templates import inventory_alert_email

        return inventory_alert_email(
            name=user_name,
            title=title,
            intro=data.get("intro") or message,
            items=data.get("items") or [],
            more=int(data.get("more") or 0),
            url=data.get("url") or "/inventory",
            tone=data.get("tone") or "warning",
        )

    # No template for this type — skip email
    return None, None


# ==================== BACKWARD-COMPATIBLE ALIASES ====================
# These wrap the old notify_* functions to use dispatch_notification.
# They will be removed in Stage 4 when scan_service.py is updated.


def notify_scan_completed(db: Session, user_id: str, domain: str, scan_id: str,
                          subdomains_count: int = 0, vulns_count: int = 0):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    msg = f"Scan completed for {domain}."
    if subdomains_count:
        msg += f" Found {subdomains_count} subdomains."
    if vulns_count:
        msg += f" {vulns_count} vulnerabilities detected."
    # Resolve org_id from user
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="scan_completed",
        title=f"Scan completed: {domain}",
        message=msg,
        related_entity_type="scan",
        related_entity_id=scan_id,
        data={"scan_id": scan_id, "domain": domain, "subdomains_count": subdomains_count, "vulns_count": vulns_count},
        skip_dedup=True,
    )


def notify_scan_failed(db: Session, user_id: str, domain: str, scan_id: str, error: str = ""):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="scan_failed",
        title=f"Scan failed: {domain}",
        message=f"Scan for {domain} failed. {error}" if error else f"Scan for {domain} failed.",
        related_entity_type="scan",
        related_entity_id=scan_id,
        priority="normal",
        data={"scan_id": scan_id, "domain": domain, "error": error},
        skip_dedup=True,
    )


def notify_ssl_expiring(db: Session, user_id: str, hostname: str, days_left: int, scan_id: str):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="ssl_expiring",
        title=f"SSL certificate expiring: {hostname}",
        message=f"SSL certificate for {hostname} expires in {days_left} days.",
        related_entity_type="certificate",
        related_entity_id=None,
        data={"hostname": hostname, "days_left": days_left, "scan_id": scan_id},
    )


def notify_new_assets(db: Session, user_id: str, domain: str, scan_id: str, new_subdomains: list):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    if not new_subdomains:
        return
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="new_shadow_asset",
        title=f"New assets discovered: {domain}",
        message=f"Found {len(new_subdomains)} new subdomains for {domain}: {', '.join(new_subdomains[:5])}{'...' if len(new_subdomains) > 5 else ''}",
        related_entity_type="asset",
        related_entity_id=None,
        data={"scan_id": scan_id, "domain": domain, "subdomains": new_subdomains, "asset_count": len(new_subdomains)},
    )


def notify_risk_score_changed(db: Session, user_id: str, domain: str, scan_id: str,
                               old_score, new_score: int):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    if old_score is None:
        return
    direction = "increased" if new_score > old_score else "decreased"
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="scan_completed",
        title=f"Risk score {direction}: {domain}",
        message=f"Risk score for {domain} {direction} from {old_score} to {new_score}.",
        related_entity_type="scan",
        related_entity_id=scan_id,
        data={"scan_id": scan_id, "domain": domain, "old_score": old_score, "new_score": new_score},
        skip_dedup=True,
    )


def notify_new_finding(db: Session, user_id: str, domain: str, scan_id: str,
                       vuln_name: str, severity: str):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    notif_type = f"new_finding_{severity.lower()}" if severity.lower() in ("critical", "high", "medium") else "new_finding_medium"
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type=notif_type,
        title=f"New {severity} finding: {vuln_name}",
        message=f"A {severity} vulnerability was found on {domain}: {vuln_name}",
        related_entity_type="finding",
        related_entity_id=None,
        data={"scan_id": scan_id, "domain": domain, "vuln_name": vuln_name, "severity": severity},
    )


def notify_dns_changed(db: Session, user_id: str, hostname: str, scan_id: str):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="scan_completed",
        title=f"DNS changed: {hostname}",
        message=f"DNS records for {hostname} have changed.",
        related_entity_type="asset",
        related_entity_id=None,
        data={"hostname": hostname, "scan_id": scan_id},
        skip_dedup=True,
    )


def notify_technology_changed(db: Session, user_id: str, hostname: str, scan_id: str):
    """Legacy wrapper — use dispatch_notification() directly for new code."""
    user = db.query(User).filter(User.id == user_id).first()
    dispatch_notification(
        db=db,
        organization_id=user.organization_id if user else None,
        user_id=user_id,
        notification_type="scan_completed",
        title=f"Technology changed: {hostname}",
        message=f"Detected technology changes for {hostname}.",
        related_entity_type="asset",
        related_entity_id=None,
        data={"hostname": hostname, "scan_id": scan_id},
        skip_dedup=True,
    )
