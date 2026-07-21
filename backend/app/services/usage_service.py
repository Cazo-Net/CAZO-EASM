"""Usage metering service.

Tracks and aggregates usage metrics against plan limits.
Records usage events and maintains period aggregations.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.usage_record import UsageRecord, UsageAggregation
from app.models.subscription import Subscription
from app.models.organization import Organization

logger = logging.getLogger(__name__)


class UsageService:
    """Service for usage metering and aggregation."""

    def __init__(self, db: Session):
        self.db = db

    def record_usage(
        self,
        org_id: str,
        metric: str,
        quantity: int = 1,
    ) -> None:
        """Record a usage event for a metric."""
        now = datetime.now(timezone.utc)
        period_start, period_end = self._get_current_period(org_id, now)

        record = UsageRecord(
            organization_id=org_id,
            period_starts_at=period_start,
            period_ends_at=period_end,
            metric_name=metric,
            quantity=quantity,
        )
        self.db.add(record)
        self.db.commit()

        self._update_aggregation(org_id, period_start, period_end, metric, quantity)

    def get_current_usage(self, org_id: str, metric: str) -> int:
        """Get current period usage for a metric."""
        now = datetime.now(timezone.utc)
        period_start, period_end = self._get_current_period(org_id, now)

        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at == period_start,
            UsageAggregation.period_ends_at == period_end,
        ).first()

        if usage:
            return getattr(usage, metric, 0) or 0

        return self._aggregate_metric_from_records(
            org_id, period_start, period_end, metric
        )

    def get_usage_summary(self, org_id: str) -> Dict[str, Any]:
        """Get complete usage summary for the current period."""
        now = datetime.now(timezone.utc)
        period_start, period_end = self._get_current_period(org_id, now)

        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at == period_start,
            UsageAggregation.period_ends_at == period_end,
        ).first()

        if not usage:
            usage = self._create_or_get_aggregation(
                org_id, period_start, period_end
            )

        return {
            "period_starts_at": period_start.isoformat(),
            "period_ends_at": period_end.isoformat(),
            "assets": usage.assets or 0,
            "domains": usage.domains or 0,
            "subdomains": usage.subdomains or 0,
            "projects": usage.projects or 0,
            "scans": usage.scans or 0,
            "storage_mb": usage.storage_mb or 0,
            "ai_requests": usage.ai_requests or 0,
            "reports": usage.reports or 0,
            "api_calls": usage.api_calls or 0,
            "users": usage.users or 0,
        }

    def compute_usage_from_database(self, org_id: str) -> Dict[str, int]:
        """Compute current usage by counting from the database directly.

        Used for initial aggregation and reconciliation.
        """
        from app.models.scan import Scan
        from app.models.asset_inventory import Asset
        from app.models.project import Project
        from app.models.user import User
        from app.models.report import Report

        user_ids = [
            uid for (uid,) in self.db.query(User.id)
            .filter(User.organization_id == org_id)
            .all()
        ]

        assets = self.db.query(func.count(Asset.id)).filter(
            Asset.organization_id == org_id
        ).scalar() or 0

        domains = self.db.query(func.count(Asset.id)).filter(
            Asset.organization_id == org_id,
            Asset.asset_type == "domain",
        ).scalar() or 0

        subdomains = self.db.query(func.count(Asset.id)).filter(
            Asset.organization_id == org_id,
            Asset.asset_type == "host",
        ).scalar() or 0

        projects = self.db.query(func.count(Project.id)).filter(
            Project.organization_id == org_id
        ).scalar() or 0

        scans = self.db.query(func.count(Scan.id)).filter(
            Scan.created_by.in_(user_ids) if user_ids else True
        ).scalar() or 0 if user_ids else 0

        users_count = self.db.query(func.count(User.id)).filter(
            User.organization_id == org_id,
            User.is_active == True,
        ).scalar() or 0

        reports_count = self.db.query(func.count(Report.id)).filter(
            Report.generated_by.in_(user_ids) if user_ids else True
        ).scalar() or 0 if user_ids else 0

        return {
            "assets": assets,
            "domains": domains,
            "subdomains": subdomains,
            "projects": projects,
            "scans": scans,
            "storage_mb": 0,
            "reports": reports_count,
            "api_calls": 0,
            "users": users_count,
        }

    def refresh_aggregation(self, org_id: str) -> Dict[str, Any]:
        """Refresh the current period aggregation from database counts."""
        now = datetime.now(timezone.utc)
        period_start, period_end = self._get_current_period(org_id, now)

        computed = self.compute_usage_from_database(org_id)

        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at == period_start,
            UsageAggregation.period_ends_at == period_end,
        ).first()

        if usage:
            for key, value in computed.items():
                setattr(usage, key, value)
        else:
            usage = UsageAggregation(
                organization_id=org_id,
                period_starts_at=period_start,
                period_ends_at=period_end,
                **computed,
            )
            self.db.add(usage)

        self.db.commit()
        self.db.refresh(usage)

        return {
            "period_starts_at": period_start.isoformat(),
            "period_ends_at": period_end.isoformat(),
            **computed,
        }

    def _get_current_period(
        self, org_id: str, now: datetime
    ) -> tuple:
        """Get the current billing period start and end dates."""
        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org_id
        ).first()

        if sub and sub.current_period_starts_at and sub.current_period_ends_at:
            if sub.current_period_starts_at <= now <= sub.current_period_ends_at:
                return sub.current_period_starts_at, sub.current_period_ends_at

        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)

        return period_start, period_end

    def _update_aggregation(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        metric: str,
        quantity: int,
    ) -> None:
        """Update the aggregation record for a period and metric."""
        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at == period_start,
            UsageAggregation.period_ends_at == period_end,
        ).first()

        if not usage:
            usage = UsageAggregation(
                organization_id=org_id,
                period_starts_at=period_start,
                period_ends_at=period_end,
            )
            self.db.add(usage)

        current = getattr(usage, metric, 0) or 0
        setattr(usage, metric, current + quantity)
        self.db.commit()

    def _create_or_get_aggregation(
        self, org_id: str, period_start: datetime, period_end: datetime
    ) -> UsageAggregation:
        """Create or get an aggregation record for a period."""
        usage = self.db.query(UsageAggregation).filter(
            UsageAggregation.organization_id == org_id,
            UsageAggregation.period_starts_at == period_start,
            UsageAggregation.period_ends_at == period_end,
        ).first()

        if not usage:
            computed = self.compute_usage_from_database(org_id)
            usage = UsageAggregation(
                organization_id=org_id,
                period_starts_at=period_start,
                period_ends_at=period_end,
                **computed,
            )
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

        return usage

    def _aggregate_metric_from_records(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        metric: str,
    ) -> int:
        """Aggregate a metric from individual usage records."""
        result = self.db.query(func.sum(UsageRecord.quantity)).filter(
            UsageRecord.organization_id == org_id,
            UsageRecord.period_starts_at == period_start,
            UsageRecord.period_ends_at == period_end,
            UsageRecord.metric_name == metric,
        ).scalar()

        return result or 0
