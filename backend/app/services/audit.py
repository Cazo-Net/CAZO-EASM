"""Audit logging.

``log_event`` records one action in an organization's audit log. Entries are
chained: each carries a keyed fingerprint (HMAC-SHA256) of its own contents
and of the previous entry, so changing, deleting or re-ordering stored entries
is detectable with ``verify_chain``. The key lives in the application's
configuration, not in the database, so someone who can only write to the
database cannot rebuild a valid chain.

``log_auth_event`` keeps writing the per-user sign-in history
(``AuthAuditLog``) and also copies the event into the organization's audit
log as ``auth.<event>``.

All audit writes are best-effort: a failure to record an event must never
break the business operation it observes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.request_context import get_request_context
from app.models.audit import AuditEvent
from app.models.auth_models import AuthAuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

# Keys whose values must never be written to the audit log.
_SECRET_KEY_PARTS = ("password", "secret", "token", "api_key", "apikey", "authorization", "private_key")


def _chain_key() -> bytes:
    raw = settings.AUDIT_LOG_KEY or settings.SECRET_KEY or ""
    return hashlib.sha256(b"cazo-audit-chain:v1:" + raw.encode()).digest()


def _scrub(value: Any, depth: int = 0) -> Any:
    """Make ``detail`` JSON-safe and strip anything that looks like a secret."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = str(k)
            if any(part in key.lower() for part in _SECRET_KEY_PARTS):
                out[key] = "[redacted]"
            else:
                out[key] = _scrub(v, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_scrub(v, depth + 1) for v in list(value)[:200]]
    if isinstance(value, str):
        return value[:2000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


def _ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_hash(event: AuditEvent, prev_hash: str) -> str:
    """Fingerprint of an entry's contents plus the previous entry's hash."""
    payload = {
        "id": event.id,
        "seq": event.seq,
        "organization_id": event.organization_id,
        "action": event.action,
        "actor_id": event.actor_id,
        "actor_type": event.actor_type,
        "actor_email": event.actor_email,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "status": event.status,
        "detail": event.detail or {},
        "request_id": event.request_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": _ts(event.created_at),
        "prev_hash": prev_hash,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(_chain_key(), body.encode(), hashlib.sha256).hexdigest()


def _lock_chain(db: Session, organization_id: Optional[str]) -> None:
    """Serialize writers of one organization's chain (Postgres only).

    The lock is released when the transaction ends. SQLite allows a single
    writer at a time anyway.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.sha256(f"audit:{organization_id or ''}".encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})


def _org_filter(query, organization_id: Optional[str]):
    if organization_id is None:
        return query.filter(AuditEvent.organization_id.is_(None))
    return query.filter(AuditEvent.organization_id == organization_id)


def log_event(
    db: Session,
    action: str,
    organization_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "user",
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: str = "success",
    detail: Optional[dict] = None,
    request_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[AuditEvent]:
    """Record an audit event (best-effort). Returns the created row or None.

    Client IP, user agent and request id default to the current HTTP request's.
    Commits the session, so call it after the business change is committed.
    """
    try:
        ctx = get_request_context()
        if actor_id and not actor_email:
            from app.models.user import User

            actor_email = db.query(User.email).filter(User.id == actor_id).scalar()

        detail = dict(detail or {})
        if target_id is not None and len(str(target_id)) > 36:
            # The column holds 36 characters; keep the full value in detail.
            detail.setdefault("target_id_full", str(target_id))

        _lock_chain(db, organization_id)
        last = (
            _org_filter(db.query(AuditEvent.seq, AuditEvent.hash), organization_id)
            .filter(AuditEvent.seq.isnot(None))
            .order_by(AuditEvent.seq.desc())
            .first()
        )
        prev_hash = last.hash if last else GENESIS_HASH
        event = AuditEvent(
            action=action[:64],
            organization_id=organization_id,
            actor_id=actor_id,
            actor_type=actor_type,
            actor_email=(actor_email or None) and actor_email[:255],
            target_type=target_type,
            target_id=(str(target_id)[:36] if target_id is not None else None),
            status=status,
            detail=_scrub(detail or {}),
            request_id=(request_id or ctx.request_id or None) and (request_id or ctx.request_id)[:32],
            ip_address=(ip_address or ctx.ip_address or None) and (ip_address or ctx.ip_address)[:64],
            user_agent=(user_agent or ctx.user_agent or None) and (user_agent or ctx.user_agent)[:400],
            created_at=datetime.now(timezone.utc),
        )
        import uuid

        event.id = str(uuid.uuid4())
        event.seq = (last.seq + 1) if last else 1
        event.prev_hash = prev_hash
        event.hash = compute_hash(event, prev_hash)
        db.add(event)
        db.commit()
        return event
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write audit event %s: %s", action, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def log_auth_event(
    db: Session,
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
    success: bool = True,
    detail: dict = None,
):
    """Log a sign-in/security event for a user and mirror it to the org audit log."""
    entry = AuthAuditLog(
        user_id=user_id,
        event_type=event_type,
        event_detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )
    db.add(entry)
    db.commit()

    # Mirror into the organization's audit log. Events with no known user or
    # no organization (e.g. a failed sign-in for an unknown email) stay in the
    # per-user history only: they belong to no tenant.
    if not user_id:
        return
    try:
        from app.models.user import User

        row = db.query(User.organization_id, User.email).filter(User.id == user_id).first()
        if not row or not row.organization_id:
            return
        log_event(
            db,
            action=f"auth.{event_type}",
            organization_id=row.organization_id,
            actor_id=user_id,
            actor_email=row.email,
            target_type="user",
            target_id=user_id,
            status="success" if success else "failure",
            detail=detail,
            # Inside a request, prefer the proxy-aware address from the
            # request context over the raw peer address callers pass in.
            ip_address=None if get_request_context().ip_address else ip_address,
            user_agent=user_agent,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to mirror auth event %s: %s", event_type, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def verify_chain(db: Session, organization_id: Optional[str], batch: int = 1000) -> dict:
    """Re-compute an organization's chain and report the first break, if any."""
    base = _org_filter(db.query(AuditEvent), organization_id)
    legacy = base.filter(AuditEvent.seq.is_(None)).count()
    checked = 0
    prev_hash = GENESIS_HASH
    expected_seq = 1
    last_seq = 0
    first_at = last_at = None
    problem = None
    while problem is None:
        rows = (
            base.filter(AuditEvent.seq.isnot(None), AuditEvent.seq > last_seq)
            .order_by(AuditEvent.seq.asc(), AuditEvent.created_at.asc())
            .limit(batch)
            .all()
        )
        if not rows:
            break
        for row in rows:
            if row.seq != expected_seq:
                kind = "duplicate" if row.seq < expected_seq else "missing"
                problem = {"seq": expected_seq, "reason": kind,
                           "message": f"Entry {expected_seq} is {kind}."}
                break
            if row.prev_hash != prev_hash or row.hash != compute_hash(row, prev_hash):
                problem = {"seq": row.seq, "reason": "modified", "id": row.id,
                           "message": f"Entry {row.seq} was changed after it was written."}
                break
            prev_hash = row.hash
            expected_seq += 1
            checked += 1
            first_at = first_at or row.created_at
            last_at = row.created_at
        last_seq = rows[-1].seq
    return {
        "valid": problem is None,
        "checked": checked,
        "legacy_unverified": legacy,
        "first_entry_at": _ts(first_at) or None,
        "last_entry_at": _ts(last_at) or None,
        "last_hash": prev_hash if checked else None,
        "problem": problem,
    }


def log_user_action(
    db: Session,
    user,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    status: str = "success",
) -> Optional[AuditEvent]:
    """Record an action by a signed-in user in that user's organization."""
    # Read these first: a failed write rolls the session back, which would
    # otherwise force a reload of ``user`` here.
    try:
        user_id, org_id, email = user.id, user.organization_id, user.email
    except Exception:  # noqa: BLE001
        return None
    return log_event(
        db,
        action=action,
        organization_id=org_id,
        actor_id=user_id,
        actor_email=email,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        status=status,
    )
