from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class SubscriptionCreate(BaseModel):
    plan: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class SubscriptionUpgrade(BaseModel):
    plan: str


class SubscriptionDowngrade(BaseModel):
    plan: str


class SubscriptionCancel(BaseModel):
    at_period_end: bool = True


class SubscriptionResponse(BaseModel):
    id: str
    organization_id: str
    plan: str
    status: str
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    current_period_starts_at: Optional[datetime] = None
    current_period_ends_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    grace_period_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanInfo(BaseModel):
    id: str
    name: str
    description: str
    price_monthly: int
    price_yearly: Optional[int] = None
    features: List[str]
    limits: Dict[str, int]


class PlanListResponse(BaseModel):
    plans: List[PlanInfo]
    current_plan: Optional[str] = None
