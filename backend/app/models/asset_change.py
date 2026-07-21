"""Persisted asset change records (timeline / change detection)."""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
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
    # What changed.
    entity_type = Column(String(30), nullable=False)  # subdomain|port|certificate|technology|dns
    entity_key = Column(String(512), nullable=False)
    # Human-readable diff detail.
    detail = Column(JSON, default=dict)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
