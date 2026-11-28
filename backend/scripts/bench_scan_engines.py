"""Benchmark both scan engines against a simulated network.

No packet leaves the machine. DNS, TCP connects, TLS handshakes and HTTP are
replaced by an in-process simulation with fixed delays, so two versions of
the engines can be compared on exactly the same "internet":

* ``bench-target.com`` with 40 in-scope hosts
  - 30 hosts behind two shared CDN addresses (a typical CDN / load-balancer
    estate): ports 80 and 443 open, everything else filtered (no answer
    until the connect timeout),
  - 10 hosts on their own address: 22, 80 and 443 open, everything else
    refused (fast "closed" answer),
* DNS answers after 5 ms, TCP and HTTP after 30 ms (a regional round trip),
  TLS handshakes are refused after 30 ms.

What it measures: wall-clock time of a full scan, TCP connection attempts,
HTTP requests and DNS queries. Real-world times depend on the target and the
network path, so treat the numbers as a like-for-like comparison of the
code, not a promise about a particular domain.

Run from ``backend/`` (any checkout of the code, so old and new versions can
be compared)::

    python scripts/bench_scan_engines.py --engine v1
    python scripts/bench_scan_engines.py --engine v2
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from collections import Counter

sys.path.insert(0, os.getcwd())
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("USE_SQLITE", "true")
os.environ.setdefault("USE_NMAP", "false")

DOMAIN = "bench-target.com"
CDN_IPS = ["93.184.215.10", "93.184.215.11"]
HOSTS = {}
for i in range(30):
    HOSTS[f"app{i}.{DOMAIN}"] = CDN_IPS[i % 2]
for i in range(10):
    HOSTS[f"srv{i}.{DOMAIN}"] = f"93.184.215.{20 + i}"
HOSTS[DOMAIN] = CDN_IPS[0]
IP_OPEN = {ip: {80, 443} for ip in CDN_IPS}
IP_OPEN.update({f"93.184.215.{20 + i}": {22, 80, 443} for i in range(10)})
IP_FILTERED = set(CDN_IPS)

DNS_RTT = 0.005
NET_RTT = 0.030
COUNTS: Counter = Counter()


def _ip_of(host: str):
    host = str(host).rstrip(".").lower()
    if host in IP_OPEN:
        return host
    return HOSTS.get(host)


# ── DNS ─────────────────────────────────────────────────────────────────────
def install_dns():
    import dns.resolver
    import dns.rdatatype

    class _RData:
        def __init__(self, ip):
            self.address = ip

        def to_text(self):
            return self.address

        def __str__(self):
            return self.address

    class _Answer(list):
        ttl = 300

        @property
        def rrset(self):
            return list(self)

    def _resolve(qname, rdtype="A", *args, **kwargs):
        COUNTS["dns_queries"] += 1
        time.sleep(DNS_RTT)
        name = str(qname).rstrip(".").lower()
        rtype = rdtype if isinstance(rdtype, str) else dns.rdatatype.to_text(rdtype)
        ip = HOSTS.get(name)
        if rtype == "A" and ip:
            return _Answer([_RData(ip)])
        if ip:
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NXDOMAIN()

    dns.resolver.resolve = _resolve
    dns.resolver.query = _resolve
    dns.resolver.Resolver.resolve = lambda self, *a, **k: _resolve(*a, **k)
    dns.resolver.Resolver.query = lambda self, *a, **k: _resolve(*a, **k)

    real_getaddrinfo = socket.getaddrinfo

    def _getaddrinfo(host, port, *args, **kwargs):
        ip = _ip_of(host) if host else None
        if ip:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]
        if host in ("localhost", "127.0.0.1", None):
            return real_getaddrinfo(host, port, *args, **kwargs)
        raise socket.gaierror(socket.EAI_NONAME, "simulated NXDOMAIN")

    socket.getaddrinfo = _getaddrinfo
    socket.gethostbyname = lambda h: _ip_of(h) or (_ for _ in ()).throw(socket.gaierror("NXDOMAIN"))


# ── TCP ─────────────────────────────────────────────────────────────────────
class _Reader:
    def __init__(self, port):
        self.port = port
        self._sent = False

    async def read(self, n=-1):
        await asyncio.sleep(NET_RTT)
        if self._sent:
            return b""
        self._sent = True
        if self.port == 22:
            return b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6\r\n"
        if self.port in (80, 443):
            return b"HTTP/1.1 200 OK\r\nServer: nginx/1.24.0\r\nContent-Length: 0\r\n\r\n"
        return b""

    async def readline(self):
        return await self.read()

    def at_eof(self):
        return self._sent


class _Writer:
    def __init__(self):
        self.transport = None

    def write(self, data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass

    async def wait_closed(self):
        pass

    def is_closing(self):
        return True

    def get_extra_info(self, *a, **k):
        return None


def install_tcp():
    async def _open_connection(host=None, port=None, *args, **kwargs):
        COUNTS["tcp_connects"] += 1
        ip = _ip_of(host)
        if not ip:
            raise OSError("simulated: no route")
        if port in IP_OPEN.get(ip, set()):
            await asyncio.sleep(NET_RTT)
            return _Reader(port), _Writer()
        if ip in IP_FILTERED:
            await asyncio.sleep(3600)  # no answer: the scanner's timeout decides
        await asyncio.sleep(NET_RTT)
        raise ConnectionRefusedError()

    asyncio.open_connection = _open_connection

    def _create_connection(address, timeout=None, *args, **kwargs):
        COUNTS["tls_handshakes"] += 1
        time.sleep(NET_RTT)
        raise ConnectionRefusedError("simulated: TLS not offered")

    socket.create_connection = _create_connection


# ── HTTP ────────────────────────────────────────────────────────────────────
def install_http():
    import httpx

    async def _handle(self, request):
        COUNTS["http_requests"] += 1
        await asyncio.sleep(NET_RTT)
        host = request.url.host
        if not _ip_of(host):
            raise httpx.ConnectError("simulated: unknown host", request=request)
        if request.url.path in ("/", ""):
            return httpx.Response(
                200, request=request,
                headers={"server": "nginx/1.24.0", "content-type": "text/html"},
                text="<html><head><title>Bench</title></head><body>ok</body></html>",
            )
        return httpx.Response(404, request=request, text="not found")

    httpx.AsyncHTTPTransport.handle_async_request = _handle


def install_sources():
    """Subdomain sources and WHOIS answer from the fixed estate."""
    hosts = sorted(h for h in HOSTS if h != DOMAIN)

    from app.scanners.subdomain import SubdomainScanner

    async def _subs(self, target, **kwargs):
        await asyncio.sleep(NET_RTT * 3)
        return {"success": True, "subdomains": hosts, "sources": {"bench": len(hosts)}}

    SubdomainScanner.scan = _subs

    from app.scanners.whois import WhoisScanner

    async def _whois(self, target, **kwargs):
        await asyncio.sleep(NET_RTT * 3)
        return {"success": True, "data": {"registrar": "Bench Registrar"}}

    WhoisScanner.scan = _whois

    from app.scanners.v2.asset_discovery import AdvancedAssetDiscoveryScanner

    async def _crtsh(self, domain, client):
        await asyncio.sleep(NET_RTT * 3)
        return hosts

    AdvancedAssetDiscoveryScanner._crtsh = _crtsh

    try:
        from app.scanners.v2.whois_intel import WhoisIntelligenceScanner
        from app.scanners.v2.base import ScanResult

        async def _whois2(self, target, **kwargs):
            await asyncio.sleep(NET_RTT * 3)
            return ScanResult(success=True, scanner=self.name, target=target,
                              data={"registrar": "Bench Registrar"})

        WhoisIntelligenceScanner.scan = _whois2
    except Exception:  # noqa: BLE001
        pass


STAGE_SECONDS: dict = {}


def install_stage_timer():
    """Record how long each v2 pipeline stage takes (works on old and new code)."""
    from app.scanners.v2.pipeline import ScanPipeline

    real = ScanPipeline._execute_stage

    async def timed(self, stage, *args, **kwargs):
        t = time.monotonic()
        try:
            return await real(self, stage, *args, **kwargs)
        finally:
            STAGE_SECONDS[stage.value] = round(time.monotonic() - t, 2)

    ScanPipeline._execute_stage = timed


async def run(engine: str, dump: str = "") -> dict:
    progress = []

    async def cb(pct, msg):
        progress.append((pct, msg))

    start = time.monotonic()
    if engine == "v1":
        from app.scanners.runner import ScanRunner
        res = await ScanRunner().run_full_scan(
            DOMAIN, progress_callback=cb, options={"subdomain_tools": ["default"]})
    else:
        from app.scanners.v2_runner import V2ScanRunner
        res = await V2ScanRunner().run_full_scan(DOMAIN, progress_callback=cb, options={})
    elapsed = time.monotonic() - start

    if dump:
        with open(dump, "w") as fh:
            json.dump(res.get("vulnerabilities") or [], fh, indent=1, default=str)
    ports = res.get("ports") or {}
    open_ports = sum(len(v or []) for v in ports.values())
    vulns = res.get("vulnerabilities") or []
    return {
        "engine": engine,
        "wall_seconds": round(elapsed, 2),
        "hosts_with_port_data": len(ports),
        "open_ports_reported": open_ports,
        "findings": len(vulns) if isinstance(vulns, list) else None,
        "tcp_connects": COUNTS["tcp_connects"],
        "tls_handshakes": COUNTS["tls_handshakes"],
        "http_requests": COUNTS["http_requests"],
        "dns_queries": COUNTS["dns_queries"],
        "progress_updates": len(progress),
        "stage_seconds": STAGE_SECONDS or None,
        "scanner_status": res.get("scanner_status"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["v1", "v2"], required=True)
    ap.add_argument("--json", action="store_true", help="print JSON only")
    ap.add_argument("--dump-findings", help="write the scan's findings to this JSON file")
    args = ap.parse_args()

    import logging
    logging.disable(logging.CRITICAL)
    install_dns()
    install_tcp()
    install_http()
    install_sources()
    install_stage_timer()
    out = asyncio.run(run(args.engine, args.dump_findings or ""))
    print(json.dumps(out, indent=None if args.json else 2, default=str))


if __name__ == "__main__":
    main()
