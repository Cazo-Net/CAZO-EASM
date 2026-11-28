"""Persisted asset change records (timeline / change detection)."""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AssetChange(Base):
    __tablename__ = "asset_changes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # Pair of scans the change was derived from.
    from_scan_id = Column(String(36), nullable=True, index=True)
    to_scan_id = Column(String(36), nullable=False, index=True)
    # Change classification.
    change_type = Column(String(20), nullable=False, index=True)  # added|removed|modified
    # What changed: domain|host|ip|service|certificate|technology|finding
    # (older rows use subdomain|port|dns).
    entity_type = Column(String(30), nullable=False)
    entity_key = Column(String(512), nullable=False)
    # Human-readable diff detail.
    detail = Column(JSON, default=dict)
    # Inventory history (app/services/inventory.py). Null on rows written
    # before the canonical inventory existed.
    asset_id = Column(String(36), nullable=True, index=True)
    # asset_new|service_new|service_closed|cert_new|cert_changed|cert_expiring|
    # tech_new|tech_changed|tech_removed|ip_changed|asset_missing|
    # asset_reappeared|finding_new
    event = Column(String(40), nullable=True, index=True)
    severity = Column(String(20), nullable=True)  # info|low|medium|high|critical
    root_domain = Column(String(255), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class InventorySync(Base):
    """One row per scan that has been folded into the inventory.

    Makes the sync idempotent and lets an older scan that is processed late
    (a rebuild from history) add first-seen dates without undoing newer state.
    """
    __tablename__ = "inventory_syncs"

    scan_id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    root_domain = Column(String(255), nullable=True, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
