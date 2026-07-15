from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(20), default="member")
    organization_id = Column(String(36), ForeignKey("organizations.id"))
    is_active = Column(Boolean, default=True)
    api_key = Column(String(255), unique=True, index=True)
    preferences = Column(JSON, default=lambda: {
        "email_notifications": True,
        "ssl_expiry_alerts": True,
        "weekly_reports": False,
        "scan_complete_alerts": True,
    })

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

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
