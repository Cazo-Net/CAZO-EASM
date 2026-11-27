from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.auth_models import UserSession, RecoveryCode
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, Token, TokenRefresh,
    PasswordResetRequest, PasswordReset, VerifyEmail, TOTPSetup, TOTPVerify,
    TwoFactorLogin,
)
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_token,
    generate_verification_token, generate_totp_secret, verify_totp,
    hash_api_key, create_mfa_token,
)
from app.config import frontend_url
from app.services.notification_service import dispatch_notification
from app.api.deps import get_current_user
from app.services.audit import log_auth_event
from app.services.email import get_email_service
from app.services.email import templates
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
RESET_TOKEN_EXPIRY_MINUTES = 30


def find_user_by_email(db: Session, email: str):
    """Case-insensitive email lookup (older rows may be stored mixed-case)."""
    if not email:
        return None
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _register_failed_attempt(db: Session, user: User, request: Request, reason: str) -> None:
    """Count a failed password / 2FA attempt and lock the account after too many."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"Account locked: {user.email} after {MAX_FAILED_ATTEMPTS} failed attempts")
        log_auth_event(db, "account_locked", user.id,
                       ip_address=_client_ip(request),
                       success=False, detail={"email": user.email})
        try:
            email_service = get_email_service()
            subject, html = templates.account_locked(
                user.full_name or user.email,
                "Too many failed login attempts",
            )
            email_service.send_async(to=user.email, subject=subject, html_body=html)
        except Exception as e:
            logger.error(f"Failed to send lockout email: {e}")
    db.commit()
    log_auth_event(db, "login_failed", user.id,
                   ip_address=_client_ip(request),
                   success=False, detail={"reason": reason})


def _raise_if_locked(db: Session, user: User) -> None:
    locked_until = db.query(User.locked_until).filter(User.id == user.id).scalar()
    if locked_until:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            remaining = (locked_until - datetime.now(timezone.utc)).seconds // 60 + 1
            raise HTTPException(
                status_code=423,
                detail=f"Account locked. Try again in {remaining} minute(s)."
            )


def issue_session_tokens(db: Session, user: User, request: Request, method: str = "password") -> dict:
    """Create a UserSession and return a fresh access/refresh token pair.

    Shared by password login, 2FA completion and Google sign-in so that every
    login path stores the refresh-token hash (needed for rotation) and embeds
    the token_version used for revocation.
    """
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token_version = user.token_version or 0
    access_token = create_access_token(
        data={"sub": user.id, "role": user.role, "tv": token_version}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.id, "tv": token_version}
    )

    client_ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_api_key(refresh_token),
        ip_address=client_ip,
        user_agent=ua,
        browser=ua[:50] if ua else "Unknown",
        os=ua[50:100] if len(ua) > 50 else "Unknown",
    )
    db.add(session)
    db.commit()

    try:
        email_service = get_email_service()
        subject, html = templates.new_login(
            user.full_name or user.email,
            client_ip,
            ua[:50] or "Unknown",
            "Unknown",
        )
        email_service.send_async(to=user.email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send login email: {e}")

    log_auth_event(db, "login_success", user.id,
                   ip_address=client_ip, detail={"session_id": session.id, "method": method})

    try:
        dispatch_notification(
            db=db,
            organization_id=user.organization_id,
            user_id=user.id,
            notification_type="new_login",
            title="New login detected",
            message=f"New login from {client_ip} ({ua[:60] or 'Unknown device'})",
            related_entity_type="user",
            related_entity_id=user.id,
            data={
                "ip_address": client_ip,
                "user_agent": ua,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Failed to dispatch login notification: {e}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_2fa": False,
    }


def mfa_challenge(user: User) -> dict:
    """Response for a correct first factor on an account with 2FA enabled."""
    return {
        "access_token": None,
        "refresh_token": None,
        "token_type": "bearer",
        "requires_2fa": True,
        "mfa_token": create_mfa_token(user.id, user.token_version or 0),
    }


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        existing_user = find_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        verification_token = generate_verification_token()

        user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password),
            verification_token=verification_token,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        verify_url = frontend_url(f"/auth/verify-email?token={verification_token}")
        try:
            email_service = get_email_service()
            subject, html = templates.welcome_email(user.full_name or user.email, verify_url)
            email_service.send_async(to=user.email, subject=subject, html_body=html)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")

        log_auth_event(db, "user_registered", user.id,
                       ip_address=request.client.host if request.client else None,
                       detail={"email": user.email})

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post("/verify-email")
async def verify_email(data: VerifyEmail, request: Request, db: Session = Depends(get_db)):
    """Verify email with token."""
    user = db.query(User).filter(User.verification_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.email_verified = True
    user.verification_token = None
    db.commit()

    try:
        email_service = get_email_service()
        subject, html = templates.email_verified(user.full_name or user.email)
        email_service.send_async(to=user.email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send verified email: {e}")

    log_auth_event(db, "email_verified", user.id,
                   ip_address=request.client.host if request.client else None)

    return {"message": "Email verified successfully"}


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Login with brute-force protection and enforced 2FA."""
    user = find_user_by_email(db, login_data.email)

    if not user:
        log_auth_event(db, "login_failed", None,
                       ip_address=_client_ip(request),
                       success=False, detail={"email": login_data.email, "reason": "user_not_found"})
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _raise_if_locked(db, user)

    if not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
        _register_failed_attempt(db, user, request, "wrong_password")
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    # Second factor: no session tokens until the TOTP / recovery code is checked.
    if user.totp_enabled and user.totp_secret:
        return mfa_challenge(user)

    return issue_session_tokens(db, user, request, method="password")


