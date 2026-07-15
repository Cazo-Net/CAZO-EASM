from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False, index=True)
    overall_score = Column(Integer, nullable=False)
    breakdown = Column(JSON, default=dict)
    factors = Column(JSON, default=list)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="risk_scores")
