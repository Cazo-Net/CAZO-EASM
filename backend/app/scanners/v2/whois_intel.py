"""V2 WHOIS Intelligence Scanner — RDAP-first with python-whois fallback.

Uses the modern RDAP (Registration Data Access Protocol) API for fast,
structured JSON domain lookups. Falls back to python-whois when RDAP
is unavailable or returns no data.

RDAP provides:
- Structured JSON (no brittle text parsing)
- Fast HTTP responses (~0.5-2s vs 3-10s for traditional WHOIS)
- Registrar contacts (abuse, admin, tech)
- Domain status code interpretation
"""
from __future__ import annotations

import re
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# RDAP base URL — rdap.org aggregates all registries
RDAP_BASE = "https://rdap.org"

# Meaningful domain status codes and their descriptions
STATUS_DESCRIPTIONS = {
    "clientdeleteprohibited": "Domain cannot be deleted by the registrant",
    "clienthold": "Domain is suspended by the registrar",
    "clienttransferprohibited": "Domain cannot be transferred without registrant authorization",
    "clientupdateprohibited": "Domain cannot be updated by the registrant",
    "serverdeleteprohibited": "Domain cannot be deleted by the registry",
    "serverhold": "Domain is suspended by the registry",
    "servertransferprohibited": "Domain cannot be transferred",
    "serverupdateprohibited": "Domain cannot be updated",
    "ok": "Domain is active and normal",
    "pendingdelete": "Domain is pending deletion",
    "pendingtransfer": "Domain transfer is in progress",
    "redemptionperiod": "Domain is in the redemption period after expiration",
    "pendingrestore": "Domain is pending restoration",
    "expired": "Domain has expired",
}


