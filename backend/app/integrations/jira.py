"""Jira integration — creates tickets for critical/high findings.

Uses Jira REST API v2 (cloud or server).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Severity → Jira priority
PRIORITY_MAP = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Lowest",
}


class JiraIntegration:
    """Jira REST API client for creating finding tickets."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        *,
        project_key: str = "SECURITY",
        verify_ssl: bool = True,
        timeout: float = 15.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._token = api_token
        self._project = project_key
        self._verify = verify_ssl
        self._timeout = timeout
        self._auth = (email, api_token)

    async def create_finding_ticket(
        self,
        finding: Dict[str, Any],
        domain: str = "",
    ) -> Optional[str]:
        """Create a Jira ticket for a finding.

        Returns the ticket key (e.g., "SECURITY-123") or None on failure.
        """
        severity = finding.get("severity", "medium")
        category = finding.get("category", "unknown")
        description = finding.get("description", finding.get("detail", "Unknown finding"))

        # Build ticket
        ticket = {
            "fields": {
                "project": {"key": self._project},
                "summary": f"[CAZO] {severity.upper()}: {description[:80]}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": f"Domain: {domain}\n"},
                                {"type": "text", "text": f"Category: {category}\n"},
                                {"type": "text", "text": f"Severity: {severity}\n"},
                                {"type": "text", "text": f"Description: {description}\n"},
                            ],
                        }
                    ],
                },
                "issuetype": {"name": "Security Issue"},
                "priority": {"name": PRIORITY_MAP.get(severity, "Medium")},
                "labels": ["cazo-easm", f"severity:{severity}", f"category:{category}"],
            }
        }

        # Add URL field if present
        if finding.get("url"):
            ticket["fields"]["description"]["content"][0]["content"].append(
                {"type": "text", "text": f"\nURL: {finding['url']}"}
            )

        return await self._create_issue(ticket)

    async def create_scan_summary_ticket(
        self,
        scan_data: Dict[str, Any],
        critical_findings: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Create a summary ticket for a completed scan with critical findings."""
        domain = scan_data.get("domain", "unknown")
        vuln_count = scan_data.get("vulnerabilities_found", 0)
        risk_score = scan_data.get("risk_score", 0)

        # Build finding list
        finding_list = "\n".join(
            f"- [{f.get('severity', '?').upper()}] {f.get('description', f.get('detail', ''))[:100]}"
            for f in critical_findings[:20]
        )

        ticket = {
            "fields": {
                "project": {"key": self._project},
                "summary": f"[CAZO] Scan Summary: {domain} — {vuln_count} findings, risk={risk_score}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": f"Domain: {domain}\n"},
                                {"type": "text", "text": f"Risk Score: {risk_score}/100\n"},
                                {"type": "text", "text": f"Vulnerabilities: {vuln_count}\n"},
                                {"type": "text", "text": f"\nCritical/High Findings:\n{finding_list}"},
                            ],
                        }
                    ],
                },
                "issuetype": {"name": "Security Issue"},
                "priority": {"name": "Highest" if risk_score >= 76 else "High"},
                "labels": ["cazo-easm", "scan-summary", f"risk:{risk_score}"],
            }
        }

        return await self._create_issue(ticket)

    async def _create_issue(self, ticket: Dict[str, Any]) -> Optional[str]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    f"{self._base_url}/rest/api/2/issue",
                    json=ticket,
                    auth=self._auth,
                )

                if resp.status_code == 201:
                    data = resp.json()
                    key = data.get("key", "")
                    logger.info("Created Jira ticket: %s", key)
                    return key
                else:
                    logger.warning(
                        "Jira create failed (%d): %s",
                        resp.status_code, resp.text[:200],
                    )
                    return None

        except Exception as e:
            logger.error("Jira create failed: %s", e)
            return None
