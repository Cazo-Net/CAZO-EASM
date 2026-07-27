"""Dark Web Intelligence API routes.

Provides search, monitoring, and reports for dark web intelligence.
Returns simulated data for development — production would integrate
with Tor crawlers, OSINT feeds, and threat intel APIs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()

# ── Simulated Data ──────────────────────────────────────────────────────────

_SIMULATED_MENTIONS: list[dict[str, Any]] = [
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://example.onion/forum/thread/1234",
        "content_type": "forum_post",
        "title": "Discussion about target organization",
        "summary": "Users discussing potential vulnerabilities in the target's public-facing infrastructure.",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "keywords": ["vulnerability", "network", "infrastructure"],
        "entities": ["target-org"],
        "threat_level": "medium",
        "confidence": 65,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "marketplace",
        "source_url": "http://example.onion/market/item/5678",
        "content_type": "marketplace_listing",
        "title": "Data dump for sale",
        "summary": "Alleged database dump allegedly containing user credentials.",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "keywords": ["database", "credentials", "data_breach"],
        "entities": [],
        "threat_level": "high",
        "confidence": 45,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "paste_site",
        "source_url": "https://paste.example.com/raw/abc123",
        "content_type": "data_dump",
        "title": "Leaked credentials",
        "summary": "Paste containing what appears to be email/password combinations.",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "keywords": ["credentials", "email", "password"],
        "entities": [],
        "threat_level": "critical",
        "confidence": 70,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "telegram",
        "source_url": "https://t.me/channel_name/123",
        "content_type": "announcement",
        "title": "Threat actor claiming breach",
        "summary": "Threat actor claiming to have access to internal systems.",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "keywords": ["breach", "access", "threat_actor"],
        "entities": ["target-org"],
        "threat_level": "high",
        "confidence": 35,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "forum",
        "source_url": "http://example.onion/forum/thread/9999",
        "content_type": "forum_post",
        "title": "Exploit discussion",
        "summary": "Forum thread discussing exploitation techniques for common web frameworks.",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "keywords": ["exploit", "web", "framework"],
        "entities": [],
        "threat_level": "low",
        "confidence": 55,
    },
]


def _filter_mentions(query: str) -> list[dict[str, Any]]:
    """Simple keyword matching for simulated data."""
    query_lower = query.lower()
    results = []
    for mention in _SIMULATED_MENTIONS:
        searchable = " ".join([
            mention.get("title", ""),
            mention.get("summary", ""),
            " ".join(mention.get("keywords", [])),
            " ".join(mention.get("entities", [])),
        ]).lower()
        if query_lower in searchable or any(query_lower in kw for kw in mention.get("keywords", [])):
            results.append(mention)
    return results


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_darkweb(
    q: str = Query(..., min_length=1, max_length=200),
):
    """Search dark web intelligence for a query."""
    results = _filter_mentions(q)
    return {
        "query": q,
        "results": results,
        "total": len(results),
        "page": 1,
        "has_next": False,
    }


@router.get("/monitors")
async def list_monitors():
    """List active monitoring targets."""
    return {
        "monitors": [
            {
                "id": str(uuid.uuid4()),
                "query": "example.com",
                "type": "domain",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "query": "admin@company.com",
                "type": "email",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ],
        "total": 2,
    }


@router.get("/reports")
async def list_reports():
    """List dark web intelligence reports."""
    return {
        "reports": [
            {
                "id": str(uuid.uuid4()),
                "title": "Weekly Dark Web Summary",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mentions_count": 12,
                "threat_level": "medium",
            },
        ],
        "total": 1,
    }
