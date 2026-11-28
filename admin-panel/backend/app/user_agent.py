"""User-agent parsing for the client diagnostics view.

Copy of ``parse_user_agent`` / ``browser_label`` / ``os_label`` from
``backend/app/core/client_info.py`` (the admin panel is a separate service and
cannot import the backend package). Keep the two in sync. Parsing here at read
time also gives useful values for sessions stored before the backend parsed
user agents itself.
"""
import re
from typing import Optional

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
