from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Subdomain(Base):
    __tablename__ = "subdomains"
    __table_args__ = (
        Index("ix_subdomains_scan_alive", "scan_id", "is_alive"),
        Index("ix_subdomains_scan_status", "scan_id", "status"),
        Index("ix_subdomains_hostname", "hostname"),
        Index("ix_subdomains_discovered", "discovered_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    ip_addresses = Column(JSON, default=list)
    is_alive = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    os_detection = Column(JSON, default=None, nullable=True)
    host_scripts = Column(JSON, default=None, nullable=True)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="subdomains")
    ports = relationship("Port", back_populates="subdomain", cascade="all, delete-orphan")
    dns_records = relationship("DNSRecord", back_populates="subdomain", cascade="all, delete-orphan")
    ssl_certificates = relationship("SSLCertificate", back_populates="subdomain", cascade="all, delete-orphan")
    technologies = relationship("Technology", back_populates="subdomain", cascade="all, delete-orphan")
    vulnerabilities = relationship("Vulnerability", back_populates="subdomain", cascade="all, delete-orphan")
