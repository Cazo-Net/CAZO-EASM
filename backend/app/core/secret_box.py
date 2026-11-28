"""Encrypt small secrets (customer integration credentials) before storing them.

Uses Fernet (AES-128-CBC + HMAC-SHA256). The key comes from
``INTEGRATIONS_ENCRYPTION_KEY`` or, when that is empty, is derived from
``SECRET_KEY``. It lives in configuration, never in the database, so a copy
of the database alone does not reveal customers' tokens.

Changing the key makes stored credentials unreadable: customers would have to
enter them again. ``decrypt`` then raises ``SecretUnreadable``.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretUnreadable(Exception):
    """The stored secret cannot be decrypted with the current key."""


def _fernet() -> Fernet:
    raw = settings.INTEGRATIONS_ENCRYPTION_KEY or settings.SECRET_KEY or ""
    key = hashlib.sha256(b"cazo-integrations:v1:" + raw.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(values: Dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(values, sort_keys=True).encode()).decode()


def decrypt(token: str) -> Dict[str, Any]:
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError) as exc:
        raise SecretUnreadable("Stored credentials cannot be read with the current key") from exc
