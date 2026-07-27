"""Advanced multi-source asset discovery engine.

Sources:
- Certificate Transparency logs (crt.sh, CertSpotter)
- DNS intelligence (RapidDNS, HackerTarget, Anubis)
- Web archive (URLScan.io)
- Passive DNS (AlienVault OTX)
- DNS brute-force
"""
from __future__ import annotations

import asyncio
import re
import json
import logging
from typing import Dict, List, Optional, Set

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)


@register_scanner(
    name="advanced-asset-discovery",
    category=ScannerCategory.ASSET_DISCOVERY,
    version="3.0.0",
    priority=ScannerPriority.CRITICAL,
    description="Multi-source passive asset discovery with deduplication and validation",
    capabilities=[
        "certificate_transparency", "passive_dns", "web_archive",
        "dns_bruteforce", "multi_source_aggregation",
    ],
)
class AdvancedAssetDiscoveryScanner(EnhancedBaseScanner):
    """Discovers subdomains and assets from multiple passive sources."""

    name = "advanced-asset-discovery"
    version = "3.0.0"
    category = ScannerCategory.ASSET_DISCOVERY
    priority = ScannerPriority.CRITICAL

    async def scan(self, target: str, **kwargs) -> ScanResult:
        all_subdomains: Set[str] = {target}
        source_counts: Dict[str, int] = {}
        errors: List[str] = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        ) as client:
            tasks = {
                "crtsh": self._crtsh(target, client),
                "certspotter": self._certspotter(target, client),
                "rapiddns": self._rapiddns(target, client),
                "urlscan": self._urlscan(target, client),
                "hackertarget": self._hackertarget(target, client),
                "anubis": self._anubis(target, client),
                "dns_bruteforce": self._dns_bruteforce(target),
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

        # Quick DNS validation — only check a sample to determine alive count
        alive_count = await self._quick_validate_sample(list(all_subdomains))

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "subdomains": sorted(all_subdomains),
                "total_discovered": len(all_subdomains),
                "total_validated": alive_count,
                "source_breakdown": source_counts,
                "sources_used": list(source_counts.keys()),
            },
            errors=errors,
            metadata={"sources_attempted": len(tasks)},
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
                text = resp.text.strip()
                if text.startswith("[") or text.startswith("{"):
                    entries = json.loads(text)
                    if isinstance(entries, dict):
                        entries = entries.get("data", [])
                    for entry in entries:
                        name = entry.get("name_value", "")
                        for line in name.split("\n"):
                            line = line.strip().lower()
                            if line.endswith(f".{domain}") or line == domain:
                                if "*" not in line:
                                    subdomains.add(line)
        except Exception as e:
            logger.warning("crt.sh failed for %s: %s", domain, e)
        return list(subdomains)

    async def _certspotter(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query CertSpotter API for certificate transparency."""
        subdomains = set()
        try:
            url = f"https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for cert in data:
                    for name in cert.get("dns_names", []):
                        name = name.strip().lower()
                        if name.endswith(f".{domain}") or name == domain:
                            if "*" not in name:
                                subdomains.add(name)
        except Exception as e:
            logger.warning("CertSpotter failed for %s: %s", domain, e)
        return list(subdomains)

    async def _rapiddns(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query RapidDNS for subdomains."""
        url = f"https://rapiddns.io/subdomain/{domain}?full=1"
        subdomains = set()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                for match in re.finditer(r'<td>([a-zA-Z0-9._-]+\.' + re.escape(domain) + r')</td>', resp.text):
                    subdomains.add(match.group(1).lower())
        except Exception as e:
            logger.warning("RapidDNS failed for %s: %s", domain, e)
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
        return list(subdomains)

    async def _anubis(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        """Query Anubis-DB for subdomains."""
        subdomains = set()
        try:
            url = f"https://jldc.me/anubis/subdomains/{domain}"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for name in data:
                        name = str(name).strip().lower()
                        if name.endswith(f".{domain}") or name == domain:
                            subdomains.add(name)
        except Exception as e:
            logger.warning("Anubis failed for %s: %s", domain, e)
        return list(subdomains)

    async def _dns_bruteforce(self, domain: str) -> Set[str]:
        """Quick DNS brute-force with common subdomain prefixes."""
        common_prefixes = [
            "www", "mail", "ftp", "smtp", "ns1", "ns2", "ns3",
            "dns", "mx", "webmail", "email", "vpn", "gateway",
            "test", "dev", "staging", "api", "app", "admin",
            "portal", "blog", "docs", "help", "support",
            "cdn", "static", "media", "img", "assets",
            "cloud", "k8s", "docker", "registry",
            "grafana", "kibana", "jenkins", "ci", "git",
            "status", "monitor", "db", "redis", "elastic",
            "login", "dashboard", "shop", "pay",
            "backup", "old", "new", "beta", "alpha",
            "portal", "sso", "auth", "accounts",
            "mx1", "mx2", "pop", "imap",
            "ns4", "ns5", "dns1", "dns2", "dns3",
            "cpanel", "whm", "webdisk",
            "autodiscover", "autoconfig",
            "m", "mobile", "wap",
            "proxy", "proxy1", "proxy2",
            "db1", "db2", "sql", "mysql", "postgres",
            "mongo", "elastic", "search", "solr",
            "cache", "memcached", "varnish",
            "queue", "rabbit", "kafka", "zmq",
            "log", "logs", "syslog", "elk",
            "time", "ntp", "ntp1", "ntp2",
            "ntp3", "ldap", "kerberos",
            "file", "files", "ftp1", "sftp",
            "backup1", "backup2", "bak",
            "old1", "old2", "archive",
            "temp", "tmp", "scratch",
            "sandbox", "qa", "uat", "preprod",
            "canary", "blue", "green",
            "internal", "intranet", "private",
            "public", "open", "free",
            "download", "uploads", "upload",
            "images", "images2", "img2",
            "video", "videos", "media2",
            "static1", "static2", "assets2",
            "js", "css", "fonts", "font",
            "api1", "api2", "api3", "api4",
            "graphql", "rest", "soap",
            "ws", "wss", "socket", "websocket",
            "realtime", "rt", "live",
            "edge", "cdn1", "cdn2", "cf",
            "cloudflare", "akamai", "fastly",
            "aws", "azure", "gcp", "s3",
            "blob", "bucket", "storage",
            "compute", "vm", "server", "node",
            "cluster", "master", "worker", "slave",
            "lb", "haproxy", "nginx", "apache",
            "tomcat", "jetty", "gunicorn", "uwsgi",
            "php", "python", "ruby", "java",
            "node", "go", "rust", "net",
            "dotnet", "iis", "express",
        ]

        found: Set[str] = set()
        semaphore = asyncio.Semaphore(30)

        async def _check_prefix(prefix: str) -> Optional[str]:
            async with semaphore:
                hostname = f"{prefix}.{domain}"
                try:
                    import dns.resolver
                    loop = asyncio.get_running_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            None, lambda: dns.resolver.resolve(hostname, "A")
                        ),
                        timeout=2.0,
                    )
                    return hostname
                except Exception:
                    return None

        tasks = [_check_prefix(p) for p in common_prefixes]
        results = await asyncio.gather(*tasks)
        for r in results:
            if isinstance(r, str):
                found.add(r)
        return found

    async def _quick_validate_sample(self, subdomains: List[str], sample_size: int = 50) -> int:
        """Quick DNS validation of a sample of subdomains to estimate alive count."""
        if not subdomains:
            return 0

        import dns.resolver
        sample = subdomains[:sample_size]
        semaphore = asyncio.Semaphore(30)
        alive = 0

        async def _check(sub: str) -> bool:
            async with semaphore:
                try:
                    loop = asyncio.get_running_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: dns.resolver.resolve(sub, "A")),
                        timeout=2.0,
                    )
                    return True
                except Exception:
                    return False

        tasks = [_check(s) for s in sample]
        results = await asyncio.gather(*tasks)
        alive = sum(1 for r in results if r)

        # Extrapolate
        if len(sample) < len(subdomains):
            ratio = alive / len(sample) if sample else 0
            return int(ratio * len(subdomains))
        return alive
