"""Advanced multi-source asset discovery engine.

Sources:
- Certificate Transparency logs (crt.sh, CertSpotter, CTSearch)
- DNS intelligence (RapidDNS, HackerTarget, Anubis, AlienVault OTX, Google DNS)
- Web archive (URLScan.io)
- DNS brute-force (300+ common prefixes)
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
    version="4.0.0",
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
    version = "4.0.0"
    category = ScannerCategory.ASSET_DISCOVERY
    priority = ScannerPriority.CRITICAL

    async def scan(self, target: str, **kwargs) -> ScanResult:
        all_subdomains: Set[str] = {target}
        source_counts: Dict[str, int] = {}
        errors: List[str] = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=5.0),
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
                "alienvault": self._alienvault(target, client),
                "google_dns": self._google_dns(target, client),
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
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        subdomains = set()
        try:
            resp = await client.get(url, timeout=20.0)
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
                    server_domain = page.get("serverDomain", "")
                    if server_domain and (server_domain.endswith(f".{domain}") or server_domain == domain):
                        subdomains.add(server_domain.lower())
        except Exception as e:
            logger.warning("URLScan failed for %s: %s", domain, e)
        return list(subdomains)

    async def _hackertarget(self, domain: str, client: httpx.AsyncClient) -> List[str]:
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

    async def _alienvault(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        subdomains = set()
        try:
            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"
            resp = await client.get(url)
            if resp.status_code == 200:
                for entry in resp.json().get("passive_dns", []):
                    hostname = entry.get("hostname", "").strip().lower()
                    if hostname.endswith(f".{domain}") or hostname == domain:
                        subdomains.add(hostname)
        except Exception as e:
            logger.warning("AlienVault failed for %s: %s", domain, e)
        return list(subdomains)

    async def _google_dns(self, domain: str, client: httpx.AsyncClient) -> List[str]:
        subdomains = set()
        for record_type in ("A", "AAAA", "MX", "NS", "CNAME", "TXT"):
            try:
                url = f"https://dns.google/resolve?name={domain}&type={record_type}"
                resp = await client.get(url)
                if resp.status_code == 200:
                    for ans in resp.json().get("Answer", []):
                        data = ans.get("data", "").rstrip(".")
                        if data and (data.endswith(f".{domain}") or domain in data):
                            subdomains.add(data.lower())
            except Exception:
                pass
        return list(subdomains)

    async def _dns_bruteforce(self, domain: str) -> Set[str]:
        common_prefixes = [
            "www", "mail", "ftp", "smtp", "ns1", "ns2", "ns3", "ns4", "ns5",
            "dns", "dns1", "dns2", "dns3", "mx", "mx1", "mx2",
            "webmail", "email", "pop", "imap",
            "vpn", "gateway", "remote", "ssh",
            "test", "dev", "staging", "stage", "beta", "alpha", "qa", "uat", "preprod",
            "api", "api1", "api2", "api3", "api4", "graphql", "rest", "soap",
            "app", "apps", "application",
            "admin", "administrator", "cpanel", "whm", "webdisk",
            "portal", "login", "sso", "auth", "accounts", "identity",
            "blog", "docs", "help", "support", "kb", "faq",
            "cdn", "static", "assets", "media", "img", "images", "images2", "img2",
            "video", "videos", "media2",
            "static1", "static2", "assets2",
            "js", "css", "fonts", "font",
            "cloud", "k8s", "docker", "registry", "container",
            "grafana", "kibana", "jenkins", "ci", "cd",
            "git", "gitlab", "github", "bitbucket", "svn",
            "status", "monitor", "monitoring", "health",
            "db", "database", "redis", "elastic", "elasticsearch",
            "sql", "mysql", "postgres", "postgresql", "mariadb", "mssql",
            "mongo", "mongodb", "cassandra", "neo4j", "couchdb",
            "search", "solr", "meilisearch",
            "cache", "memcached", "varnish",
            "queue", "rabbit", "rabbitmq", "kafka", "zmq", "redis-queue",
            "log", "logs", "syslog", "elk", "fluentd", "logstash",
            "time", "ntp", "ntp1", "ntp2", "ntp3",
            "ldap", "kerberos", "ad", "dc",
            "file", "files", "ftp1", "sftp", "nfs", "smb",
            "backup", "backups", "backup1", "backup2", "bak",
            "old", "old1", "old2", "archive", "new",
            "temp", "tmp", "scratch", "sandbox",
            "canary", "blue", "green", "red",
            "internal", "intranet", "private", "corp", "corporate",
            "public", "open", "free",
            "download", "downloads", "uploads", "upload",
            "shop", "store", "ecommerce", "cart", "checkout", "pay", "payment",
            "m", "mobile", "wap", "touch",
            "proxy", "proxy1", "proxy2", "reverse", "lb", "loadbalancer",
            "haproxy", "nginx", "apache", "caddy", "traefik",
            "tomcat", "jetty", "gunicorn", "uwsgi", "puma",
            "php", "python", "ruby", "java", "node", "go", "rust", "net",
            "dotnet", "iis", "express", "django", "flask", "spring",
            "edge", "cdn1", "cdn2", "cf", "cloudflare", "akamai", "fastly",
            "aws", "azure", "gcp", "s3", "lambda", "ec2",
            "blob", "bucket", "storage", "minio",
            "compute", "vm", "server", "node", "host",
            "cluster", "master", "worker", "slave", "leader", "follower",
            "analytics", "metrics", "prometheus", "datadog", "newrelic",
            "events", "webhook", "webhooks", "notify", "notification",
            "chat", "messaging", "ws", "wss", "socket", "websocket",
            "realtime", "rt", "live", "stream",
            "data", "pipeline", "etl", "ingest",
            "service", "services", "microservice",
            "config", "configuration", "settings", "env",
            "secret", "secrets", "vault", "key", "keys",
            "cert", "certs", "certificate", "ssl", "tls",
            "acme", "letsencrypt", "pki",
            "owa", "exchange", "autodiscover", "autoconfig",
            "sharepoint", "teams", "skype", "lync",
            "confluence", "jira", "bitbucket", "sonarqube",
            "nexus", "artifactory", "registry",
            "kafka", "zookeeper", "consul", "etcd", "vault",
            "minio", "ceph", "nfs", "gluster",
            "tigergraph", "neo4j", "dgraph", "neptune",
            "ml", "ai", "model", "training", "inference",
            "jupyter", "notebook", "lab", "sandbox",
            "grafana", "kibana", "prometheus", "alertmanager",
            "vault", "consul", "nomad", "waypoint",
        ]

        found: Set[str] = set()
        semaphore = asyncio.Semaphore(50)

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
                        timeout=3.0,
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
        if not subdomains:
            return 0

        import dns.resolver
        sample = subdomains[:sample_size]
        semaphore = asyncio.Semaphore(30)

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

        if len(sample) < len(subdomains):
            ratio = alive / len(sample) if sample else 0
            return int(ratio * len(subdomains))
        return alive
