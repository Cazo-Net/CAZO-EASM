"""Turn request headers into the support/diagnostics details staff need.

Only coarse technical metadata is derived here: browser + major version,
operating system, device type and (when the edge provides it) an approximate
country/city. Nothing is fetched from third parties: we never send a customer's
IP address to an outside geolocation service.

A copy of ``parse_user_agent`` lives in ``admin-panel/backend/app/user_agent.py``
(the admin panel is a separate service and cannot import from here). Keep the
two in sync.
"""
import re
from typing import Optional

from fastapi import Request

from app.config import settings

# Stored user agents are capped: real ones are ~150 chars, anything longer is
# junk or an attempt to bloat the sessions table.
MAX_UA_LENGTH = 512

# Order matters: many browsers also claim to be Chrome/Safari, so the more
# specific tokens are checked first.
_BROWSERS = [
    ("Edge", r"Edg(?:e|A|iOS)?/(\d+)"),
    ("Opera", r"(?:OPR|Opera)/(\d+)"),
    ("Samsung Internet", r"SamsungBrowser/(\d+)"),
    ("Brave", r"Brave/(\d+)"),
    ("Vivaldi", r"Vivaldi/(\d+)"),
    ("Firefox", r"(?:Firefox|FxiOS)/(\d+)"),
    ("Chrome", r"(?:Chrome|CriOS)/(\d+)"),
    ("Safari", r"Version/(\d+)[\d.]*.*Safari/"),
    ("Internet Explorer", r"(?:MSIE |Trident/.*rv:)(\d+)"),
]

_BOTS = re.compile(r"bot|crawler|spider|curl/|wget/|python-requests|httpx|postman|okhttp|go-http-client",
                   re.IGNORECASE)


def _windows_version(nt: str) -> str:
    return {
        "10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7",
    }.get(nt, nt)


def parse_user_agent(ua: Optional[str]) -> dict:
    """Return {browser, browser_version, os, os_version, device_type} for a UA string.

    Unknown values are None. ``device_type`` is one of desktop, mobile, tablet,
    bot or None.
    """
    out = {"browser": None, "browser_version": None, "os": None, "os_version": None, "device_type": None}
    if not ua:
        return out
    ua = ua[:MAX_UA_LENGTH]

    if _BOTS.search(ua):
        out["device_type"] = "bot"
        out["browser"] = ua.split("/")[0].split(" ")[0][:40] or None

    if out["browser"] is None:
        for name, pattern in _BROWSERS:
            m = re.search(pattern, ua)
            if m:
                out["browser"], out["browser_version"] = name, m.group(1)
                break

    m = re.search(r"Windows NT ([\d.]+)", ua)
    if m:
        out["os"], out["os_version"] = "Windows", _windows_version(m.group(1))
    elif "iPad" in ua:
        out["os"] = "iPadOS"
        m = re.search(r"OS (\d+)[_\d]*", ua)
        out["os_version"] = m.group(1) if m else None
    elif "iPhone" in ua or "iPod" in ua:
        out["os"] = "iOS"
        m = re.search(r"OS (\d+)[_\d]*", ua)
        out["os_version"] = m.group(1) if m else None
    elif "Android" in ua:
        out["os"] = "Android"
        m = re.search(r"Android (\d+)", ua)
        out["os_version"] = m.group(1) if m else None
    elif "CrOS" in ua:
        out["os"] = "ChromeOS"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        out["os"] = "macOS"
        m = re.search(r"Mac OS X (\d+)[_.](\d+)", ua)
        out["os_version"] = f"{m.group(1)}.{m.group(2)}" if m else None
    elif "Linux" in ua:
        out["os"] = "Linux"

    if out["device_type"] is None:
        if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
            out["device_type"] = "tablet"
        elif "Mobile" in ua or "iPhone" in ua:
            out["device_type"] = "mobile"
        elif out["os"] or out["browser"]:
            out["device_type"] = "desktop"
    return out


def browser_label(info: dict) -> str:
    """'Chrome 131' / 'Unknown'."""
    if not info.get("browser"):
        return "Unknown"
    return " ".join(p for p in (info["browser"], info.get("browser_version")) if p)[:100]


def os_label(info: dict) -> str:
    """'Windows 10/11' / 'Unknown'."""
    if not info.get("os"):
        return "Unknown"
    return " ".join(p for p in (info["os"], info.get("os_version")) if p)[:100]


def edge_geo(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Approximate (city, country) from headers set by the CDN/edge proxy.

    Cloudflare adds CF-IPCountry (and CF-IPCity with its location headers
    transform). A client can type these headers itself when it reaches the
    backend directly, so they are only read when TRUST_EDGE_GEO_HEADERS is on,
    i.e. when all traffic is known to pass through Cloudflare.
    """
    if not settings.TRUST_EDGE_GEO_HEADERS:
        return None, None

    def clean(value: Optional[str], limit: int) -> Optional[str]:
        if not value:
            return None
        value = value.strip()
        # "XX" = unknown, "T1" = Tor in Cloudflare's country header.
        if not value or value.upper() == "XX":
            return None
        return re.sub(r"[^\w .,'-]", "", value)[:limit] or None

    country = clean(request.headers.get("cf-ipcountry"), 100)
    city = clean(request.headers.get("cf-ipcity"), 100)
    return city, country
