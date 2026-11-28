"""Single sign-on with OpenID Connect, per organization.

How a sign-in works:

1. The person types their work email. Its domain must be one an organization
   has *verified* (a DNS TXT record), and that organization must have SSO on.
2. ``begin_login`` stores a one-time state, nonce and PKCE verifier and returns
   the identity provider's authorization URL.
3. The provider sends the browser back to ``/auth/sso/callback``.
   ``complete_login`` checks the state (single use, 10 minutes), exchanges the
   code, validates the ID token (signature, issuer, audience, expiry, nonce)
   and requires the email in it to be on one of the organization's verified
   domains. That last check is what stops one customer's identity provider
   from signing people in to another customer's organization.
4. The browser gets a one-time handoff code (60 seconds), which the frontend
   exchanges for the normal session tokens. Tokens never appear in a URL.

Outbound requests go only to public https hosts and never follow redirects.
The client secret is stored encrypted and is never returned by the API.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import frontend_url
from app.core import secret_box
from app.core.target_guard import check_public_target
from app.models.sso import OrgSsoConfig, SsoDomain, SsoLoginState
from app.models.user import User

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
HANDOFF_TTL = timedelta(seconds=60)
MAX_DOMAINS = 10
MAX_PENDING_PER_ORG = 200
ROLES = ("viewer", "analyst", "admin")
ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384"]  # asymmetric only
DNS_PREFIX = "_cazo-sso"
DNS_VALUE_PREFIX = "cazo-sso-verify="
_TIMEOUT = 10.0
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class SsoError(Exception):
    """A sign-in or configuration problem. ``code`` is safe to show; ``message`` is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Fixed messages for the login page (/login?sso_error=<code>).
