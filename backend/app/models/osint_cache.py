"""OSINT result cache — avoids re-probing the same domain repeatedly.

The cache stores serialized OSINT results keyed by domain with a configurable
TTL (default 1 hour).  On cache hit the endpoint returns instantly; on miss
it runs the full live OSINT aggregation and persists the result.
"""
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.sql import func
from app.database import Base
import uuid


class OsintCache(Base):
    __tablename__ = "osint_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(255), nullable=False, index=True, unique=True)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ttl_seconds = Column(Integer, nullable=False, default=3600)
