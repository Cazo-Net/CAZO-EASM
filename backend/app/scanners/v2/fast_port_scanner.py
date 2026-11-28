"""Massively parallel port scanner — scans all 65535 ports in ~10-30s.

Pure-Python asyncio TCP connect scanner with:
- 2000+ concurrent connections via semaphore
- Single connection per port (connect + banner + HTTP probe in one shot)
- Smart port prioritization: top-1000 first, then remaining ports
- TLS upgrade for HTTPS ports in the same connection
- Service detection from banners + HTTP Server header
"""
from __future__ import annotations

import asyncio
import re
import ssl
import socket
import time
import logging
from typing import Any, Dict, List, Optional, Set

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import ScannerCategory

# Note: This scanner is NOT registered with @register_scanner.
# It is used internally by NetworkIntelligenceScanner as a fast port scanning engine.
# Keeping it unregistered prevents duplicate scanning in the pipeline.

logger = logging.getLogger(__name__)

# Nmap's top ~1000 most common ports. Scanned first for fast discovery.
TOP_1000_PORTS = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 85, 88, 100, 106,
    110, 111, 113, 119, 135, 139, 143, 144, 179, 199, 254, 255, 280, 311,
    389, 427, 443, 444, 445, 464, 465, 497, 500, 512, 513, 514, 515, 524,
    541, 548, 554, 563, 587, 593, 617, 625, 631, 636, 646, 787, 808, 873,
    902, 990, 993, 995, 1000, 1022, 1024, 1025, 1026, 1027, 1028, 1029,
    1030, 1080, 1099, 1110, 1433, 1434, 1521, 1720, 1723, 1755, 1900,
    2000, 2001, 2049, 2100, 2103, 2121, 2222, 2717, 3000, 3128, 3306,
    3389, 3986, 4443, 4444, 4899, 5000, 5001, 5003, 5009, 5050, 5051,
    5060, 5101, 5120, 5190, 5357, 5432, 5555, 5631, 5666, 5800, 5900,
    5901, 5985, 5986, 6000, 6001, 6379, 6646, 7000, 7001, 7070, 7100,
    7443, 7938, 8000, 8001, 8008, 8009, 8010, 8080, 8081, 8082, 8083,
    8084, 8085, 8088, 8090, 8443, 8888, 9000, 9001, 9090, 9099, 9100,
    9200, 9443, 9999, 10000, 11211, 27017, 27018, 28017, 50000, 50070,
    61616, 61621, 61622, 62078, 6444, 65432, 65433,
]

# Ports that speak immediately on connect (banner before we send anything).
CONNECT_BANNER_PORTS = frozenset({
    21, 22, 23, 25, 110, 111, 113, 119, 135, 143, 465, 587, 993, 995,
    3306, 3389, 5432, 6379, 8080,
})

# Ports where we proactively send an HTTP probe to elicit a banner.
HTTP_PROBE_PORTS = frozenset({
    80, 81, 443, 591, 2082, 2083, 2086, 2087, 2095, 2096, 3000, 3001, 4000,
    4443, 5000, 5001, 5601, 7001, 7443, 8000, 8001, 8008, 8080, 8081, 8088,
    8090, 8443, 8834, 8880, 8888, 9000, 9080, 9090, 9200, 9443, 10000, 10443,
    12443, 15672,
})

# Implicit-TLS ports (we upgrade the socket before probing). STARTTLS ports
# such as 587 are not listed: they start in clear text.
TLS_PORTS = frozenset({
    443, 465, 636, 993, 995, 2083, 2087, 2096, 4443, 5986, 6443, 7443, 8443,
    8834, 9443, 10443, 12443,
})

USER_AGENT = "CAZO-EASM/2.1 (+https://cazoeasm.io; attack surface monitoring)"

# Service name map for well-known ports.
SERVICE_MAP = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
    1433: "mssql", 1521: "oracle", 1723: "pptp", 3306: "mysql",
    3389: "rdp", 5432: "postgresql", 5900: "vnc", 5985: "winrm",
    6379: "redis", 8080: "http-proxy", 8443: "https-alt", 8888: "http-alt",
    9200: "elasticsearch", 9090: "prometheus", 11211: "memcached",
    27017: "mongodb", 5601: "kibana", 9000: "http-alt",
    389: "ldap", 636: "ldaps", 873: "rsync", 1883: "mqtt", 2049: "nfs",
    2375: "docker", 2376: "docker-tls", 2379: "etcd", 3000: "http-alt",
    5000: "http-alt", 5672: "amqp", 5984: "couchdb", 5986: "winrm-https",
    6443: "kubernetes-api", 7687: "neo4j-bolt", 8086: "influxdb",
    9042: "cassandra", 9092: "kafka", 9100: "jetdirect", 10250: "kubelet",
    15672: "rabbitmq-mgmt", 25565: "minecraft", 50070: "hadoop-namenode",
    161: "snmp", 502: "modbus", 623: "ipmi", 1080: "socks", 3690: "svn",
    4369: "epmd", 8291: "mikrotik-winbox", 11211: "memcached",
}


