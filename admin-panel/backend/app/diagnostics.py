"""Client diagnostics: technical details staff need to investigate a customer's problem.

Everything shown here is metadata the platform already records while the
customer uses CAZO-EASM: sign-in sessions (browser, OS, device type, IP,
approximate location from the edge), sign-in events, the actions in the audit
log, and failed requests / front-end errors from the platform log. There is no
recording of screens, keystrokes, page content or anything outside the product.

Read-only. Every view is recorded in the platform log (security_event) with the
admin's email, so access to customer data stays accountable.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.user_agent import browser_label, os_label, parse_user_agent

# Keys from auth event details that help debugging. Anything else (which may
# grow over time) is left out of the view.
_AUTH_DETAIL_KEYS = ("method", "session_id", "reason", "provider", "attempts")
_ERROR_SEVERITIES = ("warning", "error", "critical")


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _aware(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _ua_fields(ua: Optional[str]) -> dict:
    info = parse_user_agent(ua)
    return {
        "browser": browser_label(info),
        "os": os_label(info),
        "device_type": info["device_type"] or "unknown",
    }


def _session_row(r) -> dict:
    ua = getattr(r, "user_agent", None)
    return {
        "id": r.id,
        "is_active": bool(getattr(r, "is_active", False)),
        "is_trusted": bool(getattr(r, "is_trusted", False)),
        "ip_address": getattr(r, "ip_address", None),
        "location": ", ".join(p for p in (getattr(r, "location_city", None),
                                          getattr(r, "location_country", None)) if p) or None,
        "user_agent": (ua or "")[:512] or None,
        **_ua_fields(ua),
        "created_at": _iso(getattr(r, "created_at", None)),
        "last_activity": _iso(getattr(r, "last_activity", None)),
        "expires_at": _iso(getattr(r, "expires_at", None)),
    }


def _auth_row(r) -> dict:
    detail = getattr(r, "event_detail", None) or {}
    if not isinstance(detail, dict):
        detail = {}
    ua = getattr(r, "user_agent", None)
    return {
        "id": r.id,
        "event_type": r.event_type,
        "success": bool(getattr(r, "success", True)),
        "ip_address": getattr(r, "ip_address", None),
        **({"browser": browser_label(parse_user_agent(ua)), "os": os_label(parse_user_agent(ua))} if ua else {}),
        "detail": {k: detail[k] for k in _AUTH_DETAIL_KEYS if k in detail},
        "created_at": _iso(r.created_at),
    }


def _error_row(r) -> dict:
    detail = getattr(r, "detail", None) or {}
    if not isinstance(detail, dict):
        detail = {}
    return {
        "id": r.id,
        "category": r.category,
        "severity": r.severity,
        "message": (r.message or "")[:500],
        "path": getattr(r, "path", None) or detail.get("url"),
        "method": getattr(r, "method", None),
        "status_code": getattr(r, "status_code", None),
        "request_id": getattr(r, "request_id", None),
        "client_ip": getattr(r, "client_ip", None),
        "browser": detail.get("browser"),
        "created_at": _iso(r.created_at),
    }


def _activity_row(r) -> dict:
    return {
        "id": r.id,
        "action": r.action,
        "status": getattr(r, "status", None),
        "target_type": getattr(r, "target_type", None),
        "target_id": getattr(r, "target_id", None),
        "ip_address": getattr(r, "ip_address", None),
        "created_at": _iso(r.created_at),
    }


def build_router(
    require_admin: Callable,
    get_table: Callable,
    table_names: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

    def _record_view(db: DBSession, admin: str, kind: str, target_id: str, user_id: Optional[str]):
        """Write an internal (superuser-only) access record. Best effort."""
        if "platform_logs" not in table_names(db):
            return
        try:
            t = get_table("platform_logs")
            db.execute(t.insert().values(
                id=str(uuid.uuid4()),
                category="security_event",
                severity="info",
                message=f"Admin viewed client diagnostics ({kind})",
                detail={"admin": admin, "kind": kind, "target_id": target_id},
                user_id=user_id,
                related_entity_type=kind,
                related_entity_id=target_id,
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()

    def _user_and_org(db: DBSession, user_id: str):
        t = get_table("users")
        user = db.query(t).filter(t.c.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        org = None
        org_id = getattr(user, "organization_id", None)
        tables = table_names(db)
        if org_id and "organizations" in tables:
            ot = get_table("organizations")
            o = db.query(ot).filter(ot.c.id == org_id).first()
            if o:
                org = {
                    "id": o.id, "name": o.name,
                    "plan": getattr(o, "plan", None),
                    "is_active": getattr(o, "is_active", True),
                    "subscription": None,
                }
                if "billing_subscriptions" in tables:
                    bt = get_table("billing_subscriptions")
                    sub = db.query(bt).filter(bt.c.organization_id == org_id).first()
                    if sub:
                        org["subscription"] = {
                            "plan": sub.plan, "status": sub.status,
                            "billing_interval": getattr(sub, "billing_interval", None),
                            "current_period_end": _iso(getattr(sub, "current_period_end", None)),
                            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
                            "last_payment_error": (getattr(sub, "last_payment_error", None) or "")[:300] or None,
                        }
        return user, org

    def _user_summary(user) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "full_name": getattr(user, "full_name", None),
            "role": getattr(user, "role", None),
            "is_active": bool(getattr(user, "is_active", True)),
            "email_verified": bool(getattr(user, "email_verified", False)),
            "totp_enabled": bool(getattr(user, "totp_enabled", False)),
            "mfa_enforced": bool(getattr(user, "mfa_enforced", False)),
            "sign_in_method": "google" if getattr(user, "google_id", None) else "password",
            "failed_login_attempts": getattr(user, "failed_login_attempts", 0) or 0,
            "locked_until": _iso(getattr(user, "locked_until", None)),
            "created_at": _iso(getattr(user, "created_at", None)),
            "last_login": _iso(getattr(user, "last_login", None)),
            "password_changed_at": _iso(getattr(user, "password_changed_at", None)),
        }

    @router.get("/users/{user_id}")
    async def user_diagnostics(
        user_id: str,
        limit: int = Query(50, ge=1, le=200),
        db: DBSession = Depends(get_db),
        admin: str = Depends(require_admin),
    ):
        if "users" not in table_names(db):
            raise HTTPException(404, "Users table not found")
        user, org = _user_and_org(db, user_id)
        tables = table_names(db)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        sessions = []
        active_sessions = 0
        if "user_sessions" in tables:
            st = get_table("user_sessions")
            rows = (db.query(st).filter(st.c.user_id == user_id)
                    .order_by(st.c.last_activity.desc(), st.c.created_at.desc()).limit(20).all())
            sessions = [_session_row(r) for r in rows]
            active_sessions = db.query(func.count(st.c.id)).filter(
                st.c.user_id == user_id, st.c.is_active == True,  # noqa: E712
            ).scalar() or 0

        auth_events = []
        failed_logins_7d = 0
        if "auth_audit_logs" in tables:
            at = get_table("auth_audit_logs")
            rows = (db.query(at).filter(at.c.user_id == user_id)
                    .order_by(at.c.created_at.desc()).limit(limit).all())
            auth_events = [_auth_row(r) for r in rows]
            failed_logins_7d = db.query(func.count(at.c.id)).filter(
                at.c.user_id == user_id, at.c.success == False,  # noqa: E712
                at.c.created_at >= week_ago,
            ).scalar() or 0

        activity = []
        if "audit_events" in tables:
            et = get_table("audit_events")
            rows = (db.query(et).filter(et.c.actor_id == user_id)
                    .order_by(et.c.created_at.desc()).limit(limit).all())
            activity = [_activity_row(r) for r in rows]

        errors = []
        errors_7d = 0
        if "platform_logs" in tables:
            pt = get_table("platform_logs")
            base = db.query(pt).filter(pt.c.user_id == user_id, pt.c.severity.in_(_ERROR_SEVERITIES),
                                       pt.c.category != "security_event")
            errors = [_error_row(r) for r in base.order_by(pt.c.created_at.desc()).limit(limit).all()]
            errors_7d = base.filter(pt.c.created_at >= week_ago).count()

        latest = sessions[0] if sessions else None
        seen = [_aware(s["last_activity"]) for s in sessions] + [_aware(getattr(user, "last_login", None))]
        seen = [s for s in seen if s]
        summary = {
            "last_seen": _iso(max(seen)) if seen else None,
            "active_sessions": active_sessions,
            "browser": latest["browser"] if latest else None,
            "os": latest["os"] if latest else None,
            "device_type": latest["device_type"] if latest else None,
            "ip_address": latest["ip_address"] if latest else None,
            "location": latest["location"] if latest else None,
            "errors_7d": errors_7d,
            "failed_logins_7d": failed_logins_7d,
        }

        _record_view(db, admin, "user", user_id, user_id)
        return {
            "user": _user_summary(user),
            "organization": org,
            "summary": summary,
            "sessions": sessions,
            "auth_events": auth_events,
            "activity": activity,
            "errors": errors,
        }

    @router.get("/sessions/{session_id}")
    async def session_diagnostics(
        session_id: str,
        db: DBSession = Depends(get_db),
        admin: str = Depends(require_admin),
    ):
        tables = table_names(db)
        if "user_sessions" not in tables:
            raise HTTPException(404, "Session not found")
        st = get_table("user_sessions")
        s = db.query(st).filter(st.c.id == session_id).first()
        if not s:
            raise HTTPException(404, "Session not found")
        user, org = _user_and_org(db, s.user_id)

        # Events that happened while this session was in use.
        start = (_aware(s.created_at) or datetime.now(timezone.utc)) - timedelta(minutes=1)
        last = _aware(getattr(s, "last_activity", None)) or _aware(s.created_at) or start
        end = datetime.now(timezone.utc) if s.is_active else last + timedelta(minutes=15)

        auth_events = []
        if "auth_audit_logs" in tables:
            at = get_table("auth_audit_logs")
            rows = (db.query(at).filter(at.c.user_id == s.user_id, at.c.created_at >= start,
                                        at.c.created_at <= end)
                    .order_by(at.c.created_at.desc()).limit(50).all())
            auth_events = [_auth_row(r) for r in rows]

        errors = []
        if "platform_logs" in tables:
            pt = get_table("platform_logs")
            rows = (db.query(pt).filter(pt.c.user_id == s.user_id, pt.c.severity.in_(_ERROR_SEVERITIES),
                                        pt.c.category != "security_event",
                                        pt.c.created_at >= start, pt.c.created_at <= end)
                    .order_by(pt.c.created_at.desc()).limit(50).all())
            errors = [_error_row(r) for r in rows]

        _record_view(db, admin, "session", session_id, s.user_id)
        return {
            "session": _session_row(s),
            "user": _user_summary(user),
            "organization": org,
            "window": {"start": _iso(start), "end": _iso(end)},
            "auth_events": auth_events,
            "errors": errors,
        }

    return router
