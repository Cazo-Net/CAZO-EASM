"""Microsoft Sentinel (Log Analytics) integration.

Sends findings to Sentinel via Data Collector API (REST).
"""
from __future__ import annotations

import json
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class SentinelIntegration:
    """Microsoft Sentinel Log Analytics client."""

    def __init__(
        self,
        workspace_id: str,
        primary_key: str,
        *,
        log_type: str = "CAZOFindings",
        verify_ssl: bool = True,
        timeout: float = 15.0,
    ):
        self._workspace_id = workspace_id
        self._primary_key = primary_key
        self._log_type = log_type
        self._verify = verify_ssl
        self._timeout = timeout
        self._base_url = f"https://{workspace_id}.ods.opinsights.azure.com"

    def _build_auth(self, date: str, content_length: int) -> str:
        """Build Authorization header for Log Analytics API."""
        string_to_sign = (
            f"POST\n{content_length}\napplication/json\n"
            f"x-ms-date:{date}\n/api/logs"
        )
        import hmac
        import base64
        key_bytes = base64.b64decode(self._primary_key)
        signature = base64.b64encode(
            hmac.new(key_bytes, string_to_sign.encode(), hashlib.sha256).digest()
        ).decode()
        return f"SharedKey {self._workspace_id}:{signature}"

    async def send_finding(self, finding: Dict[str, Any], domain: str = "") -> bool:
        """Send a single finding to Sentinel."""
        doc = self._finding_to_sentinel(finding, domain)
        return await self._post([doc])

    async def send_findings_batch(
        self, findings: List[Dict[str, Any]], domain: str = ""
    ) -> int:
        """Send multiple findings. Returns success count."""
        if not findings:
            return 0

        docs = [self._finding_to_sentinel(f, domain) for f in findings]
        success = await self._post(docs)
        return len(docs) if success else 0

    async def send_scan_completed(self, scan_data: Dict[str, Any]) -> bool:
        """Send scan completion event."""
        doc = {
            "TimeGenerated": datetime.now(timezone.utc).isoformat(),
            "EventType": "scan.completed",
            "Domain": scan_data.get("domain", ""),
            "ScanType": scan_data.get("scan_type", "full"),
            "SubdomainsFound": scan_data.get("subdomains_found", 0),
            "PortsFound": scan_data.get("ports_found", 0),
            "VulnerabilitiesFound": scan_data.get("vulnerabilities_found", 0),
            "RiskScore": scan_data.get("risk_score", 0),
            "Message": f"Scan completed for {scan_data.get('domain', 'unknown')}",
        }
        return await self._post([doc])

    def _finding_to_sentinel(self, finding: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Convert finding to Sentinel log entry."""
        return {
            "TimeGenerated": datetime.now(timezone.utc).isoformat(),
            "EventType": f"finding.{finding.get('severity', 'info')}",
            "Domain": domain,
            "Category": finding.get("category", "unknown"),
            "Subcategory": finding.get("subcategory", ""),
            "Severity": finding.get("severity", "info"),
            "Description": finding.get("description", finding.get("detail", ""))[:500],
            "RiskContribution": finding.get("risk_contribution", 0),
            "URL": finding.get("url", ""),
            "Header": finding.get("header", ""),
            "StatusCode": finding.get("status_code"),
            "Message": finding.get("description", finding.get("detail", "Finding detected")),
        }

    async def _post(self, logs: List[Dict[str, Any]]) -> bool:
        body = json.dumps(logs, default=str)
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        auth = self._build_auth(date, len(body))

        headers = {
            "Content-Type": "application/json",
            "Log-Type": self._log_type,
            "x-ms-date": date,
            "Authorization": auth,
            "time-generated-field": "TimeGenerated",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    f"{self._base_url}/api/logs?api-version=2016-09-01",
                    content=body,
                    headers=headers,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Sentinel send failed: %s", e)
            return False
