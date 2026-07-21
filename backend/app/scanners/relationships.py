from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.scanners.registry import ScannerCategory, register_scanner
from app.utils.asn import resolve_asn


@register_scanner(
    name="relationships",
    category=ScannerCategory.SUBDOMAIN,
    description="Discovers relationships between assets: IP-ASN mapping, shared hosting, and registrar clustering.",
    requires_scope=False,
)
class RelationshipsScanner(BaseScanner):

    def validate_target(self, target: str) -> bool:
        return True

    async def scan(self, target: str, scan_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        scan_results = scan_results or {}

        ip_asn_mapping: Dict[str, Dict[str, str]] = {}
        hosting_providers: Dict[str, List[str]] = {}

        dns_records = scan_results.get("dns_records", {})
        all_ips: List[str] = []

        for domain, records in dns_records.items():
            if isinstance(records, dict):
                for rtype, values in records.items():
                    if rtype.upper() in ("A", "AAAA") and isinstance(values, list):
                        all_ips.extend(values)

        for ip in all_ips:
            info = resolve_asn(ip)
            if info:
                ip_asn_mapping[ip] = {"asn": info["asn"], "provider": info["provider"]}
                hosting_providers.setdefault(info["provider"], []).append(ip)

        registrar_clusters: Dict[str, List[str]] = {}
        whois = scan_results.get("whois", {})
        for domain, data in whois.items():
            if isinstance(data, dict):
                registrar = data.get("registrar") or data.get("Registrar")
                if registrar:
                    registrar_clusters.setdefault(registrar, []).append(domain)

        relationships: List[Dict[str, Any]] = []
        for provider, ips in hosting_providers.items():
            hostnames = []
            for ip in ips:
                for domain, records in dns_records.items():
                    if isinstance(records, dict):
                        for rtype, values in records.items():
                            if rtype.upper() in ("A", "AAAA") and isinstance(values, list) and ip in values:
                                hostnames.append(domain)
            relationships.append({"type": "shared_hosting", "ip": ips[0], "hostnames": list(set(hostnames))})

        for registrar, domains in registrar_clusters.items():
            if len(domains) > 1:
                relationships.append({"type": "shared_registrar", "registrar": registrar, "domains": domains})

        return {
            "success": True,
            "target": target,
            "ip_asn_mapping": ip_asn_mapping,
            "hosting_providers": hosting_providers,
            "registrar_clusters": registrar_clusters,
            "relationships": relationships,
            "scanner": "relationships",
        }
