import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_token, hash_api_key
from app.database import get_db
from app.models.user import User


security = HTTPBearer(auto_error=False)

# API keys are meant for automation (CI, SIEM, scripts). They must never be
# able to manage the account that owns them: changing the password, 2FA,
# sessions, passkeys or minting more keys always needs an interactive login.
_API_KEY_BLOCKED_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/users/me",
    "/api/v1/api-keys",
    "/api/v1/security",
    "/api/v1/passkeys",
    "/api/v1/sessions",
    "/api/v1/admin",
    "/api/v1/organizations",
    "/api/v1/invitations",
)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _unauthorized(detail: str = "Invalid token") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def user_from_access_token(token: str, db: Session) -> Optional[User]:
    """Validate an access JWT and return its active user, or None.

    Checks the token type, that the user exists and is active, and that the
    token's version ("tv") matches the user's current token_version so that
    logout / password change invalidate older tokens. Tokens without a "tv"
    claim are rejected (every issuer in the app embeds it).
    """
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        return None
    if payload.get("tv") != (user.token_version or 0):
        return None
    return user


def _user_from_api_key(raw_key: str, request: Request, db: Session) -> User:
    path = request.url.path
    if any(path.startswith(p) for p in _API_KEY_BLOCKED_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys cannot be used for account or organization management",
        )

    from app.models.api_key_v2 import ApiKey

    key_hash = hash_api_key(raw_key)
    now = datetime.now(timezone.utc)
    user: Optional[User] = None
    scopes: list = []

    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active).first()
    if api_key:
        expires = api_key.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is not None and expires < now:
            raise _unauthorized("API key expired")
        scopes = list(api_key.scopes or [])
        user = db.query(User).filter(User.id == api_key.user_id).first()
        api_key.last_used_at = now
        api_key.last_used_ip = request.client.host if request.client else None
        db.commit()
    else:
        # Legacy single key stored (hashed) on the user row (/api/v1/api-keys).
        user = db.query(User).filter(User.api_key == key_hash).first()

    if not user or not user.is_active:
        raise _unauthorized("Invalid API key")

    # A key restricted to "read" (and without "write"/"admin") is read-only.
    if scopes and "read" in scopes and not ({"write", "admin"} & set(scopes)):
        if request.method.upper() not in _SAFE_METHODS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This API key is read-only",
            )

    request.state.auth_method = "api_key"
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the caller with a JWT access token or an API key.

    API keys are accepted in the ``X-API-Key`` header, or as a bearer token
    that starts with the configured key prefix (``easm_`` by default).
    """
    api_key = request.headers.get("x-api-key")
    if not api_key and credentials and credentials.credentials.startswith(settings.API_KEY_PREFIX):
        api_key = credentials.credentials
    if api_key:
        return _user_from_api_key(api_key, request, db)

    if not credentials:
        raise _unauthorized("Not authenticated")

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise _unauthorized("Invalid token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise _unauthorized("User not found or inactive")

    # Invalidate tokens issued before a logout / password change.
    if payload.get("tv") != (user.token_version or 0):
        raise _unauthorized("Session invalidated. Please log in again.")

    request.state.auth_method = "jwt"
    _note_activity(request, user, payload.get("sid"), db)
    return user


# Session last-activity is refreshed at most this often per session, so busy
# dashboards don't turn every API call into a write.
_ACTIVITY_INTERVAL_SECONDS = 300
_ACTIVITY_SEEN: dict[str, float] = {}
_ACTIVITY_SEEN_MAX = 50_000


def _note_activity(request: Request, user: User, sid: Optional[str], db: Session) -> None:
    """Record who made this request, for support diagnostics.

    Tags the request so failed calls in the platform log carry the user and
    organization, and bumps the session's last_activity (throttled). Only the
    time is stored: no URLs, payloads or page content. Never fails the request.
    """
    request.state.user_id = user.id
    request.state.organization_id = user.organization_id
    if not sid or not isinstance(sid, str):
        return
    now = time.monotonic()
    last = _ACTIVITY_SEEN.get(sid)
    if last is not None and now - last < _ACTIVITY_INTERVAL_SECONDS:
        return
    if len(_ACTIVITY_SEEN) >= _ACTIVITY_SEEN_MAX:
        _ACTIVITY_SEEN.clear()
    _ACTIVITY_SEEN[sid] = now
    try:
        from app.models.auth_models import UserSession
        db.query(UserSession).filter(
            UserSession.id == sid, UserSession.user_id == user.id, UserSession.is_active.is_(True),
        ).update({"last_activity": datetime.now(timezone.utc)}, synchronize_session=False)
        db.commit()
    except Exception:  # noqa: BLE001 - diagnostics must never break a request
        db.rollback()


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated with a valid access token, otherwise None."""
    if not credentials:
        return None
    return user_from_access_token(credentials.credentials, db)
