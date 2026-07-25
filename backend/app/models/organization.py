from sqlalchemy import Column, String, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_orgs_active", "is_active"),
        Index("ix_orgs_plan", "plan"),
        Index("ix_orgs_created_at", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    plan = Column(String(50), default="free")
    settings = Column(JSON, default=dict)

    # Profile
    logo_url = Column(String(500), nullable=True)
    website = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)

    # Security
    mfa_enforced = Column(Boolean, default=False)
    allowed_email_domains = Column(JSON, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", backref="organization", foreign_keys="User.organization_id")
    projects = relationship("Project", backref="organization", foreign_keys="Project.organization_id")