@router.post("/2fa/verify-login", response_model=Token)
async def verify_2fa_login(data: TwoFactorLogin, request: Request, db: Session = Depends(get_db)):
    """Second login step: exchange the mfa_token + a TOTP or recovery code for tokens."""
    payload = decode_token(data.mfa_token)
    if not payload or payload.get("type") != "mfa":
        raise HTTPException(status_code=401, detail="Login step expired. Please sign in again.")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Login step expired. Please sign in again.")
    if payload.get("tv") != (user.token_version or 0):
        raise HTTPException(status_code=401, detail="Login step expired. Please sign in again.")

    _raise_if_locked(db, user)

    code = (data.code or "").strip().replace(" ", "")
    ok = False
    method = "totp"
    if code.isdigit() and len(code) == 6:
        ok = verify_totp(user.totp_secret, code)
    elif code:
        # Recovery code (format XXXX-XXXX), single use.
        method = "recovery_code"
        for rc in db.query(RecoveryCode).filter(
            RecoveryCode.user_id == user.id, RecoveryCode.used.is_(False)
        ).all():
            if verify_password(code.upper(), rc.code_hash) or verify_password(code, rc.code_hash):
                rc.used = True
                rc.used_at = datetime.now(timezone.utc)
                db.commit()
                ok = True
                break

    if not ok:
        _register_failed_attempt(db, user, request, "wrong_2fa_code")
        raise HTTPException(status_code=401, detail="Invalid authentication code")

    return issue_session_tokens(db, user, request, method=f"password+{method}")


