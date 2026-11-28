"""Celery tasks."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.scan_service import ScanService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.execute_scan")
def execute_scan_task(self, scan_id: str):
    """Run a full scan in a Celery worker."""
    logger.info("Starting scan task for scan_id=%s", scan_id)
    db = SessionLocal()
    try:
        service = ScanService(db)
        asyncio.run(service.execute_scan(scan_id))
        logger.info("Scan task completed for scan_id=%s", scan_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scan task failed for scan_id=%s", scan_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.execute_scan_v2")
def execute_scan_task_v2(self, scan_id: str):
    """Run a full scan using the v2 enterprise scanner pipeline in a Celery worker."""
    logger.info("Starting v2 scan task for scan_id=%s", scan_id)
    db = SessionLocal()
    try:
        from app.services.scan_service_v2 import ScanServiceV2
        service = ScanServiceV2(db)
        asyncio.run(service.execute_scan(scan_id))
        logger.info("V2 scan task completed for scan_id=%s", scan_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("V2 scan task failed for scan_id=%s", scan_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.tasks.check_ssl_expiry")
def check_ssl_expiry():
    """Notify organizations about certificates expiring within 30 days.

    Looks at certificates found by scans completed in the last 14 days and
    sends one notification per organization and hostname to the user who ran
    the scan (the notification service de-duplicates repeats).
    """
    from app.models.asset import Subdomain
    from app.models.ssl import SSLCertificate
    from app.models.scan import Scan
    from app.services.notification_service import dispatch_notification

    logger.info("Starting scheduled SSL expiry check")
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=30)
        recent = now - timedelta(days=14)
        rows = (
            db.query(SSLCertificate, Subdomain.hostname, Scan.organization_id, Scan.created_by, Scan.id)
            .join(Subdomain, SSLCertificate.subdomain_id == Subdomain.id)
            .join(Scan, Subdomain.scan_id == Scan.id)
            .filter(
                Scan.status == "completed",
                Scan.completed_at >= recent,
                Scan.organization_id.isnot(None),
                SSLCertificate.not_after.isnot(None),
                SSLCertificate.not_after <= threshold,
                SSLCertificate.not_after > now,
            )
            .order_by(Scan.completed_at.desc())
            .all()
        )
        seen = set()
        sent = 0
        for cert, hostname, org_id, user_id, scan_id in rows:
            key = (org_id, hostname)
            if key in seen or not user_id:
                continue
            seen.add(key)
            not_after = cert.not_after if cert.not_after.tzinfo else cert.not_after.replace(tzinfo=timezone.utc)
            days_left = (not_after - now).days
            try:
                dispatch_notification(
                    db=db,
                    organization_id=org_id,
                    user_id=user_id,
                    notification_type="ssl_expiring",
                    title=f"SSL certificate expiring: {hostname}",
                    message=f"The SSL certificate for {hostname} expires in {days_left} days.",
                    related_entity_type="certificate",
                    related_entity_id=cert.id,
                    data={"hostname": hostname, "days_left": days_left, "scan_id": scan_id},
                )
                sent += 1
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to send SSL expiry notification for %s: %s", hostname, e)
        logger.info("SSL expiry check complete. Sent %d notifications.", sent)
    finally:
        db.close()


@celery_app.task(name="app.tasks.send_weekly_digest")
def send_weekly_digest():
    """Send weekly digest email to all users with notifications enabled."""
    from app.models.user import User
    from app.models.notification import Notification
    from app.services.notification_service import dispatch_notification

    logger.info("Starting weekly digest")
    db = SessionLocal()
    try:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
        sent = 0
        for user in users:
            if not user.organization_id:
                continue
            # Count notifications from last week
            notif_count = (
                db.query(Notification)
                .filter(
                    Notification.organization_id == user.organization_id,
                    Notification.created_at >= week_ago,
                )
                .count()
            )
            if notif_count == 0:
                continue
            try:
                dispatch_notification(
                    db=db,
                    organization_id=user.organization_id,
                    user_id=user.id,
                    notification_type="weekly_digest",
                    title="Weekly security digest",
                    message=f"You had {notif_count} notifications this week.",
                    related_entity_type=None,
                    related_entity_id=None,
                    data={"week_start": week_ago.isoformat(), "notif_count": notif_count},
                )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send weekly digest to {user.id}: {e}")
        logger.info(f"Weekly digest complete. Sent to {sent} users.")
    finally:
        db.close()


@celery_app.task(name="app.tasks.sync_cve_database")
def sync_cve_database():
    """Pull recent CVEs from NVD into the local snapshot."""
    import subprocess
    import sys

    logger.info("Starting scheduled CVE sync")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.services.cve_sync", "--days", "7", "--limit", "2000"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info(f"CVE sync completed: {result.stdout[-200:] if result.stdout else 'done'}")
        else:
            logger.error(f"CVE sync failed: {result.stderr[-300:] if result.stderr else 'unknown error'}")
    except Exception as e:
        logger.exception(f"CVE sync task failed: {e}")
