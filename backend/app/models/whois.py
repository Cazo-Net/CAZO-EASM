from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class WhoisRecord(Base):
    __tablename__ = "whois_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(255), nullable=False, index=True)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    registrar = Column(String(255))
    creation_date = Column(DateTime(timezone=True))
    expiration_date = Column(DateTime(timezone=True))
    updated_date = Column(DateTime(timezone=True))
    name_servers = Column(JSON, default=list)
    registrant_name = Column(String(255))
    registrant_org = Column(String(255))
    registrant_country = Column(String(100))
    raw_text = Column(Text)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="whois_records")
