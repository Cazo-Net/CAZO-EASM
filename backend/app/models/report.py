from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    format = Column(String(10), nullable=False)
    file_path = Column(String(500))
    file_size = Column(Integer)
    generated_by = Column(String(36), ForeignKey("users.id"))
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="reports")
