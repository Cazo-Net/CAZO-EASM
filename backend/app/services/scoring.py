"""Asset health and exposure scoring.

Two complementary, deterministic, unit-testable scores:

- ``HealthScorer`` reflects *operational* health: is the asset alive, are its
  certificates valid and not expiring, is it running current technology? Higher
  is healthier.
- ``ExposureScorer`` reflects *attack surface*: internet-facing open ports,
  especially high-risk services, weighted by the severity of any findings on the
  asset. Higher means more exposed.

Both are pure functions over a normalized asset snapshot, so they can be exercised
in unit tests without a database and reused by the dashboard, AI context, and
report generation. Results are persisted to ``AssetScore``.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.asset_inventory import Asset
from app.models.asset_score import AssetScore

logger = logging.getLogger(__name__)

# Severity -> exposure weight used by ExposureScorer.
_SEVERITY_WEIGHT = {
    "critical": 10.0,
    "high": 6.0,
    "medium": 3.0,
    "low": 1.0,
    "info": 0.5,
    "unknown": 0.5,
}

# Service -> intrinsic exposure weight (broadly reachable / sensitive services).
_SERVICE_WEIGHT = {
    "http": 1.0,
    "https": 1.0,
    "ssh": 2.0,
    "telnet": 5.0,
    "ftp": 3.0,
    "smb": 4.0,
    "rdp": 4.0,
    "dns": 1.0,
    "smtp": 2.0,
    "database": 3.0,
    "mqtt": 3.0,
}


@dataclass
class HealthResult:
    score: float  # 0-100, higher is healthier
    factors: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ExposureResult:
    score: float  # 0-100, higher is more exposed
    factors: List[Dict[str, str]] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def score_health(asset: Dict) -> HealthResult:
    """Compute a 0-100 health score for a normalized asset snapshot.

    ``asset`` keys: is_alive (bool), cert_valid (bool|None),
    cert_days_left (int|None), tech_stale (bool|None).
    """
    factors: List[Dict[str, str]] = []
    score = 100.0

    if asset.get("is_alive") is False:
        score -= 40
        factors.append({"detail": "Asset is not reachable (dead).", "impact": "-40"})
    elif asset.get("is_alive") is None:
        factors.append({"detail": "Reachability unknown.", "impact": "0"})

    days_left = asset.get("cert_days_left")
    cert_valid = asset.get("cert_valid")
    if cert_valid is False:
        score -= 25
        factors.append({"detail": "SSL certificate is invalid.", "impact": "-25"})
    elif days_left is not None:
        if days_left < 0:
            score -= 25
            factors.append({"detail": "SSL certificate expired.", "impact": "-25"})
        elif days_left <= 14:
            score -= 12
            factors.append({"detail": f"Certificate expires in {days_left}d.", "impact": "-12"})
        elif days_left <= 30:
            score -= 5
            factors.append({"detail": f"Certificate expires in {days_left}d.", "impact": "-5"})

    if asset.get("tech_stale") is True:
        score -= 8
        factors.append({"detail": "Outdated technology detected.", "impact": "-8"})

    score = max(0.0, min(100.0, score))
    return HealthResult(score=round(score, 1), factors=factors)


def score_exposure(asset: Dict) -> ExposureResult:
    """Compute a 0-100 exposure score for a normalized asset snapshot.

    ``asset`` keys: open_ports (list[int]), services (list[str]),
    severities (list[str] of finding severities).
    """
    factors: List[Dict[str, str]] = []
    score = 0.0

    open_ports = asset.get("open_ports") or []
    services = [str(s).lower() for s in (asset.get("services") or [])]
    severities = [str(s).lower() for s in (asset.get("severities") or [])]

    if open_ports:
        score += min(len(open_ports) * 2.0, 30.0)
        factors.append({
            "detail": f"{len(open_ports)} open port(s).",
            "impact": f"+{min(len(open_ports) * 2.0, 30.0):.0f}",
        })

    for svc in services:
        w = _SERVICE_WEIGHT.get(svc, 1.0)
        score += w
        if w >= 3.0:
            factors.append({"detail": f"Sensitive service '{svc}' exposed.", "impact": f"+{w:.0f}"})

    sev_total = 0.0
    for sev in severities:
        w = _SEVERITY_WEIGHT.get(sev, 0.5)
        sev_total += w
    if sev_total:
        capped = min(sev_total, 40.0)
        score += capped
        factors.append({"detail": f"Findings severity load: {sev_total:.1f}.", "impact": f"+{capped:.0f}"})

    score = max(0.0, min(100.0, score))
    return ExposureResult(score=round(score, 1), factors=factors)


def compute_asset_scores(db: Session, organization_id: str) -> int:
    """Recompute and persist Health/Exposure scores for an organization's assets.

    Returns the number of assets scored. Reads canonical ``Asset`` rows plus
    associated findings. Pure-scoring functions keep this side-effect free beyond
    the DB write, which makes the logic trivially unit-testable.
    """
    assets = db.query(Asset).filter(Asset.organization_id == organization_id).all()
    count = 0
    now = _now()
    for asset in assets:
        attrs = asset.attributes or {}
        open_ports = attrs.get("open_ports", [])
        services = attrs.get("services", [])
        severities = attrs.get("severities", [])

        health = score_health({
            "is_alive": asset.is_alive,
            "cert_valid": attrs.get("cert_valid"),
            "cert_days_left": attrs.get("cert_days_left"),
            "tech_stale": attrs.get("tech_stale"),
        })
        exposure = score_exposure({
            "open_ports": open_ports,
            "services": services,
            "severities": severities,
        })

        existing = (
            db.query(AssetScore)
            .filter(AssetScore.asset_id == asset.id)
            .first()
        )
        if existing:
            existing.health_score = health.score
            existing.exposure_score = exposure.score
            existing.health_factors = health.factors
            existing.exposure_factors = exposure.factors
            existing.scored_at = now
        else:
            db.add(AssetScore(
                asset_id=asset.id,
                organization_id=organization_id,
                health_score=health.score,
                exposure_score=exposure.score,
                health_factors=health.factors,
                exposure_factors=exposure.factors,
                scored_at=now,
            ))
        count += 1
    db.commit()
    return count
