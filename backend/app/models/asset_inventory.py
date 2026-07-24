"""Canonical asset inventory and cross-asset relationships.

The existing ``Subdomain`` model is tied to a single scan. ``Asset`` is the
organization-owned, scan-independent record of a discovered entity (host, domain,
IP, certificate). Relationships between assets (e.g. ``host`` resolves to ``ip``,
``domain`` serves ``certificate``) are stored explicitly in ``AssetRelationship``
so the attack-surface graph is stable across scans and supports filtering and
clustering.

Backfill of ``Asset`` rows from existing ``Subdomain``/``Port``/``SSLCertificate``
rows is performed by a migration-safe helper (see ``app/repositories/assets.py``),
never by destructive schema changes.
"""
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Boolean, JSON, Text, UniqueConstraint,
)
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Asset kind: domain | host | ip | certificate | technology
    asset_type = Column(String(20), nullable=False, default="host", index=True)
    # Canonical identifier: FQDN, IP, or cert serial depending on type.
    value = Column(String(512), nullable=False)
    # Human-friendly label (e.g. hostname).
    label = Column(String(512), nullable=True)
    is_alive = Column(Boolean, default=True, nullable=False)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Most recent scan that observed this asset.
    last_scan_id = Column(String(36), nullable=True)
    # Free-form, queryable attributes (ports, grade, etc.).
    attributes = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Inventory confirmation state for Shadow Asset Detection.
    #   discovered  = auto-discovered via scan, not yet reviewed (default)
    #   known       = confirmed as owned inventory (user or scope match)
    #   shadow      = suspected unknown asset sharing infra with known assets
    #   rejected    = reviewed and confirmed unrelated
    confirmed = Column(Boolean, default=False, nullable=False, index=True)
    inventory_status = Column(String(20), default="discovered", nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "asset_type", "value", name="uq_asset_org_type_value"
        ),
    )


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    source_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    target_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    # Relationship kind: resolves_to | serves | belongs_to | depends_on | same_as
    relationship_type = Column(String(30), nullable=False, default="resolves_to", index=True)
    # Optional strength/confidence (0-1) for clustering.
    weight = Column(JSON, default=lambda: {"value": 1.0})
    # Scan that established/refreshed this edge.
    last_scan_id = Column(String(36), nullable=True)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "source_asset_id", "target_asset_id", "relationship_type",
            name="uq_asset_rel_src_tgt_type",
        ),
    )


class AssetReviewLog(Base):
    """Audit trail for Shadow Asset Detection review decisions.

    Every confirm / reject / investigate action on a discovered asset is logged
    here with the actor and prior state, so the inventory history is auditable.
    """
    __tablename__ = "asset_review_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    # confirm | reject | investigate
    action = Column(String(20), nullable=False, index=True)
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
