from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Port(Base):
    __tablename__ = "ports"
    __table_args__ = (
        Index("ix_ports_subdomain_number", "subdomain_id", "port_number"),
        Index("ix_ports_number", "port_number"),
        Index("ix_ports_service", "service"),
        Index("ix_ports_status", "status"),
        Index("ix_ports_scanned", "scanned_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subdomain_id = Column(String(36), ForeignKey("subdomains.id"), nullable=False, index=True)
    port_number = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False)
    service = Column(String(100))
    version = Column(String(100))
    banner = Column(String(500))
    status = Column(String(20), default="active")
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    subdomain = relationship("Subdomain", back_populates="ports")
