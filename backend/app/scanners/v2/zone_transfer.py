"""V2 Zone Transfer Scanner — DNS AXFR attempt against nameservers."""
from __future__ import annotations

import re
import asyncio
import logging
from typing import Any, Dict, List

import dns.resolver
import dns.query
import dns.zone
import dns.rdatatype

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

TRANSFER_RDTYPES = ["A", "AAAA", "CNAME", "MX", "TXT"]


@register_scanner(
    name="zone-transfer",
    category=ScannerCategory.DNS,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="DNS zone transfer (AXFR) attempt against nameservers",
    capabilities=["zone_transfer", "subdomain_discovery"],
)
class ZoneTransferScanner(EnhancedBaseScanner):
    name = "zone-transfer"
    version = "2.0.0"
    category = ScannerCategory.DNS
    priority = ScannerPriority.NORMAL

    def validate_target(self, target: str) -> bool:
        return bool(re.match(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", target,
        ))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        if not self.validate_target(target):
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Invalid hostname: {target}"])

        ns_ips = await self._get_ns_ips(target)
        if not ns_ips:
            return ScanResult(success=True, scanner=self.name, target=target,
                              data={"transfer_success": False, "nameservers": [], "records": {}, "subdomains": []})

        all_records: Dict[str, Dict[str, List[str]]] = {}
        transfer_success = False

        for ns_ip in ns_ips:
            try:
                zone = await asyncio.wait_for(self._attempt_transfer(ns_ip, target), timeout=5)
                records = self._extract_records(zone, target)
                for hostname, rdtype_map in records.items():
                    if hostname not in all_records:
                        all_records[hostname] = {}
                    for rdtype, values in rdtype_map.items():
                        all_records[hostname].setdefault(rdtype, []).extend(values)
                transfer_success = True
                break
            except asyncio.TimeoutError:
                logger.debug("Zone transfer timed out for %s", ns_ip)
            except dns.query.TransferError as e:
                logger.debug("Zone transfer refused by %s: %s", ns_ip, e)
            except Exception as e:
                logger.debug("Zone transfer failed for %s: %s", ns_ip, e)

        return ScanResult(
            success=True, scanner=self.name, target=target,
            data={
                "transfer_success": transfer_success,
                "nameservers": ns_ips,
                "records": all_records,
                "subdomains": sorted(set(all_records.keys())),
            },
        )

    async def _get_ns_ips(self, target: str) -> List[str]:
        ns_ips = []
        try:
            def _resolve():
                answers = dns.resolver.resolve(target, "NS")
                return [str(rdata).rstrip(".") for rdata in answers]
            ns_hostnames = await asyncio.to_thread(_resolve)

            async def _resolve_a(ns_host):
                try:
                    def _do():
                        return [str(rdata) for rdata in dns.resolver.resolve(ns_host, "A")]
                    return await asyncio.to_thread(_do)
                except Exception:
                    return []

            results = await asyncio.gather(*[_resolve_a(ns) for ns in ns_hostnames], return_exceptions=True)
            for ips in results:
                if isinstance(ips, list):
                    ns_ips.extend(ips)
        except Exception as e:
            logger.warning("Failed to query NS records for %s: %s", target, e)
        return ns_ips

    async def _attempt_transfer(self, ns_ip: str, target: str):
        def _do():
            transfer = dns.query.xfr(ns_ip, target, lifetime=5, one_rr_per_rrset=False)
            return dns.zone.from_xfr(transfer, relativize=False)
        return await asyncio.to_thread(_do)

    def _extract_records(self, zone, target: str) -> Dict[str, Dict[str, List[str]]]:
        records: Dict[str, Dict[str, List[str]]] = {}
        for name, node in zone.nodes.items():
            hostname = str(name).rstrip(".")
            if hostname in ("@", target.rstrip(".")):
                hostname = target
            for rdataset in node.rdatasets:
                rdtype = dns.rdatatype.to_text(rdataset.rdtype)
                if rdtype not in TRANSFER_RDTYPES:
                    continue
                records.setdefault(hostname, {}).setdefault(rdtype, [])
                for rdata in rdataset:
                    if rdtype in ("A", "AAAA"):
                        records[hostname][rdtype].append(str(rdata))
                    elif rdtype == "CNAME":
                        records[hostname][rdtype].append(str(rdata.target).rstrip("."))
                    elif rdtype == "MX":
                        records[hostname][rdtype].append(str(rdata.exchange).rstrip("."))
                    elif rdtype == "TXT":
                        records[hostname][rdtype].append(str(rdata))
        return records
