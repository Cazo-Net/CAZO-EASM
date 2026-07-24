"""Subscription management service.

Handles subscription lifecycle, plan limits, feature gating,
and usage tracking against plan entitlements.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.usage_record import UsageAggregation
from app.plans import (
    get_plan_info,
    get_plan_limits,
    get_plan_features,
    is_feature_enabled,
    list_all_plans,
)
from app.config import settings

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for subscription and plan management."""

    def __init__(self, db: Session):
        self.db = db

    def get_org_subscription(self, org_id: str) -> Optional[Subscription]:
        """Get the current subscription for an organization."""
        return self.db.query(Subscription).filter(
            Subscription.organization_id == org_id
        ).first()

    def get_or_create_subscription(
        self, org_id: str, plan: str = "free"
    ) -> Subscription:
        """Get existing subscription or create one."""
        sub = self.get_org_subscription(org_id)
        if sub:
            return sub

        sub = Subscription(
            organization_id=org_id,
            plan=plan,
            status="active",
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def get_current_plan(self, org_id: str) -> str:
        """Get the current plan for an organization."""
        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            return org.plan

        sub = self.get_org_subscription(org_id)
        if sub:
            return sub.plan

        return "free"

    def get_plan_limits_for_org(self, org_id: str) -> Dict[str, int]:
        """Get plan limits for an organization."""
        plan = self.get_current_plan(org_id)
        return get_plan_limits(plan)

    def get_plan_features_for_org(self, org_id: str) -> List[str]:
        """Get enabled features for an organization."""
        plan = self.get_current_plan(org_id)
        return get_plan_features(plan)

    def is_feature_enabled_for_org(self, org_id: str, feature: str) -> bool:
        """Check if a feature is enabled for an organization."""
        plan = self.get_current_plan(org_id)
        return is_feature_enabled(plan, feature)

    def check_usage_limit_for_org(
        self, org_id: str, metric: str
    ) -> Dict[str, Any]:
        """Check if an organization is within usage limits for a metric.

        Returns dict with:
            - allowed: bool
            - current: int
            - limit: int
            - remaining: int (-1 if unlimited)
            - percentage: float
        """
        plan = self.get_current_plan(org_id)
        limits = get_plan_limits(plan)
        limit = limits.get(metric, 0)

        current = self._get_current_usage(org_id, metric)

        if limit == -1:
            return {
                "allowed": True,
                "current": current,
                "limit": -1,
                "remaining": -1,
                "percentage": 0,
            }

        allowed = current < limit
        remaining = max(0, limit - current)
        percentage = (current / limit * 100) if limit > 0 else 0

        return {
            "allowed": allowed,
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "percentage": round(percentage, 1),
        }

    def get_usage_summary(self, org_id: str) -> Dict[str, Any]:
        """Get complete usage summary for an organization."""
        plan = self.get_current_plan(org_id)
        limits = get_plan_limits(plan)

        metrics = {}
        for metric, limit in limits.items():
            current = self._get_current_usage(org_id, metric)
            if limit == -1:
                metrics[metric] = {
                    "current": current,
                    "limit": -1,
                    "remaining": -1,
                    "percentage": 0,
                    "unlimited": True,
                }
            else:
                remaining = max(0, limit - current)
                percentage = (current / limit * 100) if limit > 0 else 0
                metrics[metric] = {
                    "current": current,
                    "limit": limit,
                    "remaining": remaining,
                    "percentage": round(percentage, 1),
                    "unlimited": False,
                }

        return {
            "plan": plan,
            "plan_info": get_plan_info(plan),
            "metrics": metrics,
        }

    def list_plans(self) -> List[Dict[str, Any]]:
        """List all available plans."""
        return list_all_plans()

    def start_trial(self, org_id: str, plan: str = "free_trial") -> Subscription:
        """Start a free trial for an organization."""
        from datetime import timedelta

        sub = self.get_org_subscription(org_id)
        if sub and sub.status == "trialing":
            raise ValueError("Organization already has an active trial")

        trial_days = settings.TRIAL_DURATION_DAYS
        now = datetime.now(timezone.utc)
        trial_end = now + timedelta(days=trial_days)

        if sub:
            sub.plan = plan
            sub.status = "trialing"
            sub.trial_starts_at = now
            sub.trial_ends_at = trial_end
        else:
            sub = Subscription(
                organization_id=org_id,
                plan=plan,
                status="trialing",
                trial_starts_at=now,
                trial_ends_at=trial_end,
            )
            self.db.add(sub)

        self.db.commit()
        self.db.refresh(sub)

        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            org.plan = plan
            org.trial_ends_at = trial_end
            self.db.commit()

        return sub

    def handle_trial_expiration(self, org_id: str) -> None:
        """Handle trial expiration - downgrade to free plan."""
        sub = self.get_org_subscription(org_id)
        if not sub:
            return

        sub.plan = "free"
        sub.status = "active"
        sub.trial_starts_at = None
        sub.trial_ends_at = None
        self.db.commit()

        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        if org:
            org.plan = "free"
            self.db.commit()

        logger.info(f"Trial expired for org {org_id}, downgraded to free")

    def handle_payment_failure(self, org_id: str) -> Dict[str, Any]:
        """Handle a payment failure.

        Returns dict with:
            - should_suspend: bool
            - failure_count: int
            - grace_period_ends: datetime or None
        """
        sub = self.get_org_subscription(org_id)
        if not sub:
            return {"should_suspend": False, "failure_count": 0, "grace_period_ends": None}

        sub.payment_failed_count = (sub.payment_failed_count or 0) + 1
        sub.status = "past_due"

        if sub.payment_failed_count >= 3:
            from datetime import timedelta
            sub.grace_period_ends_at = datetime.now(timezone.utc) + timedelta(
                days=settings.GRACE_PERIOD_DAYS
            )
            self.db.commit()
            return {
                "should_suspend": False,
                "failure_count": sub.payment_failed_count,
                "grace_period_ends": sub.grace_period_ends_at,
            }

        self.db.commit()
        return {
            "should_suspend": False,
            "failure_count": sub.payment_failed_count,
            "grace_period_ends": None,
        }

    def handle_grace_period_expiration(self, org_id: str) -> bool:
        """Suspend an organization after grace period expires.

        Returns True if the org was suspended.
        """
        sub = self.get_org_subscription(org_id)
        if not sub:
            return False

        if sub.grace_period_ends_at and sub.grace_period_ends_at <= datetime.now(timezone.utc):
            sub.status = "suspended"
            self.db.commit()

            org = self.db.query(Organization).filter(Organization.id == org_id).first()
            if org:
                org.is_active = False
                self.db.commit()

            logger.warning(f"Organization {org_id} suspended due to payment failure")
            return True

        return False

    def _get_current_usage(self, org_id: str, metric: str) -> int:
        """Get current usage count for a metric in the current billing period."""
        now = datetime.now(timezone.utc)

        sub = self.get_org_subscription(org_id)
        if sub and sub.current_period_starts_at:
            pass

        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at <= now,
            UsageAggregation.period_ends_at >= now,
        ).first()

        if usage:
            return getattr(usage, metric, 0) or 0

        return self._count_metric(org_id, metric)

    def _count_metric(self, org_id: str, metric: str) -> int:
        """Count current usage by querying the database directly."""
        from app.models.scan import Scan
        from app.models.asset_inventory import Asset
        from app.models.project import Project
        from app.models.user import User
        from app.models.report import Report

        metric_queries = {
            "assets": lambda: self.db.query(func.count(Asset.id)).filter(
                Asset.organization_id == org_id
            ).scalar() or 0,
            "projects": lambda: self.db.query(func.count(Project.id)).filter(
                Project.organization_id == org_id
            ).scalar() or 0,
            "scans": lambda: self.db.query(func.count(Scan.id)).filter(
                Scan.created_by.in_(
                    self.db.query(User.id).filter(User.organization_id == org_id)
                )
            ).scalar() or 0,
            "users": lambda: self.db.query(func.count(User.id)).filter(
                User.organization_id == org_id,
                User.is_active,
            ).scalar() or 0,
            "reports": lambda: self.db.query(func.count(Report.id)).filter(
                Report.generated_by.in_(
                    self.db.query(User.id).filter(User.organization_id == org_id)
                )
            ).scalar() or 0,
        }

        counter = metric_queries.get(metric)
        if counter:
            return counter()
        return 0
