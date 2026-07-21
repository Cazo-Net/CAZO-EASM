"""Subscription plan definitions and feature entitlements.

Each plan defines:
- Metadata (name, description, pricing)
- Usage limits (-1 = unlimited)
- Feature flags (which features are enabled)
"""

from typing import Dict, List, Any


PLAN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free",
        "description": "Get started with basic EASM capabilities",
        "price_monthly": 0,
        "price_yearly": 0,
        "trial_days": 0,
        "limits": {
            "assets": 50,
            "domains": 5,
            "subdomains": 25,
            "projects": 1,
            "scans_per_month": 5,
            "storage_mb": 50,
            "ai_requests_per_month": 0,
            "reports_per_month": 2,
            "api_calls_per_month": 100,
            "users": 1,
            "api_keys": 1,
        },
        "features": [
            "basic_scans",
        ],
    },
    "free_trial": {
        "id": "free_trial",
        "name": "Free Trial",
        "description": "14-day trial of Professional plan features",
        "price_monthly": 0,
        "price_yearly": 0,
        "trial_days": 14,
        "limits": {
            "assets": 100,
            "domains": 10,
            "subdomains": 50,
            "projects": 2,
            "scans_per_month": 10,
            "storage_mb": 100,
            "ai_requests_per_month": 50,
            "reports_per_month": 5,
            "api_calls_per_month": 1000,
            "users": 3,
            "api_keys": 3,
        },
        "features": [
            "basic_scans",
            "basic_reports",
            "basic_ai",
        ],
    },
    "starter": {
        "id": "starter",
        "name": "Starter",
        "description": "For small teams getting started with attack surface management",
        "price_monthly": 4900,
        "price_yearly": 49000,
        "trial_days": 0,
        "stripe_price_id_monthly": "STRIPE_PRICE_STARTER",
        "stripe_price_id_yearly": "STRIPE_PRICE_STARTER_YEARLY",
        "limits": {
            "assets": 500,
            "domains": 50,
            "subdomains": 250,
            "projects": 10,
            "scans_per_month": 50,
            "storage_mb": 1024,
            "ai_requests_per_month": 200,
            "reports_per_month": 20,
            "api_calls_per_month": 10000,
            "users": 5,
            "api_keys": 5,
        },
        "features": [
            "basic_scans",
            "basic_reports",
            "basic_ai",
            "continuous_monitoring",
            "alerts",
            "email_notifications",
        ],
    },
    "professional": {
        "id": "professional",
        "name": "Professional",
        "description": "For growing security teams needing advanced capabilities",
        "price_monthly": 19900,
        "price_yearly": 199000,
        "trial_days": 0,
        "stripe_price_id_monthly": "STRIPE_PRICE_PROFESSIONAL",
        "stripe_price_id_yearly": "STRIPE_PRICE_PROFESSIONAL_YEARLY",
        "limits": {
            "assets": 5000,
            "domains": 200,
            "subdomains": 2000,
            "projects": 50,
            "scans_per_month": 200,
            "storage_mb": 10240,
            "ai_requests_per_month": 1000,
            "reports_per_month": 100,
            "api_calls_per_month": 100000,
            "users": 20,
            "api_keys": 10,
        },
        "features": [
            "basic_scans",
            "advanced_scans",
            "basic_reports",
            "advanced_reports",
            "basic_ai",
            "advanced_ai",
            "continuous_monitoring",
            "alerts",
            "email_notifications",
            "replay",
            "graph",
            "exports",
            "api_access",
            "webhooks",
        ],
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "description": "For large organizations requiring unlimited scale and premium support",
        "price_monthly": 0,
        "price_yearly": 0,
        "trial_days": 0,
        "stripe_price_id_monthly": "STRIPE_PRICE_ENTERPRISE",
        "stripe_price_id_yearly": "STRIPE_PRICE_ENTERPRISE_YEARLY",
        "limits": {
            "assets": -1,
            "domains": -1,
            "subdomains": -1,
            "projects": -1,
            "scans_per_month": -1,
            "storage_mb": -1,
            "ai_requests_per_month": -1,
            "reports_per_month": -1,
            "api_calls_per_month": -1,
            "users": -1,
            "api_keys": -1,
        },
        "features": [
            "all",
        ],
    },
}


def get_plan_info(plan_id: str) -> Dict[str, Any]:
    """Get plan definition by ID."""
    return PLAN_DEFINITIONS.get(plan_id, PLAN_DEFINITIONS["free"])


def get_plan_limits(plan_id: str) -> Dict[str, int]:
    """Get usage limits for a plan."""
    plan = get_plan_info(plan_id)
    return plan.get("limits", {})


def get_plan_features(plan_id: str) -> List[str]:
    """Get enabled features for a plan."""
    plan = get_plan_info(plan_id)
    return plan.get("features", [])


def is_feature_enabled(plan_id: str, feature: str) -> bool:
    """Check if a feature is enabled for a plan."""
    features = get_plan_features(plan_id)
    if "all" in features:
        return True
    return feature in features


def check_usage_limit(plan_id: str, metric: str, current_usage: int) -> bool:
    """Check if usage is within plan limits. Returns True if allowed."""
    limits = get_plan_limits(plan_id)
    limit = limits.get(metric, 0)
    if limit == -1:
        return True
    return current_usage < limit


def get_remaining_capacity(plan_id: str, metric: str, current_usage: int) -> int:
    """Get remaining capacity for a metric. Returns -1 if unlimited."""
    limits = get_plan_limits(plan_id)
    limit = limits.get(metric, 0)
    if limit == -1:
        return -1
    return max(0, limit - current_usage)


def list_all_plans() -> List[Dict[str, Any]]:
    """List all available plans with full details."""
    return [
        {
            "id": plan["id"],
            "name": plan["name"],
            "description": plan["description"],
            "price_monthly": plan["price_monthly"],
            "price_yearly": plan["price_yearly"],
            "limits": plan["limits"],
            "features": plan["features"],
        }
        for plan in PLAN_DEFINITIONS.values()
        if plan["id"] != "free_trial"
    ]
