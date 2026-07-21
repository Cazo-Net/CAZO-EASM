"""Google OAuth credential verification service.

Uses google-auth to verify ID tokens issued by Google Identity Services.
"""
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleOAuthError(Exception):
    """Raised when Google token verification fails."""
    pass


def verify_google_credential(credential: str) -> dict:
    """Verify a Google ID token and return the decoded payload.

    Args:
        credential: The JWT ID token from Google Identity Services.

    Returns:
        Dict with keys: sub, email, name, picture, email_verified.

    Raises:
        GoogleOAuthError: If verification fails.
    """
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise GoogleOAuthError("Google OAuth is not configured (GOOGLE_CLIENT_ID missing)")

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except Exception as exc:
        logger.warning(f"Google token verification failed: {exc}")
        raise GoogleOAuthError(f"Invalid Google credential: {exc}") from exc

    if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleOAuthError(f"Invalid issuer: {idinfo.get('iss')}")

    return {
        "sub": idinfo["sub"],
        "email": idinfo.get("email", ""),
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", ""),
        "email_verified": idinfo.get("email_verified", False),
    }
