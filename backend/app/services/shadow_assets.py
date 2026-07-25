"""Shadow Asset Detection service.

A *shadow asset* is a discovered host that shares infrastructure (IP, TLS
certificate, or ASN) with an asset already confirmed as owned inventory
(``inventory_status='known'``) but was itself never confirmed. The confidence
score reflects how strongly the shared infrastructure implies common ownership:

  * shared IP            -> strong, but penalized when the IP sits on a
                            multi-tenant cloud/CDN ASN (co-tenancy != ownership)
  * shared cert serial   -> strong (same certificate == same deployment)
  * SAN overlap          -> strong (same cert covers both names)
  * shared ASN only      -> weak (many unrelated customers share a cloud ASN);
                            further suppressed for known cloud providers

The relationship graph built by :mod:`app.repositories.assets` is the sole data
source, so detection is stable across scans and additive (no raw-scan reads).
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.asset_inventory import Asset, AssetRelationship, AssetReviewLog
from app.utils.asn import is_cloud_asn


# Confidence weights (0-100)
W_IP = 70
W_CERT = 85
W_IP_AND_CERT = 95
W_ASN_DEDICATED = 60
W_ASN_CLOUD = 25

REVIEW_ACTIONS = {"confirm", "reject", "investigate"}


def _known_asset_ids(db: Session, org_id: str) -> set:
    """IDs of assets the org has confirmed as owned inventory."""
    return {
        a.id for a in db.query(Asset).filter(
            Asset.organization_id == org_id,
            Asset.inventory_status == "known",
        ).all()
    }


def _neighbors(db: Session, org_id: str, asset_id: str, rel_type: str) -> List[str]:
    """Target asset IDs reachable from ``asset_id`` via ``rel_type`` edges."""
    rels = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.organization_id == org_id,
            AssetRelationship.source_asset_id == asset_id,
            AssetRelationship.relationship_type == rel_type,
        )
        .all()
    )
    return [r.target_asset_id for r in rels]


def _reverse_neighbors(db: Session, org_id: str, asset_id: str, rel_type: str) -> List[str]:
    """Source asset IDs that point TO ``asset_id`` via ``rel_type`` (e.g. hosts
    resolving to / serving / belonging to a given IP/cert/ASN node)."""
    rels = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.organization_id == org_id,
            AssetRelationship.target_asset_id == asset_id,
            AssetRelationship.relationship_type == rel_type,
        )
        .all()
    )
    return [r.source_asset_id for r in rels]


def _san_overlap(db: Session, org_id: str, cert_asset_id: str, known_ids: set) -> bool:
    """True if any known host's cert shares a SAN with the given cert asset."""
    known_cert = db.query(Asset).filter(Asset.id == cert_asset_id).first()
    if not known_cert:
        return False
    known_sans = set((known_cert.attributes or {}).get("san") or [])
    if not known_sans:
        return False

    certs = (
        db.query(Asset)
        .filter(Asset.organization_id == org_id, Asset.asset_type == "certificate")
        .all()
    )
    for cert in certs:
        if cert.id == cert_asset_id:
            continue
        san = set((cert.attributes or {}).get("san") or [])
        if san & known_sans:
            # Only count if this cert is served by a known host.
            servers = _reverse_neighbors(db, org_id, cert.id, "serves")
            if any(s in known_ids for s in servers):
                return True
    return False


def score_signals(
    ip_signal: bool,
    cert_signal: bool,
    asn_signal: bool,
    cloud_asn: bool,
) -> int:
    """Combine matched signals into a 0-100 confidence score."""
    if ip_signal and cert_signal:
        return W_IP_AND_CERT
    if cert_signal:
        return W_CERT
    if ip_signal:
        # Shared IP on a cloud/CDN ASN is weak evidence of ownership.
        return W_IP - 30 if cloud_asn else W_IP
    if asn_signal:
        return W_ASN_CLOUD if cloud_asn else W_ASN_DEDICATED
    return 0


