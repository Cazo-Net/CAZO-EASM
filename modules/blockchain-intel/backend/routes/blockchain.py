"""Blockchain Intelligence API routes.

Provides wallet analysis, transaction tracing, contract details,
risk scoring, entity attribution, and search functionality.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..domain.models.base import Chain
from ..providers.base import registry
from ..services.attribution import attribution_service
from ..services.risk_engine import risk_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/blockchain", tags=["Blockchain Intelligence"])


class WalletAnalysisRequest(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)
    chain: Chain = Field(default=Chain.ETHEREUM)


class TransactionListRequest(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)
    chain: Chain = Field(default=Chain.ETHEREUM)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    chain: Chain | None = None


@router.get("/chains")
async def supported_chains():
    """List supported blockchains."""
    return {
        "chains": [c.value for c in registry.supported_chains()],
        "primary": "ethereum",
    }


@router.get("/wallet/{address}")
async def get_wallet(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get wallet summary with attribution and risk score."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        wallet = await provider.get_wallet_summary(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Wallet lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch wallet data")

    # Run attribution + risk scoring in parallel
    try:
        attribution, risk = await __import__("asyncio").gather(
            attribution_service.attribute(address, chain),
            risk_engine.score(address, chain, wallet=wallet),
            return_exceptions=True,
        )
    except Exception:
        attribution = None
        risk = None

    return {
        "wallet": wallet.model_dump(mode="json"),
        "attribution": attribution.model_dump(mode="json") if attribution and not isinstance(attribution, Exception) else None,
        "risk": risk.model_dump(mode="json") if risk and not isinstance(risk, Exception) else None,
    }


@router.get("/wallet/{address}/transactions")
async def get_transactions(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Get paginated transaction history for a wallet."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        return await provider.get_transactions(address, page, page_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@router.get("/transaction/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get full transaction detail by hash."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        tx = await provider.get_transaction(tx_hash)
        return tx.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")


@router.get("/contract/{address}")
async def get_contract(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get contract details if the address is a contract."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        contract = await provider.get_contract(address)
        if not contract:
            raise HTTPException(status_code=404, detail="Address is not a contract")
        return contract.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Contract fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch contract data")


@router.get("/wallet/{address}/tokens")
async def get_token_balances(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get token balances for a wallet."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        tokens = await provider.get_token_balances(address)
        return {"tokens": tokens}
    except Exception as e:
        logger.error("Token balance fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch token balances")


@router.get("/wallet/{address}/risk")
async def get_risk_score(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get detailed risk assessment for a wallet."""
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        wallet = await provider.get_wallet_summary(address)
    except Exception:
        wallet = None

    try:
        attribution = await attribution_service.attribute(address, chain)
    except Exception:
        attribution = None

    try:
        risk = await risk_engine.score(address, chain, wallet=wallet, attribution=attribution)
        return risk.model_dump(mode="json")
    except Exception as e:
        logger.error("Risk scoring failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to compute risk score")


@router.get("/wallet/{address}/attribution")
async def get_attribution(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get entity attribution for a wallet."""
    try:
        attribution = await attribution_service.attribute(address, chain)
        return attribution.model_dump(mode="json")
    except Exception as e:
        logger.error("Attribution failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to attribute wallet")


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    chain: Chain | None = Query(default=None),
):
    """Search for addresses, transactions, or entities."""
    results = []

    # Search curated labels
    from ...labels.curated import search_labels
    label_results = search_labels(q)
    for label in label_results:
        results.append({
            "type": "entity",
            "value": label["address"],
            "chain": label["chain"],
            "entity": label["entity"],
            "category": label["category"].value if hasattr(label["category"], "value") else str(label["category"]),
            "confidence": max(e.confidence for e in label.get("evidence", [])),
        })

    # Search chain providers
    chains_to_search = [chain] if chain else registry.supported_chains()
    for c in chains_to_search:
        provider = registry.get(c)
        if provider:
            try:
                chain_results = await provider.search(q)
                results.extend(chain_results)
            except Exception as e:
                logger.debug("Search on %s failed: %s", c, e)

    return {"results": results, "total": len(results)}
