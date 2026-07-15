from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class SSLCertificate(Base):
    __tablename__ = "ssl_certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subdomain_id = Column(String(36), ForeignKey("subdomains.id"), nullable=False, index=True)
    issuer = Column(String(255))
    subject = Column(String(255))
    serial_number = Column(String(255))
    not_before = Column(DateTime(timezone=True))
    not_after = Column(DateTime(timezone=True))
    is_valid = Column(Boolean, default=True)
    grade = Column(String(10))
    protocol = Column(String(50))
    cipher_suite = Column(String(255))
    status = Column(String(20), default="active")
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    subdomain = relationship("Subdomain", back_populates="ssl_certificates")