LOGIN_ERRORS = {
    "expired": "That sign-in attempt expired. Please try again.",
    "denied": "Your identity provider did not complete the sign-in.",
    "provider": "We could not confirm your identity with your provider. Please try again or contact your administrator.",
    "domain": "Your identity provider returned an email address that does not belong to this organization.",
    "no_account": "You do not have an account in this organization. Ask an administrator to invite you.",
    "other_org": "This email address already belongs to a different organization. Contact support to move it.",
    "inactive": "Your account is deactivated. Contact your administrator.",
    "seats": "Your organization has no free user seats. Contact your administrator.",
    "off": "Single sign-on is not available for this organization.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def redirect_uri() -> str:
    return frontend_url("/api/v1/auth/sso/callback")


# ── Domains ──────────────────────────────────────────────────────────────


def normalize_domain(raw: str) -> str:
    domain = (raw or "").strip().lower().rstrip(".")
    if domain.startswith("@"):
        domain = domain[1:]
    if not _DOMAIN_RE.match(domain):
        raise SsoError("domain", "Enter a domain name such as example.com.")
    return domain


def email_domain(email: str) -> str:
    return (email or "").strip().lower().rpartition("@")[2]


def dns_record(domain: SsoDomain) -> Dict[str, str]:
    return {"type": "TXT", "name": f"{DNS_PREFIX}.{domain.domain}",
            "value": f"{DNS_VALUE_PREFIX}{domain.verification_token}"}


def _lookup_txt(name: str) -> List[str]:
    """TXT strings at ``name`` (empty when missing or on any DNS error)."""
    import dns.resolver

    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 6.0
        answers = resolver.resolve(name, "TXT")
        return [b"".join(r.strings).decode("utf-8", "replace").strip() for r in answers]
    except Exception:  # noqa: BLE001
        return []


def add_domain(db: Session, organization_id: str, raw: str) -> SsoDomain:
    domain = normalize_domain(raw)
    rows = db.query(SsoDomain).filter(SsoDomain.organization_id == organization_id).all()
    if any(r.domain == domain for r in rows):
        raise SsoError("exists", "That domain is already in the list.")
    if len(rows) >= MAX_DOMAINS:
        raise SsoError("limit", f"At most {MAX_DOMAINS} domains are allowed.")
    row = SsoDomain(organization_id=organization_id, domain=domain, verification_token=secrets.token_hex(20))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def verify_domain(db: Session, row: SsoDomain) -> bool:
    """Check the DNS record. A domain can be verified by one organization only."""
    taken = (
        db.query(SsoDomain)
        .filter(SsoDomain.domain == row.domain, SsoDomain.verified_at.isnot(None),
                SsoDomain.organization_id != row.organization_id)
        .first()
    )
    if taken:
        raise SsoError("taken", "This domain is already verified by another organization. Contact support if it is yours.")
    expected = dns_record(row)
    if expected["value"] not in _lookup_txt(expected["name"]):
        return False
    row.verified_at = _now()
    db.commit()
    return True


def verified_domains(db: Session, organization_id: str) -> List[str]:
    return [
        d for (d,) in db.query(SsoDomain.domain)
        .filter(SsoDomain.organization_id == organization_id, SsoDomain.verified_at.isnot(None)).all()
    ]


def config_for_email(db: Session, email: str) -> Optional[OrgSsoConfig]:
    """The enabled SSO configuration that owns this email's domain, if any."""
    domain = email_domain(email)
    if not domain:
        return None
    return (
        db.query(OrgSsoConfig)
        .join(SsoDomain, SsoDomain.organization_id == OrgSsoConfig.organization_id)
        .filter(SsoDomain.domain == domain, SsoDomain.verified_at.isnot(None), OrgSsoConfig.enabled.is_(True))
        .first()
    )


def password_login_blocked(db: Session, user: User) -> bool:
    """True when this member must sign in through their organization's SSO.

    Owners are never blocked, so a broken identity provider cannot lock an
    organization out of its own settings.
    """
    if not user.organization_id or user.role == "owner":
        return False
    cfg = (
        db.query(OrgSsoConfig)
        .filter(OrgSsoConfig.organization_id == user.organization_id,
                OrgSsoConfig.enabled.is_(True), OrgSsoConfig.enforce.is_(True))
        .first()
    )
    if not cfg:
        return False
    # Only people the provider can actually sign in (their domain is verified).
    return email_domain(user.email) in verified_domains(db, user.organization_id)


# ── Talking to the identity provider ─────────────────────────────────────


def normalize_issuer(raw: str) -> str:
    issuer = (raw or "").strip().rstrip("/")
    parts = urlsplit(issuer)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.query or parts.fragment:
        raise SsoError("issuer", "The issuer must be an https address, for example https://login.example.com.")
    if len(issuer) > 500:
        raise SsoError("issuer", "The issuer address is too long.")
    return issuer


def _require_public(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or not check_public_target(parts.hostname).allowed:
        raise SsoError("provider", "The identity provider address must be a public https address.")


def _http() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT, follow_redirects=False, headers={"User-Agent": "CAZO-EASM-SSO/1.0"})


_discovery_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def discover(issuer: str, *, fresh: bool = False) -> Dict[str, Any]:
    """The provider's OpenID configuration, validated. Cached for 10 minutes."""
    cached = _discovery_cache.get(issuer)
    if cached and not fresh and time.monotonic() - cached[0] < 600:
        return cached[1]
    url = issuer + "/.well-known/openid-configuration"
    _require_public(url)
    try:
        with _http() as client:
            resp = client.get(url)
        doc = resp.json() if resp.status_code == 200 else None
    except SsoError:
        raise
    except Exception:  # noqa: BLE001
        doc = None
    if not isinstance(doc, dict):
        raise SsoError("provider", "Could not read the identity provider's configuration. Check the issuer address.")
    if str(doc.get("issuer", "")).rstrip("/") != issuer:
        raise SsoError("provider", "The identity provider reports a different issuer than the one entered.")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        value = doc.get(key)
        if not isinstance(value, str) or urlsplit(value).scheme != "https":
            raise SsoError("provider", "The identity provider's configuration is incomplete.")
    _discovery_cache[issuer] = (time.monotonic(), doc)
    return doc


def _client_secret(cfg: OrgSsoConfig) -> str:
    try:
        return str(secret_box.decrypt(cfg.client_secret_encrypted).get("client_secret", ""))
    except secret_box.SecretUnreadable:
        raise SsoError("provider", "The stored client secret cannot be read. Enter it again.")


def _exchange_code(cfg: OrgSsoConfig, doc: Dict[str, Any], code: str, verifier: str) -> Dict[str, Any]:
    _require_public(doc["token_endpoint"])
    try:
        with _http() as client:
            resp = client.post(doc["token_endpoint"], data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
                "client_id": cfg.client_id, "client_secret": _client_secret(cfg), "code_verifier": verifier,
            }, headers={"Accept": "application/json"})
        body = resp.json() if resp.status_code == 200 else None
    except SsoError:
        raise
    except Exception:  # noqa: BLE001
        body = None
    if not isinstance(body, dict) or not isinstance(body.get("id_token"), str):
        raise SsoError("provider", "The identity provider did not return a sign-in token.")
    return body


