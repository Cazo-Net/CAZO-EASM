"""Enhanced network intelligence scanner with service fingerprinting.

Upgrades port scanning with:
- Async TCP connect with banner grabbing
- TLS/SSL service detection
- HTTP/HTTPS service identification
- Service version detection from banners
- Protocol analysis
- Historical comparison
"""
from __future__ import annotations

import asyncio
import ssl
import logging
from typing import Any, Dict, Optional

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# Top ports to scan (subset for speed, nmap-like ordering)
TOP_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
    993, 995, 1723, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 8888, 9200, 27017,
]

# Service name mapping
SERVICE_MAP = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
    1723: "pptp", 3306: "mysql", 3389: "rdp", 5432: "postgresql",
    5900: "vnc", 6379: "redis", 8080: "http-proxy", 8443: "https-alt",
    8888: "http-alt", 9200: "elasticsearch", 27017: "mongodb",
}


@register_scanner(
    name="network-intelligence",
    category=ScannerCategory.NETWORK_INTELLIGENCE,
    version="2.0.0",
    priority=ScannerPriority.HIGH,
    description="Enhanced port scanning with service fingerprinting and banner collection",
    capabilities=[
        "port_discovery", "service_fingerprinting", "banner_grabbing",
        "tls_detection", "version_detection",
    ],
)
class NetworkIntelligenceScanner(EnhancedBaseScanner):
    """Advanced network scanner with service fingerprinting."""

    name = "network-intelligence"
    version = "2.0.0"
    category = ScannerCategory.NETWORK_INTELLIGENCE
    priority = ScannerPriority.HIGH

    def __init__(self, config=None):
        super().__init__(config)
        self.connect_timeout = self.config.get("connect_timeout", 1.5)
        self.banner_timeout = self.config.get("banner_timeout", 2.0)
        self.max_concurrency = self.config.get("max_concurrency", 200)
        self.top_ports = self.config.get("top_ports", TOP_PORTS)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        context = kwargs.get("context")
        # Get hosts from context, or resolve target IP
        hosts = [target]
        if context and context.discovered_assets:
            host_list = list({a.get("hostname", target) for a in context.discovered_assets if a.get("hostname")})
            if host_list:
                hosts = host_list

        # Resolve hostnames to IPs if needed
        resolved_hosts = []
        for host in hosts[:50]:
            try:
                import dns.resolver
                loop = asyncio.get_running_loop()
                answers = await loop.run_in_executor(None, lambda h=host: dns.resolver.resolve(h, "A"))
                for rdata in answers:
                    resolved_hosts.append((host, str(rdata)))
            except Exception:
                resolved_hosts.append((host, host))

        # Scan each host
        host_port_map: Dict[str, list] = {}
        for hostname, ip in resolved_hosts[:30]:
            host_result = await self._scan_host(ip)
            if host_result.get("open_ports"):
                host_port_map[hostname] = host_result["open_ports"]

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "hosts_scanned": len(resolved_hosts),
                "hosts": host_port_map,
                "summary": {
                    "total_hosts": len(resolved_hosts),
                    "hosts_with_open_ports": len(host_port_map),
                    "total_open_ports": sum(len(v) for v in host_port_map.values()),
                },
            },
        )

    def validate_target(self, target: str) -> bool:
        # Accept IPs and hostnames
        import re
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        host_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$'
        return bool(re.match(ip_pattern, target) or re.match(host_pattern, target))

    async def _scan_host(self, host: str) -> Dict[str, Any]:
        """Scan a single host for open ports and services."""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        open_ports = []

        async def _probe(port: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    # TCP connect
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port),
                        timeout=self.connect_timeout,
                    )

                    # Banner grabbing
                    banner = await self._grab_banner(host, port)

                    # TLS detection
                    tls_info = await self._detect_tls(host, port)

                    # HTTP detection
                    http_info = await self._detect_http(host, port, tls_info is not None)

                    writer.close()
                    await writer.wait_closed()

                    service = SERVICE_MAP.get(port, "unknown")
                    version = self._extract_version(banner, http_info)

                    return {
                        "port": port,
                        "state": "open",
                        "service": service,
                        "version": version,
                        "banner": banner[:200] if banner else None,
                        "tls": tls_info,
                        "http": http_info,
                    }

                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    return None

        tasks = [_probe(port) for port in self.top_ports]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r:
                open_ports.append(r)

        return {
            "open_ports": sorted(open_ports, key=lambda x: x["port"]),
            "total_scanned": len(self.top_ports),
        }

    async def _grab_banner(self, host: str, port: int) -> Optional[str]:
        """Attempt to grab service banner."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.banner_timeout,
            )
            # For HTTP ports, send a request
            if port in (80, 8080, 8888):
                writer.write(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
            elif port in (443, 8443):
                pass  # TLS, banner comes after handshake
            else:
                # For other services, just wait for banner
                pass

            await writer.drain()
            data = await asyncio.wait_for(reader.read(1024), timeout=self.banner_timeout)
            writer.close()
            await writer.wait_closed()
            return data.decode("utf-8", errors="replace").strip()
        except Exception:
            return None

    async def _detect_tls(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Detect TLS/SSL and extract certificate info."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ctx),
                timeout=self.connect_timeout,
            )

            ssl_obj = writer.get_extra_info("ssl_object")
            if ssl_obj and ssl_obj.getpeercert():
                cert = ssl_obj.getpeercert()
                writer.close()
                await writer.wait_closed()
                return {
                    "enabled": True,
                    "version": ssl_obj.version(),
                    "cipher": ssl_obj.cipher(),
                    "subject": dict(x[0] for x in cert.get("subject", [])),
                    "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    "not_after": cert.get("notAfter"),
                }

            writer.close()
            await writer.wait_closed()
            return {"enabled": True, "version": ssl_obj.version() if ssl_obj else None}
        except Exception:
            return None

    async def _detect_http(self, host: str, port: int, is_tls: bool) -> Optional[Dict[str, Any]]:
        """Detect HTTP/HTTPS service."""
        import httpx

        scheme = "https" if is_tls or port in (443, 8443) else "http"
        url = f"{scheme}://{host}:{port}/"

        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False, verify=False) as client:
                resp = await client.get(url)
                server = resp.headers.get("server", "")
                powered_by = resp.headers.get("x-powered-by", "")
                return {
                    "detected": True,
                    "scheme": scheme,
                    "status_code": resp.status_code,
                    "server": server,
                    "powered_by": powered_by,
                    "content_type": resp.headers.get("content-type", ""),
                    "title": self._extract_title(resp.text) if resp.status_code == 200 else None,
                }
        except Exception:
            return None

    def _extract_title(self, html: str) -> Optional[str]:
        """Extract title from HTML."""
        import re
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_version(self, banner: Optional[str], http_info: Optional[Dict]) -> Optional[str]:
        """Extract version from banner or HTTP headers."""
        if http_info and http_info.get("server"):
            import re
            match = re.search(r'[\d.]+', http_info["server"])
            if match:
                return match.group(0)
        if banner:
            import re
            match = re.search(r'[\d]+\.[\d]+[\.\d]*', banner)
            if match:
                return match.group(0)
        return None
