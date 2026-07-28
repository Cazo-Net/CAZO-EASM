"""Splunk HTTP Event Collector (HEC) integration.

Sends CEF-formatted events to Splunk via HEC endpoint.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.cef import (
    format_cef,
    finding_to_cef,
    scan_completed_to_cef,
    risk_score_to_cef,
)

logger = logging.getLogger(__name__)


class SplunkHEC:
    """Splunk HTTP Event Collector client."""

    def __init__(
        self,
        hec_url: str,
        hec_token: str,
        *,
        verify_ssl: bool = True,
        timeout: float = 15.0,
        index: str = "main",
        source: str = "cazo_easm",
        source_type: str = "cef",
    ):
        self._url = hec_url.rstrip("/")
        self._token = hec_token
        self._verify = verify_ssl
        self._timeout = timeout
        self._index = index
        self._source = source
        self._source_type = source_type

    async def send_event(
        self,
        cef_line: str,
        *,
        index: Optional[str] = None,
        source: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Send a single CEF event to Splunk HEC.

        Returns True if successful.
        """
        import time
        payload = {
            "event": cef_line,
            "index": index or self._index,
            "source": source or self._source,
            "sourcetype": self._source_type,
        }
        if timestamp:
            payload["time"] = timestamp

        return await self._send(payload)

    async def send_finding(self, finding: Dict[str, Any], domain: str = "") -> bool:
        """Send a CAZO finding to Splunk."""
        cef_line = finding_to_cef(finding, domain)
        return await self.send_event(cef_line)

    async def send_findings_batch(
        self, findings: List[Dict[str, Any]], domain: str = ""
    ) -> int:
        """Send multiple findings to Splunk. Returns count of successful sends."""
        payloads = []
        for finding in findings:
            cef_line = finding_to_cef(finding, domain)
            payloads.append({
                "event": cef_line,
                "index": self._index,
                "source": self._source,
                "sourcetype": self._source_type,
            })

        return await self._send_batch(payloads)

    async def send_scan_completed(self, scan_data: Dict[str, Any]) -> bool:
        """Send scan completion event to Splunk."""
        cef_line = scan_completed_to_cef(scan_data)
        return await self.send_event(cef_line)

    async def send_risk_change(self, risk_data: Dict[str, Any]) -> bool:
        """Send risk score change to Splunk."""
        cef_line = risk_score_to_cef(risk_data)
        return await self.send_event(cef_line)

    async def _send(self, payload: Dict[str, Any]) -> bool:
        headers = {
            "Authorization": f"Splunk {self._token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    f"{self._url}/services/collector/event",
                    json=payload,
                    headers=headers,
                )

                if resp.status_code == 200:
                    return True
                else:
                    logger.warning(
                        "Splunk HEC returned %d: %s",
                        resp.status_code, resp.text[:200],
                    )
                    return False

        except Exception as e:
            logger.error("Splunk HEC send failed: %s", e)
            return False

    async def _send_batch(self, payloads: List[Dict[str, Any]]) -> int:
        """Send multiple events. Returns count of successful sends."""
        import asyncio

        # Splunk HEC accepts newline-delimited JSON
        headers = {
            "Authorization": f"Splunk {self._token}",
            "Content-Type": "application/json",
        }

        # Send in chunks of 100
        success_count = 0
        chunk_size = 100

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout * 2,
                verify=self._verify,
            ) as client:
                for i in range(0, len(payloads), chunk_size):
                    chunk = payloads[i:i + chunk_size]
                    # Build NDJSON
                    ndjson = "\n".join(json.dumps(p, default=str) for p in chunk)

                    resp = await client.post(
                        f"{self._url}/services/collector/event",
                        content=ndjson,
                        headers={**headers, "Content-Type": "text/plain"},
                    )

                    if resp.status_code == 200:
                        success_count += len(chunk)
                    else:
                        logger.warning(
                            "Splunk HEC batch returned %d",
                            resp.status_code,
                        )

        except Exception as e:
            logger.error("Splunk HEC batch send failed: %s", e)

        return success_count
