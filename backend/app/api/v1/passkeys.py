"""WebAuthn Passkey routes.

Provides passkey registration and authentication endpoints
for passwordless login.

SECURITY: passkey registration and sign-in are DISABLED.

The previous implementation never verified the WebAuthn attestation or the
assertion signature: anyone who knew (or fetched, via authenticate/begin?email=)
a user's credential_id could POST it to authenticate/complete and receive a full
session for that account. Until real verification exists (py_webauthn with a
server-stored challenge, signature + sign-count checks and a configurable RP ID),
the register/authenticate endpoints return 501. Listing and removing existing
passkey rows still works so users can clean up.
"""

import logging
import base64
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.passkey import Passkey
from app.services.audit import log_auth_event

logger = logging.getLogger(__name__)

router = APIRouter()

_DISABLED = HTTPException(
    status_code=501,
    detail="Passkeys are not available yet. Please sign in with your password.",
)

WEBAUTHN_RP_NAME = "CAZO EASM"
WEBAUTHN_RP_ID = "localhost"


@router.get("")
async def list_passkeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all passkeys for the current user."""
    passkeys = db.query(Passkey).filter(
        Passkey.user_id == current_user.id,
        Passkey.is_active,
    ).order_by(Passkey.created_at.desc()).all()

    return {
        "passkeys": [
            {
                "id": p.id,
                "device_name": p.device_name,
                "aaguid": p.aaguid,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
            }
            for p in passkeys
        ]
    }


@router.post("/register/begin")
async def register_passkey_begin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start passkey registration.

    Returns a PublicKeyCredentialCreationOptions dictionary
    that the client uses to create a new credential.
    """
    raise _DISABLED

    existing_credentials = db.query(Passkey).filter(
        Passkey.user_id == current_user.id,
        Passkey.is_active,
    ).all()

    exclude_credentials = [
        {
            "type": "public-key",
            "id": p.credential_id,
        }
        for p in existing_credentials
    ]

    # SECURITY FIX: Use cryptographically random challenge instead of
    # predictable SHA256(user_id + timestamp). The old implementation was
    # guessable — an attacker could predict the challenge and craft a
    # fraudulent assertion.
    challenge = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).rstrip(b"=").decode()

    options = {
        "challenge": challenge,
        "rp": {
            "name": WEBAUTHN_RP_NAME,
            "id": WEBAUTHN_RP_ID,
        },
        "user": {
            "id": base64.urlsafe_b64encode(current_user.id.encode()).rstrip(b"=").decode(),
            "name": current_user.email,
            "displayName": current_user.full_name or current_user.email,
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},
            {"type": "public-key", "alg": -257},
        ],
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",
            "userVerification": "preferred",
        },
        "timeout": 60000,
        "attestation": "none",
    }

    if exclude_credentials:
        options["excludeCredentials"] = exclude_credentials

    return options


@router.post("/register/complete")
async def register_passkey_complete(
    request: Request,
    credential_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete passkey registration.

    Receives the credential created by the authenticator and stores it.
    """
    raise _DISABLED

    credential_id = credential_data.get("credential_id", "")
    public_key = credential_data.get("public_key", "")
    device_name = credential_data.get("device_name", "Passkey")
    aaguid = credential_data.get("aaguid", "")
    sign_count = credential_data.get("sign_count", 0)

    if not credential_id or not public_key:
        raise HTTPException(status_code=400, detail="Missing credential data")

    existing = db.query(Passkey).filter(
        Passkey.credential_id == credential_id,
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Passkey already registered")

    passkey = Passkey(
        user_id=current_user.id,
        credential_id=credential_id,
        public_key=public_key,
        device_name=device_name,
        aaguid=aaguid,
        sign_count=sign_count,
        is_active=True,
    )
    db.add(passkey)
    db.commit()
    db.refresh(passkey)

    log_auth_event(
        db=db,
        user_id=current_user.id,
        event_type="passkey_registered",
        success=True,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
        detail={"device_name": device_name},
    )

    return {
        "id": passkey.id,
        "device_name": passkey.device_name,
        "created_at": passkey.created_at.isoformat() if passkey.created_at else None,
    }


@router.post("/authenticate/begin")
async def authenticate_passkey_begin(
    email: str,
    db: Session = Depends(get_db),
):
    """Start passkey authentication.

    Returns a PublicKeyCredentialRequestOptions dictionary.
    """
    raise _DISABLED

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    passkeys = db.query(Passkey).filter(
        Passkey.user_id == user.id,
        Passkey.is_active,
    ).all()

    if not passkeys:
        raise HTTPException(
            status_code=404,
            detail="No passkeys registered for this account",
        )

    # SECURITY FIX: Cryptographically random challenge
    challenge = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).rstrip(b"=").decode()

    options = {
        "challenge": challenge,
        "timeout": 60000,
        "rpId": WEBAUTHN_RP_ID,
        "allowCredentials": [
            {
                "type": "public-key",
                "id": p.credential_id,
                "transports": ["internal"],
            }
            for p in passkeys
        ],
        "userVerification": "preferred",
    }

    return options


@router.post("/authenticate/complete")
async def authenticate_passkey_complete(
    request: Request,
    auth_data: dict,
    db: Session = Depends(get_db),
):
    """Complete passkey authentication.

    Verifies the credential and returns JWT tokens.
    """
    raise _DISABLED

    credential_id = auth_data.get("credential_id", "")

    passkey = db.query(Passkey).filter(
        Passkey.credential_id == credential_id,
        Passkey.is_active,
    ).first()

    if not passkey:
        raise HTTPException(status_code=401, detail="Invalid passkey")

    user = db.query(User).filter(User.id == passkey.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account inactive")

    passkey.last_used_at = datetime.now(timezone.utc)
    passkey.sign_count += 1
    db.commit()

    from app.core.security import create_access_token, create_refresh_token
    # SECURITY FIX: Include token_version so passkey-issued tokens can be
    # invalidated by logout or password change (previously bypassed tv check).
    token_version = user.token_version or 0
    access_token = create_access_token({"sub": user.id, "role": user.role, "tv": token_version})
    refresh_token = create_refresh_token({"sub": user.id, "tv": token_version})

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    log_auth_event(
        db=db,
        user_id=user.id,
        event_type="passkey_login",
        success=True,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@router.delete("/{passkey_id}")
async def remove_passkey(
    passkey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a passkey."""
    passkey = db.query(Passkey).filter(
        Passkey.id == passkey_id,
        Passkey.user_id == current_user.id,
    ).first()

    if not passkey:
        raise HTTPException(status_code=404, detail="Passkey not found")

    passkey.is_active = False
    db.commit()

    return {"message": "Passkey removed", "id": passkey_id}
