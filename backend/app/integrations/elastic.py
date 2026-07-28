"""Elasticsearch / Elastic Security integration.

Sends findings in Elastic Common Schema (ECS) format.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "informational",
}


class ElasticIntegration:
    """Elasticsearch / Elastic Security client."""

    def __init__(
        self,
        es_url: str,
        api_key: Optional[str] = None,
        *,
        index_prefix: str = "cazo-easm",
        verify_ssl: bool = True,
        timeout: float = 15.0,
    ):
        self._url = es_url.rstrip("/")
        self._api_key = api_key
        self._index_prefix = index_prefix
        self._verify = verify_ssl
        self._timeout = timeout
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"ApiKey {api_key}"

    async def send_finding(self, finding: Dict[str, Any], domain: str = "") -> bool:
        """Send a single finding to Elasticsearch."""
        doc = self._finding_to_ecs(finding, domain)
        index = f"{self._index_prefix}-findings-{datetime.now().strftime('%Y.%m')}"
        return await self._index_doc(index, doc)

    async def send_findings_batch(
        self, findings: List[Dict[str, Any]], domain: str = ""
    ) -> int:
        """Send multiple findings via bulk API. Returns success count."""
        if not findings:
            return 0

        index = f"{self._index_prefix}-findings-{datetime.now().strftime('%Y.%m')}"
        actions = []
        for finding in findings:
            doc = self._finding_to_ecs(finding, domain)
            actions.append(json.dumps({"index": {"_index": index}}))
            actions.append(json.dumps(doc, default=str))

        bulk_body = "\n".join(actions) + "\n"
        return await self._bulk(bulk_body, len(findings))

    async def send_scan_completed(self, scan_data: Dict[str, Any]) -> bool:
        """Send scan completion event."""
        doc = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "event": {
                "kind": "event",
                "category": ["network"],
                "type": ["info"],
                "module": "cazo-easm",
                "outcome": "success",
            },
            "cazo": {
                "event_type": "scan.completed",
                "domain": scan_data.get("domain", ""),
                "scan_type": scan_data.get("scan_type", "full"),
                "subdomains_found": scan_data.get("subdomains_found", 0),
                "ports_found": scan_data.get("ports_found", 0),
                "vulnerabilities_found": scan_data.get("vulnerabilities_found", 0),
                "risk_score": scan_data.get("risk_score", 0),
            },
            "host": {"name": scan_data.get("domain", "")},
            "message": f"Scan completed for {scan_data.get('domain', 'unknown')}",
        }

        index = f"{self._index_prefix}-events-{datetime.now().strftime('%Y.%m')}"
        return await self._index_doc(index, doc)

    def _finding_to_ecs(self, finding: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Convert CAZO finding to Elastic Common Schema."""
        severity = finding.get("severity", "info")
        category = finding.get("category", "unknown")

        # Map CAZO categories to ECS
        ecs_category = ["vulnerability"]
        if category in ("cors_misconfiguration", "open_redirect"):
            ecs_category = ["network", "configuration"]
        elif category == "subdomain_takeover":
            ecs_category = ["vulnerability"]
        elif category == "ssrf_surface":
            ecs_category = ["vulnerability", "web"]
        elif category in ("missing_security_header", "info_disclosure"):
            ecs_category = ["configuration"]
        elif category in ("environment_file", "config_file", "source_control", "backup_file"):
            ecs_category = ["file"]

        return {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "event": {
                "kind": "alert",
                "category": ecs_category,
                "type": ["info"],
                "module": "cazo-easm",
                "severity": SEVERITY_MAP.get(severity, "medium"),
            },
            "cazo": {
                "event_type": f"finding.{severity}",
                "category": category,
                "subcategory": finding.get("subcategory", ""),
                "description": finding.get("description", finding.get("detail", ""))[:500],
                "risk_contribution": finding.get("risk_contribution", 0),
                "url": finding.get("url", ""),
                "header": finding.get("header", ""),
                "status_code": finding.get("status_code"),
            },
            "vulnerability": {
                "severity": severity,
                "description": finding.get("description", finding.get("detail", ""))[:500],
            },
            "host": {"name": domain},
            "url": {"full": finding.get("url", "")},
            "message": finding.get("description", finding.get("detail", "Finding detected")),
        }

    async def _index_doc(self, index: str, doc: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    f"{self._url}/{index}/_doc",
                    json=doc,
                    headers=self._headers,
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.error("Elastic index failed: %s", e)
            return False

    async def _bulk(self, body: str, expected: int) -> int:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout * 2,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    f"{self._url}/_bulk",
                    content=body,
                    headers={**self._headers, "Content-Type": "application/x-ndjson"},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    errors = result.get("errors", False)
                    if not errors:
                        return expected
                    items = result.get("items", [])
                    return sum(1 for item in items if item.get("index", {}).get("status", 500) < 300)
                return 0
        except Exception as e:
            logger.error("Elastic bulk failed: %s", e)
            return 0
