"""CAZO Admin Panel - Main application."""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, text, desc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
import psutil
import os
import time
import uuid

from app.config import settings
from app.database import get_db, engine, check_db_health, SessionLocal

security = HTTPBearer()


def create_admin_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ADMIN_JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": email, "exp": expire, "type": "admin"},
        settings.ADMIN_JWT_SECRET,
        algorithm=settings.ADMIN_JWT_ALGORITHM,
    )


def verify_admin_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=[settings.ADMIN_JWT_ALGORITHM])
        if payload.get("type") != "admin":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    email = verify_admin_token(credentials.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
    # A token for a database superuser stops working as soon as that account
    # is disabled or demoted. (The env-var fallback admin has no DB row.)
    if _db_superuser(email.strip().lower()) is None and not _env_admin_matches(email):
        raise HTTPException(status_code=401, detail="Admin account is no longer active")
    return email


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_start_time = time.time()


def _get_table(name):
    from sqlalchemy import Table, MetaData
    return Table(name, MetaData(), autoload_with=engine)


def _col(table_name, col_name):
    return _get_table(table_name).c[col_name]


def _table_names(db) -> set:
    from sqlalchemy import inspect
    return set(inspect(engine).get_table_names())


def _count(db, table, *filters):
    tables = _table_names(db)
    if table not in tables:
        return 0
    try:
        t = _get_table(table)
        q = db.query(func.count(t.c.id))
        for f in filters:
            q = q.filter(f)
        return q.scalar() or 0
    except Exception:
        return 0


def _safe_query(db, fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ── Schemas ───────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PlatformStats(BaseModel):
    users_total: int
    users_active: int
    users_locked: int
    orgs_total: int
    orgs_active: int
    projects_total: int
    scans_total: int
    scans_running: int
    scans_completed: int
    scans_failed: int
    subdomains_total: int
    ports_total: int
    vulns_total: int
    vulns_critical: int
    vulns_high: int
    vulns_medium: int
    vulns_low: int
    vulns_info: int
    notifications_total: int
    sessions_active: int
    scopes_total: int
    assets_total: int
    reports_total: int
    api_keys_total: int
    audit_events_total: int
    db_size_mb: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    uptime_seconds: float
    scan_history_total: int

class SystemHealth(BaseModel):
    database: str
    database_pool_size: int
    database_pool_checked_out: int
    redis: str
    disk_usage_percent: float
    disk_free_gb: float
    cpu_count: int
    memory_total_mb: float
    env: str
    use_sqlite: bool
    uptime_seconds: float
    cpu_freq_mhz: float
    load_avg_1m: float
    swap_total_mb: float
    swap_used_mb: float
    net_bytes_sent: int
    net_bytes_recv: int
    processes_count: int

class UserRow(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    email_verified: bool
    totp_enabled: bool
    mfa_enforced: bool
    organization_id: Optional[str]
    failed_login_attempts: int
    locked_until: Optional[str]
    created_at: str
    last_login: Optional[str]
    api_key: Optional[str]

class OrgRow(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    is_archived: bool
    mfa_enforced: bool
    user_count: int
    scan_count: int
    project_count: int
    created_at: str

class ScanRow(BaseModel):
    id: str
    domain: str
    status: str
    scan_type: str
    progress: int
    organization_id: Optional[str]
    project_id: Optional[str]
    created_by: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    created_at: str

class VulnerabilityRow(BaseModel):
    id: str
    scan_id: str
    subdomain_id: Optional[str]
    name: str
    severity: str
    vuln_type: Optional[str]
    host: str
    status: str
    matched_at: Optional[str]
    organization_id: Optional[str]
    assigned_to: Optional[str]
    found_at: str
    first_seen: str
    last_seen: str

class AssetRow(BaseModel):
    id: str
    organization_id: str
    asset_type: str
    value: str
    label: Optional[str]
    is_alive: bool
    inventory_status: str
    confirmed: bool
    first_seen: str
    last_seen: str

class NotificationRow(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    priority: str
    channel: str
    read: bool
    email_sent: bool
    created_at: str

class AuditEventRow(BaseModel):
    id: str
    action: str
    organization_id: Optional[str]
    actor_id: Optional[str]
    actor_type: str
    target_type: Optional[str]
    target_id: Optional[str]
    status: str
    detail: Optional[Dict[str, Any]]
    created_at: str

class SessionRow(BaseModel):
    id: str
    user_id: str
    browser: Optional[str]
    os: Optional[str]
    ip_address: Optional[str]
    location_city: Optional[str]
    location_country: Optional[str]
    is_trusted: bool
    is_active: bool
    last_activity: str
    created_at: str
    expires_at: Optional[str]

class ApiKeyRow(BaseModel):
    id: str
    user_id: str
    organization_id: Optional[str]
    name: str
    prefix: str
    scopes: Optional[list]
    is_active: bool
    last_used_at: Optional[str]
    last_used_ip: Optional[str]
    created_at: str
    expires_at: Optional[str]

class FeatureFlagRow(BaseModel):
    id: str
    key: str
    name: str
    description: Optional[str]
    enabled: bool
    allowed_plans: Optional[list]
    created_at: str

class RoleRow(BaseModel):
    id: str
    organization_id: Optional[str]
    name: str
    slug: str
    description: Optional[str]
    permissions: Optional[list]
    is_system: bool
    is_default: bool
    created_at: str

class InvitationRow(BaseModel):
    id: str
    email: str
    invited_by: str
    organization_id: str
    role: str
    status: str
    created_at: str
    expires_at: str

class ReportRow(BaseModel):
    id: str
    scan_id: str
    format: str
    file_size: Optional[int]
    generated_by: Optional[str]
    generated_at: str

class ScanHistoryRow(BaseModel):
    id: str
    domain: str
    scan_type: str
    status: str
    triggered_by: str
    subdomains_found: int
    open_ports_found: int
    technologies_found: int
    risk_score: float
    risk_severity: Optional[str]
    duration_ms: Optional[float]
    created_at: str

class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    status: str
    created_at: Optional[str]


# ── Auth ──────────────────────────────────────────────────────────────
def _env_fallback_enabled() -> bool:
    from app.config import WEAK_ADMIN_PASSWORDS
    pw = settings.ADMIN_PASSWORD
    return bool(settings.ADMIN_EMAIL) and pw not in WEAK_ADMIN_PASSWORDS and len(pw) >= 12


def _env_admin_matches(email: str) -> bool:
    """True when `email` is the env-var fallback admin and that fallback is enabled."""
    return _env_fallback_enabled() and email.strip().lower() == settings.ADMIN_EMAIL.strip().lower()


def _db_superuser(email: str):
    """Active platform superuser with this email from the EASM users table, or None."""
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT id, email, hashed_password FROM users "
                "WHERE lower(email) = :email AND role = 'superuser' AND is_active = :active"
            ),
            {"email": email, "active": True},
        ).first()
        return row
    except Exception:  # noqa: BLE001
        return None
    finally:
        db.close()


@app.post("/auth/login", response_model=TokenResponse)
async def admin_login(req: LoginRequest):
    """Sign in as a platform superuser.

    The password is checked against the superuser account stored (bcrypt-hashed)
    in the EASM database. Create or reset that account with:
        python -m app.utils.create_admin --email you@example.com   (in backend/)
    ADMIN_EMAIL / ADMIN_PASSWORD env vars are only a fallback, used when they
    are set to a strong value and no database superuser matches.
    """
    import hmac
    import bcrypt as _bcrypt
    # Simple per-process brute-force brake: 5 failures -> 15 minute pause.
    now = time.time()
    _ADMIN_FAILS[:] = [t for t in _ADMIN_FAILS if now - t < 900]
    if len(_ADMIN_FAILS) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    email = req.email.strip().lower()
    row = _db_superuser(email)
    if row is not None:
        hashed = row.hashed_password or ""
        ok = False
        if hashed.startswith("$2"):
            try:
                ok = _bcrypt.checkpw(req.password.encode(), hashed.encode())
            except ValueError:
                ok = False
        if ok:
            _ADMIN_FAILS.clear()
            return TokenResponse(access_token=create_admin_token(row.email))
        _ADMIN_FAILS.append(now)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if _env_fallback_enabled():
        email_ok = hmac.compare_digest(email.encode(), settings.ADMIN_EMAIL.strip().lower().encode())
        pw_ok = hmac.compare_digest(req.password.encode(), settings.ADMIN_PASSWORD.encode())
        if email_ok and pw_ok:
            _ADMIN_FAILS.clear()
            return TokenResponse(access_token=create_admin_token(settings.ADMIN_EMAIL))

    _ADMIN_FAILS.append(now)
    raise HTTPException(status_code=401, detail="Invalid credentials")


_ADMIN_FAILS: list = []


@app.get("/auth/me")
async def admin_me(admin: str = Depends(require_admin)):
    return {"email": admin, "role": "superadmin"}


# ── Platform Stats ────────────────────────────────────────────────────
@app.get("/stats", response_model=PlatformStats)
async def get_stats(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    mem = psutil.virtual_memory()
    db_size_mb = 0.0
    try:
        if settings.USE_SQLITE and os.path.exists(settings.EASM_SQLITE_PATH):
            db_size_mb = os.path.getsize(settings.EASM_SQLITE_PATH) / (1024 * 1024)
        elif not settings.USE_SQLITE:
            with engine.connect() as conn:
                r = conn.execute(text("SELECT pg_database_size(current_database())"))
                db_size_mb = (r.scalar() or 0) / (1024 * 1024)
    except Exception:
        pass

    return PlatformStats(
        users_total=_count(db, "users"),
        users_active=_count(db, "users", _col("users", "is_active") == True),
        users_locked=_count(db, "users", _col("users", "locked_until") != None),
        orgs_total=_count(db, "organizations"),
        orgs_active=_count(db, "organizations", _col("organizations", "is_active") == True),
        projects_total=_count(db, "projects"),
        scans_total=_count(db, "scans"),
        scans_running=_count(db, "scans", _col("scans", "status").in_(["running", "pending"])),
        scans_completed=_count(db, "scans", _col("scans", "status") == "completed"),
        scans_failed=_count(db, "scans", _col("scans", "status") == "failed"),
        subdomains_total=_count(db, "subdomains"),
        ports_total=_count(db, "ports"),
        vulns_total=_count(db, "vulnerabilities"),
        vulns_critical=_count(db, "vulnerabilities", _col("vulnerabilities", "severity") == "critical"),
        vulns_high=_count(db, "vulnerabilities", _col("vulnerabilities", "severity") == "high"),
        vulns_medium=_count(db, "vulnerabilities", _col("vulnerabilities", "severity") == "medium"),
        vulns_low=_count(db, "vulnerabilities", _col("vulnerabilities", "severity") == "low"),
        vulns_info=_count(db, "vulnerabilities", _col("vulnerabilities", "severity") == "info"),
        notifications_total=_count(db, "notifications"),
        sessions_active=_count(db, "user_sessions", _col("user_sessions", "is_active") == True),
        scopes_total=_count(db, "authorized_scopes"),
        assets_total=_count(db, "assets"),
        reports_total=_count(db, "reports"),
        api_keys_total=_count(db, "api_keys"),
        audit_events_total=_count(db, "audit_events"),
        db_size_mb=round(db_size_mb, 2),
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=mem.percent,
        memory_used_mb=round(mem.used / (1024**2), 1),
        uptime_seconds=round(time.time() - _start_time, 1),
        scan_history_total=_count(db, "scan_history"),
    )


# ── System Health ──────────────────────────────────────────────────────
@app.get("/health", response_model=SystemHealth)
async def get_health(admin: str = Depends(require_admin)):
    db_info = check_db_health()
    redis_status = "not_configured"
    try:
        import redis as r
        client = r.from_url("redis://localhost:6379/0", socket_connect_timeout=2)
        client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unavailable"

    disk = psutil.disk_usage("/")
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_freq = psutil.cpu_freq()
    load = psutil.getloadavg()
    net = psutil.net_io_counters()
    procs = len(psutil.pids())

    return SystemHealth(
        database=db_info["status"],
        database_pool_size=db_info.get("pool_size", 0),
        database_pool_checked_out=db_info.get("checked_out", 0),
        redis=redis_status,
        disk_usage_percent=round(disk.percent, 1),
        disk_free_gb=round(disk.free / (1024**3), 1),
        cpu_count=psutil.cpu_count() or 0,
        memory_total_mb=round(mem.total / (1024**2), 1),
        env=settings.ENVIRONMENT,
        use_sqlite=settings.USE_SQLITE,
        uptime_seconds=round(time.time() - _start_time, 1),
        cpu_freq_mhz=round(cpu_freq.current, 0) if cpu_freq else 0,
        load_avg_1m=round(load[0], 2),
        swap_total_mb=round(swap.total / (1024**2), 1),
        swap_used_mb=round(swap.used / (1024**2), 1),
        net_bytes_sent=net.bytes_sent,
        net_bytes_recv=net.bytes_recv,
        processes_count=procs,
    )


# ── Users ──────────────────────────────────────────────────────────────
@app.get("/users", response_model=List[UserRow])
async def list_users(
    skip: int = 0, limit: int = 200, search: Optional[str] = None,
    role: Optional[str] = None, is_active: Optional[bool] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "users" not in _table_names(db):
        return []
    t = _get_table("users")
    q = db.query(t)
    if search:
        q = q.filter(t.c.email.ilike(f"%{search}%") | t.c.full_name.ilike(f"%{search}%"))
    if role:
        q = q.filter(t.c.role == role)
    if is_active is not None:
        q = q.filter(t.c.is_active == is_active)
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [UserRow(
        id=r.id, email=r.email, full_name=r.full_name, role=r.role,
        is_active=r.is_active, email_verified=getattr(r, 'email_verified', False),
        totp_enabled=getattr(r, 'totp_enabled', False),
        mfa_enforced=getattr(r, 'mfa_enforced', False),
        organization_id=getattr(r, 'organization_id', None),
        failed_login_attempts=getattr(r, 'failed_login_attempts', 0) or 0,
        locked_until=str(getattr(r, 'locked_until', None)) if getattr(r, 'locked_until', None) else None,
        created_at=str(r.created_at), last_login=str(getattr(r, 'last_login', None)) if getattr(r, 'last_login', None) else None,
        api_key=getattr(r, 'api_key', None),
    ) for r in rows]


@app.put("/users/{user_id}/disable")
async def disable_user(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    db.execute(t.update().where(t.c.id == user_id).values(is_active=False))
    db.commit()
    return {"message": "User disabled"}


@app.put("/users/{user_id}/enable")
async def enable_user(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    db.execute(t.update().where(t.c.id == user_id).values(is_active=True, failed_login_attempts=0, locked_until=None))
    db.commit()
    return {"message": "User enabled"}


@app.put("/users/{user_id}/unlock")
async def unlock_user(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    db.execute(t.update().where(t.c.id == user_id).values(failed_login_attempts=0, locked_until=None))
    db.commit()
    return {"message": "User unlocked"}


@app.put("/users/{user_id}/role")
async def change_role(user_id: str, role: str = Query(...), db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if role not in ("member", "admin", "superuser"):
        raise HTTPException(400, "Invalid role")
    t = _get_table("users")
    db.execute(t.update().where(t.c.id == user_id).values(role=role))
    db.commit()
    return {"message": f"Role changed to {role}"}


@app.delete("/users/{user_id}/sessions")
async def revoke_sessions(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if "user_sessions" not in _table_names(db):
        return {"message": "Sessions table not found"}
    t = _get_table("user_sessions")
    db.execute(t.update().where(t.c.user_id == user_id).values(is_active=False))
    db.commit()
    return {"message": "All sessions revoked"}


@app.delete("/users/{user_id}")
async def delete_user(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    db.execute(t.delete().where(t.c.id == user_id))
    db.commit()
    return {"message": "User deleted"}


class UserProfileUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None

class PasswordReset(BaseModel):
    new_password: str


@app.get("/users/{user_id}")
async def get_user(user_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if "users" not in _table_names(db):
        raise HTTPException(404, "Users table not found")
    t = _get_table("users")
    row = db.query(t).filter(t.c.id == user_id).first()
    if not row:
        raise HTTPException(404, "User not found")
    org_name = None
    if getattr(row, 'organization_id', None) and "organizations" in _table_names(db):
        ot = _get_table("organizations")
        org = db.query(ot).filter(ot.c.id == row.organization_id).first()
        if org:
            org_name = org.name
    session_count = 0
    if "user_sessions" in _table_names(db):
        st = _get_table("user_sessions")
        session_count = db.query(func.count(st.c.id)).filter(st.c.user_id == user_id, st.c.is_active == True).scalar() or 0
    scan_count = 0
    if "scans" in _table_names(db):
        st = _get_table("scans")
        scan_count = db.query(func.count(st.c.id)).filter(st.c.created_by == user_id).scalar() or 0
    api_key_count = 0
    if "api_keys" in _table_names(db):
        at = _get_table("api_keys")
        api_key_count = db.query(func.count(at.c.id)).filter(at.c.user_id == user_id).scalar() or 0
    return {
        "id": row.id, "email": row.email, "full_name": row.full_name,
        "role": row.role, "is_active": row.is_active,
        "email_verified": getattr(row, 'email_verified', False),
        "totp_enabled": getattr(row, 'totp_enabled', False),
        "mfa_enforced": getattr(row, 'mfa_enforced', False),
        "organization_id": getattr(row, 'organization_id', None),
        "organization_name": org_name,
        "failed_login_attempts": getattr(row, 'failed_login_attempts', 0) or 0,
        "locked_until": str(getattr(row, 'locked_until', None)) if getattr(row, 'locked_until', None) else None,
        "created_at": str(row.created_at),
        "last_login": str(getattr(row, 'last_login', None)) if getattr(row, 'last_login', None) else None,
        "password_changed_at": str(getattr(row, 'password_changed_at', None)) if getattr(row, 'password_changed_at', None) else None,
        "token_version": getattr(row, 'token_version', 0),
        "session_count": session_count,
        "scan_count": scan_count,
        "api_key_count": api_key_count,
    }


@app.put("/users/{user_id}/profile")
async def update_user_profile(user_id: str, body: UserProfileUpdate, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    row = db.query(t).filter(t.c.id == user_id).first()
    if not row:
        raise HTTPException(404, "User not found")
    updates = {}
    if body.email is not None:
        existing = db.query(t).filter(t.c.email == body.email, t.c.id != user_id).first()
        if existing:
            raise HTTPException(400, "Email already in use")
        updates["email"] = body.email
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.role is not None:
        if body.role not in ("member", "admin", "superuser"):
            raise HTTPException(400, "Invalid role")
        updates["role"] = body.role
    if body.organization_id is not None:
        updates["organization_id"] = body.organization_id if body.organization_id else None
    if body.is_active is not None:
        updates["is_active"] = body.is_active
        if body.is_active:
            updates["failed_login_attempts"] = 0
            updates["locked_until"] = None
    if body.email_verified is not None:
        updates["email_verified"] = body.email_verified
    if updates:
        db.execute(t.update().where(t.c.id == user_id).values(**updates))
        db.commit()
    return {"message": "Profile updated", "fields_updated": list(updates.keys())}


@app.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, body: PasswordReset, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    t = _get_table("users")
    row = db.query(t).filter(t.c.id == user_id).first()
    if not row:
        raise HTTPException(404, "User not found")
    import bcrypt as bc
    hashed = bc.hashpw(body.new_password.encode("utf-8"), bc.gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc)
    db.execute(t.update().where(t.c.id == user_id).values(
        hashed_password=hashed,
        password_changed_at=now,
        failed_login_attempts=0,
        locked_until=None,
        token_version=getattr(row, 'token_version', 0) + 1,
    ))
    if "user_sessions" in _table_names(db):
        st = _get_table("user_sessions")
        db.execute(st.update().where(st.c.user_id == user_id).values(is_active=False))
    db.commit()
    return {"message": "Password reset successfully. All sessions revoked."}


@app.put("/users/{user_id}/mfa")
async def toggle_user_mfa(user_id: str, enforced: bool = Query(...), db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("users")
    row = db.query(t).filter(t.c.id == user_id).first()
    if not row:
        raise HTTPException(404, "User not found")
    db.execute(t.update().where(t.c.id == user_id).values(mfa_enforced=enforced))
    db.commit()
    return {"message": f"MFA {'enforced' if enforced else 'disabled'} for user"}


# ── Organizations ──────────────────────────────────────────────────────
@app.get("/organizations", response_model=List[OrgRow])
async def list_orgs(
    skip: int = 0, limit: int = 200, search: Optional[str] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "organizations" not in _table_names(db):
        return []
    t = _get_table("organizations")
    q = db.query(t)
    if search:
        q = q.filter(t.c.name.ilike(f"%{search}%") | t.c.slug.ilike(f"%{search}%"))
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for r in rows:
        uc = _count(db, "users", _col("users", "organization_id") == r.id)
        sc = _count(db, "scans", _col("scans", "organization_id") == r.id)
        pc = _count(db, "projects", _col("projects", "organization_id") == r.id)
        result.append(OrgRow(
            id=r.id, name=r.name, slug=r.slug, plan=r.plan,
            is_active=r.is_active, is_archived=getattr(r, 'is_archived', False),
            mfa_enforced=getattr(r, 'mfa_enforced', False),
            user_count=uc, scan_count=sc, project_count=pc,
            created_at=str(r.created_at),
        ))
    return result


@app.put("/organizations/{org_id}/toggle")
async def toggle_org(org_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("organizations")
    row = db.query(t).filter(t.c.id == org_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    new_val = not row.is_active
    db.execute(t.update().where(t.c.id == org_id).values(is_active=new_val))
    db.commit()
    return {"message": f"Organization {'enabled' if new_val else 'disabled'}"}


# ── Scans ──────────────────────────────────────────────────────────────
@app.get("/scans", response_model=List[ScanRow])
async def list_scans(
    skip: int = 0, limit: int = 200, status: Optional[str] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "scans" not in _table_names(db):
        return []
    t = _get_table("scans")
    q = db.query(t)
    if status:
        q = q.filter(t.c.status == status)
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [ScanRow(
        id=r.id, domain=r.domain, status=r.status, scan_type=r.scan_type,
        progress=r.progress, organization_id=getattr(r, 'organization_id', None),
        project_id=getattr(r, 'project_id', None),
        created_by=getattr(r, 'created_by', None),
        started_at=str(getattr(r, 'started_at', None)) if getattr(r, 'started_at', None) else None,
        completed_at=str(getattr(r, 'completed_at', None)) if getattr(r, 'completed_at', None) else None,
        error_message=getattr(r, 'error_message', None),
        created_at=str(r.created_at),
    ) for r in rows]


@app.delete("/scans/{scan_id}")
async def cancel_scan(scan_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("scans")
    db.execute(t.update().where(t.c.id == scan_id).values(status="failed", error_message="Cancelled by admin"))
    db.commit()
    return {"message": "Scan cancelled"}


# ── Scan History ───────────────────────────────────────────────────────
@app.get("/scan-history", response_model=List[ScanHistoryRow])
async def list_scan_history(
    skip: int = 0, limit: int = 200, domain: Optional[str] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "scan_history" not in _table_names(db):
        return []
    t = _get_table("scan_history")
    q = db.query(t)
    if domain:
        q = q.filter(t.c.domain.ilike(f"%{domain}%"))
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [ScanHistoryRow(
        id=r.id, domain=r.domain, scan_type=r.scan_type, status=r.status,
        triggered_by=getattr(r, 'triggered_by', 'manual'),
        subdomains_found=getattr(r, 'subdomains_found', 0) or 0,
        open_ports_found=getattr(r, 'open_ports_found', 0) or 0,
        technologies_found=getattr(r, 'technologies_found', 0) or 0,
        risk_score=getattr(r, 'risk_score', 0.0) or 0.0,
        risk_severity=getattr(r, 'risk_severity', None),
        duration_ms=getattr(r, 'duration_ms', None),
        created_at=str(r.created_at),
    ) for r in rows]


# ── Vulnerabilities ───────────────────────────────────────────────────
@app.get("/vulnerabilities", response_model=List[VulnerabilityRow])
async def list_vulns(
    skip: int = 0, limit: int = 200, severity: Optional[str] = None,
    status: Optional[str] = None, db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "vulnerabilities" not in _table_names(db):
        return []
    t = _get_table("vulnerabilities")
    q = db.query(t)
    if severity:
        q = q.filter(t.c.severity == severity)
    if status:
        q = q.filter(t.c.status == status)
    rows = q.order_by(t.c.found_at.desc()).offset(skip).limit(limit).all()
    return [VulnerabilityRow(
        id=r.id, scan_id=r.scan_id,
        subdomain_id=getattr(r, 'subdomain_id', None),
        name=r.name, severity=r.severity,
        vuln_type=getattr(r, 'vuln_type', None),
        host=r.host, status=r.status,
        matched_at=getattr(r, 'matched_at', None),
        organization_id=getattr(r, 'organization_id', None),
        assigned_to=getattr(r, 'assigned_to', None),
        found_at=str(r.found_at),
        first_seen=str(getattr(r, 'first_seen', r.found_at)),
        last_seen=str(getattr(r, 'last_seen', r.found_at)),
    ) for r in rows]


# ── Assets ─────────────────────────────────────────────────────────────
@app.get("/assets", response_model=List[AssetRow])
async def list_assets(
    skip: int = 0, limit: int = 200, asset_type: Optional[str] = None,
    search: Optional[str] = None, db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "assets" not in _table_names(db):
        return []
    t = _get_table("assets")
    q = db.query(t)
    if asset_type:
        q = q.filter(t.c.asset_type == asset_type)
    if search:
        q = q.filter(t.c.value.ilike(f"%{search}%"))
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [AssetRow(
        id=r.id, organization_id=r.organization_id, asset_type=r.asset_type,
        value=r.value, label=getattr(r, 'label', None),
        is_alive=getattr(r, 'is_alive', True),
        inventory_status=getattr(r, 'inventory_status', 'discovered'),
        confirmed=getattr(r, 'confirmed', False),
        first_seen=str(getattr(r, 'first_seen', '')),
        last_seen=str(getattr(r, 'last_seen', '')),
    ) for r in rows]


# ── Notifications ──────────────────────────────────────────────────────
@app.get("/notifications", response_model=List[NotificationRow])
async def list_notifications(
    skip: int = 0, limit: int = 200, unread_only: bool = False,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "notifications" not in _table_names(db):
        return []
    t = _get_table("notifications")
    q = db.query(t)
    if unread_only:
        q = q.filter(t.c.read == False)
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [NotificationRow(
        id=r.id, user_id=r.user_id, type=r.type, title=r.title,
        message=r.message, priority=r.priority, channel=r.channel,
        read=r.read, email_sent=getattr(r, 'email_sent', False),
        created_at=str(r.created_at),
    ) for r in rows]


@app.put("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("notifications")
    db.execute(t.update().where(t.c.id == notif_id).values(read=True))
    db.commit()
    return {"message": "Marked as read"}


@app.put("/notifications/mark-all-read")
async def mark_all_read(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("notifications")
    db.execute(t.update().where(t.c.read == False).values(read=True))
    db.commit()
    return {"message": "All notifications marked as read"}


# ── Audit Events ───────────────────────────────────────────────────────
@app.get("/audit-events", response_model=List[AuditEventRow])
async def list_audit_events(
    skip: int = 0, limit: int = 200, action: Optional[str] = None,
    actor_type: Optional[str] = None, status_filter: Optional[str] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "audit_events" not in _table_names(db):
        return []
    t = _get_table("audit_events")
    q = db.query(t)
    if action:
        q = q.filter(t.c.action.ilike(f"%{action}%"))
    if actor_type:
        q = q.filter(t.c.actor_type == actor_type)
    if status_filter:
        q = q.filter(t.c.status == status_filter)
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [AuditEventRow(
        id=r.id, action=r.action,
        organization_id=getattr(r, 'organization_id', None),
        actor_id=getattr(r, 'actor_id', None),
        actor_type=getattr(r, 'actor_type', 'user'),
        target_type=getattr(r, 'target_type', None),
        target_id=getattr(r, 'target_id', None),
        status=getattr(r, 'status', 'success'),
        detail=getattr(r, 'detail', None),
        created_at=str(r.created_at),
    ) for r in rows]


# ── Sessions ───────────────────────────────────────────────────────────
@app.get("/sessions", response_model=List[SessionRow])
async def list_sessions(
    skip: int = 0, limit: int = 200, active_only: bool = True,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "user_sessions" not in _table_names(db):
        return []
    t = _get_table("user_sessions")
    q = db.query(t)
    if active_only:
        q = q.filter(t.c.is_active == True)
    rows = q.order_by(t.c.last_activity.desc()).offset(skip).limit(limit).all()
    return [SessionRow(
        id=r.id, user_id=r.user_id,
        browser=getattr(r, 'browser', None),
        os=getattr(r, 'os', None),
        ip_address=getattr(r, 'ip_address', None),
        location_city=getattr(r, 'location_city', None),
        location_country=getattr(r, 'location_country', None),
        is_trusted=getattr(r, 'is_trusted', False),
        is_active=r.is_active,
        last_activity=str(getattr(r, 'last_activity', '')),
        created_at=str(r.created_at),
        expires_at=str(getattr(r, 'expires_at', None)) if getattr(r, 'expires_at', None) else None,
    ) for r in rows]


@app.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("user_sessions")
    db.execute(t.update().where(t.c.id == session_id).values(is_active=False))
    db.commit()
    return {"message": "Session revoked"}


@app.delete("/sessions")
async def revoke_all_sessions(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("user_sessions")
    db.execute(t.update().where(t.c.is_active == True).values(is_active=False))
    db.commit()
    return {"message": "All sessions revoked"}


# ── API Keys ───────────────────────────────────────────────────────────
@app.get("/api-keys", response_model=List[ApiKeyRow])
async def list_api_keys(
    skip: int = 0, limit: int = 200,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "api_keys" not in _table_names(db):
        return []
    t = _get_table("api_keys")
    rows = db.query(t).order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [ApiKeyRow(
        id=r.id, user_id=r.user_id,
        organization_id=getattr(r, 'organization_id', None),
        name=r.name, prefix=r.prefix,
        scopes=getattr(r, 'scopes', None),
        is_active=r.is_active,
        last_used_at=str(getattr(r, 'last_used_at', None)) if getattr(r, 'last_used_at', None) else None,
        last_used_ip=getattr(r, 'last_used_ip', None),
        created_at=str(r.created_at),
        expires_at=str(getattr(r, 'expires_at', None)) if getattr(r, 'expires_at', None) else None,
    ) for r in rows]


@app.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("api_keys")
    db.execute(t.update().where(t.c.id == key_id).values(is_active=False))
    db.commit()
    return {"message": "API key revoked"}


# ── Feature Flags ──────────────────────────────────────────────────────
@app.get("/feature-flags", response_model=List[FeatureFlagRow])
async def list_feature_flags(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if "feature_flags" not in _table_names(db):
        return []
    t = _get_table("feature_flags")
    rows = db.query(t).order_by(t.c.created_at.desc()).all()
    return [FeatureFlagRow(
        id=r.id, key=r.key, name=r.name,
        description=getattr(r, 'description', None),
        enabled=r.enabled,
        allowed_plans=getattr(r, 'allowed_plans', None),
        created_at=str(r.created_at),
    ) for r in rows]


@app.put("/feature-flags/{flag_id}/toggle")
async def toggle_feature_flag(flag_id: str, db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    t = _get_table("feature_flags")
    row = db.query(t).filter(t.c.id == flag_id).first()
    if not row:
        raise HTTPException(404, "Feature flag not found")
    new_val = not row.enabled
    db.execute(t.update().where(t.c.id == flag_id).values(enabled=new_val))
    db.commit()
    return {"message": f"Feature flag {'enabled' if new_val else 'disabled'}"}


# ── Roles ──────────────────────────────────────────────────────────────
@app.get("/roles", response_model=List[RoleRow])
async def list_roles(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    if "roles" not in _table_names(db):
        return []
    t = _get_table("roles")
    rows = db.query(t).order_by(t.c.created_at.desc()).all()
    return [RoleRow(
        id=r.id, organization_id=getattr(r, 'organization_id', None),
        name=r.name, slug=r.slug,
        description=getattr(r, 'description', None),
        permissions=getattr(r, 'permissions', None),
        is_system=getattr(r, 'is_system', False),
        is_default=getattr(r, 'is_default', False),
        created_at=str(r.created_at),
    ) for r in rows]


# ── Invitations ────────────────────────────────────────────────────────
@app.get("/invitations", response_model=List[InvitationRow])
async def list_invitations(
    skip: int = 0, limit: int = 200, status_filter: Optional[str] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "invitations" not in _table_names(db):
        return []
    t = _get_table("invitations")
    q = db.query(t)
    if status_filter:
        q = q.filter(t.c.status == status_filter)
    rows = q.order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [InvitationRow(
        id=r.id, email=r.email, invited_by=r.invited_by,
        organization_id=r.organization_id, role=r.role,
        status=r.status, created_at=str(r.created_at),
        expires_at=str(r.expires_at),
    ) for r in rows]


# ── Reports ────────────────────────────────────────────────────────────
@app.get("/reports", response_model=List[ReportRow])
async def list_reports(
    skip: int = 0, limit: int = 200,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "reports" not in _table_names(db):
        return []
    t = _get_table("reports")
    rows = db.query(t).order_by(t.c.generated_at.desc()).offset(skip).limit(limit).all()
    return [ReportRow(
        id=r.id, scan_id=r.scan_id, format=r.format,
        file_size=getattr(r, 'file_size', None),
        generated_by=getattr(r, 'generated_by', None),
        generated_at=str(r.generated_at),
    ) for r in rows]


# ── Auth Audit Logs ────────────────────────────────────────────────────
@app.get("/auth-audit")
async def list_auth_audit(
    skip: int = 0, limit: int = 200,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "auth_audit_logs" not in _table_names(db):
        return []
    t = _get_table("auth_audit_logs")
    rows = db.query(t).order_by(t.c.created_at.desc()).offset(skip).limit(limit).all()
    return [{
        "id": r.id,
        "user_id": getattr(r, 'user_id', None),
        "event_type": r.event_type,
        "event_detail": getattr(r, 'event_detail', None),
        "ip_address": getattr(r, 'ip_address', None),
        "success": getattr(r, 'success', True),
        "created_at": str(r.created_at),
    } for r in rows]


# ── System Processes ───────────────────────────────────────────────────
@app.get("/system/processes")
async def list_processes(admin: str = Depends(require_admin)):
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status', 'create_time']):
        try:
            info = p.info
            procs.append(ProcessInfo(
                pid=info['pid'],
                name=info['name'] or "unknown",
                cpu_percent=info['cpu_percent'] or 0.0,
                memory_mb=round((info['memory_info'].rss / (1024**2)) if info['memory_info'] else 0, 1),
                status=info['status'] or "unknown",
                created_at=str(datetime.fromtimestamp(info['create_time'], tz=timezone.utc)) if info['create_time'] else None,
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.memory_mb, reverse=True)
    return procs[:100]


# ── Database Stats ────────────────────────────────────────────────────
@app.get("/database/stats")
async def db_stats(db: DBSession = Depends(get_db), admin: str = Depends(require_admin)):
    tables = _table_names(db)
    counts = {}
    for name in tables:
        try:
            t = _get_table(name)
            counts[name] = db.query(func.count(t.c.id)).scalar() or 0
        except Exception:
            counts[name] = -1
    return counts


@app.get("/database/table/{table_name}")
async def db_table_schema(table_name: str, admin: str = Depends(require_admin)):
    tables = _table_names(None)
    if table_name not in tables:
        raise HTTPException(404, f"Table '{table_name}' not found")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = []
    for col in inspector.get_columns(table_name):
        columns.append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "default": str(col.get("default", "")) if col.get("default") else None,
        })
    pk = inspector.get_pk_constraint(table_name)
    indexes = inspector.get_indexes(table_name)
    fks = inspector.get_foreign_keys(table_name)
    return {
        "table": table_name,
        "columns": columns,
        "primary_key": pk,
        "indexes": [{"name": i["name"], "columns": i["column_names"]} for i in indexes],
        "foreign_keys": [{"constrained_columns": fk["constrained_columns"], "referred_table": fk["referred_table"]} for fk in fks],
    }


# ── Notifications ──────────────────────────────────────────────────────
@app.post("/notifications/broadcast")
async def broadcast_notification(
    title: str = Query(...), message: str = Query(...), priority: str = Query("normal"),
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "notifications" not in _table_names(db):
        return {"message": "Notifications table not found"}
    t = _get_table("notifications")
    import uuid
    notif_id = str(uuid.uuid4())
    users = []
    if "users" in _table_names(db):
        ut = _get_table("users")
        users = db.query(ut.c.id).filter(ut.c.is_active == True).all()
    now = datetime.now(timezone.utc)
    for u in users:
        db.execute(t.insert().values(
            id=str(uuid.uuid4()), user_id=u.id, type="admin_broadcast",
            title=title, message=message, priority=priority,
            channel="in_app", read=False, email_sent=False, created_at=now,
        ))
    db.commit()
    return {"message": f"Broadcast sent to {len(users)} users"}


# ── Platform Logs ────────────────────────────────────────────────────
class PlatformLogRow(BaseModel):
    id: str
    category: str
    severity: str
    message: str
    detail: Optional[Dict[str, Any]] = None
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    client_ip: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    created_at: str


class LogSummary(BaseModel):
    errors_24h: int = 0
    security_24h: int = 0
    total_24h: int = 0
    orgs_active_24h: int = 0
    top_error_types: List[Dict[str, Any]] = []
    critical_events: List[Dict[str, Any]] = []


@app.get("/platform-logs/summary", response_model=LogSummary)
async def platform_log_summary(
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "platform_logs" not in _table_names(db):
        return LogSummary()
    t = _get_table("platform_logs")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    base = db.query(t).filter(t.c.created_at >= cutoff)

    errors_24h = base.filter(t.c.severity.in_(["error", "critical"])).count()
    security_24h = base.filter(t.c.category == "security_event").count()
    total_24h = base.count()

    orgs_q = db.query(func.count(func.distinct(t.c.organization_id))).filter(
        t.c.created_at >= cutoff, t.c.organization_id.isnot(None)
    )
    orgs_active_24h = orgs_q.scalar() or 0

    top_errors = (
        db.query(t.c.message, func.count(t.c.id).label("cnt"))
        .filter(t.c.created_at >= cutoff, t.c.severity.in_(["error", "critical"]))
        .group_by(t.c.message)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )

    critical_rows = (
        db.query(t)
        .filter(t.c.created_at >= cutoff, t.c.severity == "critical")
        .order_by(desc(t.c.created_at))
        .limit(10)
        .all()
    )

    return LogSummary(
        errors_24h=errors_24h,
        security_24h=security_24h,
        total_24h=total_24h,
        orgs_active_24h=orgs_active_24h,
        top_error_types=[{"message": m, "count": c} for m, c in top_errors],
        critical_events=[
            {"id": r.id, "category": r.category, "message": r.message, "created_at": str(r.created_at)}
            for r in critical_rows
        ],
    )


@app.get("/platform-logs", response_model=List[PlatformLogRow])
async def list_platform_logs(
    skip: int = 0, limit: int = 200,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    search: Optional[str] = None,
    hours: Optional[int] = None,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "platform_logs" not in _table_names(db):
        return []
    t = _get_table("platform_logs")
    q = db.query(t)
    if category:
        q = q.filter(t.c.category == category)
    if severity:
        q = q.filter(t.c.severity == severity)
    if organization_id:
        q = q.filter(t.c.organization_id == organization_id)
    if user_id:
        q = q.filter(t.c.user_id == user_id)
    if search:
        q = q.filter(t.c.message.ilike(f"%{search}%"))
    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = q.filter(t.c.created_at >= cutoff)
    rows = q.order_by(desc(t.c.created_at)).offset(skip).limit(limit).all()
    return [PlatformLogRow(
        id=r.id, category=r.category, severity=r.severity, message=r.message,
        detail=getattr(r, 'detail', None),
        organization_id=getattr(r, 'organization_id', None),
        user_id=getattr(r, 'user_id', None),
        request_id=getattr(r, 'request_id', None),
        client_ip=getattr(r, 'client_ip', None),
        path=getattr(r, 'path', None),
        method=getattr(r, 'method', None),
        status_code=getattr(r, 'status_code', None),
        duration_ms=getattr(r, 'duration_ms', None),
        related_entity_type=getattr(r, 'related_entity_type', None),
        related_entity_id=getattr(r, 'related_entity_id', None),
        created_at=str(r.created_at),
    ) for r in rows]


@app.get("/platform-logs/{log_id}", response_model=PlatformLogRow)
async def get_platform_log(
    log_id: str,
    db: DBSession = Depends(get_db), admin: str = Depends(require_admin),
):
    if "platform_logs" not in _table_names(db):
        raise HTTPException(404, "Platform logs table not found")
    t = _get_table("platform_logs")
    r = db.query(t).filter(t.c.id == log_id).first()
    if not r:
        raise HTTPException(404, "Log entry not found")
    return PlatformLogRow(
        id=r.id, category=r.category, severity=r.severity, message=r.message,
        detail=getattr(r, 'detail', None),
        organization_id=getattr(r, 'organization_id', None),
        user_id=getattr(r, 'user_id', None),
        request_id=getattr(r, 'request_id', None),
        client_ip=getattr(r, 'client_ip', None),
        path=getattr(r, 'path', None),
        method=getattr(r, 'method', None),
        status_code=getattr(r, 'status_code', None),
        duration_ms=getattr(r, 'duration_ms', None),
        related_entity_type=getattr(r, 'related_entity_type', None),
        related_entity_id=getattr(r, 'related_entity_id', None),
        created_at=str(r.created_at),
    )


# ── Blockchain ────────────────────────────────────────────────────────
class ChainProviderRow(BaseModel):
    name: str
    chain: str
    chain_id: Optional[int] = None
    native_symbol: str
    api_source: str
    has_api_key: bool
    supports_wallet: bool
    supports_transactions: bool
    supports_contracts: bool
    supports_tokens: bool
    supports_graph: bool

class OFACEntryRow(BaseModel):
    address: str
    entity_name: str
    category: str
    source: str
    reason: str
    confidence: int

class CuratedLabelRow(BaseModel):
    chain: str
    address: str
    entity_name: str
    category: str
    confidence: int
    evidence_count: int

class BlockchainStats(BaseModel):
    providers_total: int
    chains_supported: int
    ofac_entries: int
    curated_labels: int
    watches_total: int
    alerts_total: int
    alerts_unacknowledged: int
    cases_total: int
    cases_open: int
    travel_rule_records: int
    compliance_configs: int

class WatchRow(BaseModel):
    id: str
    organization_id: Optional[str]
    user_id: Optional[str]
    address: str
    chain: str
    alert_on_new_tx: bool
    alert_on_risk_change: bool
    risk_threshold: Optional[int]
    is_active: bool
    created_at: str

class AlertRow(BaseModel):
    id: str
    watch_id: Optional[str]
    organization_id: Optional[str]
    user_id: Optional[str]
    address: str
    chain: str
    alert_type: str
    title: str
    message: Optional[str]
    severity: str
    acknowledged: bool
    acknowledged_by: Optional[str]
    created_at: str

class CaseRow(BaseModel):
    id: str
    organization_id: Optional[str]
    title: str
    description: Optional[str]
    status: str
    created_by: Optional[str]
    assigned_to: Optional[str]
    created_at: str
    updated_at: Optional[str]

class TravelRuleRecordRow(BaseModel):
    id: str
    organization_id: Optional[str]
    chain: str
    tx_hash: str
    from_address: str
    to_address: str
    amount: Optional[str]
    amount_usd: Optional[float]
    status: str
    compliance_score: Optional[int]
    jurisdiction: Optional[str]
    checked_at: Optional[str]


def _import_blockchain_services():
    """Import blockchain services from the main EASM backend."""
    import sys
    import importlib
    main_backend = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend")
    main_backend = os.path.normpath(main_backend)
    if main_backend not in sys.path:
        sys.path.insert(0, main_backend)
    return main_backend


@app.get("/blockchain/providers", response_model=List[ChainProviderRow])
async def list_blockchain_providers(admin: str = Depends(require_admin)):
    try:
        _import_blockchain_services()
        from app.services.blockchain.providers import registry
        providers = []
        for name, p in registry._providers.items():
            cap = p.capabilities if hasattr(p, "capabilities") else {}
            providers.append(ChainProviderRow(
                name=name,
                chain=p.chain.value if hasattr(p.chain, "value") else str(p.chain),
                chain_id=getattr(p, "chain_id", None),
                native_symbol=getattr(p, "native_symbol", "?"),
                api_source=getattr(p, "base_url", getattr(p, "api_source", "unknown")),
                has_api_key=bool(getattr(p, "api_key", None)),
                supports_wallet=cap.get("wallet", False) if isinstance(cap, dict) else True,
                supports_transactions=cap.get("transactions", False) if isinstance(cap, dict) else True,
                supports_contracts=cap.get("contracts", False) if isinstance(cap, dict) else True,
                supports_tokens=cap.get("tokens", False) if isinstance(cap, dict) else True,
                supports_graph=cap.get("graph", False) if isinstance(cap, dict) else False,
            ))
        return providers
    except Exception as e:
        return [ChainProviderRow(
            name="error", chain="unknown", native_symbol="?", api_source=str(e)[:200],
            has_api_key=False, supports_wallet=False, supports_transactions=False,
            supports_contracts=False, supports_tokens=False, supports_graph=False,
        )]


@app.get("/blockchain/ofac", response_model=List[OFACEntryRow])
async def list_ofac_entries(admin: str = Depends(require_admin)):
    try:
        _import_blockchain_services()
        from app.services.blockchain.intel import _OFAC_ADDRESSES
        return [OFACEntryRow(
            address=addr,
            entity_name=info.get("entity_name", ""),
            category=info.get("category", "unknown").value if hasattr(info.get("category", ""), "value") else str(info.get("category", "")),
            source=info.get("source", "ofac_sdn"),
            reason=info.get("reason", ""),
            confidence=info.get("confidence", 100),
        ) for addr, info in _OFAC_ADDRESSES.items()]
    except Exception:
        return []


@app.get("/blockchain/labels", response_model=List[CuratedLabelRow])
async def list_curated_labels(
    chain: Optional[str] = None,
    admin: str = Depends(require_admin),
):
    try:
        _import_blockchain_services()
        from app.services.blockchain.labels.curated import get_curated_labels
        labels = get_curated_labels(chain=chain)
        return [CuratedLabelRow(
            chain=l.chain.value if hasattr(l.chain, "value") else str(l.chain),
            address=l.address,
            entity_name=l.entity_name,
            category=l.category.value if hasattr(l.category, "value") else str(l.category),
            confidence=l.confidence,
            evidence_count=len(l.evidence) if l.evidence else 0,
        ) for l in labels]
    except Exception:
        return []


@app.get("/blockchain/stats", response_model=BlockchainStats)
async def blockchain_stats(
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    providers_count = 0
    chains_set = set()
    ofac_count = 0
    labels_count = 0
    try:
        _import_blockchain_services()
        from app.services.blockchain.providers import registry
        providers_count = len(registry._providers)
        for p in registry._providers.values():
            c = p.chain.value if hasattr(p.chain, "value") else str(p.chain)
            chains_set.add(c)
    except Exception:
        pass
    try:
        _import_blockchain_services()
        from app.services.blockchain.intel import _OFAC_ADDRESSES
        ofac_count = len(_OFAC_ADDRESSES)
    except Exception:
        pass
    try:
        _import_blockchain_services()
        from app.services.blockchain.labels.curated import get_curated_labels
        labels_count = len(get_curated_labels())
    except Exception:
        pass

    watches_total = _count(db, "blockchain_watches") if "blockchain_watches" in _table_names(db) else 0
    alerts_total = _count(db, "blockchain_alerts") if "blockchain_alerts" in _table_names(db) else 0
    alerts_unack = 0
    if "blockchain_alerts" in _table_names(db):
        t = _get_table("blockchain_alerts")
        alerts_unack = db.query(func.count(t.c.id)).filter(t.c.acknowledged == False).scalar() or 0
    cases_total = _count(db, "blockchain_cases") if "blockchain_cases" in _table_names(db) else 0
    cases_open = 0
    if "blockchain_cases" in _table_names(db):
        t = _get_table("blockchain_cases")
        cases_open = db.query(func.count(t.c.id)).filter(t.c.status == "open").scalar() or 0
    travel_rule_count = _count(db, "travel_rule_records") if "travel_rule_records" in _table_names(db) else 0
    compliance_count = _count(db, "compliance_config") if "compliance_config" in _table_names(db) else 0

    return BlockchainStats(
        providers_total=providers_count,
        chains_supported=len(chains_set),
        ofac_entries=ofac_count,
        curated_labels=labels_count,
        watches_total=watches_total,
        alerts_total=alerts_total,
        alerts_unacknowledged=alerts_unack,
        cases_total=cases_total,
        cases_open=cases_open,
        travel_rule_records=travel_rule_count,
        compliance_configs=compliance_count,
    )


@app.get("/blockchain/watches", response_model=List[WatchRow])
async def list_blockchain_watches(
    skip: int = 0, limit: int = 200,
    chain: Optional[str] = None,
    organization_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if "blockchain_watches" not in _table_names(db):
        return []
    t = _get_table("blockchain_watches")
    q = db.query(t)
    if chain:
        q = q.filter(t.c.chain == chain)
    if organization_id:
        q = q.filter(t.c.organization_id == organization_id)
    rows = q.order_by(desc(t.c.created_at)).offset(skip).limit(limit).all()
    return [WatchRow(
        id=r.id,
        organization_id=getattr(r, "organization_id", None),
        user_id=getattr(r, "user_id", None),
        address=r.address,
        chain=r.chain,
        alert_on_new_tx=getattr(r, "alert_on_new_tx", True),
        alert_on_risk_change=getattr(r, "alert_on_risk_change", True),
        risk_threshold=getattr(r, "risk_threshold", None),
        is_active=getattr(r, "is_active", True),
        created_at=str(r.created_at),
    ) for r in rows]


@app.get("/blockchain/alerts", response_model=List[AlertRow])
async def list_blockchain_alerts(
    skip: int = 0, limit: int = 200,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    chain: Optional[str] = None,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if "blockchain_alerts" not in _table_names(db):
        return []
    t = _get_table("blockchain_alerts")
    q = db.query(t)
    if severity:
        q = q.filter(t.c.severity == severity)
    if acknowledged is not None:
        q = q.filter(t.c.acknowledged == acknowledged)
    if chain:
        q = q.filter(t.c.chain == chain)
    rows = q.order_by(desc(t.c.created_at)).offset(skip).limit(limit).all()
    return [AlertRow(
        id=r.id,
        watch_id=getattr(r, "watch_id", None),
        organization_id=getattr(r, "organization_id", None),
        user_id=getattr(r, "user_id", None),
        address=r.address,
        chain=r.chain,
        alert_type=r.alert_type,
        title=r.title,
        message=getattr(r, "message", None),
        severity=r.severity,
        acknowledged=getattr(r, "acknowledged", False),
        acknowledged_by=getattr(r, "acknowledged_by", None),
        created_at=str(r.created_at),
    ) for r in rows]


@app.put("/blockchain/alerts/{alert_id}/acknowledge")
async def acknowledge_blockchain_alert(
    alert_id: str,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if "blockchain_alerts" not in _table_names(db):
        raise HTTPException(404, "Alerts table not found")
    t = _get_table("blockchain_alerts")
    row = db.query(t).filter(t.c.id == alert_id).first()
    if not row:
        raise HTTPException(404, "Alert not found")
    db.execute(t.update().where(t.c.id == alert_id).values(
        acknowledged=True, acknowledged_by=admin, acknowledged_at=datetime.now(timezone.utc)
    ))
    db.commit()
    return {"message": "Alert acknowledged"}


@app.get("/blockchain/cases", response_model=List[CaseRow])
async def list_blockchain_cases(
    skip: int = 0, limit: int = 200,
    status: Optional[str] = None,
    organization_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if "blockchain_cases" not in _table_names(db):
        return []
    t = _get_table("blockchain_cases")
    q = db.query(t)
    if status:
        q = q.filter(t.c.status == status)
    if organization_id:
        q = q.filter(t.c.organization_id == organization_id)
    rows = q.order_by(desc(t.c.created_at)).offset(skip).limit(limit).all()
    return [CaseRow(
        id=r.id,
        organization_id=getattr(r, "organization_id", None),
        title=r.title,
        description=getattr(r, "description", None),
        status=r.status,
        created_by=getattr(r, "created_by", None),
        assigned_to=getattr(r, "assigned_to", None),
        created_at=str(r.created_at),
        updated_at=str(getattr(r, "updated_at", "")),
    ) for r in rows]


@app.get("/blockchain/travel-rule", response_model=List[TravelRuleRecordRow])
async def list_travel_rule_records(
    skip: int = 0, limit: int = 200,
    status: Optional[str] = None,
    chain: Optional[str] = None,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if "travel_rule_records" not in _table_names(db):
        return []
    t = _get_table("travel_rule_records")
    q = db.query(t)
    if status:
        q = q.filter(t.c.status == status)
    if chain:
        q = q.filter(t.c.chain == chain)
    rows = q.order_by(desc(t.c.checked_at)).offset(skip).limit(limit).all()
    return [TravelRuleRecordRow(
        id=r.id,
        organization_id=getattr(r, "organization_id", None),
        chain=r.chain,
        tx_hash=r.tx_hash,
        from_address=r.from_address,
        to_address=r.to_address,
        amount=getattr(r, "amount", None),
        amount_usd=getattr(r, "amount_usd", None),
        status=r.status,
        compliance_score=getattr(r, "compliance_score", None),
        jurisdiction=getattr(r, "jurisdiction", None),
        checked_at=str(getattr(r, "checked_at", "")),
    ) for r in rows]


# ── Support Chat (Admin) ──────────────────────────────────────────────
#
# The customer side lives in the main API (backend/app/api/v1/support.py).
# Queries here use SQLAlchemy expressions rather than raw SQL so they behave
# the same on Postgres and SQLite (``is_read = 0`` fails on a Postgres boolean).

SUPPORT_MAX_MESSAGE_LENGTH = 4000
SUPPORT_STATUSES = ("open", "closed")
# Same rule as the customer API: plain text, no control or invisible characters.
import re as _re  # noqa: E402
_SUPPORT_UNSAFE_CHARS = _re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]"
)


class SupportReply(BaseModel):
    message: str


class SupportStatusUpdate(BaseModel):
    status: str


def _support_tables(db):
    tables = _table_names(db)
    if "support_conversations" not in tables or "support_messages" not in tables:
        return None, None, None, None
    return (
        _get_table("support_conversations"),
        _get_table("support_messages"),
        _get_table("users") if "users" in tables else None,
        _get_table("organizations") if "organizations" in tables else None,
    )


def _support_ts(value) -> Optional[str]:
    """Timestamps are stored as naive UTC; send ISO 8601 with an offset."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _support_unread_filter(msg_t):
    """Customer messages the team has not opened yet (NULL counts as unread)."""
    return (msg_t.c.sender_type == "user") & (msg_t.c.is_read.isnot(True))


def _support_customer(r, users_t, orgs_t, db) -> dict:
    """Who a conversation is with: an account holder or a website visitor."""
    info = {"user_name": "Unknown", "user_email": None, "organization": None, "is_guest": False}
    if r.user_id is None:
        email = getattr(r, "guest_email", None)
        info.update(
            user_name=getattr(r, "guest_name", None) or email or "Website visitor",
            user_email=email,
            is_guest=True,
        )
        return info
    if users_t is None:
        return info
    u = db.query(users_t).filter(users_t.c.id == r.user_id).first()
    if not u:
        return info
    email = getattr(u, "email", None)
    info.update(user_name=getattr(u, "full_name", None) or email or "Unknown", user_email=email)
    org_id = getattr(r, "organization_id", None) or getattr(u, "organization_id", None)
    if org_id and orgs_t is not None:
        o = db.query(orgs_t).filter(orgs_t.c.id == org_id).first()
        if o:
            info["organization"] = getattr(o, "name", None)
    return info


@app.get("/support/conversations")
async def admin_list_support_conversations(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    conv_t, msg_t, users_t, orgs_t = _support_tables(db)
    if conv_t is None:
        return {"conversations": [], "total": 0}

    if status and status not in SUPPORT_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be 'open' or 'closed'")
    q = db.query(conv_t)
    if status:
        q = q.filter(conv_t.c.status == status)
    total = q.count()
    rows = q.order_by(desc(conv_t.c.updated_at)).offset(skip).limit(limit).all()

    results = []
    for r in rows:
        last_msg_row = (
            db.query(msg_t)
            .filter(msg_t.c.conversation_id == r.id)
            .order_by(desc(msg_t.c.created_at))
            .first()
        )
        unread = (
            db.query(func.count(msg_t.c.id))
            .filter(msg_t.c.conversation_id == r.id, _support_unread_filter(msg_t))
            .scalar()
        ) or 0
        results.append({
            "id": r.id,
            "user_id": r.user_id,
            **_support_customer(r, users_t, orgs_t, db),
            "subject": r.subject,
            "status": r.status,
            "created_at": _support_ts(getattr(r, "created_at", None)),
            "updated_at": _support_ts(getattr(r, "updated_at", None)),
            "last_message": last_msg_row.message[:100] if last_msg_row else None,
            "last_sender": last_msg_row.sender_type if last_msg_row else None,
            "unread_count": unread,
        })

    return {"conversations": results, "total": total}


@app.get("/support/conversations/{conversation_id}/messages")
async def admin_get_support_messages(
    conversation_id: str,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    conv_t, msg_t, users_t, orgs_t = _support_tables(db)
    if conv_t is None:
        return {"messages": []}
    conv = db.query(conv_t).filter(conv_t.c.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Opening the conversation marks the customer's messages as seen.
    db.execute(
        msg_t.update()
        .where(msg_t.c.conversation_id == conversation_id, _support_unread_filter(msg_t))
        .values(is_read=True)
    )
    db.commit()

    customer = _support_customer(conv, users_t, orgs_t, db)
    rows = (
        db.query(msg_t)
        .filter(msg_t.c.conversation_id == conversation_id)
        .order_by(msg_t.c.created_at, msg_t.c.id)
        .all()
    )
    return {
        "status": conv.status,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "sender_name": (
                    (getattr(m, "sender_name", None) or "Admin")
                    if m.sender_type == "admin"
                    else customer["user_name"]
                ),
                "message": m.message,
                "is_read": bool(m.is_read),
                "created_at": _support_ts(getattr(m, "created_at", None)),
            }
            for m in rows
        ],
    }


@app.post("/support/conversations/{conversation_id}/messages")
async def admin_send_support_message(
    conversation_id: str,
    body: SupportReply,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    conv_t, msg_t, _, _ = _support_tables(db)
    if conv_t is None:
        raise HTTPException(status_code=400, detail="Support tables not found")

    message = _SUPPORT_UNSAFE_CHARS.sub("", (body.message or "").replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(message) > SUPPORT_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Message is too long (max {SUPPORT_MAX_MESSAGE_LENGTH} characters)")

    conv = db.query(conv_t).filter(conv_t.c.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = {
        "id": msg_id,
        "conversation_id": conversation_id,
        "sender_type": "admin",
        # sender_id is 36 characters wide; the admin's address goes in sender_name.
        "sender_id": "admin",
        "message": message,
        "is_read": False,
        "created_at": now,
    }
    if "sender_name" in msg_t.c:
        values["sender_name"] = admin[:255]
    db.execute(msg_t.insert().values(**values))
    db.execute(conv_t.update().where(conv_t.c.id == conversation_id).values(updated_at=now))
    db.commit()

    return {
        "id": msg_id,
        "sender_type": "admin",
        "sender_name": admin,
        "message": message,
        "created_at": _support_ts(now),
    }


@app.put("/support/conversations/{conversation_id}/status")
async def admin_update_support_status(
    conversation_id: str,
    body: SupportStatusUpdate,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    conv_t, _, _, _ = _support_tables(db)
    if conv_t is None:
        raise HTTPException(status_code=400, detail="Support table not found")
    if body.status not in SUPPORT_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be 'open' or 'closed'")

    # updated_at is left alone so closing does not reorder the inbox.
    result = db.execute(
        conv_t.update().where(conv_t.c.id == conversation_id).values(status=body.status)
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": body.status}


@app.get("/support/unread")
async def admin_support_unread(
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    _, msg_t, _, _ = _support_tables(db)
    if msg_t is None:
        return {"count": 0}
    count = db.query(func.count(msg_t.c.id)).filter(_support_unread_filter(msg_t)).scalar() or 0
    return {"count": count}


@app.delete("/support/conversations/{conversation_id}")
async def admin_delete_conversation(
    conversation_id: str,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Delete a conversation and its messages (spam, tests)."""
    conv_t, msg_t, _, _ = _support_tables(db)
    if conv_t is None:
        raise HTTPException(status_code=400, detail="Support tables not found")
    conv = db.query(conv_t).filter(conv_t.c.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.execute(msg_t.delete().where(msg_t.c.conversation_id == conversation_id))
    db.execute(conv_t.delete().where(conv_t.c.id == conversation_id))
    db.commit()
    return {"status": "deleted", "conversation_id": conversation_id}


# ── Team Chat (admins only) ───────────────────────────────────────────
#
# An internal room where platform admins talk to each other. It is separate
# from the customer support chat: customers never see it, and nothing here is
# reachable from the main API. Same rules as support replies: plain text only
# (the UI renders it as text, never HTML), no uploads, control and invisible
# characters stripped, 4,000 characters, and a per-admin send rate limit.
# Tables are created by the backend (model app/models/admin_chat.py).

TEAM_CHAT_MAX_MESSAGE_LENGTH = 4000
TEAM_CHAT_RATE_LIMIT = 20          # messages per admin ...
TEAM_CHAT_RATE_WINDOW = 60         # ... per this many seconds
TEAM_CHAT_PAGE_MAX = 100
_TEAM_CHAT_SENDS: Dict[str, list] = {}


class TeamChatMessageIn(BaseModel):
    message: str


def _team_chat_tables(db):
    tables = _table_names(db)
    if "admin_chat_messages" not in tables or "admin_chat_reads" not in tables:
        return None, None
    return _get_table("admin_chat_messages"), _get_table("admin_chat_reads")


def _team_chat_require_tables(db):
    msg_t, read_t = _team_chat_tables(db)
    if msg_t is None:
        raise HTTPException(
            status_code=503,
            detail="Team chat is not set up yet. Run the backend database migration (python -m app.db_migrate).",
        )
    return msg_t, read_t


def _team_chat_display_name(db, email: str) -> str:
    try:
        row = db.execute(
            text("SELECT full_name FROM users WHERE lower(email) = :email"), {"email": email}
        ).first()
        if row and row.full_name and row.full_name.strip():
            return row.full_name.strip()[:255]
    except Exception:  # noqa: BLE001
        db.rollback()
    return email


def _team_chat_row(m, me: str) -> dict:
    return {
        "id": m.id,
        "author_email": m.author_email,
        "author_name": m.author_name or m.author_email,
        "message": m.message,
        "created_at": _support_ts(getattr(m, "created_at", None)),
        "mine": (m.author_email or "").lower() == me,
    }


def _team_chat_last_read(db, read_t, me: str):
    row = db.query(read_t).filter(read_t.c.admin_email == me).first()
    return row.last_read_at if row else None


@app.get("/team-chat/messages")
async def team_chat_messages(
    before: Optional[str] = Query(None, description="Message id; returns older messages"),
    limit: int = Query(50, ge=1, le=TEAM_CHAT_PAGE_MAX),
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Newest messages (or the page before `before`), returned oldest first."""
    me = admin.strip().lower()
    msg_t, read_t = _team_chat_tables(db)
    if msg_t is None:
        return {"messages": [], "has_more": False, "me": me, "last_read_at": None}
    q = db.query(msg_t)
    if before:
        anchor = db.query(msg_t).filter(msg_t.c.id == before).first()
        if not anchor:
            raise HTTPException(status_code=404, detail="Message not found")
        q = q.filter(
            (msg_t.c.created_at < anchor.created_at)
            | ((msg_t.c.created_at == anchor.created_at) & (msg_t.c.id < anchor.id))
        )
    rows = q.order_by(desc(msg_t.c.created_at), desc(msg_t.c.id)).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    return {
        "messages": [_team_chat_row(m, me) for m in rows],
        "has_more": has_more,
        "me": me,
        "last_read_at": _support_ts(_team_chat_last_read(db, read_t, me)),
    }


@app.post("/team-chat/messages")
async def team_chat_send(
    body: TeamChatMessageIn,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    me = admin.strip().lower()
    message = _SUPPORT_UNSAFE_CHARS.sub(
        "", (body.message or "").replace("\r\n", "\n").replace("\r", "\n")
    ).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(message) > TEAM_CHAT_MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message is too long (max {TEAM_CHAT_MAX_MESSAGE_LENGTH} characters)",
        )

    now_ts = time.time()
    recent = [t for t in _TEAM_CHAT_SENDS.get(me, []) if now_ts - t < TEAM_CHAT_RATE_WINDOW]
    if len(recent) >= TEAM_CHAT_RATE_LIMIT:
        _TEAM_CHAT_SENDS[me] = recent
        raise HTTPException(status_code=429, detail="You are sending messages too quickly. Wait a moment.")
    recent.append(now_ts)
    _TEAM_CHAT_SENDS[me] = recent

    msg_t, read_t = _team_chat_require_tables(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    msg_id = str(uuid.uuid4())
    values = {
        "id": msg_id,
        "author_email": me[:255],
        "author_name": _team_chat_display_name(db, me),
        "message": message,
        "created_at": now,
    }
    db.execute(msg_t.insert().values(**values))
    # Your own message never counts as unread for you.
    _team_chat_mark_read(db, read_t, me, now)
    db.commit()
    return {
        "id": msg_id,
        "author_email": values["author_email"],
        "author_name": values["author_name"],
        "message": message,
        "created_at": _support_ts(now),
        "mine": True,
    }


def _team_chat_mark_read(db, read_t, me: str, when) -> None:
    row = db.query(read_t).filter(read_t.c.admin_email == me).first()
    if row is None:
        db.execute(read_t.insert().values(admin_email=me, last_read_at=when))
    elif row.last_read_at is None or row.last_read_at < when:
        db.execute(read_t.update().where(read_t.c.admin_email == me).values(last_read_at=when))


@app.post("/team-chat/read")
async def team_chat_mark_read(
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Mark everything posted so far as read for the signed-in admin."""
    me = admin.strip().lower()
    msg_t, read_t = _team_chat_tables(db)
    if msg_t is None:
        return {"count": 0}
    latest = db.query(func.max(msg_t.c.created_at)).scalar()
    if latest is not None:
        _team_chat_mark_read(db, read_t, me, latest)
        db.commit()
    return {"count": 0}


@app.get("/team-chat/unread")
async def team_chat_unread(
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Messages from other admins posted after you last read the room."""
    me = admin.strip().lower()
    msg_t, read_t = _team_chat_tables(db)
    if msg_t is None:
        return {"count": 0}
    q = db.query(func.count(msg_t.c.id)).filter(func.lower(msg_t.c.author_email) != me)
    last = _team_chat_last_read(db, read_t, me)
    if last is not None:
        q = q.filter(msg_t.c.created_at > last)
    return {"count": q.scalar() or 0}


@app.delete("/team-chat/messages/{message_id}")
async def team_chat_delete(
    message_id: str,
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Admins can delete their own messages only."""
    me = admin.strip().lower()
    msg_t, _ = _team_chat_require_tables(db)
    row = db.query(msg_t).filter(msg_t.c.id == message_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    if (row.author_email or "").lower() != me:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    db.execute(msg_t.delete().where(msg_t.c.id == message_id))
    db.commit()
    return {"status": "deleted", "id": message_id}


@app.get("/team-chat/members")
async def team_chat_members(
    db: DBSession = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """Everyone who can read the team chat: active superusers (plus the env fallback admin)."""
    members = []
    try:
        rows = db.execute(
            text(
                "SELECT email, full_name FROM users "
                "WHERE role = 'superuser' AND is_active = :active ORDER BY email"
            ),
            {"active": True},
        ).all()
        members = [
            {"email": r.email.lower(), "name": (r.full_name or "").strip() or r.email.lower()}
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        db.rollback()
    if _env_fallback_enabled():
        env_email = settings.ADMIN_EMAIL.strip().lower()
        if all(m["email"] != env_email for m in members):
            members.append({"email": env_email, "name": env_email})
    return {"members": members, "me": admin.strip().lower()}


# ── Helpers ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}

@app.get("/ping")
async def ping():
    return {"pong": True}
