"""Platform-wide operational log model.

Captures application errors, scan events, auth events, security events,
notification delivery, API request summaries, and unexpected exceptions
in a single queryable table for the admin panel Logs view.

Category/severity are indexed for fast filtered queries. The ``detail``
JSON column holds structured metadata (stack traces, request context,
scanner status) that varies per category.
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, Float, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class PlatformLog(Base):
    __tablename__ = "platform_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    detail = Column(JSON, nullable=True)

    organization_id = Column(String(36), nullable=True)
    user_id = Column(String(36), nullable=True)
    request_id = Column(String(32), nullable=True)
    client_ip = Column(String(45), nullable=True)
    path = Column(String(512), nullable=True)
    method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)

    related_entity_type = Column(String(40), nullable=True)
    related_entity_id = Column(String(36), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_platform_logs_cat_time", "category", "created_at"),
        Index("ix_platform_logs_sev_time", "severity", "created_at"),
        Index("ix_platform_logs_org_time", "organization_id", "created_at"),
        Index("ix_platform_logs_user_time", "user_id", "created_at"),
        Index("ix_platform_logs_request", "request_id"),
    )
