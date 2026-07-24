from sqlalchemy import Column, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"

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

    # Billing
    billing_email = Column(String(255), nullable=True)
    tax_id = Column(String(100), nullable=True)
    invoice_prefix = Column(String(20), nullable=True)
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)

    # Trial
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)

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
