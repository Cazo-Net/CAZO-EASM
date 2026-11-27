"""Keep scans pointed at the public internet.

Scanners run inside the platform's own network, so a target that resolves to
a private, loopback, link-local or cloud-metadata address would turn a scan
into a probe of the platform's own infrastructure (SSRF). These checks run
when a scan is created and again right before a worker starts it, because DNS
can change in between.
"""
from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$"
)

# Hostnames that always point inside a network, whatever DNS says.
_INTERNAL_SUFFIXES = (
    ".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa",
    ".corp", ".private", ".svc", ".cluster.local", ".railway.internal",
    ".default", ".kube-system", ".docker", ".consul", ".test", ".invalid", ".example",
)
_INTERNAL_NAMES = {"localhost", "metadata", "metadata.google.internal", "instance-data"}

# Ranges Python's ipaddress flags do not all cover.
_EXTRA_BLOCKED = [
    ipaddress.ip_network("100.64.0.0/10"),   # carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),    # IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),   # benchmarking
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("64:ff9b::/96"),    # NAT64 (can embed private IPv4)
]


@dataclass
class TargetCheck:
    allowed: bool
    target: str
    reason: str = ""
    resolved_ips: List[str] = field(default_factory=list)


def normalize_target(raw: str) -> str:
    """Turn user input like ``https://App.Example.com:443/path`` into ``app.example.com``."""
    t = (raw or "").strip().lower()
    if "://" in t:
        t = t.split("://", 1)[1]
    t = t.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in t:
        t = t.rsplit("@", 1)[1]
    if t.startswith("[") and "]" in t:          # [ipv6]:port
        t = t[1:t.index("]")]
    elif t.count(":") == 1:                       # host:port
        t = t.split(":", 1)[0]
    return t.rstrip(".")


def is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return is_blocked_ip(str(addr.ipv4_mapped))
    if (
        addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
        or addr.is_multicast or addr.is_unspecified
    ):
        return True
    return any(addr in net for net in _EXTRA_BLOCKED)


def is_ip_literal(target: str) -> bool:
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return False


def is_valid_hostname(target: str) -> bool:
    return bool(_HOST_RE.match(target))


def is_internal_name(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host in _INTERNAL_NAMES or host.endswith(_INTERNAL_SUFFIXES) or "." not in host


def resolve_host(host: str, timeout: float = 4.0) -> List[str]:
    """Return A and AAAA records for ``host`` (empty list if it does not resolve)."""
    import dns.resolver  # type: ignore[import-untyped]

    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    ips: List[str] = []
    for rtype in ("A", "AAAA"):
        try:
            for rdata in resolver.resolve(host, rtype):
                ips.append(rdata.to_text())
        except Exception:  # noqa: BLE001 — NXDOMAIN, NoAnswer, timeouts
            continue
    return ips


def check_public_target(raw: str, *, resolve: bool = True) -> TargetCheck:
    """Allow only syntactically valid, public, non-internal targets."""
    target = normalize_target(raw)
    if not target:
        return TargetCheck(False, target, "Target is empty.")

    if is_ip_literal(target):
        if is_blocked_ip(target):
            return TargetCheck(False, target, "Private, loopback or reserved addresses cannot be scanned.")
        return TargetCheck(True, target, resolved_ips=[target])

    if not is_valid_hostname(target):
        return TargetCheck(False, target, f"'{raw}' is not a valid domain name.")
    if is_internal_name(target):
        return TargetCheck(False, target, "Internal hostnames cannot be scanned.")

    if not resolve:
        return TargetCheck(True, target)

    ips = resolve_host(target)
    blocked = [ip for ip in ips if is_blocked_ip(ip)]
    if blocked:
        logger.warning("Blocked scan target %s: resolves to internal address(es) %s", target, blocked)
        return TargetCheck(
            False, target,
            f"{target} resolves to an internal address ({blocked[0]}), which cannot be scanned.",
            resolved_ips=ips,
        )
    # A name that does not resolve is allowed: passive discovery (certificate
    # logs, DNS history) still works, and active probes resolve again later.
    return TargetCheck(True, target, resolved_ips=ips)


def filter_public_hosts(hosts: Iterable[str], resolve: bool = False) -> List[str]:
    """Drop internal names and private IPs from a list of discovered hosts."""
    kept: List[str] = []
    for h in hosts:
        check = check_public_target(h, resolve=resolve)
        if check.allowed:
            kept.append(h)
        else:
            logger.info("Skipping non-public host %s: %s", h, check.reason)
    return kept


def host_in_scope(host: str, root_domain: Optional[str]) -> bool:
    """True if ``host`` is ``root_domain`` or a subdomain of it."""
    if not root_domain:
        return True
    host = normalize_target(host)
    root = normalize_target(root_domain)
    return host == root or host.endswith("." + root)


async def probe_allowed(host: str, root_domain: Optional[str]) -> bool:
    """May a scanner actively connect to ``host`` during a scan of ``root_domain``?

    Hosts turned up *during* a scan (certificate SANs, reverse DNS, zone
    transfers, subdomain sources) are untrusted input: they can name other
    companies' servers or internal addresses. Only hosts under the authorized
    root domain that resolve to public addresses are probed. Everything else
    is still recorded as a discovery, just never connected to.
    """
    import asyncio

    if not host_in_scope(host, root_domain):
        logger.info("Not probing %s: outside the authorized domain %s", host, root_domain)
        return False
    check = await asyncio.to_thread(check_public_target, host)
    if not check.allowed:
        logger.info("Not probing %s: %s", host, check.reason)
    return check.allowed


async def filter_probe_targets(hosts: Iterable[str], root_domain: Optional[str]) -> List[str]:
    import asyncio

    hosts = list(hosts)
    flags = await asyncio.gather(*(probe_allowed(h, root_domain) for h in hosts))
    return [h for h, ok in zip(hosts, flags) if ok]


# ── Outbound HTTP guard ──────────────────────────────────────────────────────
_HOST_VERDICTS: dict = {}
_VERDICT_TTL = 60.0


async def block_internal_requests(request) -> None:
    """httpx request hook: refuse requests (and redirects) to internal hosts.

    Scanners follow redirects, and a public site can redirect to
    ``http://169.254.169.254/`` or an internal name. Attach with
    ``httpx.AsyncClient(event_hooks=GUARDED_HOOKS)``.
    """
    import asyncio
    import time

    import httpx

    host = request.url.host
    now = time.monotonic()
    cached = _HOST_VERDICTS.get(host)
    if cached and now - cached[1] < _VERDICT_TTL:
        allowed = cached[0]
    else:
        allowed = (await asyncio.to_thread(check_public_target, host)).allowed
        if len(_HOST_VERDICTS) > 5000:
            _HOST_VERDICTS.clear()
        _HOST_VERDICTS[host] = (allowed, now)
    if not allowed:
        raise httpx.RequestError(f"Blocked request to non-public host {host}", request=request)


GUARDED_HOOKS = {"request": [block_internal_requests]}
