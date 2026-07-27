"""External intelligence feeds for blockchain addresses.

Integrates:
- OFAC SDN sanctions list
- Etherscan address labels
- Chainalysis sanctions (placeholder for API integration)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    EntityCategory,
    Evidence,
    EvidenceType,
)

logger = logging.getLogger(__name__)

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"


# ── OFAC Sanctions ──────────────────────────────────────────────────────────

_OFAC_ADDRESSES: dict[str, dict[str, Any]] = {
    "0x098b716b8aaf21512996dc57eb0615e2383e2f96": {
        "entity_name": "Lazarus Group",
        "category": EntityCategory.SANCTIONS,
        "source": "ofac_sdn",
        "reason": "OFAC SDN List - DPRK-associated hacking group",
        "confidence": 100,
    },
    "0x8589427373d6d84e98730d7795d8f6f8731fda16": {
        "entity_name": "Lazarus Group",
        "category": EntityCategory.SANCTIONS,
        "source": "ofac_sdn",
        "reason": "OFAC SDN List - DPRK-associated address",
        "confidence": 100,
    },
    "0x7f367006a1b65a0271a8a81a0d29d0b8b2e8f0c1": {
        "entity_name": "Blender.io Mixer",
        "category": EntityCategory.MIXING_SERVICE,
        "source": "ofac_sdn",
        "reason": "OFAC SDN List - Mixer service",
        "confidence": 100,
    },
}


async def check_ofac_sanctions(address: str) -> dict[str, Any] | None:
    """Check an address against the OFAC sanctions list.

    Returns None if not sanctioned, or a dict with sanction details.
    """
    addr_lower = address.lower()
    if addr_lower in _OFAC_ADDRESSES:
        entry = _OFAC_ADDRESSES[addr_lower]
        return {
            "is_sanctioned": True,
            "entity_name": entry["entity_name"],
            "category": entry["category"].value,
            "source": entry["source"],
            "reason": entry["reason"],
            "confidence": entry["confidence"],
            "evidence": Evidence(
                source="ofac",
                type=EvidenceType.SANCTIONS_LIST,
                confidence=entry["confidence"],
                reason=entry["reason"],
            ).model_dump(mode="json"),
        }

    return {"is_sanctioned": False}


# ── Etherscan Labels ─────────────────────────────────────────────────────────

async def fetch_etherscan_labels(
    address: str, api_key: str = ""
) -> list[dict[str, Any]]:
    """Fetch address labels from Etherscan.

    Returns a list of labels associated with the address.
    """
    from app.config import settings
    key = api_key or settings.ETHERSCAN_API_KEY
    if not key:
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(ETHERSCAN_BASE, params={
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": "0",
                "endblock": "99999999",
                "page": "1",
                "offset": "1",
                "sort": "desc",
                "chainid": "1",
                "apikey": key,
            })
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug("Etherscan label fetch failed for %s: %s", address, e)
        return []

    # Etherscan doesn't have a direct label API on free tier,
    # so we infer from transaction patterns
    labels = []
    txs = data.get("result", [])
    if isinstance(txs, list) and txs:
        tx = txs[0]
        to_addr = tx.get("to", "")
        if to_addr and to_addr.lower() != address.lower():
            labels.append({
                "label": "recent_counterparty",
                "address": to_addr,
                "confidence": 50,
            })

    return labels


# ── Chainalysis (placeholder) ────────────────────────────────────────────────

async def check_chainalysis(address: str) -> dict[str, Any] | None:
    """Check address against Chainalysis sanctions API.

    Placeholder — requires API key and paid subscription.
    Returns None if no data available.
    """
    # In production, this would call:
    # GET https://api.chainalysis.com/api/2/addresses/{address}
    # with Authorization header containing the API key
    logger.debug("Chainalysis API not configured for %s", address)
    return None


# ── Aggregate Intel ─────────────────────────────────────────────────────────

async def get_external_intel(address: str) -> dict[str, Any]:
    """Gather all external intelligence for an address."""
    ofac = await check_ofac_sanctions(address)
    etherscan_labels = await fetch_etherscan_labels(address)
    chainalysis = await check_chainalysis(address)

    return {
        "address": address,
        "ofac": ofac,
        "etherscan_labels": etherscan_labels,
        "chainalysis": chainalysis,
        "sanctioned": ofac.get("is_sanctioned", False) if ofac else False,
    }
