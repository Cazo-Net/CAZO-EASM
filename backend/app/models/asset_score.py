"""Persisted asset scores (health + exposure)."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AssetScore(Base):
    __tablename__ = "asset_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # 0-100, higher is healthier.
    health_score = Column(Float, default=100.0)
    # 0-100, higher is more exposed.
    exposure_score = Column(Float, default=0.0)
    health_factors = Column(JSON, default=list)
    exposure_factors = Column(JSON, default=list)
    scored_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
