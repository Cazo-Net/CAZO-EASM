"""External intelligence feeds for blockchain addresses.

Integrates:
- OFAC SDN sanctions list (live, see sanctions.py)
- Chainalysis free sanctions-screening API (when CHAINALYSIS_API_KEY is set)
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.blockchain import (
    Chain,
    Evidence,
    EvidenceType,
)

logger = logging.getLogger(__name__)



# ── OFAC Sanctions ──────────────────────────────────────────────────────────
# Screened against the live OFAC SDN list (see sanctions.py). The old
# hardcoded table here was wrong: most entries were not on the list, and one
# (the Uniswap V3 factory) was falsely tagged as a sanctioned exchange.


async def check_ofac_sanctions(address: str, chain: Chain = Chain.ETHEREUM) -> dict[str, Any]:
    """Check an address against the OFAC SDN list.

    ``is_sanctioned`` is True, False, or None when the list could not be read.
    """
    from app.services.blockchain.sanctions import check_address

    result = await check_address(address, chain)
    if result.get("is_sanctioned"):
        result["evidence"] = Evidence(
            source="ofac",
            type=EvidenceType.SANCTIONS_LIST,
            confidence=100,
            reason="Address appears on the OFAC SDN list",
        ).model_dump(mode="json")
    return result


# ── Aggregate Intel ─────────────────────────────────────────────────────────

async def get_external_intel(address: str, chain: Chain = Chain.ETHEREUM) -> dict[str, Any]:
    """Gather external intelligence for an address from real sources.

    Today that is sanctions screening (OFAC SDN list, plus Chainalysis when
    a key is set). Each result carries its source and status so the UI can
    show "not screened" instead of implying "clean".
    """
    ofac = await check_ofac_sanctions(address, chain)
    return {
        "address": address,
        "chain": chain.value,
        "ofac": ofac,
        "chainalysis": ofac.get("chainalysis"),
        "sanctioned": ofac.get("is_sanctioned"),
    }
