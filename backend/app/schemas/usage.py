from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime


class UsageMetric(BaseModel):
    name: str
    display_name: str
    quantity: int
    limit: int
    remaining: int
    percentage: float
    unlimited: bool = False


class UsageSummary(BaseModel):
    period_starts_at: datetime
    period_ends_at: datetime
    metrics: Dict[str, UsageMetric]
    plan: str


class UsageRecordCreate(BaseModel):
    metric_name: str
    quantity: int = 1
