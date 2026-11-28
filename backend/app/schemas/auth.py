from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
import re


def _normalize_email(v):
    """Emails are case-insensitive: store and compare them lower-cased."""
    return v.strip().lower() if isinstance(v, str) else v


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v):
        return _normalize_email(v)


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v):
        return _normalize_email(v)


class UserResponse(UserBase):
    id: str
    role: str
    organization_id: Optional[str] = None
    is_active: bool
    email_verified: bool = False
    totp_enabled: bool = False
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Login result.

    When the account has two-factor authentication enabled, the password step
    returns ``requires_2fa=True`` and a short-lived ``mfa_token`` instead of
    session tokens. The client then calls POST /auth/2fa/verify-login.
    """
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    mfa_token: Optional[str] = None


class TwoFactorLogin(BaseModel):
    mfa_token: str
    code: str


class TokenRefresh(BaseModel):
    refresh_token: str


class VerifyEmail(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v):
        return _normalize_email(v)


class PasswordReset(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class TOTPSetup(BaseModel):
    provisioning_uri: str


class TOTPVerify(BaseModel):
    code: str
