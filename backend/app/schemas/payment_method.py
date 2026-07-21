from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PaymentMethodCreate(BaseModel):
    payment_method_id: str
    set_as_default: bool = False


class PaymentMethodResponse(BaseModel):
    id: str
    organization_id: str
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentMethodListResponse(BaseModel):
    payment_methods: List[PaymentMethodResponse] = []
    default_id: Optional[str] = None
