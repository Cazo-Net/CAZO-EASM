"""Password policy enforcement service.

Configurable per-organization password requirements.
"""

import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization


DEFAULT_PASSWORD_POLICY = {
    "min_length": 12,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_numbers": True,
    "require_symbols": True,
    "max_age_days": 90,
    "prevent_reuse": 5,
    "min_entropy": 40,
}


def get_password_policy(db: Session, organization_id: Optional[str] = None) -> Dict[str, Any]:
    """Get the password policy for an organization or the global default."""
    if organization_id:
        org = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()

        if org and org.settings and "password_policy" in org.settings:
            policy = DEFAULT_PASSWORD_POLICY.copy()
            policy.update(org.settings["password_policy"])
            return policy

    return DEFAULT_PASSWORD_POLICY.copy()


def validate_password_strength(
    password: str,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a password against the policy.

    Returns dict with:
        - valid: bool
        - errors: list of error messages
        - strength: weak/fair/strong/very_strong
        - score: 0-100
    """
    if policy is None:
        policy = DEFAULT_PASSWORD_POLICY

    errors = []
    score = 0

    # Length check
    min_len = policy.get("min_length", 12)
    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters")
    else:
        score += min(25, len(password) * 2)

    # Uppercase
    if policy.get("require_uppercase", True) and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    elif re.search(r"[A-Z]", password):
        score += 10

    # Lowercase
    if policy.get("require_lowercase", True) and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    elif re.search(r"[a-z]", password):
        score += 10

    # Numbers
    if policy.get("require_numbers", True) and not re.search(r"\d", password):
        errors.append("Password must contain at least one number")
    elif re.search(r"\d", password):
        score += 10

    # Symbols
    if policy.get("require_symbols", True) and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one symbol")
    elif re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 10

    # Common patterns
    common_patterns = [
        r"(.)\1{2,}",  # Repeated characters
        r"(012|123|234|345|456|567|678|789|890)",  # Sequential numbers
        r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)",
    ]
    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            score -= 5

    # Entropy approximation
    charset_size = 0
    if re.search(r"[a-z]", password):
        charset_size += 26
    if re.search(r"[A-Z]", password):
        charset_size += 26
    if re.search(r"\d", password):
        charset_size += 10
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        charset_size += 30

    import math
    entropy = len(password) * math.log2(max(charset_size, 1))
    min_entropy = policy.get("min_entropy", 40)
    if entropy < min_entropy:
        errors.append(f"Password entropy too low ({entropy:.0f} bits, need {min_entropy})")
    else:
        score += min(20, int(entropy / 5))

    # Determine strength
    score = max(0, min(100, score))
    if score >= 80:
        strength = "very_strong"
    elif score >= 60:
        strength = "strong"
    elif score >= 40:
        strength = "fair"
    else:
        strength = "weak"

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "strength": strength,
        "score": score,
    }


def check_password_expired(user: User, db: Session) -> Dict[str, Any]:
    """Check if the user's password has expired.

    Returns dict with:
        - expired: bool
        - days_until_expiry: int or None
        - must_change: bool
    """
    if not user.password_expires_at:
        policy = get_password_policy(db, user.organization_id)
        max_age_days = policy.get("max_age_days", 90)

        if user.password_changed_at and max_age_days > 0:
            expires_at = user.password_changed_at + timedelta(days=max_age_days)
            days_until = (expires_at - datetime.now(timezone.utc)).days

            return {
                "expired": days_until <= 0,
                "days_until_expiry": max(0, days_until),
                "must_change": days_until <= 0,
            }

        return {
            "expired": False,
            "days_until_expiry": None,
            "must_change": False,
        }

    days_until = (user.password_expires_at - datetime.now(timezone.utc)).days
    return {
        "expired": days_until <= 0,
        "days_until_expiry": max(0, days_until),
        "must_change": days_until <= 0,
    }


def set_password_expiry(user: User, db: Session) -> None:
    """Set the password expiry date after a password change."""
    policy = get_password_policy(db, user.organization_id)
    max_age_days = policy.get("max_age_days", 90)

    user.password_changed_at = datetime.now(timezone.utc)
    if max_age_days > 0:
        user.password_expires_at = datetime.now(timezone.utc) + timedelta(days=max_age_days)
    else:
        user.password_expires_at = None

    db.commit()
