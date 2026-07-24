"""Google OAuth login/register endpoint.

POST /api/v1/auth/google — accepts a Google ID token, creates or links a user,
and returns the same JWT pair as the regular login endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.auth_models import UserSession
from app.schemas.auth import Token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_api_key,
)
from app.services.google_oauth import verify_google_credential, GoogleOAuthError
from app.services.audit import log_auth_event
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GoogleLoginRequest:
    """Request body for Google OAuth login."""
    def __init__(self, credential: str):
        self.credential = credential


@router.post("/google", response_model=Token)
async def google_auth(request: Request, db: Session = Depends(get_db)):
    """Login or register with Google.

    Accepts a JSON body with a single field: `credential` (the Google ID token).
    If a user with the matching google_id exists, log them in.
    If a user with the same email exists, link the Google account to that user.
    Otherwise, create a new user (no password, email_verified=True).
    """

    body = await request.json()
    credential = body.get("credential")
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'credential' field",
        )

    # Verify the Google token
    try:
        google_user = verify_google_credential(credential)
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    google_id = google_user["sub"]
    email = google_user["email"]
    name = google_user["name"]

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # 1. Look up by google_id
    user = db.query(User).filter(User.google_id == google_id).first()

    # 2. If not found, look up by email
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # SECURITY FIX: Do NOT silently link a Google account to an existing
            # password-based account. This was an account takeover vector — an
            # attacker who controls a Google account with the same email could
            # gain access without the original user's knowledge or consent.
            #
            # Instead: only allow linking if the existing account is already a
            # Google-only account (no password) or has no password set. For
            # password-based accounts, reject the link and instruct the user to
            # link from their account settings after logging in with their
            # password.
            is_google_only = (
                user.hashed_password
                and user.hashed_password.startswith("GOOGLE_OAUTH:")
            )
            if not is_google_only:
                # Password-based account exists — block silent linking.
                logger.warning(
                    f"Google OAuth attempted to link to existing password account: {email}. "
                    "Silent linking blocked — user must link from account settings."
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "An account with this email already exists. "
                        "Please log in with your password and link your Google account "
                        "from Account Settings."
                    ),
                )
            # Google-only account (no password) — safe to link.
            user.google_id = google_id
            if not user.full_name and name:
                user.full_name = name
            user.email_verified = True
            logger.info(f"Linked Google account to existing Google-only user: {email}")

    # 3. If still not found, create new user
    if not user:
        # Use a sentinel password hash — Google-only users can't log in with password
        import hashlib
        sentinel = hashlib.sha256(f"google-oauth:{google_id}".encode()).hexdigest()
        user = User(
            email=email,
            full_name=name or email.split("@")[0],
            google_id=google_id,
            email_verified=True,
            hashed_password=f"GOOGLE_OAUTH:{sentinel}",
        )
        db.add(user)
        logger.info(f"Created new user via Google: {email}")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Create session (same as normal login)
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    ua = request.headers.get("user-agent", "")

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_api_key(create_access_token(data={"sub": user.id})),
        ip_address=client_ip,
        user_agent=ua,
        browser=ua[:50] if ua else "Unknown",
        os=ua[50:100] if len(ua) > 50 else "Unknown",
    )
    db.add(session)
    db.commit()

    log_auth_event(db, "google_login_success", user.id,
                   ip_address=client_ip, detail={"session_id": session.id})

    # Issue JWT tokens (same as normal login)
    token_version = user.token_version or 0
    access_token = create_access_token(
        data={"sub": user.id, "role": user.role, "tv": token_version}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.id, "tv": token_version}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_2fa": False,
    }
