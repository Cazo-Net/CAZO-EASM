"""Plan catalog.

Prices and allowances follow the CAZO-EASM business plan (27 Nov 2026):
priced by root domain, billed annually or quarterly, no free tier at launch.

* Essentials  USD   500/month   3 root domains    250 hosts   weekly scans
* Business    USD 1,000/month  10 root domains  1,000 hosts   daily scans
* Plus        USD 2,000/month  25 root domains  3,000 hosts   daily scans
* MSSP        USD   200/client/month (min 10)  3 domains + 250 hosts per client
* Extra root domain: USD 100/month each

User seats and monthly scan counts are not in the business plan; the numbers
below are placeholders. Everything here can be overridden without a code
change through ``BILLING_PLANS_JSON``, for example::

    {"business": {"prices": {"usd": 100000, "myr": 450000}, "limits": {"users": 20}},
     "addon_extra_domain": {"prices": {"myr": 45000}}}

Prices are per month in the smallest currency unit (cents / sen); a term is
billed as ``monthly price x months`` (12 for a year, 3 for a quarter).
``None`` as a limit means unlimited.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)

LIMIT_KEYS = ("root_domains", "hosts", "users", "scans_per_month")

# interval id -> (label, months, Stripe recurring interval, interval_count)
INTERVALS: dict[str, dict] = {
    "year": {"label": "Annual", "months": 12, "stripe_interval": "year", "stripe_interval_count": 1},
    "quarter": {"label": "Quarterly", "months": 3, "stripe_interval": "month", "stripe_interval_count": 3},
}

_DEFAULT_CATALOG: dict[str, dict] = {
    # Every organization without a paid plan. Not sold; enough to try the product.
    "free": {
        "name": "Trial",
        "tagline": "Try CAZO on one domain",
        "purchasable": False,
        "prices": {},
        "limits": {"root_domains": 1, "hosts": 50, "users": 2, "scans_per_month": 10},
        "scan_frequency": "weekly",
        "features": ["1 root domain", "Up to 50 hosts", "Manual and weekly scans"],
    },
    "essentials": {
        "name": "Essentials",
        "tagline": "For a single company watching its own perimeter",
        "purchasable": True,
        "prices": {"usd": 50_000},
        "limits": {"root_domains": 3, "hosts": 250, "users": 5, "scans_per_month": 100},
        "scan_frequency": "weekly",
        "features": [
            "Dashboard and risk score",
            "CVE matching",
            "Monthly report",
            "Email alerts",
        ],
    },
    "business": {
        "name": "Business",
        "tagline": "Daily monitoring with alerts and integrations",
        "purchasable": True,
        "highlight": True,
        "prices": {"usd": 100_000},
        "limits": {"root_domains": 10, "hosts": 1_000, "users": 15, "scans_per_month": 400},
        "scan_frequency": "daily",
        "features": [
            "Everything in Essentials",
            "Change alerts",
            "Slack, Teams and Jira",
            "API access",
        ],
    },
    "plus": {
        "name": "Plus",
        "tagline": "Larger estates and a named contact",
        "purchasable": True,
        "prices": {"usd": 200_000},
        "limits": {"root_domains": 25, "hosts": 3_000, "users": 40, "scans_per_month": 1_000},
        "scan_frequency": "daily",
        "features": [
            "Everything in Business",
            "Quarterly review call",
            "Custom report branding",
        ],
    },
    "mssp": {
        "name": "MSSP",
        "tagline": "Monitor many client organizations from one console",
        "purchasable": True,
        "per_client": True,
        "min_quantity": 10,
        "prices": {"usd": 20_000},
        # Per client; multiplied by the number of clients bought.
        "limits": {"root_domains": 3, "hosts": 250, "users": None, "scans_per_month": 100},
        "scan_frequency": "daily",
        "features": [
            "Multi-client console",
            "White-label reports",
            "Volume discounts on request",
        ],
    },
    # Staff and design-partner orgs set by a platform admin; never sold online.
    "internal": {
        "name": "Internal",
        "tagline": "Unlimited, set by CAZO staff",
        "purchasable": False,
        "prices": {},
        "limits": {"root_domains": None, "hosts": None, "users": None, "scans_per_month": None},
        "scan_frequency": "daily",
        "features": [],
    },
    "addon_extra_domain": {
        "name": "Extra root domain",
        "purchasable": False,
        "addon": True,
        "prices": {"usd": 10_000},
        "limits": {},
        "features": [],
    },
}

FREE_PLAN_ID = "free"
EXTRA_DOMAIN_ADDON_ID = "addon_extra_domain"
# Minimum hours between scheduled scans for each frequency.
FREQUENCY_MIN_HOURS = {"daily": 24, "weekly": 168}


@dataclass
class Plan:
    id: str
    name: str
    tagline: str = ""
    purchasable: bool = False
    highlight: bool = False
    per_client: bool = False
    addon: bool = False
    min_quantity: int = 1
    prices: dict[str, int] = field(default_factory=dict)
    limits: dict[str, int | None] = field(default_factory=dict)
    scan_frequency: str = "weekly"
    features: list[str] = field(default_factory=list)

    def monthly_price(self, currency: str) -> int | None:
        return self.prices.get(currency.lower())

    def term_price(self, currency: str, interval: str) -> int | None:
        monthly = self.monthly_price(currency)
        if monthly is None:
            return None
        return monthly * INTERVALS[interval]["months"]


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_catalog() -> dict[str, Plan]:
    raw = copy.deepcopy(_DEFAULT_CATALOG)
    if settings.BILLING_PLANS_JSON:
        try:
            overrides = json.loads(settings.BILLING_PLANS_JSON)
            for plan_id, override in overrides.items():
                raw[plan_id] = _merge(raw.get(plan_id, {"name": plan_id}), override)
        except (ValueError, AttributeError) as exc:
            logger.error("Ignoring invalid BILLING_PLANS_JSON: %s", exc)
    catalog = {}
    for plan_id, data in raw.items():
        data = {k: v for k, v in data.items() if k in Plan.__dataclass_fields__}
        catalog[plan_id] = Plan(id=plan_id, **data)
    return catalog


_catalog: dict[str, Plan] | None = None


def catalog() -> dict[str, Plan]:
    global _catalog
    if _catalog is None:
        _catalog = _load_catalog()
    return _catalog


def reload_catalog() -> None:
    """Re-read overrides (used by tests)."""
    global _catalog
    _catalog = None


def get_plan(plan_id: str | None) -> Plan:
    plans = catalog()
    return plans.get(plan_id or FREE_PLAN_ID) or plans[FREE_PLAN_ID]


def purchasable_plans() -> list[Plan]:
    return [p for p in catalog().values() if p.purchasable]


def billing_currency() -> str:
    return (settings.BILLING_CURRENCY or "usd").lower()


def plan_limits(plan: Plan, quantity: int = 1, extra_domains: int = 0) -> dict[str, int | None]:
    """Allowances for an organization on ``plan``."""
    limits: dict[str, int | None] = {}
    multiplier = max(quantity, 1) if plan.per_client else 1
    for key in LIMIT_KEYS:
        value = plan.limits.get(key)
        limits[key] = None if value is None else value * multiplier
    if limits["root_domains"] is not None and extra_domains:
        limits["root_domains"] += extra_domains
    return limits


def order_total(plan: Plan, interval: str, quantity: int, extra_domains: int, currency: str) -> int | None:
    """Total for one billing term in the smallest currency unit."""
    base = plan.term_price(currency, interval)
    if base is None:
        return None
    total = base * (max(quantity, 1) if plan.per_client else 1)
    if extra_domains:
        addon = catalog()[EXTRA_DOMAIN_ADDON_ID].term_price(currency, interval)
        if addon is None:
            return None
        total += addon * extra_domains
    return total
