from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    stripe_invoice_id = Column(String(255), unique=True, nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="usd")
    status = Column(String(30), nullable=False, default="open")

    invoice_url = Column(String(500), nullable=True)
    invoice_pdf_url = Column(String(500), nullable=True)

    period_starts_at = Column(DateTime(timezone=True), nullable=True)
    period_ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)

    description = Column(String(500), nullable=False)
    amount_cents = Column(Integer, nullable=False, default=0)
    quantity = Column(Integer, nullable=False, default=1)

    period_starts_at = Column(DateTime(timezone=True), nullable=True)
    period_ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