def _extract_version(banner: str, http_server: str = "") -> tuple[str, str]:
    """Best-effort product/version from a banner or HTTP Server header.
    Returns (product, version).
    """
    source = http_server or banner
    if not source:
        return "", ""

    # HTTP Server header: "Apache/2.4.7 (Ubuntu)"
    if http_server:
        m = re.match(r"^([A-Za-z][\w\- ]*?)[/_](\d[\w\.\-]*)", http_server.strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
        m = re.match(r"^([A-Za-z][\w\- ]*?)\s+(\d[\w\.\-]*)", http_server.strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return http_server.strip(), ""

    # SSH: "SSH-2.0-OpenSSH_6.6.1p1 Ubuntu-2ubuntu2.13"
    if banner.startswith("SSH-"):
        m = re.search(r"SSH-[^\s-]*-(.+)", banner)
        if m:
            prod, ver = _extract_version(m.group(1).strip())
            return prod or "OpenSSH", ver

    # Generic "Product/version"
    m = re.search(r"\b([A-Za-z][\w\-]+)[_/]?\s?(\d+\.[\w\.\-]+)", banner)
    if m:
        return m.group(1), m.group(2)

    return "", ""


def _parse_nmap_services(xml_text: str) -> Dict[int, Dict[str, str]]:
    """port -> {service, product, version} from nmap -oX output."""
    import xml.etree.ElementTree as ET

    out: Dict[int, Dict[str, str]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for port_el in root.iter("port"):
        state = port_el.find("state")
        if state is None or state.get("state") != "open":
            continue
        svc = port_el.find("service")
        if svc is None:
            continue
        tunnel = "ssl/" if svc.get("tunnel") == "ssl" else ""
        version = " ".join(x for x in (svc.get("version"), svc.get("extrainfo")) if x).strip()
        out[int(port_el.get("portid", "0"))] = {
            "service": (tunnel + svc.get("name", "")) if svc.get("name") else "",
            "product": svc.get("product", "") or "",
            "version": version[:120],
        }
    return out


class FastPortScanner(EnhancedBaseScanner):
    """Scans all 65535 ports using asyncio with 2000+ concurrency.

    One connection per port: connect + TLS upgrade + banner grab + HTTP probe.
    Smart prioritization: top-1000 ports first, then remaining.
    """

    name = "fast-port-scanner"
    version = "1.0.0"
    category = ScannerCategory.NETWORK_INTELLIGENCE
    priority = ScannerPriority.CRITICAL

    def __init__(self, config=None):
        super().__init__(config)
        self.connect_timeout = float(self.config.get("connect_timeout", 1.0))
        self.banner_timeout = float(self.config.get("banner_timeout", 1.5))
        # Per-host concurrency: polite by default (the old 2000 looked like a
        # SYN flood to most IDS/WAFs). Profiles raise it within limits.
        self.max_concurrency = int(self.config.get(
            "port_concurrency_per_host", self.config.get("max_concurrency", 100)))
        self.max_hosts = int(self.config.get("max_port_hosts", 10))
        self.host_parallelism = int(self.config.get("port_host_concurrency", 3))
        self.host_budget_s = float(self.config.get("port_host_budget_s", 60))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        context = kwargs.get("context")
        scan_type = kwargs.get("scan_type", "full")
        explicit_ports = kwargs.get("port_list")

        # Hosts: the target first, then in-scope discovered hosts. The
        # pipeline has already dropped out-of-scope and internal names from
        # context.discovered_assets.
        hosts: List[str] = [target]
        if context and context.discovered_assets:
            for a in context.discovered_assets:
                h = a.get("hostname")
                if h and h not in hosts:
                    hosts.append(h)

        from app.core.target_guard import is_blocked_ip

        async def _resolve(host: str) -> List[str]:
            loop = asyncio.get_running_loop()
            try:
                answers = await asyncio.wait_for(loop.run_in_executor(
                    None, lambda h=host: __import__("dns.resolver").resolver.resolve(h, "A")
                ), timeout=5)
                return [str(r) for r in answers]
            except Exception:
                return []

        # Many subdomains share one address (CDN, load balancer): scan each
        # public IP once and attribute the result to every host on it.
        ip_hosts: Dict[str, List[str]] = {}
        candidates = hosts[: max(self.max_hosts * 4, self.max_hosts)]
        resolved = await asyncio.gather(*(_resolve(h) for h in candidates))
        for host, ips in zip(candidates, resolved):
            public = [ip for ip in ips if not is_blocked_ip(ip)]
            if not public:
                continue
            ip = public[0]
            if ip not in ip_hosts and len(ip_hosts) >= self.max_hosts:
                continue
            ip_hosts.setdefault(ip, []).append(host)

        host_port_map: Dict[str, list] = {}
        per_ip: Dict[str, Dict[str, Any]] = {}
        sem = asyncio.Semaphore(max(1, self.host_parallelism))

        async def _one(ip: str, names: List[str]) -> None:
            async with sem:
                # Use the first hostname for SNI / Host headers.
                per_ip[ip] = await self._scan_host(ip, scan_type, explicit_ports, server_name=names[0])

        await asyncio.gather(*(_one(ip, names) for ip, names in ip_hosts.items()))

        for ip, result in per_ip.items():
            open_ports = result.get("open_ports") or []
            for name in ip_hosts[ip]:
                if open_ports:
                    host_port_map[name] = [dict(p, ip=ip) for p in open_ports]

        await self._nmap_enrich(host_port_map, ip_hosts)

        ports_checked = len(self._get_ports(scan_type, explicit_ports))
        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "hosts_scanned": sum(len(v) for v in ip_hosts.values()),
                "hosts": host_port_map,
                "summary": {
                    "total_hosts": sum(len(v) for v in ip_hosts.values()),
                    "unique_ips": len(ip_hosts),
                    "ports_per_host": ports_checked,
                    "hosts_with_open_ports": len(host_port_map),
                    "total_open_ports": sum(len(v) for v in host_port_map.values()),
                    "incomplete_hosts": [
                        ip for ip, r in per_ip.items() if r.get("budget_exceeded")
                    ],
                },
            },
        )

    async def _nmap_enrich(self, host_port_map: Dict[str, list], ip_hosts: Dict[str, List[str]]) -> None:
        """Run nmap -sV on ports already found open, for accurate versions.

        Only open ports are touched, so this adds a handful of connections per
        host rather than another full scan. Skipped when nmap is not installed.
        """
        if not self.config.get("nmap_enrich", True) or not host_port_map:
            return
        import shutil
        binary = shutil.which("nmap")
        if not binary:
            return
        sem = asyncio.Semaphore(2)

        async def _one(ip: str, names: List[str]) -> None:
            ports = sorted({p["port"] for n in names for p in host_port_map.get(n, [])})
            if not ports:
                return
            cmd = [binary, "-oX", "-", "-Pn", "-sV", "--version-light", "-T3", "--open",
                   "--host-timeout", "90s", "-p", ",".join(map(str, ports[:200])), ip]
            async with sem:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                    try:
                        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                    except BaseException:
                        if proc.returncode is None:
                            proc.kill()
                            await asyncio.shield(proc.wait())
                        raise
                except Exception as exc:  # noqa: BLE001
                    logger.debug("nmap enrich failed for %s: %s", ip, exc)
                    return
            versions = _parse_nmap_services(out.decode("utf-8", "replace"))
            for name in names:
                for p in host_port_map.get(name, []):
                    v = versions.get(p["port"])
                    if not v:
                        continue
                    if v.get("service"):
                        p["service"] = v["service"]
                    if v.get("product"):
                        p["product"] = v["product"]
                    if v.get("version"):
                        p["version"] = v["version"]
                    p["detected_by"] = "nmap"

        await asyncio.gather(*(_one(ip, names) for ip, names in ip_hosts.items()))

    def validate_target(self, target: str) -> bool:
        ip_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        host_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$"
        return bool(re.match(ip_pattern, target) or re.match(host_pattern, target))

    def _get_ports(self, scan_type: str, explicit_ports: Optional[List[int]]) -> List[int]:
        """Return the ordered list of ports to scan."""
        if explicit_ports:
            return sorted(set(explicit_ports))

        if scan_type == "quick":
            return [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432]

        # Full scan: top-1000 first, then remaining well-known ports
        seen = set()
        ordered = []
        for p in TOP_1000_PORTS:
            if p not in seen:
                ordered.append(p)
                seen.add(p)
        # Add remaining common ports not in top-1000
        for p in sorted(SERVICE_MAP.keys()):
            if p not in seen:
                ordered.append(p)
                seen.add(p)
        return ordered

    async def _scan_host(
        self, host: str, scan_type: str, explicit_ports: Optional[List[int]],
        server_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scan one IP with bounded concurrency inside a time budget."""
        ports = self._get_ports(scan_type, explicit_ports)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        start = time.monotonic()
        host_timeout = self.host_budget_s if scan_type != "quick" else min(self.host_budget_s, 20.0)
        skipped = 0

        async def _probe(port: int) -> Optional[Dict[str, Any]]:
            nonlocal skipped
            async with semaphore:
                if time.monotonic() - start > host_timeout:
                    skipped += 1
                    return None
                return await self._probe_port(host, port, server_name=server_name)

        results = await asyncio.gather(*(_probe(p) for p in ports), return_exceptions=True)
        open_ports = [r for r in results if isinstance(r, dict) and r.get("state") == "open"]
        if skipped:
            logger.info("Port scan of %s stopped after %.0fs; %d ports not checked", host, host_timeout, skipped)

        return {
            "open_ports": sorted(open_ports, key=lambda x: x["port"]),
            "total_scanned": len(ports) - skipped,
            "budget_exceeded": skipped > 0,
            "duration_ms": round((time.monotonic() - start) * 1000, 1),
        }

    async def _probe_port(
        self, host: str, port: int, server_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Single-connection probe: connect + TLS upgrade + banner grab + HTTP probe."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.connect_timeout,
            )
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError, socket.error):
            return None

        service = SERVICE_MAP.get(port, "unknown")
        product = ""
        version = ""
        banner = ""
        tls_info = None
        http_info = None
        use_tls = port in TLS_PORTS

        try:
            # TLS upgrade for HTTPS ports
            if use_tls:
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    # StreamWriter.start_tls (3.11+) upgrades the connection
                    # in place, so `reader` keeps working afterwards.
                    await asyncio.wait_for(
                        writer.start_tls(ctx, server_hostname=server_name or host),
                        timeout=self.banner_timeout,
                    )
                    tls_info = {"enabled": True}
                    # Try to get TLS version
                    ssl_obj = writer.get_extra_info("ssl_object")
                    if ssl_obj:
                        tls_info["version"] = getattr(ssl_obj, "version", lambda: None)()
                except Exception:
                    use_tls = False

            # Banner grabbing strategy (single attempt, fast)
            if (port in CONNECT_BANNER_PORTS and not use_tls) or (use_tls and port in (465, 993, 995)):
                banner = await self._fast_read(reader)
                if not banner:
                    await asyncio.sleep(0.15)
                    banner = await self._fast_read(reader)
            elif port in HTTP_PROBE_PORTS or use_tls:
                try:
                    probe = (
                        f"GET / HTTP/1.0\r\nHost: {server_name or host}\r\n"
                        f"User-Agent: {USER_AGENT}\r\nConnection: close\r\n\r\n"
                    ).encode()
                    writer.write(probe)
                    await writer.drain()
                    banner = await self._fast_read(reader)
                except (asyncio.TimeoutError, OSError):
                    pass

            # Extract service info from banner
            if banner:
                # Check for HTTP response
                if banner.startswith("HTTP/"):
                    http_info = self._parse_http_banner(banner)
                    if http_info.get("server"):
                        product, version = _extract_version("", http_info["server"])
                    service = "https" if use_tls else "http"
                    # nginx/Apache answer a plain request on a TLS port with 400.
                    if not use_tls and re.search(r"plain HTTP request was sent to HTTPS|speaking plain HTTP to an SSL", banner, re.I):
                        service = "https"
                        tls_info = {"enabled": True, "inferred": True}
                else:
                    product, version = _extract_version(banner)
                    if not product and service == "unknown":
                        first_line = banner.splitlines()[0] if banner.splitlines() else ""
                        if first_line:
                            product = first_line[:200]

            return {
                "port": port,
                "protocol": "tcp",
                "state": "open",
                "service": service,
                "version": version,
                "product": product,
                "banner": banner[:500] if banner else "",
                "tls": tls_info,
                "http": http_info,
            }
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _fast_read(self, reader) -> str:
        """Fast banner read with short timeout."""
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=self.banner_timeout)
            return data.decode(errors="replace").strip()
        except (asyncio.TimeoutError, OSError):
            return ""

    @staticmethod
    def _parse_http_banner(banner: str) -> Dict[str, Any]:
        """Parse an HTTP response banner for service info."""
        lines = banner.split("\r\n")
        server = ""
        powered_by = ""
        status_code = 0
        content_type = ""

        if lines:
            # First line: "HTTP/1.1 200 OK"
            m = re.search(r"(\d{3})", lines[0])
            if m:
                status_code = int(m.group(1))

        for line in lines[1:]:
            lower = line.lower()
            if lower.startswith("server:"):
                server = line.split(":", 1)[1].strip()
            elif lower.startswith("x-powered-by:"):
                powered_by = line.split(":", 1)[1].strip()
            elif lower.startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()

        return {
            "detected": True,
            "status_code": status_code,
            "server": server,
            "powered_by": powered_by,
            "content_type": content_type,
        }