def detect_shadow_assets(db: Session, org_id: str) -> List[Dict]:
    """Return shadow-asset candidates for an org, highest confidence first.

    Only ``discovered`` host assets are evaluated; each is flagged when it
    shares infrastructure with at least one ``known`` asset.
    """
    known_ids = _known_asset_ids(db, org_id)
    if not known_ids:
        return []

    candidates: List[Dict] = []

    discovered_hosts = (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id,
            Asset.asset_type == "host",
            Asset.inventory_status == "discovered",
            Asset.is_alive == True,  # noqa: E712
        )
        .all()
    )

    for host in discovered_hosts:
        # --- IP signal: hosts sharing an IP with a known asset ---
        ip_signal = False
        cloud_asn = False
        shared_ip_with: List[str] = []
        for ip_id in _neighbors(db, org_id, host.id, "resolves_to"):
            ip_shared_hosts = _reverse_neighbors(db, org_id, ip_id, "resolves_to")
            known_here = [h for h in ip_shared_hosts if h in known_ids and h != host.id]
            if known_here:
                ip_signal = True
                shared_ip_with = known_here
                for asn_id in _neighbors(db, org_id, ip_id, "belongs_to"):
                    asn_asset = db.query(Asset).filter(Asset.id == asn_id).first()
                    if asn_asset:
                        cloud_asn = is_cloud_asn(asn_asset.value)

        # --- Cert signal: same cert serial OR SAN overlap with a known asset ---
        cert_signal = False
        shared_cert_with: List[str] = []
        for cert_id in _neighbors(db, org_id, host.id, "serves"):
            cert_shared_hosts = _reverse_neighbors(db, org_id, cert_id, "serves")
            known_here = [h for h in cert_shared_hosts if h in known_ids and h != host.id]
            if known_here:
                cert_signal = True
                shared_cert_with = known_here
                break
            if _san_overlap(db, org_id, cert_id, known_ids):
                cert_signal = True
                break

        # --- ASN signal: same ASN as a known asset (weak) ---
        asn_signal = False
        shared_asn_with: List[str] = []
        for asn_id in _neighbors(db, org_id, host.id, "belongs_to"):
            asn_shared_hosts = _reverse_neighbors(db, org_id, asn_id, "belongs_to")
            known_here = [h for h in asn_shared_hosts if h in known_ids and h != host.id]
            if known_here:
                asn_signal = True
                shared_asn_with = known_here

        if not (ip_signal or cert_signal or asn_signal):
            continue

        confidence = score_signals(ip_signal, cert_signal, asn_signal, cloud_asn)
        matched: List[Dict] = []
        if ip_signal:
            matched.append({"type": "shared_ip", "with": shared_ip_with})
        if cert_signal:
            matched.append({"type": "shared_cert", "with": shared_cert_with})
        if asn_signal:
            matched.append({"type": "shared_asn", "with": shared_asn_with, "cloud": cloud_asn})

        candidates.append({
            "asset_id": host.id,
            "value": host.value,
            "label": host.label,
            "first_seen": host.first_seen.isoformat() if host.first_seen else None,
            "confidence": confidence,
            "signals": matched,
        })

    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    # Dispatch notifications for high-confidence shadow assets
    from app.services.notification_service import dispatch_notification
    import logging
    _logger = logging.getLogger(__name__)
    for candidate in candidates:
        if candidate["confidence"] >= 70:
            try:
                dispatch_notification(
                    db=db,
                    organization_id=org_id,
                    notification_type="new_shadow_asset",
                    title="New shadow asset detected",
                    message=f"New shadow asset detected: {candidate['value']} (confidence: {candidate['confidence']}%)",
                    related_entity_type="asset",
                    related_entity_id=candidate["asset_id"],
                    data=candidate,
                )
            except Exception as exc:
                _logger.warning("Failed to send shadow asset notification for %s: %s", candidate.get("value"), exc)

    return candidates


def review_shadow_asset(
    db: Session,
    org_id: str,
    asset_id: str,
    action: str,
    actor_id: Optional[str] = None,
    note: Optional[str] = None,
) -> Asset:
    """Apply a review decision to a shadow/discovered asset.

    ``confirm``    -> inventory_status='known', confirmed=True (joins known inventory)
    ``reject``     -> inventory_status='rejected' (suppresses future flags)
    ``investigate``-> inventory_status='shadow' (flagged for follow-up)

    Writes an audit row to ``asset_review_log``.
    """
    if action not in REVIEW_ACTIONS:
        raise ValueError(f"Invalid review action: {action}")

    asset = db.query(Asset).filter(
        Asset.id == asset_id, Asset.organization_id == org_id
    ).first()
    if not asset:
        raise ValueError("Asset not found")

    old_status = asset.inventory_status
    if action == "confirm":
        asset.inventory_status = "known"
        asset.confirmed = True
    elif action == "reject":
        asset.inventory_status = "rejected"
        asset.confirmed = False
    else:  # investigate
        asset.inventory_status = "shadow"
        asset.confirmed = False

    asset.last_seen = datetime.now(timezone.utc)

    log = AssetReviewLog(
        organization_id=org_id,
        asset_id=asset_id,
        actor_id=actor_id,
        action=action,
        old_status=old_status,
        new_status=asset.inventory_status,
        note=note,
    )
    db.add(log)
    db.commit()
    db.refresh(asset)
    return asset
