"""Blockchain Intelligence module — FastAPI application.

Standalone service that can run independently or be mounted into the main EASM app.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.blockchain import router as blockchain_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI application for blockchain intelligence."""
    app = FastAPI(
        title="CAZO Blockchain Intelligence",
        description="On-chain analytics, wallet analysis, and risk scoring",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(blockchain_router)

    @app.get("/health")
    async def health():
        from .providers.base import registry
        return {
            "status": "ok",
            "module": "blockchain-intel",
            "chains": [c.value for c in registry.supported_chains()],
        }

    return app


# For direct uvicorn invocation
app = create_app()
