from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class DNSRecord(Base):
    __tablename__ = "dns_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subdomain_id = Column(String(36), ForeignKey("subdomains.id"), nullable=False, index=True)
    record_type = Column(String(10), nullable=False)
    value = Column(String(500), nullable=False)
    ttl = Column(Integer)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subdomain = relationship("Subdomain", back_populates="dns_records")
