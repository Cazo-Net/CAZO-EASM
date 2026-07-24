"""V2 WHOIS Intelligence Scanner — domain registration lookups."""
from __future__ import annotations

import re
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)


@register_scanner(
    name="whois-intelligence",
    category=ScannerCategory.WHOIS,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="WHOIS registration lookups (registrar, dates, nameservers, registrant)",
    capabilities=["whois", "domain_age", "registrar_info"],
)
class WhoisIntelligenceScanner(EnhancedBaseScanner):
    name = "whois-intelligence"
    version = "2.0.0"
    category = ScannerCategory.WHOIS
    priority = ScannerPriority.NORMAL

    def validate_target(self, target: str) -> bool:
        return bool(re.match(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", target,
        ))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        if not self.validate_target(target):
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Invalid domain: {target}"])

        try:
            import whois as _whois
            w = await asyncio.to_thread(_whois.whois, target)
        except ImportError:
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=["python-whois not installed"])
        except Exception as e:
            return ScanResult(success=True, scanner=self.name, target=target,
                              data={"registrar": None, "error": str(e)})

        if w is None:
            return ScanResult(success=True, scanner=self.name, target=target,
                              data={"registrar": None, "error": "No WHOIS data available"})

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

        return ScanResult(
            success=True, scanner=self.name, target=target,
            data={
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
                "statuses": w.status if isinstance(w.status, list) else [str(w.status)] if w.status else [],
                "domain_age_days": domain_age_days,
            },
        )
