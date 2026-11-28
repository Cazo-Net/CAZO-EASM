"""Single sign-on (OpenID Connect).

Two routers:

``admin_router`` at /api/v1/sso — an organization's own SSO settings
(``manage_settings``: owner and administrator by default).

- GET    /sso                      — settings, domains and what to enter at the provider
- PUT    /sso                      — save settings (blank client secret = keep stored)
- DELETE /sso                      — remove SSO and its domains
- POST   /sso/test                 — check the provider can be reached
- POST   /sso/domains              — claim an email domain
- POST   /sso/domains/{id}/verify  — check the DNS record
- DELETE /sso/domains/{id}         — remove a domain

``public_router`` at /api/v1/auth/sso — the sign-in itself.

- POST /auth/sso/start     — email in, provider URL out
- GET  /auth/sso/callback  — where the provider sends the browser back
- POST /auth/sso/exchange  — one-time code in, session tokens out
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import frontend_url, settings
from app.core import secret_box
from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.sso import OrgSsoConfig, SsoDomain
from app.models.user import User
from app.schemas.auth import Token
from app.services import sso
from app.services.audit import log_user_action

admin_router = APIRouter()
public_router = APIRouter()


# ── Settings ─────────────────────────────────────────────────────────────


class SsoSettingsIn(BaseModel):
    issuer: str = Field(..., max_length=500)
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=1000)
    enabled: bool = False
    enforce: bool = False
    auto_provision: bool = True
    default_role: str = Field("viewer", max_length=20)


class DomainIn(BaseModel):
    domain: str = Field(..., max_length=255)


def _org_id(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="Create or join an organization first.")
    return user.organization_id


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _domain_out(row: SsoDomain) -> dict:
    return {"id": row.id, "domain": row.domain, "verified": row.verified_at is not None,
            "verified_at": _utc(row.verified_at), "dns_record": sso.dns_record(row)}


def _state(db: Session, org_id: str) -> dict:
    cfg = db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == org_id).first()
    domains = db.query(SsoDomain).filter(SsoDomain.organization_id == org_id).order_by(SsoDomain.created_at.asc()).all()
    config = None
    if cfg:
        config = {
            "issuer": cfg.issuer, "client_id": cfg.client_id, "has_secret": bool(cfg.client_secret_encrypted),
            "enabled": bool(cfg.enabled), "enforce": bool(cfg.enforce), "auto_provision": bool(cfg.auto_provision),
            "default_role": cfg.default_role, "last_login_at": _utc(cfg.last_login_at), "last_error": cfg.last_error,
        }
    return {"config": config, "domains": [_domain_out(d) for d in domains],
            "redirect_uri": sso.redirect_uri(), "roles": list(sso.ROLES), "max_domains": sso.MAX_DOMAINS}


def _fail(exc: sso.SsoError, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail=exc.message)


@admin_router.get("")
def get_sso(
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    return _state(db, _org_id(current_user))


@admin_router.put("")
def save_sso(
    payload: SsoSettingsIn,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    if payload.default_role not in sso.ROLES:
        raise HTTPException(status_code=422, detail="Choose viewer, analyst or admin as the role for new people.")
    if payload.default_role == "admin" and current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can make new SSO users administrators.")
    cfg = db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == org_id).first()
    secret = (payload.client_secret or "").strip()
    if not cfg and not secret:
        raise HTTPException(status_code=422, detail="Enter the client secret from your identity provider.")
    try:
        issuer = sso.normalize_issuer(payload.issuer)
        if payload.enabled:
            sso.discover(issuer, fresh=True)
    except sso.SsoError as exc:
        raise _fail(exc)
    if payload.enabled and not sso.verified_domains(db, org_id):
        raise HTTPException(status_code=422, detail="Verify at least one email domain before turning single sign-on on.")
    if payload.enforce and not payload.enabled:
        raise HTTPException(status_code=422, detail="Turn single sign-on on before requiring it.")

    if not cfg:
        cfg = OrgSsoConfig(organization_id=org_id, issuer=issuer, client_id=payload.client_id.strip(),
                           client_secret_encrypted=secret_box.encrypt({"client_secret": secret}))
        db.add(cfg)
    else:
        if cfg.issuer != issuer and not secret:
            # A stored secret must never be sent to a different provider address.
            raise HTTPException(status_code=422, detail="Enter the client secret again when changing the issuer.")
        cfg.issuer, cfg.client_id = issuer, payload.client_id.strip()
        if secret:
            cfg.client_secret_encrypted = secret_box.encrypt({"client_secret": secret})
    before = {"enabled": bool(cfg.enabled), "enforce": bool(cfg.enforce)}
    cfg.enabled, cfg.enforce = payload.enabled, payload.enforce
    cfg.auto_provision, cfg.default_role = payload.auto_provision, payload.default_role
    cfg.updated_by = current_user.id
    cfg.last_error = None
    db.commit()
    log_user_action(db, current_user, "sso.config.update", target_type="sso_config", target_id=cfg.id, detail={
        "issuer": issuer, "enabled": payload.enabled, "enforce": payload.enforce, "was": before,
        "auto_provision": payload.auto_provision, "default_role": payload.default_role,
        "secret_changed": bool(secret),
    })
    return _state(db, org_id)


@admin_router.delete("")
def delete_sso(
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == org_id).delete(synchronize_session=False)
    db.query(SsoDomain).filter(SsoDomain.organization_id == org_id).delete(synchronize_session=False)
    db.commit()
    log_user_action(db, current_user, "sso.config.delete", target_type="sso_config")
    return {"deleted": True}


@admin_router.post("/test")
def test_sso(
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    cfg = db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == _org_id(current_user)).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Save the settings first.")
    try:
        sso.discover(cfg.issuer, fresh=True)
    except sso.SsoError as exc:
        return {"success": False, "error": exc.message}
    return {"success": True, "error": None}


@admin_router.post("/domains", status_code=201)
def add_domain(
    payload: DomainIn,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    try:
        row = sso.add_domain(db, _org_id(current_user), payload.domain)
    except sso.SsoError as exc:
        raise _fail(exc, 409 if exc.code in ("exists", "limit") else 422)
    log_user_action(db, current_user, "sso.domain.add", target_type="sso_domain", target_id=row.id,
                    detail={"domain": row.domain})
    return _domain_out(row)


def _domain(db: Session, org_id: str, domain_id: str) -> SsoDomain:
    row = db.query(SsoDomain).filter(SsoDomain.id == domain_id, SsoDomain.organization_id == org_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Domain not found.")
    return row


@admin_router.post("/domains/{domain_id}/verify")
def verify_domain(
    domain_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    row = _domain(db, _org_id(current_user), domain_id)
    try:
        ok = row.verified_at is not None or sso.verify_domain(db, row)
    except sso.SsoError as exc:
        raise _fail(exc, 409)
    if ok:
        log_user_action(db, current_user, "sso.domain.verify", target_type="sso_domain", target_id=row.id,
                        detail={"domain": row.domain})
    return {**_domain_out(row), "error": None if ok else
            "The DNS record was not found yet. DNS changes can take up to an hour; try again later."}


@admin_router.delete("/domains/{domain_id}")
def remove_domain(
    domain_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    row = _domain(db, org_id, domain_id)
    name, was_verified = row.domain, row.verified_at is not None
    db.delete(row)
    db.flush()
    cfg = db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == org_id).first()
    turned_off = False
    if cfg and cfg.enabled and was_verified and not sso.verified_domains(db, org_id):
        # No verified domain left: nobody could sign in, so do not leave it "on" (or enforced).
        cfg.enabled = cfg.enforce = False
        turned_off = True
    db.commit()
    log_user_action(db, current_user, "sso.domain.remove", target_type="sso_domain", target_id=domain_id,
                    detail={"domain": name, "sso_turned_off": turned_off})
    return {"deleted": True, "sso_turned_off": turned_off}


# ── Sign-in ──────────────────────────────────────────────────────────────


class StartIn(BaseModel):
    email: str = Field(..., max_length=254)


class ExchangeIn(BaseModel):
    code: str = Field(..., max_length=200)


def _throttle(request: Request, name: str, limit: int) -> None:
    from app.api.v1.auth import _client_ip
    from app.core.rate_limit import get_rate_limiter

    if settings.RATE_LIMIT_ENABLED and not get_rate_limiter().is_allowed(f"sso:{name}:{_client_ip(request)}", limit):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a minute and try again.")


@public_router.post("/start")
def start(payload: StartIn, request: Request, db: Session = Depends(get_db)):
    _throttle(request, "start", 20)
    try:
        return {"url": sso.begin_login(db, payload.email)}
    except sso.SsoError as exc:
        status = {"off": 404, "busy": 429}.get(exc.code, 502)
        raise HTTPException(status_code=status, detail=exc.message)


@public_router.get("/callback", include_in_schema=False)
def callback(request: Request, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    """The identity provider's redirect. Always answers with a redirect to the frontend."""
    _throttle(request, "callback", 60)
    headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    try:
        handoff = sso.complete_login(db, state, "" if error else code)
    except sso.SsoError as exc:
        code_out = exc.code if exc.code in sso.LOGIN_ERRORS else "provider"
        return RedirectResponse(frontend_url(f"/login?sso_error={code_out}"), status_code=303, headers=headers)
    return RedirectResponse(frontend_url(f"/auth/callback/sso#code={handoff}"), status_code=303, headers=headers)


@public_router.post("/exchange", response_model=Token)
def exchange(payload: ExchangeIn, request: Request, db: Session = Depends(get_db)):
    from app.api.v1.auth import issue_session_tokens, mfa_challenge

    _throttle(request, "exchange", 30)
    user = sso.redeem_handoff(db, payload.code)
    if not user:
        raise HTTPException(status_code=401, detail="This sign-in link has expired. Please sign in again.")
    if user.totp_enabled and user.totp_secret:
        return mfa_challenge(user)
    return issue_session_tokens(db, user, request, method="sso")
