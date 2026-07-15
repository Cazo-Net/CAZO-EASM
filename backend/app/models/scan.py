from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(255), nullable=False, index=True)
    project_id = Column(String(36), nullable=True)
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    scan_type = Column(String(20), default="full")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_by = Column(String(36), ForeignKey("users.id"))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subdomains = relationship("Subdomain", back_populates="scan", cascade="all, delete-orphan")
    vulnerabilities = relationship("Vulnerability", back_populates="scan", cascade="all, delete-orphan")
    whois_records = relationship("WhoisRecord", back_populates="scan", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="scan", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="scan", cascade="all, delete-orphan")
