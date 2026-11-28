"""Authorized-scope models.

An authorized scope is an explicit, organization-owned authorization to assess a
target. Discovery (subdomain enumeration, port scanning, etc.) is only permitted
against targets that match at least one active scope for the owning organization.
This enforces the platform's "authorized data collection only" policy and
produces an auditable record of what was approved and by whom.
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AuthorizedScope(Base):
    __tablename__ = "authorized_scopes"
    __table_args__ = (
        Index("ix_scopes_org_type", "organization_id", "scope_type"),
        Index("ix_scopes_org_verified", "organization_id", "verified"),
        Index("ix_scopes_value", "value"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Scope kinds:
    #   domain      -> exact FQDN (e.g. "app.example.com")
    #   wildcard    -> "*.example.com" authorizes the apex and all subdomains
    #   ip          -> single IPv4/IPv6 host
    #   cidr        -> CIDR block (e.g. "10.0.0.0/24")
    scope_type = Column(String(20), nullable=False, default="domain")
    value = Column(String(512), nullable=False)
    # Whether the scope has been verified (e.g. via DNS/email/ownership proof).
    # Unverified scopes can still gate scans when REQUIRE_VERIFIED_SCOPE is off.
    verified = Column(Boolean, default=False, nullable=False)
    # Ownership proof (DNS TXT). The token is published by the customer at
    # ``_cazo-verify.<domain>`` as ``cazo-verify=<token>``.
    verification_token = Column(String(64), nullable=True)
    verification_method = Column(String(20), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    # Optional human note (ticket ref, authorization basis, etc.)
    note = Column(Text, nullable=True)
    added_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
