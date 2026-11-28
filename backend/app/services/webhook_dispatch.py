"""Webhook dispatch service — sends signed HTTP requests to registered webhooks.

Features:
- HMAC-SHA256 payload signing
- Exponential backoff retry (3 attempts)
- Rate limiting per organization
- Failure tracking with auto-disable
- Async execution via asyncio
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.target_guard import GUARDED_HOOKS
from app.models.webhook import Webhook

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds


async def dispatch_webhook(
    webhook: Webhook,
    event_type: str,
    payload: Dict[str, Any],
    *,
    timeout: float = 15.0,
) -> bool:
    """Send a signed webhook notification.

    Returns True if delivered successfully.
    """
    # Check event filter
    if not webhook.matches_event(event_type):
        return False

    # Check rate limit
    if not webhook.check_rate_limit():
        logger.warning("Webhook %s rate limited, skipping", webhook.id[:8])
        return False

    # Build final payload
    body = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_id": webhook.id,
        "organization_id": webhook.organization_id,
        "data": payload,
    }

    body_bytes = json.dumps(body, default=str).encode()
    signature = webhook.sign_payload(body_bytes)

    # Custom headers go first so they can never replace the signature,
    # event or content headers set below.
    headers = {
        k: v for k, v in (webhook.custom_headers or {}).items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }
    headers.update({
        "Content-Type": webhook.content_type,
        "X-CAZO-Event": event_type,
        "X-CAZO-Signature": f"sha256={signature}",
        "X-CAZO-Timestamp": str(int(time.time())),
        "User-Agent": "CAZO-EASM-Webhook/2.0",
    })

    # Send with retry
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            # GUARDED_HOOKS refuses internal hosts at send time (SSRF);
            # redirects are not followed.
            async with httpx.AsyncClient(
                timeout=timeout, event_hooks=GUARDED_HOOKS, follow_redirects=False
            ) as client:
                resp = await client.post(
                    webhook.url,
                    content=body_bytes,
                    headers=headers,
                )

                if 200 <= resp.status_code < 300:
                    webhook.record_success()
                    logger.info(
                        "Webhook %s delivered: %s (HTTP %d)",
                        webhook.id[:8], event_type, resp.status_code,
                    )
                    return True

                # Do not echo the response body back to the user: with a
                # misconfigured URL it could contain another service's data.
                last_error = f"HTTP {resp.status_code}"
                logger.warning(
                    "Webhook %s returned %d (attempt %d/%d)",
                    webhook.id[:8], resp.status_code, attempt + 1, MAX_RETRIES,
                )

        except httpx.TimeoutException:
            last_error = "Request timed out"
            logger.warning(
                "Webhook %s timed out (attempt %d/%d)",
                webhook.id[:8], attempt + 1, MAX_RETRIES,
            )
        except Exception as e:
            last_error = str(e)[:200]
            logger.warning(
                "Webhook %s error: %s (attempt %d/%d)",
                webhook.id[:8], last_error, attempt + 1, MAX_RETRIES,
            )

        # Exponential backoff
        if attempt < MAX_RETRIES - 1:
            delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
            await asyncio.sleep(delay)

    # All retries failed
    webhook.record_failure(last_error)
    logger.error(
        "Webhook %s failed after %d attempts: %s",
        webhook.id[:8], MAX_RETRIES, last_error,
    )
    return False


async def dispatch_webhooks(
    webhooks: List[Webhook],
    event_type: str,
    payload: Dict[str, Any],
) -> Dict[str, bool]:
    """Dispatch an event to multiple webhooks concurrently.

    Returns dict of webhook_id → success.
    """
    if not webhooks:
        return {}

    # Filter to matching webhooks
    matching = [wh for wh in webhooks if wh.matches_event(event_type)]
    if not matching:
        return {}

    # Dispatch concurrently
    tasks = [
        dispatch_webhook(wh, event_type, payload)
        for wh in matching
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        wh.id: result if isinstance(result, bool) else False
        for wh, result in zip(matching, results)
    }


def get_webhooks_for_event(
    webhooks: List[Webhook],
    event_type: str,
) -> List[Webhook]:
    """Filter webhooks that should receive this event type."""
    return [wh for wh in webhooks if wh.matches_event(event_type)]
