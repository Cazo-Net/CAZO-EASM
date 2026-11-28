"""Work out the real client IP behind reverse proxies.

X-Forwarded-For is a comma-separated list. Each proxy *appends* the address it
received the request from, so only the right-most entries were written by
proxies we control; anything to the left can be typed by the client. Taking
the first (left-most) entry, as the app used to, lets anyone bypass per-IP
rate limits by sending a fake header.

TRUSTED_PROXY_HOPS = number of proxies in front of the backend that append to
X-Forwarded-For (e.g. 1 for "Railway edge -> backend"). The client IP is the
entry that many places from the right. 0 keeps the legacy left-most behaviour.
Note: the Next.js rewrite proxy forwards X-Forwarded-For unchanged and does not
append, so it does not count as a hop.
"""
from fastapi import Request

from app.config import settings


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    if not parts:
        return peer
    hops = settings.TRUSTED_PROXY_HOPS
    if hops <= 0:
        return parts[0]
    if len(parts) >= hops:
        return parts[-hops]
    return parts[0]
