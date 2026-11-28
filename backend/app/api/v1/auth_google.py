"""Google sign-in.

GET  /api/v1/auth/google/config  tells the frontend whether Google sign-in is
     on and which client ID to use. It is on when GOOGLE_CLIENT_ID is set.
POST /api/v1/auth/google  accepts a Google ID token, creates or links a user,
     and returns the same JWT pair as the regular login endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.services.google_oauth import verify_google_credential, GoogleOAuthError
from app.api.v1.auth import find_user_by_email, issue_session_tokens, mfa_challenge
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GoogleLoginRequest:
    """Request body for Google OAuth login."""
    def __init__(self, credential: str):
        self.credential = credential


@router.get("/google/config")
def google_config():
    """Public: whether Google sign-in is enabled, and the OAuth client ID.

    The client ID is not a secret (it is embedded in every page that shows the
    Google button). Serving it here means one backend variable turns the
    feature on, with no frontend rebuild.
    """
    client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
    return {"enabled": bool(client_id), "client_id": client_id or None}


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
        if not (settings.GOOGLE_CLIENT_ID or "").strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google sign-in is not enabled.",
            )
        logger.warning(f"Google sign-in rejected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google sign-in failed. Please try again.",
        )

    google_id = google_user["sub"]
    email = (google_user["email"] or "").strip().lower()
    name = google_user["name"]

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )
    if google_user.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Google account email is not verified.",
        )

    # 1. Look up by google_id
    user = db.query(User).filter(User.google_id == google_id).first()

    # 2. If not found, look up by email
    if not user:
        user = find_user_by_email(db, email)
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

    db.commit()
    db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    if user.totp_enabled and user.totp_secret:
        return mfa_challenge(user)

    return issue_session_tokens(db, user, request, method="google")