def _validate_token_version(user: User, payload: dict) -> None:
    """Raise 401 if the token's embedded version is stale."""
    if payload.get("tv") != (user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token with rotation.

    SECURITY: On each refresh, the old refresh token is invalidated and a new
    pair is issued. If a revoked refresh token is reused (reuse detection), ALL
    sessions for the user are terminated — indicating token theft.
    """
    payload = decode_token(token_data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    _validate_token_version(user, payload)

    # Find the session matching this refresh token
    old_token_hash = hash_api_key(token_data.refresh_token)
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.refresh_token_hash == old_token_hash,
    ).first()

    if not session:
        # Refresh tokens are only valid while their session exists. This also
        # makes "revoke session" in the UI actually end that session.
        raise HTTPException(status_code=401, detail="Session not found. Please log in again.")

    if not session.is_active:
        # REUSE DETECTION: A revoked refresh token was reused.
        # This strongly suggests token theft. Kill all sessions.
        logger.warning(f"Refresh token reuse detected for user {user_id} — terminating all sessions")
        db.query(UserSession).filter(UserSession.user_id == user_id).update({"is_active": False})
        # Bump token version to invalidate all outstanding tokens
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Refresh token reuse detected. All sessions have been terminated.",
        )

    # Invalidate the old session
    session.is_active = False

    # Issue new token pair
    token_version = user.token_version or 0
    new_access = create_access_token(
        data={"sub": user.id, "role": user.role, "tv": token_version}
    )
    new_refresh = create_refresh_token(
        data={"sub": user.id, "tv": token_version}
    )

    # Create new session with the new refresh token
    new_session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_api_key(new_refresh),
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        browser=session.browser,
        os=session.os,
        is_active=True,
    )
    db.add(new_session)
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "requires_2fa": False,
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Server-side logout: invalidate all refresh tokens and sessions."""
    current_user.token_version = (current_user.token_version or 0) + 1
    # Also deactivate all sessions for this user
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active,
    ).update({"is_active": False})
    db.commit()
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    """Request a password reset token."""
    user = find_user_by_email(db, data.email)
    if user and user.is_active:
        from secrets import token_urlsafe
        user.reset_token = token_urlsafe(32)
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
        db.commit()

        reset_url = frontend_url(f"/auth/reset-password?token={user.reset_token}")
        try:
            email_service = get_email_service()
            subject, html = templates.password_reset(
                user.full_name or user.email, reset_url
            )
            email_service.send_async(to=user.email, subject=subject, html_body=html)
        except Exception as e:
            logger.error(f"Failed to send reset email: {e}")

        log_auth_event(db, "password_reset_requested", user.id,
                       ip_address=request.client.host if request.client else None,
                       detail={"email": user.email})
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(data: PasswordReset, request: Request, db: Session = Depends(get_db)):
    """Reset password with token."""
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    expires = user.reset_token_expires
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired")
    user.hashed_password = get_password_hash(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    # Invalidate all existing sessions/tokens
    user.token_version = (user.token_version or 0) + 1
    db.commit()

    try:
        email_service = get_email_service()
        subject, html = templates.password_changed(user.full_name or user.email, "unknown")
        email_service.send_async(to=user.email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send password changed email: {e}")

    log_auth_event(db, "password_reset_completed", user.id,
                   ip_address=request.client.host if request.client else None)

    # Dispatch password changed notification
    try:
        client_ip = request.client.host if request.client else "unknown"
        dispatch_notification(
            db=db,
            organization_id=user.organization_id,
            user_id=user.id,
            notification_type="password_changed",
            title="Password changed",
            message="Your password was changed via reset link.",
            related_entity_type="user",
            related_entity_id=user.id,
            data={
                "ip_address": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Failed to dispatch password changed notification: {e}")

    return {"message": "Password reset successfully"}


# ==================== 2FA / TOTP ====================

@router.post("/2fa/setup", response_model=TOTPSetup)
async def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate TOTP secret and QR provisioning URI."""
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.commit()
    import pyotp
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email, issuer_name="CAZO"
    )
    return TOTPSetup(provisioning_uri=provisioning_uri)


@router.post("/2fa/enable")
async def enable_2fa(data: TOTPVerify, current_user: User = Depends(get_current_user),
                     request: Request = None, db: Session = Depends(get_db)):
    """Enable 2FA after verifying a TOTP code."""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Run /2fa/setup first")
    if not verify_totp(current_user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.totp_enabled = True
    db.commit()

    try:
        email_service = get_email_service()
        subject, html = templates.mfa_enabled(current_user.full_name or current_user.email)
        email_service.send_async(to=current_user.email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send MFA enabled email: {e}")

    log_auth_event(db, "mfa_enabled", current_user.id,
                   ip_address=request.client.host if request and request.client else None)

    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(data: TOTPVerify, current_user: User = Depends(get_current_user),
                      request: Request = None, db: Session = Depends(get_db)):
    """Disable 2FA after verifying current TOTP code."""
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")
    if not verify_totp(current_user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()

    try:
        email_service = get_email_service()
        subject, html = templates.mfa_disabled(current_user.full_name or current_user.email, "unknown")
        email_service.send_async(to=current_user.email, subject=subject, html_body=html)
    except Exception as e:
        logger.error(f"Failed to send MFA disabled email: {e}")

    log_auth_event(db, "mfa_disabled", current_user.id,
                   ip_address=request.client.host if request and request.client else None)

    return {"message": "2FA disabled successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return current_user
