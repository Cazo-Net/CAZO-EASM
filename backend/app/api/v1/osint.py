"""OSINT lookup API: passive, sourced public intelligence about an authorized domain."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.osint_cache import OsintCache
from app.api.deps import get_current_user
from app.core.permissions import Permission, require_any_permission
from app.core.scope import authorize_scan_target
from app.services import osint
from app.services.osint_import import import_osint_findings
from fastapi.concurrency import run_in_threadpool

router = APIRouter()
log = logging.getLogger("osint.api")

DEFAULT_TTL = 3600  # 1 hour


def _get_cached(domain: str, db: Session, ttl: int = DEFAULT_TTL) -> dict | None:
    """Return cached OSINT result if within TTL, else None."""
    row = db.query(OsintCache).filter(OsintCache.domain == domain).first()
    if not row:
        return None
    age = (datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)).total_seconds()
    if age > row.ttl_seconds:
        db.delete(row)
        db.flush()
        return None
    data = json.loads(row.result_json)
    if data.get("engine_version") != osint.ENGINE_VERSION:
        # Produced by an older engine (different sources/meaning): don't serve it.
        db.delete(row)
        db.flush()
        return None
    return data


def _set_cache(domain: str, result: dict, db: Session, ttl: int = DEFAULT_TTL) -> None:
    """Upsert the OSINT result cache."""
    existing = db.query(OsintCache).filter(OsintCache.domain == domain).first()
    if existing:
        existing.result_json = json.dumps(result)
        existing.created_at = datetime.now(timezone.utc)
        existing.ttl_seconds = ttl
    else:
        row = OsintCache(
            domain=domain,
            result_json=json.dumps(result),
            ttl_seconds=ttl,
        )
        db.add(row)
    db.flush()


def _authorize(db: Session, user: User, raw: str) -> str:
    """Only domains the organization is authorized for (same rules as scans)."""
    auth = authorize_scan_target(db, user.organization_id, raw, actor_id=user.id, auto_register=False)
    if not auth.authorized:
        raise HTTPException(status_code=403, detail=auth.as_error_detail())
    return auth.target


@router.get("")
async def osint_lookup(
    q: str = Query(..., description="Domain or company to investigate (e.g. example.com)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate passive public intelligence for an authorized domain.

    Third-party sources and public DNS only; the target itself is not
    contacted. Every item names its source (see ``sources`` in the result).
    Results are cached for 1 hour to spare the free third-party APIs.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    domain = await run_in_threadpool(_authorize, db, current_user, q)

    # Check cache first
    cached = _get_cached(domain, db)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    try:
        result = await run_in_threadpool(osint.lookup_domain, domain)
        result_dict = osint.intel_to_dict(result)
    except Exception as e:
        log.exception("OSINT lookup failed for %s", domain)
        raise HTTPException(status_code=500, detail="Lookup failed")

    # Only cache results that have meaningful data (not empty/partial)
    has_data = (
        len(result_dict.get("subdomains") or []) > 1
        or result_dict.get("ports")
        or result_dict.get("dns_records")
        or result_dict.get("whois")
    )
    if has_data:
        try:
            _set_cache(domain, result_dict, db)
            db.commit()
        except Exception as e:
            log.warning("Cache write failed for %s: %s", domain, e)
            db.rollback()
    else:
        log.info("Skipping cache for %s — no meaningful data found", domain)

    result_dict["from_cache"] = False
    return result_dict


@router.post("/import")
async def osint_import(
    q: str = Query(..., description="Domain to import OSINT findings for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)),
):
    """Run OSINT lookup and import findings into the Asset Inventory.

    Pushes discovered subdomains, certificates, and CVEs into the same
    canonical Asset / AssetRelationship / Vulnerability tables used by
    scan results, so shadow detection, search, and host intelligence
    work across both data sources seamlessly.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="No organization linked to your account")

    domain = await run_in_threadpool(_authorize, db, current_user, q)

    # Check cache first (import uses cached result if available)
    cached = _get_cached(domain, db)
    if cached:
        intel = osint.intel_from_dict(cached)
    else:
        intel = await run_in_threadpool(osint.lookup_domain, domain)
        result_dict = osint.intel_to_dict(intel)
        _set_cache(domain, result_dict, db)
        db.flush()

    counts = await run_in_threadpool(
        import_osint_findings, db, current_user.organization_id, intel
    )
    db.commit()
    return {
        "domain": domain,
        "imported": counts,
        "sources_status": intel.sources_status,
    }
