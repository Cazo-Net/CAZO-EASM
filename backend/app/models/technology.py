from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Technology(Base):
    __tablename__ = "technologies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subdomain_id = Column(String(36), ForeignKey("subdomains.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    version = Column(String(100))
    confidence = Column(Integer, default=100)
    status = Column(String(20), default="active")
    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    subdomain = relationship("Subdomain", back_populates="technologies")