def _fetch_jwks(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    _require_public(doc["jwks_uri"])
    try:
        with _http() as client:
            resp = client.get(doc["jwks_uri"])
        keys = resp.json().get("keys") if resp.status_code == 200 else None
    except SsoError:
        raise
    except Exception:  # noqa: BLE001
        keys = None
    if not isinstance(keys, list) or not keys:
        raise SsoError("provider", "Could not read the identity provider's signing keys.")
    return keys


def _validate_id_token(cfg: OrgSsoConfig, doc: Dict[str, Any], id_token: str, nonce: str) -> Dict[str, Any]:
    from jose import jwt
    from jose.exceptions import JOSEError

    try:
        header = jwt.get_unverified_header(id_token)
    except JOSEError:
        raise SsoError("provider", "The sign-in token is malformed.")
    if header.get("alg") not in ALGORITHMS:
        raise SsoError("provider", "The sign-in token uses an unsupported signature.")
    keys = _fetch_jwks(doc)
    kid = header.get("kid")
    candidates = [k for k in keys if k.get("kid") == kid] if kid else keys
    claims = None
    for key in candidates[:5]:
        try:
            claims = jwt.decode(
                id_token, key, algorithms=ALGORITHMS, audience=cfg.client_id, issuer=str(doc["issuer"]),
                options={"verify_at_hash": False, "require_exp": True, "require_iat": False},
            )
            break
        except JOSEError:
            continue
        except Exception:  # noqa: BLE001  (a malformed key)
            continue
    if claims is None:
        raise SsoError("provider", "The sign-in token could not be verified.")
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SsoError("provider", "The sign-in token does not match this sign-in attempt.")
    return claims


def _email_from_claims(claims: Dict[str, Any]) -> str:
    if claims.get("email_verified") is False:
        raise SsoError("provider", "Your identity provider has not verified this email address.")
    for key in ("email", "preferred_username", "upn"):
        value = str(claims.get(key) or "").strip().lower()
        if re.match(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[a-z]{2,}$", value) and len(value) <= 254:
            return value
    raise SsoError("provider", "Your identity provider did not send an email address.")


# ── The sign-in flow ─────────────────────────────────────────────────────


def begin_login(db: Session, email: str) -> str:
    """Start a sign-in for this email. Returns the provider URL to send the browser to."""
    cfg = config_for_email(db, email)
    if not cfg:
        raise SsoError("off", "Single sign-on is not set up for this email address.")
    doc = discover(cfg.issuer)

    now = _now()
    db.query(SsoLoginState).filter(SsoLoginState.expires_at < now - timedelta(hours=1)).delete(synchronize_session=False)
    pending = (
        db.query(func.count(SsoLoginState.id))
        .filter(SsoLoginState.organization_id == cfg.organization_id, SsoLoginState.expires_at > now,
                SsoLoginState.used_at.is_(None)).scalar()
    )
    if pending >= MAX_PENDING_PER_ORG:
        db.commit()
        raise SsoError("busy", "Too many sign-in attempts are in progress. Try again in a few minutes.")

    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    db.add(SsoLoginState(organization_id=cfg.organization_id, state_hash=_hash(state), nonce=nonce,
                         code_verifier=verifier, expires_at=now + STATE_TTL))
    db.commit()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({
        "response_type": "code", "client_id": cfg.client_id, "redirect_uri": redirect_uri(),
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256", "login_hint": email.strip().lower(),
    })
    sep = "&" if "?" in doc["authorization_endpoint"] else "?"
    return doc["authorization_endpoint"] + sep + query


def _claim_state(db: Session, state: str) -> Optional[SsoLoginState]:
    """Mark the state used and return it; None if unknown, expired or already used."""
    if not state or len(state) > 200:
        return None
    now = _now()
    claimed = (
        db.query(SsoLoginState)
        .filter(SsoLoginState.state_hash == _hash(state), SsoLoginState.used_at.is_(None),
                SsoLoginState.expires_at > now)
        .update({"used_at": now}, synchronize_session=False)
    )
    db.commit()
    if not claimed:
        return None
    return db.query(SsoLoginState).filter(SsoLoginState.state_hash == _hash(state)).first()


def _resolve_user(db: Session, cfg: OrgSsoConfig, email: str, name: str) -> User:
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        if user.organization_id != cfg.organization_id:
            # Never move or adopt an existing account: an invitation does that, with the person's consent.
            raise SsoError("other_org" if user.organization_id else "no_account", "Account is not in this organization.")
        if not user.is_active:
            raise SsoError("inactive", "Account is deactivated.")
        return user
    if not cfg.auto_provision:
        raise SsoError("no_account", "No account and automatic creation is off.")
    from app.billing.entitlements import PlanLimitExceeded, check_seat_available

    try:
        check_seat_available(db, cfg.organization_id)
    except PlanLimitExceeded:
        raise SsoError("seats", "No free seats.")
    user = User(
        email=email, full_name=(name or email.split("@")[0])[:255], hashed_password=None,
        organization_id=cfg.organization_id, role=cfg.default_role if cfg.default_role in ROLES else "viewer",
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    from app.services.audit import log_event

    log_event(db, action="sso.user_provisioned", organization_id=cfg.organization_id, actor_type="system",
              target_type="user", target_id=user.id, detail={"email": email, "role": user.role})
    return user


def complete_login(db: Session, state: str, code: str) -> str:
    """Finish a sign-in from the provider's redirect. Returns a one-time handoff code."""
    row = _claim_state(db, state)
    if not row:
        raise SsoError("expired", "Unknown or expired state.")
    cfg = db.query(OrgSsoConfig).filter(OrgSsoConfig.organization_id == row.organization_id).first()
    if not cfg or not cfg.enabled:
        raise SsoError("off", "SSO is off.")
    try:
        if not code or len(code) > 4000:
            raise SsoError("denied", "No authorization code.")
        doc = discover(cfg.issuer)
        tokens = _exchange_code(cfg, doc, code, row.code_verifier)
        claims = _validate_id_token(cfg, doc, tokens["id_token"], row.nonce)
        email = _email_from_claims(claims)
        if email_domain(email) not in verified_domains(db, cfg.organization_id):
            raise SsoError("domain", "Email domain is not verified for this organization.")
        user = _resolve_user(db, cfg, email, str(claims.get("name") or ""))
    except SsoError as exc:
        cfg.last_error = LOGIN_ERRORS.get(exc.code, exc.message)[:300]
        db.commit()
        raise
    handoff = secrets.token_urlsafe(32)
    row.handoff_hash = _hash(handoff)
    row.handoff_expires_at = _now() + HANDOFF_TTL
    row.user_id = user.id
    cfg.last_login_at = _now()
    cfg.last_error = None
    db.commit()
    return handoff


def redeem_handoff(db: Session, code: str) -> Optional[User]:
    """Trade the one-time handoff code for the user it was issued to (single use)."""
    if not code or len(code) > 200:
        return None
    digest = _hash(code)
    row = db.query(SsoLoginState).filter(SsoLoginState.handoff_hash == digest).first()
    if not row:
        return None
    user_id, expires = row.user_id, _aware(row.handoff_expires_at)
    cleared = (
        db.query(SsoLoginState).filter(SsoLoginState.id == row.id, SsoLoginState.handoff_hash == digest)
        .update({"handoff_hash": None, "handoff_expires_at": None}, synchronize_session=False)
    )
    db.commit()
    if not cleared or not expires or expires < _now():
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user if user and user.is_active else None
