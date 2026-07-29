"""Dark Web Intelligence API routes.

Provides search, monitoring, and reports for dark web intelligence.
Returns simulated data for development — production would integrate
with Tor crawlers, OSINT feeds, and threat intel APIs.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()

# ── Simulated Data ──────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)

_SIMULATED_MENTIONS: list[dict[str, Any]] = [
    # --- Credentials & Data Breaches ---
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://alphaxdd7k7.onion/forum/thread/4821",
        "content_type": "forum_post",
        "title": "Database dump containing 2.4M user records",
        "summary": "Threat actor posting a database dump allegedly from a major SaaS platform. Includes email, password hashes, and API keys.",
        "discovered_at": (_NOW - timedelta(hours=3)).isoformat(),
        "keywords": ["database", "credentials", "data_breach", "password", "hash", "api_keys"],
        "entities": ["saas-platform"],
        "threat_level": "critical",
        "confidence": 78,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "paste_site",
        "source_url": "https://paste.gg/p/abc123/raw",
        "content_type": "data_dump",
        "title": "Corporate email list with plaintext passwords",
        "summary": "Paste containing ~50K corporate email/password pairs. Passwords appear to be from a credential stuffing attack.",
        "discovered_at": (_NOW - timedelta(hours=6)).isoformat(),
        "keywords": ["credentials", "email", "password", "corporate", "credential_stuffing"],
        "entities": ["enterprise-corp"],
        "threat_level": "critical",
        "confidence": 82,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "telegram",
        "source_url": "https://t.me/leakdb_channel/4521",
        "content_type": "announcement",
        "title": "New credential leak from financial services API",
        "summary": "Threat actor claims access to leaked API tokens from a financial services provider. Tokens allegedly grant read access to customer accounts.",
        "discovered_at": (_NOW - timedelta(hours=12)).isoformat(),
        "keywords": ["api", "tokens", "financial", "credentials", "leak", "customer"],
        "entities": ["finserv-provider"],
        "threat_level": "high",
        "confidence": 60,
    },
    # --- Exploits & Vulnerabilities ---
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://exploit0x3.onion/vuln/cve-2025-1234",
        "content_type": "exploit_listing",
        "title": "Zero-day exploit for popular web framework",
        "summary": "0-day RCE exploit targeting a widely-used JavaScript framework. Affects versions 4.x through 5.2. Proof-of-concept available.",
        "discovered_at": (_NOW - timedelta(days=1)).isoformat(),
        "keywords": ["exploit", "zero_day", "rce", "web", "framework", "javascript", "vulnerability"],
        "entities": [],
        "threat_level": "critical",
        "confidence": 70,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "forum",
        "source_url": "http://darkforum01.onion/thread/99234",
        "content_type": "forum_post",
        "title": "SQL injection technique for modern ORMs",
        "summary": "New SQL injection bypass technique for Sequelize, Prisma, and TypeORM. Works on default configurations.",
        "discovered_at": (_NOW - timedelta(days=2)).isoformat(),
        "keywords": ["sql_injection", "orm", "sequelize", "prisma", "vulnerability", "web"],
        "entities": [],
        "threat_level": "high",
        "confidence": 65,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://vulnmarket.onion/item/8812",
        "content_type": "marketplace_listing",
        "title": "Privilege escalation exploit — cloud providers",
        "summary": "Privilege escalation vulnerability affecting major cloud providers. Allows lateral movement from container to host.",
        "discovered_at": (_NOW - timedelta(days=3)).isoformat(),
        "keywords": ["privilege_escalation", "cloud", "container", "lateral_movement", "exploit"],
        "entities": ["cloud-provider"],
        "threat_level": "high",
        "confidence": 55,
    },
    # --- Threat Actors & Campaigns ---
    {
        "id": str(uuid.uuid4()),
        "source": "telegram",
        "source_url": "https://t.me/apt_watch/112",
        "content_type": "announcement",
        "title": "APT group targeting cryptocurrency exchanges",
        "summary": "Known APT group (Lazarus-associated) actively targeting crypto exchange APIs and hot wallets with phishing campaigns.",
        "discovered_at": (_NOW - timedelta(hours=18)).isoformat(),
        "keywords": ["apt", "cryptocurrency", "exchange", "phishing", "lazarus", "threat_actor"],
        "entities": ["crypto-exchange", "lazarus-group"],
        "threat_level": "critical",
        "confidence": 72,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "forum",
        "source_url": "http://threatintel.onion/thread/5567",
        "content_type": "forum_post",
        "title": "Ransomware group recruiting affiliates",
        "summary": "Major ransomware-as-a-service operation recruiting new affiliates. Offering 80/20 revenue split. Targeting healthcare and education.",
        "discovered_at": (_NOW - timedelta(days=1, hours=6)).isoformat(),
        "keywords": ["ransomware", "recruiting", "affiliate", "healthcare", "education", "threat_actor"],
        "entities": ["ransomware-group"],
        "threat_level": "high",
        "confidence": 68,
    },
    # --- Marketplace Listings ---
    {
        "id": str(uuid.uuid4()),
        "source": "marketplace",
        "source_url": "http://darkmarket01.onion/item/33456",
        "content_type": "marketplace_listing",
        "title": "Stolen OAuth tokens for enterprise SaaS",
        "summary": "Listing selling active OAuth tokens for popular enterprise tools. Tokens allegedly valid for 30 days.",
        "discovered_at": (_NOW - timedelta(hours=9)).isoformat(),
        "keywords": ["oauth", "tokens", "enterprise", "saas", "stolen", "access"],
        "entities": ["enterprise-saas"],
        "threat_level": "high",
        "confidence": 50,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "marketplace",
        "source_url": "http://hydra2market.onion/product/78901",
        "content_type": "marketplace_listing",
        "title": "VPN credentials — Fortune 500 companies",
        "summary": "Bulk listing of VPN credentials for major corporations. Includes username, password, and MFA seed.",
        "discovered_at": (_NOW - timedelta(days=2, hours=4)).isoformat(),
        "keywords": ["vpn", "credentials", "fortune500", "mfa", "bulk", "corporate"],
        "entities": ["fortune-500"],
        "threat_level": "critical",
        "confidence": 45,
    },
    # --- Malware & Tools ---
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://malwarevault.onion/tool/new_stealer",
        "content_type": "malware_listing",
        "title": "New infostealer targeting browser wallets",
        "summary": "Sophisticated infostealer that extracts cryptocurrency wallet private keys from Chrome, Firefox, and Brave extensions.",
        "discovered_at": (_NOW - timedelta(hours=15)).isoformat(),
        "keywords": ["malware", "infostealer", "browser", "wallet", "crypto", "private_key", "extension"],
        "entities": [],
        "threat_level": "high",
        "confidence": 75,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "forum",
        "source_url": "http://crimeware.onion/thread/2234",
        "content_type": "forum_post",
        "title": "Phishing kit for banking apps — updated 2025",
        "summary": "Updated phishing kit with real-time proxy for banking 2FA bypass. Supports 20+ banks.",
        "discovered_at": (_NOW - timedelta(days=4)).isoformat(),
        "keywords": ["phishing", "banking", "2fa", "bypass", "kit", "fraud"],
        "entities": [],
        "threat_level": "high",
        "confidence": 62,
    },
    # --- Supply Chain ---
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://supplychainsec.onion/advisory/npm_backdoor",
        "content_type": "advisory",
        "title": "Backdoor discovered in popular npm package",
        "summary": "A popular npm package with 2M+ weekly downloads found to contain a backdoor exfiltrating environment variables to a C2 server.",
        "discovered_at": (_NOW - timedelta(hours=5)).isoformat(),
        "keywords": ["supply_chain", "npm", "backdoor", "malware", "javascript", "exfiltration", "c2"],
        "entities": ["npm-package"],
        "threat_level": "critical",
        "confidence": 85,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "telegram",
        "source_url": "https://t.me/supply_chain_intel/78",
        "content_type": "announcement",
        "title": "Compromised Docker image on public registry",
        "summary": "Malicious Docker image discovered on Docker Hub mimicking a popular base image. Contains cryptocurrency miner.",
        "discovered_at": (_NOW - timedelta(days=1, hours=12)).isoformat(),
        "keywords": ["docker", "supply_chain", "malware", "cryptominer", "container", "registry"],
        "entities": ["docker-hub"],
        "threat_level": "high",
        "confidence": 70,
    },
    # --- Data for sale ---
    {
        "id": str(uuid.uuid4()),
        "source": "marketplace",
        "source_url": "http://datalekmarket.onion/product/9981",
        "content_type": "marketplace_listing",
        "title": "Healthcare patient records — 500K entries",
        "summary": "For sale: complete patient records including SSN, medical history, insurance IDs. Allegedly from a US hospital network.",
        "discovered_at": (_NOW - timedelta(days=5)).isoformat(),
        "keywords": ["healthcare", "patient_records", "ssn", "medical", "data_breach", "insurance"],
        "entities": ["hospital-network"],
        "threat_level": "critical",
        "confidence": 40,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "paste_site",
        "source_url": "https://rentry.co/leaked_data_xyz/raw",
        "content_type": "data_dump",
        "title": "Internal source code repository leak",
        "summary": "Leaked Git repository containing internal API keys, database credentials, and proprietary source code.",
        "discovered_at": (_NOW - timedelta(hours=20)).isoformat(),
        "keywords": ["source_code", "git", "api_keys", "database", "credentials", "internal"],
        "entities": ["target-org"],
        "threat_level": "critical",
        "confidence": 73,
    },
    # --- Recon & Targeting ---
    {
        "id": str(uuid.uuid4()),
        "source": "tor_search",
        "source_url": "http://recon0nion.onion/target/corp_x",
        "content_type": "forum_post",
        "title": "Active recon thread — corporate infrastructure mapping",
        "summary": "Detailed mapping of target's cloud infrastructure, including AWS subnets, Kubernetes clusters, and exposed services.",
        "discovered_at": (_NOW - timedelta(hours=8)).isoformat(),
        "keywords": ["recon", "infrastructure", "aws", "kubernetes", "cloud", "mapping", "exposed"],
        "entities": ["target-corp"],
        "threat_level": "medium",
        "confidence": 58,
    },
    {
        "id": str(uuid.uuid4()),
        "source": "forum",
        "source_url": "http://hackforum01.onion/thread/88123",
        "content_type": "forum_post",
        "title": "Web application attack surface analysis shared",
        "summary": "Detailed attack surface map for a major e-commerce platform. Includes subdomains, APIs, and admin panels.",
        "discovered_at": (_NOW - timedelta(days=2, hours=8)).isoformat(),
        "keywords": ["attack_surface", "subdomains", "api", "admin_panel", "web", "ecommerce"],
        "entities": ["ecommerce-platform"],
        "threat_level": "medium",
        "confidence": 52,
    },
]


def _filter_mentions(query: str) -> list[dict[str, Any]]:
    """Fuzzy keyword matching for simulated data.

    Splits the query into words and matches against any mention where
    at least one word appears (case-insensitive substring) in the
    title, summary, keywords, or entities.
    """
    query_lower = query.lower().strip()
    words = query_lower.split()
    results = []
    for mention in _SIMULATED_MENTIONS:
        searchable = " ".join([
            mention.get("title", ""),
            mention.get("summary", ""),
            " ".join(mention.get("keywords", [])),
            " ".join(mention.get("entities", [])),
        ]).lower()
        # Match if the full query or any individual word appears
        if query_lower in searchable or any(w in searchable for w in words):
            results.append(mention)
    return results


def _generate_contextual_results(query: str) -> list[dict[str, Any]]:
    """Generate realistic contextual results for any query term."""
    h = int(hashlib.sha256(query.lower().encode()).hexdigest(), 16)
    now = datetime.now(timezone.utc)

    templates = [
        {
            "source": "tor_search",
            "source_url": f"http://{hashlib.md5(f'{h}a'.encode()).hexdigest()[:16]}.onion/forum/thread/{h % 100000}",
            "content_type": "forum_post",
            "title": f"Discussion about {query} in underground forums",
            "summary": f"Forum thread discussing potential exploitation of {query}-related systems. Multiple threat actors participating with technical details.",
            "keywords": [query.lower(), "forum", "exploitation", "discussion"],
            "entities": [query.lower()] if len(query) > 3 else [],
            "threat_level": ["medium", "high", "low"][h % 3],
            "confidence": min(40 + (h % 50), 90),
        },
        {
            "source": "marketplace",
            "source_url": f"http://{hashlib.md5(f'{h}b'.encode()).hexdigest()[:16]}.onion/item/{h % 100000}",
            "content_type": "marketplace_listing",
            "title": f"Stolen {query} credentials circulating on dark web markets",
            "summary": f"Listings found selling compromised {query} access credentials. Prices range from $50-$500 depending on access level.",
            "keywords": [query.lower(), "credentials", "stolen", "marketplace", "access"],
            "entities": [query.lower()] if len(query) > 3 else [],
            "threat_level": ["high", "critical"][h % 2],
            "confidence": min(35 + (h % 45), 80),
        },
        {
            "source": "paste_site",
            "source_url": f"https://rentry.co/{hashlib.md5(f'{h}c'.encode()).hexdigest()[:12]}/raw",
            "content_type": "data_dump",
            "title": f"Leaked {query} data found on paste site",
            "summary": f"Data paste containing what appears to be {query}-related information. Includes email addresses and partial credentials.",
            "keywords": [query.lower(), "leak", "paste", "credentials", "data"],
            "entities": [],
            "threat_level": "medium",
            "confidence": min(30 + (h % 40), 70),
        },
        {
            "source": "telegram",
            "source_url": f"https://t.me/{hashlib.md5(f'{h}d'.encode()).hexdigest()[:12]}/{h % 10000}",
            "content_type": "announcement",
            "title": f"Threat actor claims {query} breach",
            "summary": f"Anonymous threat actor claiming to have breached {query} systems. Claims include user database and internal documents.",
            "keywords": [query.lower(), "breach", "threat_actor", "claim", "access"],
            "entities": [query.lower()] if len(query) > 3 else [],
            "threat_level": ["high", "critical"][h % 2],
            "confidence": min(25 + (h % 40), 65),
        },
        {
            "source": "forum",
            "source_url": f"http://{hashlib.md5(f'{h}e'.encode()).hexdigest()[:16]}.onion/thread/{h % 100000}",
            "content_type": "forum_post",
            "title": f"Exploit development targeting {query} infrastructure",
            "summary": f"Active thread where threat actors are collaborating on exploit development for {query}-related vulnerabilities.",
            "keywords": [query.lower(), "exploit", "vulnerability", "development", "infrastructure"],
            "entities": [],
            "threat_level": "high",
            "confidence": min(45 + (h % 35), 80),
        },
    ]

    # Pick 3-4 results based on the hash
    count = 3 + (h % 2)
    selected = []
    for i, t in enumerate(templates[:count]):
        mention = dict(t)
        mention["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{query}-{i}"))
        mention["discovered_at"] = (now - timedelta(hours=(h + i * 7) % 168)).isoformat()
        selected.append(mention)
    return selected


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_darkweb(
    q: str = Query(..., min_length=1, max_length=200),
):
    """Search dark web intelligence for a query."""
    # First, try to match against simulated data
    results = _filter_mentions(q)

    # Always add contextual results so the engine returns something useful
    contextual = _generate_contextual_results(q)
    results.extend(contextual)

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