@register_scanner(
    name="whois-intelligence",
    category=ScannerCategory.WHOIS,
    version="3.0.0",
    priority=ScannerPriority.NORMAL,
    description="WHOIS via RDAP (fast, structured) with python-whois fallback + status analysis",
    capabilities=["whois", "rdap", "domain_age", "registrar_info", "contacts", "status_analysis"],
)
class WhoisIntelligenceScanner(EnhancedBaseScanner):
    name = "whois-intelligence"
    version = "3.0.0"
    category = ScannerCategory.WHOIS
    priority = ScannerPriority.NORMAL

    def validate_target(self, target: str) -> bool:
        return bool(re.match(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$",
            target,
        ))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        if not self.validate_target(target):
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Invalid domain: {target}"])

        # Try RDAP first
        rdap_result = await self._rdap_lookup(target)
        if rdap_result and rdap_result.get("registrar"):
            return ScanResult(
                success=True, scanner=self.name, target=target,
                data={**rdap_result, "rdap_used": True},
            )

        # Fallback to python-whois
        whois_result = await self._whois_fallback(target)
        return ScanResult(
            success=True, scanner=self.name, target=target,
            data={**whois_result, "rdap_used": False},
        )

    # ── RDAP lookup ──────────────────────────────────────────────────────

    async def _rdap_lookup(self, target: str) -> Optional[Dict[str, Any]]:
        """Query RDAP API for structured domain data."""
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                resp = await client.get(f"{RDAP_BASE}/domain/{target}")
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception as exc:
            logger.debug("RDAP lookup failed for %s: %s", target, exc)
            return None

        return self._parse_rdap(data)

    def _parse_rdap(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse RDAP JSON response into our standard format."""
        # Registrar
        registrar = None
        for entity in data.get("entities", []):
            roles = entity.get("roles", [])
            if "registrar" in roles:
                registrar = self._extract_rdap_entity_name(entity)
                break

        # Dates
        events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
        creation_date = events.get("registration")
        expiration_date = events.get("expiration")
        updated_date = events.get("last changed")

        # Nameservers
        nameservers = [
            ns.get("ldhName", "").lower()
            for ns in data.get("nameservers", [])
            if ns.get("ldhName")
        ]

        # Status
        statuses = data.get("status", [])

        # Contacts
        contacts = self._extract_rdap_contacts(data.get("entities", []))

        # Domain age
        domain_age_days = None
        if creation_date:
            try:
                cd = datetime.fromisoformat(creation_date.replace("Z", "+00:00"))
                domain_age_days = (datetime.now(cd.tzinfo) - cd).days
            except Exception:
                pass

        return {
            "registrar": registrar,
            "creation_date": creation_date,
            "expiration_date": expiration_date,
            "updated_date": updated_date,
            "name_servers": sorted(set(nameservers)),
            "registrant_name": contacts.get("registrant", {}).get("name"),
            "registrant_org": contacts.get("registrant", {}).get("org"),
            "registrant_country": contacts.get("registrant", {}).get("country"),
            "emails": [c.get("email") for c in contacts.values() if c.get("email")],
            "dnssec": data.get("secureDNS", {}).get("delegationSigned", False),
            "statuses": statuses,
            "domain_age_days": domain_age_days,
            "contacts": contacts,
            "status_analysis": self._analyze_statuses(statuses),
        }

    def _extract_rdap_entity_name(self, entity: Dict) -> Optional[str]:
        """Extract the name from an RDAP entity (registrar, etc.)."""
        vcard = entity.get("vcardArray", [])
        if len(vcard) > 1:
            for item in vcard[1]:
                if item[0] == "fn":
                    return item[3] if len(item) > 3 else None
        # Fallback to handle
        return entity.get("handle")

    def _extract_rdap_contacts(self, entities: List[Dict]) -> Dict[str, Dict]:
        """Extract registrant, admin, and tech contacts from RDAP entities."""
        contacts = {}
        role_map = {
            "registrant": "registrant",
            "administrative": "admin",
            "technical": "tech",
            "abuse": "abuse",
        }
        for entity in entities:
            roles = entity.get("roles", [])
            for role in roles:
                if role in role_map:
                    contact_key = role_map[role]
                    vcard = entity.get("vcardArray", [])
                    contact = {}
                    if len(vcard) > 1:
                        for item in vcard[1]:
                            if item[0] == "fn" and len(item) > 3:
                                contact["name"] = item[3]
                            elif item[0] == "org" and len(item) > 3:
                                contact["org"] = item[3]
                            elif item[0] == "email" and len(item) > 3:
                                contact["email"] = item[3]
                            elif item[0] == "adr" and len(item) > 3:
                                addr = item[3]
                                if isinstance(addr, list) and len(addr) >= 3:
                                    contact["country"] = addr[-1] if addr[-1] else None
                    contact["handle"] = entity.get("handle")
                    contacts[contact_key] = contact
        return contacts

    def _analyze_statuses(self, statuses: List[str]) -> Dict[str, Any]:
        """Interpret domain status codes."""
        if not statuses:
            return {"raw": [], "summary": "No status information available"}

        analyzed = []
        warnings = []
        for status in statuses:
            # Normalize: remove trailing punctuation, lowercase
            clean = status.strip().lower().rstrip(".")
            description = STATUS_DESCRIPTIONS.get(clean, "Unknown status")
            analyzed.append({"status": clean, "description": description})
            if clean not in ("ok",):
                warnings.append(clean)

        # Determine overall health
        has_hold = any("hold" in s for s in statuses)
        has_pending = any("pending" in s for s in statuses)
        has_expired = any("expired" in s or "redemption" in s for s in statuses)

        if has_hold:
            health = "suspended"
        elif has_expired:
            health = "expired"
        elif has_pending:
            health = "transitioning"
        elif not warnings:
            health = "healthy"
        else:
            health = "restricted"

        return {
            "raw": statuses,
            "analyzed": analyzed,
            "health": health,
            "warnings": warnings,
        }

    # ── python-whois fallback ────────────────────────────────────────────

    async def _whois_fallback(self, target: str) -> Dict[str, Any]:
        """Fallback to python-whois when RDAP fails."""
        try:
            import whois as _whois
            w = await asyncio.to_thread(_whois.whois, target)
        except ImportError:
            return {"registrar": None, "error": "python-whois not installed"}
        except Exception as e:
            return {"registrar": None, "error": str(e)}

        if w is None:
            return {"registrar": None, "error": "No WHOIS data available"}

        def _fmt_date(d):
            if d is None:
                return None
            if isinstance(d, list):
                d = d[0]
            if isinstance(d, datetime):
                return d.isoformat()
            return str(d) if d else None

        name_servers = []
        if w.name_servers:
            if isinstance(w.name_servers, list):
                name_servers = [ns.lower() for ns in w.name_servers]
            else:
                name_servers = [str(w.name_servers).lower()]

        domain_age_days = None
        if w.creation_date:
            cd = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
            if isinstance(cd, datetime):
                domain_age_days = (datetime.now() - cd).days

        statuses = []
        if hasattr(w, "status") and w.status:
            if isinstance(w.status, list):
                statuses = w.status
            else:
                statuses = [str(w.status)]

        return {
            "registrar": w.registrar,
            "creation_date": _fmt_date(w.creation_date),
            "expiration_date": _fmt_date(w.expiration_date),
            "updated_date": _fmt_date(w.updated_date),
            "name_servers": name_servers,
            "registrant_name": w.name,
            "registrant_org": w.org,
            "registrant_country": w.country,
            "emails": w.emails if hasattr(w, "emails") else [],
            "dnssec": w.dnssec if hasattr(w, "dnssec") else None,
            "statuses": statuses,
            "domain_age_days": domain_age_days,
            "contacts": {},
            "status_analysis": self._analyze_statuses(statuses),
        }
