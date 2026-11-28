"""Sanctions screening for blockchain addresses, from real published lists.

Source: the U.S. Treasury OFAC SDN list. OFAC publishes sanctioned digital
currency addresses inside ``sdn_advanced.xml``; the open-source project
github.com/0xB10C/ofac-sanctioned-digital-currency-addresses extracts them
into one plain-text file per asset and refreshes the files every day. Those
files are what this module downloads (the base URL is configurable through
``OFAC_SANCTIONS_LIST_BASE_URL`` for anyone who mirrors them).

Optionally, Chainalysis's free sanctions-screening API is queried as a second
opinion when ``CHAINALYSIS_API_KEY`` is set.

Nothing here is hardcoded. If the list cannot be downloaded the answer is
"unknown" (``is_sanctioned: None``), never a confident "clean".
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.schemas.blockchain import Chain

logger = logging.getLogger(__name__)

DEFAULT_LIST_BASE_URL = (
    "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists"
)
OFAC_REFERENCE_URL = "https://sanctionssearch.ofac.treas.gov/"
SOURCE_NAME = "OFAC SDN list (U.S. Treasury)"
CACHE_TTL_SECONDS = 12 * 3600
RETRY_AFTER_FAILURE_SECONDS = 10 * 60

_EVM_CHAINS = {
    Chain.ETHEREUM, Chain.POLYGON, Chain.BNB, Chain.ARBITRUM,
    Chain.OPTIMISM, Chain.BASE, Chain.AVALANCHE,
}

# Which OFAC asset files hold addresses in each chain's address format.
# EVM addresses are the same on every EVM chain, so all EVM-family lists apply.
_ASSET_FILES: dict[str, tuple[str, ...]] = {
    "evm": ("ETH", "USDT", "USDC", "ARB", "BSC", "ETC"),
    "bitcoin": ("XBT",),
    "tron": ("TRX", "USDT"),
    "solana": ("SOL",),
}


def _family(chain: Chain) -> str | None:
    if chain in _EVM_CHAINS:
        return "evm"
    if chain == Chain.BITCOIN:
        return "bitcoin"
    if chain == Chain.TRON:
        return "tron"
    if chain == Chain.SOLANA:
        return "solana"
    return None


def _normalize(address: str, family: str) -> str:
    address = address.strip()
    # EVM addresses are case-insensitive (checksum casing only); bech32 BTC
    # addresses are case-insensitive too. Base58 (Tron, Solana, legacy BTC) is not.
    if family == "evm" or address.lower().startswith("bc1"):
        return address.lower()
    return address


def _belongs(address: str, family: str) -> bool:
    if family == "evm":
        return address.lower().startswith("0x") and len(address) == 42
    if family == "tron":
        return address.startswith("T")
    return True


class _ListCache:
    def __init__(self) -> None:
        self.addresses: dict[str, set[str]] = {}
        self.fetched_at: dict[str, float] = {}
        self.failed_at: dict[str, float] = {}


_cache = _ListCache()


def _base_url() -> str:
    return (getattr(settings, "OFAC_SANCTIONS_LIST_BASE_URL", "") or DEFAULT_LIST_BASE_URL).rstrip("/")


async def _download(family: str) -> set[str]:
    found: set[str] = set()
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for asset in _ASSET_FILES[family]:
            resp = await client.get(f"{_base_url()}/sanctioned_addresses_{asset}.txt")
            if resp.status_code == 404:
                continue  # that asset has no list (yet)
            resp.raise_for_status()
            for line in resp.text.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and _belongs(line, family):
                    found.add(_normalize(line, family))
    return found


async def _list_for(family: str) -> tuple[set[str] | None, str, float | None]:
    """Return (addresses, status, fetched_at). status is ok, stale or unavailable."""
    now = time.time()
    fetched = _cache.fetched_at.get(family)
    if fetched and now - fetched < CACHE_TTL_SECONDS:
        return _cache.addresses[family], "ok", fetched
    failed = _cache.failed_at.get(family)
    if failed and now - failed < RETRY_AFTER_FAILURE_SECONDS:
        if fetched:
            return _cache.addresses[family], "stale", fetched
        return None, "unavailable", None
    # No lock: the engine runs checks from short-lived event loops, and two
    # overlapping downloads of the same public file are harmless.
    try:
        addresses = await _download(family)
        if not addresses:
            raise ValueError("sanctions list came back empty")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not download the OFAC %s list: %s", family, exc)
        _cache.failed_at[family] = time.time()
        if fetched:
            return _cache.addresses[family], "stale", fetched
        return None, "unavailable", None
    _cache.addresses[family] = addresses
    _cache.fetched_at[family] = time.time()
    _cache.failed_at.pop(family, None)
    return addresses, "ok", _cache.fetched_at[family]


async def _chainalysis(address: str) -> dict[str, Any] | None:
    key = getattr(settings, "CHAINALYSIS_API_KEY", "") or ""
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://public.chainalysis.com/api/v1/address/{address}",
                headers={"X-API-Key": key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chainalysis sanctions check failed: %s", exc)
        return {"status": "unavailable"}
    ids = data.get("identifications") or []
    return {
        "status": "ok",
        "is_sanctioned": bool(ids),
        "identifications": [
            {k: i.get(k) for k in ("category", "name", "description", "url")} for i in ids[:10]
        ],
    }


async def check_address(address: str, chain: Chain) -> dict[str, Any]:
    """Screen one address. ``is_sanctioned`` is True, False, or None (unknown)."""
    family = _family(chain)
    result: dict[str, Any] = {
        "address": address,
        "chain": chain.value,
        "source": SOURCE_NAME,
        "reference_url": OFAC_REFERENCE_URL,
    }
    if family is None:
        result.update(is_sanctioned=None, status="unsupported_chain")
        return result

    addresses, status, fetched_at = await _list_for(family)
    result["status"] = status
    result["list_updated_at"] = (
        datetime.fromtimestamp(fetched_at, tz=timezone.utc).isoformat() if fetched_at else None
    )
    if addresses is None:
        result["is_sanctioned"] = None
        result["message"] = "The OFAC list could not be downloaded, so this address was not screened."
    else:
        result["is_sanctioned"] = _normalize(address, family) in addresses
        result["list_size"] = len(addresses)

    second = await _chainalysis(address)
    if second is not None:
        result["chainalysis"] = second
        if second.get("is_sanctioned"):
            result["is_sanctioned"] = True
    return result


async def screen_many(addresses: list[str], chain: Chain) -> set[str]:
    """Return the subset of ``addresses`` on the OFAC list (list lookups only).

    Used by the watch engine to check counterparties in bulk without calling
    Chainalysis once per address. Returns an empty set if the list is down.
    """
    family = _family(chain)
    if family is None:
        return set()
    listed, _status, _ = await _list_for(family)
    if not listed:
        return set()
    return {a for a in addresses if a and _normalize(a, family) in listed}


def _reset_cache_for_tests() -> None:
    global _cache
    _cache = _ListCache()
