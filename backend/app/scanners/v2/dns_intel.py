"""V2 DNS Intelligence Scanner — comprehensive record analysis with DMARC/DKIM/SPF."""
from __future__ import annotations

import re
import asyncio
import logging
from typing import Any, Dict, List, Optional

import dns.resolver
import dns.rdatatype
import dns.exception

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SRV"]
DKIM_SELECTORS = [
    "default", "selector1", "selector2", "google", "k1",
    "mandrill", "everlytickey1", "dkim", "s1", "s2",
]


def _resolve_sync(target: str, record_type: str):
    return dns.resolver.resolve(target, record_type)


@register_scanner(
    name="dns-intelligence",
    category=ScannerCategory.DNS,
    version="2.0.0",
    priority=ScannerPriority.HIGH,
    description="DNS record analysis (A/AAAA/CNAME/MX/TXT/NS/SOA/SRV) + DMARC/DKIM/SPF",
    capabilities=["dns_records", "dmarc", "dkim", "spf", "reverse_dns"],
)
class DNSIntelligenceScanner(EnhancedBaseScanner):
    name = "dns-intelligence"
    version = "2.0.0"
    category = ScannerCategory.DNS
    priority = ScannerPriority.HIGH

    def validate_target(self, target: str) -> bool:
        return bool(re.match(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$",
            target,
        ))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        if not self.validate_target(target):
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Invalid hostname: {target}"])

        records: Dict[str, List[Dict[str, Any]]] = {}
        ips: List[str] = []
        errors: List[str] = []

        # Parallel: all record types
        tasks = [self._query_one(target, rt) for rt in RECORD_TYPES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, Exception):
                errors.append(str(item))
                continue
            rt, recs, rt_ips, err = item
            if recs:
                records[rt] = recs
            ips.extend(rt_ips)
            if err and "NXDOMAIN" in err:
                return ScanResult(success=True, scanner=self.name, target=target,
                                  data={"records": {}, "ips": [], "status": "not_applicable"})
            if err:
                errors.append(err)

        # DMARC
        try:
            dmarc_records = await asyncio.wait_for(
                asyncio.to_thread(self._resolve_dmarc, target), timeout=3,
            )
            if dmarc_records:
                records["DMARC"] = dmarc_records
        except Exception:
            pass

        # DKIM
        dkim_tasks = [
            asyncio.to_thread(self._resolve_dkim, f"{sel}._domainkey.{target}")
            for sel in DKIM_SELECTORS
        ]
        dkim_results = await asyncio.gather(*dkim_tasks, return_exceptions=True)
        for sel, item in zip(DKIM_SELECTORS, dkim_results):
            if isinstance(item, list) and item:
                records[f"DKIM_{sel}"] = item

        # SPF (from TXT records)
        spf_records = []
        for txt in records.get("TXT", []):
            val = txt.get("value", "")
            if isinstance(val, str) and val.startswith("v=spf1"):
                spf_records.append(txt)
        if spf_records:
            records["SPF"] = spf_records

        # Reverse DNS for each IP
        reverse_dns: Dict[str, List[str]] = {}
        unique_ips = sorted(set(ips))[:20]
        if unique_ips:
            rdns_tasks = [self._reverse_dns(ip) for ip in unique_ips]
            rdns_results = await asyncio.gather(*rdns_tasks, return_exceptions=True)
            for ip, hostnames in zip(unique_ips, rdns_results):
                if isinstance(hostnames, list) and hostnames:
                    reverse_dns[ip] = hostnames

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "records": records,
                "ips": sorted(set(ips)),
                "reverse_dns": reverse_dns,
                "dmarc": "DMARC" in records,
                "dkim": any(k.startswith("DKIM_") for k in records),
                "spf": bool(spf_records),
                "record_types_found": list(records.keys()),
            },
            errors=errors,
        )

    def _query_one(self, target: str, record_type: str):
        try:
            answers = dns.resolver.resolve(target, record_type)
            ttl = int(answers.ttl) if getattr(answers, "ttl", None) is not None else None
            recs = []
            ips = []
            for rdata in answers:
                rec: Dict[str, Any] = {"type": record_type, "ttl": ttl}
                if record_type == "A":
                    rec["value"] = str(rdata); ips.append(str(rdata))
                elif record_type == "AAAA":
                    rec["value"] = str(rdata); ips.append(str(rdata))
                elif record_type == "MX":
                    rec["value"] = str(rdata.exchange); rec["priority"] = rdata.preference
                elif record_type == "CNAME":
                    rec["value"] = str(rdata)
                elif record_type == "NS":
                    rec["value"] = str(rdata)
                elif record_type == "TXT":
                    rec["value"] = str(rdata)
                elif record_type == "SOA":
                    rec["value"] = {"mname": str(rdata.mname), "rname": str(rdata.rname), "serial": rdata.serial}
                elif record_type == "SRV":
                    rec["value"] = {"target": str(rdata.target), "port": rdata.port,
                                    "priority": rdata.priority, "weight": rdata.weight}
                recs.append(rec)
            return record_type, recs, ips, None
        except dns.resolver.NoAnswer:
            return record_type, [], [], None
        except dns.resolver.NXDOMAIN:
            return record_type, [], [], "NXDOMAIN"
        except (dns.exception.Timeout, asyncio.TimeoutError, TimeoutError):
            return record_type, [], [], f"Timeout for {target} ({record_type})"
        except Exception as e:
            return record_type, [], [], f"DNS error: {e}"

    def _resolve_dmarc(self, target: str):
        try:
            answers = dns.resolver.resolve(f"_dmarc.{target}", "TXT")
            ttl = int(answers.ttl) if getattr(answers, "ttl", None) is not None else None
            return [{"type": "DMARC", "value": str(rdata), "ttl": ttl} for rdata in answers]
        except Exception:
            return []

    def _resolve_dkim(self, fqdn: str):
        try:
            answers = dns.resolver.resolve(fqdn, "TXT")
            ttl = int(answers.ttl) if getattr(answers, "ttl", None) is not None else None
            return [{"type": "DKIM", "value": str(rdata), "ttl": ttl} for rdata in answers]
        except Exception:
            return []

    def _reverse_dns(self, ip: str):
        try:
            rev = dns.reversename.from_address(ip)
            answers = dns.resolver.resolve(rev, "PTR")
            return [str(rdata) for rdata in answers]
        except Exception:
            return []
