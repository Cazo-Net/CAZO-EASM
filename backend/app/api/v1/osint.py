"""OSINT intelligence API — key-free Shodan-style lookup for any domain/company."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.osint_cache import OsintCache
from app.api.deps import get_current_user
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
    return json.loads(row.result_json)


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
    """OSINT lookups connect to the target (ports, TLS), so they follow scan scope rules."""
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
    """Aggregate public OSINT (subdomains, certs, vulns, ports) for a target.

    Key-free: uses hackertarget, certspotter, live TLS/DNS, NVD, and CISA KEV.
    Results are cached for 1 hour to avoid re-probing the same domain.
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
        result_dict.get("subdomains")
        or result_dict.get("ports")
        or result_dict.get("technologies")
        or result_dict.get("dns_records")
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
    current_user: User = Depends(get_current_user),
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
        # Convert cached dict back to IntelResult-like structure for import
        from app.services.osint import (
            IntelResult, SubdomainResult, CertResult, PortResult, VulnResult,
        )
        intel = IntelResult(query=cached["query"])
        for s in cached.get("subdomains", []):
            intel.subdomains.append(SubdomainResult(hostname=s["hostname"], ips=s["ips"], sources=s["sources"]))
        for c in cached.get("certificates", []):
            intel.certificates.append(CertResult(
                issuer=c.get("issuer"), subject=c.get("subject"), san=c.get("san", []),
                not_before=c.get("not_before"), not_after=c.get("not_after"),
                serial=c.get("serial"), source=c.get("source"),
            ))
        for p in cached.get("ports", []):
            intel.ports.append(PortResult(
                port=p["port"], state=p["state"], service=p.get("service"),
                banner=p.get("banner"), tls=p.get("tls", False), title=p.get("title"),
            ))
        intel.technologies = cached.get("technologies", [])
        for v in cached.get("vulnerabilities", []):
            intel.vulnerabilities.append(VulnResult(
                cve_id=v["cve_id"], description=v.get("description", ""),
                severity=v.get("severity"), cvss=v.get("cvss"),
                published=v.get("published"), is_kev=v.get("is_kev", False),
                source=v.get("source", "NVD"),
            ))
        intel.dns_records = cached.get("dns_records", {})
        intel.sources_status = cached.get("sources_status", {})
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
