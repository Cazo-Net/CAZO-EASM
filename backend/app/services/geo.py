"""Where a domain's servers are: IP geolocation through ipinfo.io.

ipinfo.io answers without a token for light use; set ``IPINFO_TOKEN`` (free
plan: 50,000 lookups a month) for production volume. Private, loopback and
other reserved addresses are never sent out. Answers are cached in memory
for ``_TTL`` seconds so opening the same domain twice costs one lookup.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from app.config import settings

logger = logging.getLogger(__name__)

PROVIDER = "ipinfo.io"
_URL = "https://ipinfo.io/{ip}/json"
_TIMEOUT = 6
_TTL = 6 * 3600
_MAX_IPS = 10
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_global


def _parse(ip: str, data: Dict[str, Any]) -> Dict[str, Any]:
    org = (data.get("org") or "").strip()
    asn, provider = None, org or None
    m = re.match(r"^(AS\d+)\s+(.*)$", org)
    if m:
        asn, provider = m.group(1), m.group(2).strip() or None
    country = (data.get("country") or "").strip().upper() or None
    return {
        "ip": ip,
        "country": country if country and len(country) == 2 else None,
        "region": data.get("region") or None,
        "city": data.get("city") or None,
        "provider": provider,
        "asn": asn,
        "anycast": bool(data.get("anycast")),
        "private": False,
        "error": None,
    }


def lookup_ip(ip: str) -> Dict[str, Any]:
    """Hosting location of one IP. Never raises; failures come back in ``error``."""
    if not is_public_ip(ip):
        return {"ip": ip, "country": None, "region": None, "city": None, "provider": None,
                "asn": None, "anycast": False, "private": True, "error": None}
    now = time.time()
    hit = _cache.get(ip)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    params = {"token": settings.IPINFO_TOKEN} if settings.IPINFO_TOKEN else None
    try:
        resp = requests.get(_URL.format(ip=ip), params=params, timeout=_TIMEOUT,
                            headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        logger.info("ipinfo lookup failed for %s: %s", ip, exc.__class__.__name__)
        return {"ip": ip, "country": None, "region": None, "city": None, "provider": None,
                "asn": None, "anycast": False, "private": False, "error": "unreachable"}
    if resp.status_code == 429:
        error = "rate_limited"
    elif resp.status_code != 200:
        error = f"http_{resp.status_code}"
    else:
        try:
            result = _parse(ip, resp.json())
        except ValueError:
            error = "bad_response"
        else:
            _cache[ip] = (now, result)
            return result
    return {"ip": ip, "country": None, "region": None, "city": None, "provider": None,
            "asn": None, "anycast": False, "private": False, "error": error}


def unique_ips(values: Iterable[Any]) -> List[str]:
    seen: List[str] = []
    for v in values:
        if isinstance(v, str):
            v = v.strip()
            if v and v not in seen:
                try:
                    ipaddress.ip_address(v)
                except ValueError:
                    continue
                seen.append(v)
    return seen[:_MAX_IPS]


def locate(ips: Iterable[str]) -> List[Dict[str, Any]]:
    return [lookup_ip(ip) for ip in unique_ips(ips)]


def clear_cache() -> None:
    _cache.clear()


def configured() -> Optional[bool]:
    return bool(settings.IPINFO_TOKEN)
