from pydantic import BaseModel
from typing import Optional


class CheckoutSessionCreate(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: str


class BillingPortalCreate(BaseModel):
    return_url: str


class BillingPortalResponse(BaseModel):
    url: str


class WebhookEventResponse(BaseModel):
    id: str
    stripe_event_id: str
    event_type: str
    processed: bool
    error: Optional[str] = None
