from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Integer, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Composite indexes for 1M+ user queries
        Index("ix_users_org_active", "organization_id", "is_active"),
        Index("ix_users_org_role", "organization_id", "role"),
        Index("ix_users_email_active", "email", "is_active"),
        Index("ix_users_created_at", "created_at"),
        Index("ix_users_last_login", "last_login"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255))
    role = Column(String(20), default="member")
    organization_id = Column(String(36), ForeignKey("organizations.id"), index=True)
    is_active = Column(Boolean, default=True)
    api_key = Column(String(255), unique=True, index=True)
    preferences = Column(JSON, default=lambda: {
        "email_notifications": True,
        "ssl_expiry_alerts": True,
        "weekly_reports": False,
        "scan_complete_alerts": True,
    })

    # Google OAuth (nullable for password-only users)
    google_id = Column(String(255), unique=True, nullable=True, index=True)

    # Brute-force protection
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Email verification
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True, index=True)

    # Password reset
    reset_token = Column(String(255), nullable=True, index=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    # 2FA / TOTP
    totp_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(255), nullable=True)

    # Password expiry
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    password_expires_at = Column(DateTime(timezone=True), nullable=True)

    # MFA enforcement
    mfa_enforced = Column(Boolean, default=False)

    # Token invalidation (incremented on logout / password change to revoke
    # all existing refresh tokens)
    token_version = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
