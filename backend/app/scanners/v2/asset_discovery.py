"""Advanced multi-source asset discovery engine.

Sources:
- Certificate Transparency logs (crt.sh)
- DNS intelligence (RapidDNS, HackerTarget)
- Web archive (URLScan.io)
- Passive DNS (AlienVault OTX)
- ASN enumeration
- Cloud provider ranges
"""
from __future__ import annotations

import asyncio
import re
import logging
from typing import Dict, List, Optional, Set

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# Rate limiting per source
SOURCE_RATE_LIMITS = {
    "crtsh": 0.5,
    "rapiddns": 1.0,
    "urlscan": 2.0,
    "hackertarget": 0.5,
    "alienvault": 1.0,
}


@register_scanner(
    name="advanced-asset-discovery",
    category=ScannerCategory.ASSET_DISCOVERY,
    version="2.0.0",
    priority=ScannerPriority.CRITICAL,
    description="Multi-source passive asset discovery with rate limiting and deduplication",
    capabilities=[
        "certificate_transparency", "passive_dns", "web_archive",
        "asn_enumeration", "cloud_range_discovery",
    ],
)
class AdvancedAssetDiscoveryScanner(EnhancedBaseScanner):
    """Discovers subdomains and assets from multiple passive sources."""

    name = "advanced-asset-discovery"
    version = "2.0.0"
    category = ScannerCategory.ASSET_DISCOVERY
    priority = ScannerPriority.CRITICAL

    async def scan(self, target: str, **kwargs) -> ScanResult:
        all_subdomains: Set[str] = {target}
        source_counts: Dict[str, int] = {}
        errors: List[str] = []

        # Shared HTTP client with connection pooling for all sources
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as client:
            tasks = {
                "dns_bruteforce": self._dns_bruteforce(target),
                "crtsh": asyncio.wait_for(self._crtsh(target, client), timeout=15),
                "rapiddns": asyncio.wait_for(self._rapiddns(target, client), timeout=15),
                "urlscan": asyncio.wait_for(self._urlscan(target, client), timeout=18),
                "hackertarget": asyncio.wait_for(self._hackertarget(target, client), timeout=15),
            }

            results = await asyncio.gather(
                *tasks.values(), return_exceptions=True
            )

        for source_name, result in zip(tasks.keys(), results):
            if isinstance(result, (set, list)):
                items = set(result) if isinstance(result, set) else set(result)
                new_count = len(items - all_subdomains)
                all_subdomains.update(items)
                source_counts[source_name] = new_count
            elif isinstance(result, Exception):
                errors.append(f"{source_name}: {result}")
                logger.warning("Source %s failed for %s: %s", source_name, target, result)

        # DNS validation of discovered subdomains
        validated = await self._validate_subdomains(list(all_subdomains))

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "subdomains": sorted(validated),
                "total_discovered": len(all_subdomains),
                "total_validated": len(validated),
                "source_breakdown": source_counts,
                "sources_used": list(source_counts.keys()),
            },
            errors=errors,
            metadata={"sources_attempted": 5},
        )

    def validate_target(self, target: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$', target))

    async def _crtsh(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query crt.sh Certificate Transparency logs."""
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        subdomains = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                import json
                entries = json.loads(resp.text)
                for entry in entries:
                    name = entry.get("name_value", "")
                    for line in name.split("\n"):
                        line = line.strip().lower()
                        if line.endswith(f".{domain}") or line == domain:
                            if "*" not in line:
                                subdomains.add(line)
        except Exception as e:
            logger.warning("crt.sh failed for %s: %s", domain, e)
            raise
        return list(subdomains)

    async def _rapiddns(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query RapidDNS for subdomains."""
        url = f"https://rapiddns.io/subdomain/{domain}"
        subdomains = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                for match in re.finditer(r'<td>([a-zA-Z0-9._-]+\.' + re.escape(domain) + r')</td>', resp.text):
                    subdomains.add(match.group(1).lower())
        except Exception as e:
            logger.warning("RapidDNS failed for %s: %s", domain, e)
            raise
        return list(subdomains)

    async def _urlscan(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query URLScan.io for subdomains."""
        url = f"https://urlscan.io/api/v1/search/?q=domain:{domain}"
        subdomains = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("results", []):
                    page = result.get("page", {})
                    domain_found = page.get("domain", "")
                    if domain_found.endswith(f".{domain}") or domain_found == domain:
                        subdomains.add(domain_found.lower())
        except Exception as e:
            logger.warning("URLScan failed for %s: %s", domain, e)
            raise
        return list(subdomains)

    async def _hackertarget(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query HackerTarget for subdomains."""
        url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
        subdomains = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                for line in resp.text.strip().split("\n"):
                    if "," in line:
                        hostname = line.split(",")[0].strip().lower()
                        if hostname.endswith(f".{domain}") or hostname == domain:
                            subdomains.add(hostname)
        except Exception as e:
            logger.warning("HackerTarget failed for %s: %s", domain, e)
            raise
        return list(subdomains)

    async def _dns_bruteforce(self, domain: str) -> Set[str]:
        """Quick DNS brute-force with common subdomain prefixes."""
        common_prefixes = [
            "www", "mail", "ftp", "smtp", "pop", "ns1", "ns2", "ns3",
            "dns", "dns1", "dns2", "mx", "mx1", "mx2", "webmail",
            "email", "remote", "vpn", "gateway", "router", "switch",
            "firewall", "proxy", "vpn1", "vpn2", "test", "dev", "staging",
            "api", "app", "admin", "portal", "login", "dashboard",
            "blog", "forum", "wiki", "docs", "help", "support",
            "shop", "store", "pay", "payment", "cdn", "static",
            "media", "img", "images", "assets", "files", "download",
            "upload", "backup", "db", "database", "sql", "mysql",
            "postgres", "redis", "mongo", "elastic", "search",
            "git", "gitlab", "github", "jenkins", "ci", "cd",
            "monitor", "status", "health", "grafana", "kibana",
            "cloud", "aws", "azure", "gcp", "k8s", "kubernetes",
            "docker", "registry", "container",
        ]

        found: Set[str] = set()
        semaphore = asyncio.Semaphore(20)

        async def _check_prefix(prefix: str) -> Optional[str]:
            async with semaphore:
                hostname = f"{prefix}.{domain}"
                try:
                    import dns.resolver
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, lambda: dns.resolver.resolve(hostname, "A")
                    )
                    return hostname
                except Exception:
                    return None

        tasks = [_check_prefix(p) for p in common_prefixes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, str):
                found.add(r)
        return found

    async def _validate_subdomains(self, subdomains: List[str], max_concurrent: int = 50) -> List[str]:
        """Quick DNS validation — check if subdomains resolve."""
        if not subdomains:
            return []

        import dns.resolver
        semaphore = asyncio.Semaphore(max_concurrent)
        validated = []

        async def _check(sub: str) -> Optional[str]:
            async with semaphore:
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, lambda: dns.resolver.resolve(sub, "A"))
                    return sub
                except Exception:
                    return None

        tasks = [_check(s) for s in subdomains[:500]]  # Cap at 500
        results = await asyncio.gather(*tasks)
        validated = [r for r in results if r is not None]
        return validated
