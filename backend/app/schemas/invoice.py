from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class InvoiceLineItemResponse(BaseModel):
    id: str
    description: str
    amount_cents: int
    quantity: int
    period_starts_at: Optional[datetime] = None
    period_ends_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: str
    organization_id: str
    stripe_invoice_id: Optional[str] = None
    amount_cents: int
    currency: str
    status: str
    invoice_url: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    period_starts_at: Optional[datetime] = None
    period_ends_at: Optional[datetime] = None
    line_items: List[InvoiceLineItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total: int
