from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_org", "organization_id"),
        Index("ix_projects_created_by", "created_by"),
        Index("ix_projects_created_at", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(String(36), ForeignKey("organizations.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
