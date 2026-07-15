from sqlalchemy.orm import Session
from app.models.notification import Notification
from typing import Optional, Dict, Any
import uuid


def create_notification(
    db: Session,
    user_id: str,
    type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Notification:
    """Create a notification for a user."""
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        data=data or {},
    )
    db.add(notification)
    db.commit()
    return notification


def notify_scan_completed(db: Session, user_id: str, domain: str, scan_id: str, subdomains_count: int = 0, vulns_count: int = 0):
    """Notify user that a scan completed."""
    msg = f"Scan completed for {domain}."
    if subdomains_count:
        msg += f" Found {subdomains_count} subdomains."
    if vulns_count:
        msg += f" {vulns_count} vulnerabilities detected."
    create_notification(
        db, user_id, "scan_completed",
        f"Scan completed: {domain}",
        msg,
        {"scan_id": scan_id, "domain": domain},
    )


def notify_scan_failed(db: Session, user_id: str, domain: str, scan_id: str, error: str = ""):
    """Notify user that a scan failed."""
    create_notification(
        db, user_id, "scan_failed",
        f"Scan failed: {domain}",
        f"Scan for {domain} failed. {error}" if error else f"Scan for {domain} failed.",
        {"scan_id": scan_id, "domain": domain},
    )


def notify_ssl_expiring(db: Session, user_id: str, hostname: str, days_left: int, scan_id: str):
    """Notify user about SSL certificate expiring soon."""
    create_notification(
        db, user_id, "ssl_expiring",
        f"SSL certificate expiring: {hostname}",
        f"SSL certificate for {hostname} expires in {days_left} days.",
        {"hostname": hostname, "days_left": days_left, "scan_id": scan_id},
    )


def notify_new_assets(db: Session, user_id: str, domain: str, scan_id: str, new_subdomains: list[str]):
    """Notify user about newly discovered assets."""
    if not new_subdomains:
        return
    create_notification(
        db, user_id, "new_asset",
        f"New assets discovered: {domain}",
        f"Found {len(new_subdomains)} new subdomains for {domain}: {', '.join(new_subdomains[:5])}{'...' if len(new_subdomains) > 5 else ''}",
        {"scan_id": scan_id, "domain": domain, "subdomains": new_subdomains},
    )


def notify_risk_score_changed(db: Session, user_id: str, domain: str, scan_id: str, old_score: Optional[int], new_score: int):
    """Notify user about risk score change."""
    if old_score is None:
        return
    direction = "increased" if new_score > old_score else "decreased"
    create_notification(
        db, user_id, "risk_score_changed",
        f"Risk score {direction}: {domain}",
        f"Risk score for {domain} {direction} from {old_score} to {new_score}.",
        {"scan_id": scan_id, "domain": domain, "old_score": old_score, "new_score": new_score},
    )


def notify_new_finding(db: Session, user_id: str, domain: str, scan_id: str, vuln_name: str, severity: str):
    """Notify user about a new vulnerability finding."""
    create_notification(
        db, user_id, "new_finding",
        f"New {severity} finding: {vuln_name}",
        f"A {severity} vulnerability was found on {domain}: {vuln_name}",
        {"scan_id": scan_id, "domain": domain, "vuln_name": vuln_name, "severity": severity},
    )


def notify_dns_changed(db: Session, user_id: str, hostname: str, scan_id: str):
    """Notify user about DNS changes."""
    create_notification(
        db, user_id, "dns_changed",
        f"DNS changed: {hostname}",
        f"DNS records for {hostname} have changed.",
        {"hostname": hostname, "scan_id": scan_id},
    )


def notify_technology_changed(db: Session, user_id: str, hostname: str, scan_id: str):
    """Notify user about technology stack changes."""
    create_notification(
        db, user_id, "technology_changed",
        f"Technology changed: {hostname}",
        f"Detected technology changes for {hostname}.",
        {"hostname": hostname, "scan_id": scan_id},
    )
