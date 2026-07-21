from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Float
from sqlalchemy.sql import func
from app.database import Base
import uuid


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    period_starts_at = Column(DateTime(timezone=True), nullable=False)
    period_ends_at = Column(DateTime(timezone=True), nullable=False)

    metric_name = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageAggregation(Base):
    __tablename__ = "usage_aggregations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    period_starts_at = Column(DateTime(timezone=True), nullable=False)
    period_ends_at = Column(DateTime(timezone=True), nullable=False)

    assets = Column(Integer, default=0)
    domains = Column(Integer, default=0)
    subdomains = Column(Integer, default=0)
    projects = Column(Integer, default=0)
    scans = Column(Integer, default=0)
    storage_mb = Column(Float, default=0)
    ai_requests = Column(Integer, default=0)
    reports = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    users = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
