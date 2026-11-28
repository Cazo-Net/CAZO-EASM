"""Single sign-on (OpenID Connect) per organization."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.sql import func

from app.database import Base


class OrgSsoConfig(Base):
    """One identity provider per organization."""

    __tablename__ = "org_sso_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)

    issuer = Column(String(500), nullable=False)
    client_id = Column(String(255), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)  # app.core.secret_box

    enabled = Column(Boolean, nullable=False, default=False)
    # Members must use SSO; password and Google sign-in are refused (owners excepted).
    enforce = Column(Boolean, nullable=False, default=False)
    # Create an account the first time a person from a verified domain signs in.
    auto_provision = Column(Boolean, nullable=False, default=True)
    default_role = Column(String(20), nullable=False, default="viewer")

    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(300), nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SsoDomain(Base):
    """An email domain an organization claims. Only verified domains route sign-ins."""

    __tablename__ = "sso_domains"
    __table_args__ = (Index("ix_sso_domains_org_domain", "organization_id", "domain", unique=True),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    verification_token = Column(String(64), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SsoLoginState(Base):
    """One sign-in attempt: the state sent to the provider, then a one-time handoff code.

    Only hashes of the state and the handoff code are stored.
    """

    __tablename__ = "sso_login_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    state_hash = Column(String(64), nullable=False, unique=True, index=True)
    nonce = Column(String(64), nullable=False)
    code_verifier = Column(String(128), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)

    handoff_hash = Column(String(64), nullable=True, unique=True, index=True)
    handoff_expires_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
