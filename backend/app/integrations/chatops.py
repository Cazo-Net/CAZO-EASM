"""Slack / Microsoft Teams notifications integration.

Posts alerts to Slack channels via incoming webhooks or Slack API.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "⚪",
}

SEVERITY_COLOR = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#ffc107",
    "low": "#28a745",
    "info": "#6c757d",
}


class SlackIntegration:
    """Slack incoming webhook / chat.postMessage client."""

    def __init__(
        self,
        webhook_url: str,
        *,
        bot_token: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: float = 10.0,
    ):
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._verify = verify_ssl
        self._timeout = timeout

    async def send_finding(
        self,
        finding: Dict[str, Any],
        domain: str = "",
        channel: Optional[str] = None,
    ) -> bool:
        """Send a finding alert to Slack."""
        severity = finding.get("severity", "info")
        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        color = SEVERITY_COLOR.get(severity, "#6c757d")
        description = finding.get("description", finding.get("detail", "Unknown finding"))
        category = finding.get("category", "unknown")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} CAZO Finding: {severity.upper()}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                    {"type": "mrkdwn", "text": f"*Category:*\n{category}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Risk Contribution:*\n{finding.get('risk_contribution', 'N/A')}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n{description[:300]}"},
            },
        ]

        if finding.get("url"):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*URL:* <{finding['url']}|{finding['url'][:60]}>"},
            })

        blocks.append({"type": "divider"})

        payload = {"blocks": blocks}
        if channel:
            payload["channel"] = channel

        return await self._send_webhook(payload)

    async def send_scan_summary(
        self,
        scan_data: Dict[str, Any],
        channel: Optional[str] = None,
    ) -> bool:
        """Send scan completion summary."""
        domain = scan_data.get("domain", "unknown")
        risk_score = scan_data.get("risk_score", 0)
        subdomains = scan_data.get("subdomains_found", 0)
        ports = scan_data.get("ports_found", 0)
        vulns = scan_data.get("vulnerabilities_found", 0)

        risk_emoji = "🔴" if risk_score >= 76 else ("🟠" if risk_score >= 51 else ("🟡" if risk_score >= 26 else "🟢"))

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📊 CAZO Scan Complete: {domain}"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_emoji} {risk_score}/100"},
                        {"type": "mrkdwn", "text": f"*Subdomains:*\n{subdomains}"},
                        {"type": "mrkdwn", "text": f"*Open Ports:*\n{ports}"},
                        {"type": "mrkdwn", "text": f"*Vulnerabilities:*\n{vulns}"},
                    ],
                },
                {"type": "divider"},
            ]
        }

        if channel:
            payload["channel"] = channel

        return await self._send_webhook(payload)

    async def send_risk_change(
        self,
        domain: str,
        old_score: int,
        new_score: int,
        channel: Optional[str] = None,
    ) -> bool:
        """Send risk score change alert."""
        direction = "increased" if new_score > old_score else "decreased"
        emoji = "📈" if new_score > old_score else "📉"

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *Risk Score Changed:* {domain}\n{old_score} → {new_score} ({direction})",
                    },
                },
            ]
        }

        if channel:
            payload["channel"] = channel

        return await self._send_webhook(payload)

    async def _send_webhook(self, payload: Dict[str, Any]) -> bool:
        """Send payload to Slack webhook."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._verify,
            ) as client:
                resp = await client.post(
                    self._webhook_url,
                    json=payload,
                )
                if resp.status_code == 200:
                    return True
                else:
                    logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text[:100])
                    return False
        except Exception as e:
            logger.error("Slack webhook failed: %s", e)
            return False


class TeamsIntegration:
    """Microsoft Teams incoming webhook client."""

    def __init__(self, webhook_url: str, *, verify_ssl: bool = True, timeout: float = 10.0):
        self._webhook_url = webhook_url
        self._verify = verify_ssl
        self._timeout = timeout

    async def send_finding(self, finding: Dict[str, Any], domain: str = "") -> bool:
        """Send a finding alert to Teams."""
        severity = finding.get("severity", "info")
        description = finding.get("description", finding.get("detail", "Unknown finding"))
        category = finding.get("category", "unknown")
        color = SEVERITY_COLOR.get(severity, "#6c757d")

        payload = {
            "@type": "MessageCard",
            "themeColor": color.replace("#", ""),
            "summary": f"CAZO Finding: {severity.upper()}",
            "sections": [
                {
                    "activityTitle": f"CAZO Finding: {severity.upper()}",
                    "facts": [
                        {"name": "Domain", "value": domain},
                        {"name": "Category", "value": category},
                        {"name": "Severity", "value": severity.upper()},
                        {"name": "Description", "value": description[:200]},
                    ],
                }
            ],
        }

        if finding.get("url"):
            payload["sections"][0]["facts"].append(
                {"name": "URL", "value": finding["url"]}
            )

        return await self._send(payload)

    async def send_scan_summary(self, scan_data: Dict[str, Any]) -> bool:
        """Send scan summary to Teams."""
        domain = scan_data.get("domain", "unknown")
        risk_score = scan_data.get("risk_score", 0)

        payload = {
            "@type": "MessageCard",
            "summary": f"CAZO Scan: {domain}",
            "sections": [
                {
                    "activityTitle": f"Scan Complete: {domain}",
                    "facts": [
                        {"name": "Risk Score", "value": f"{risk_score}/100"},
                        {"name": "Subdomains", "value": str(scan_data.get("subdomains_found", 0))},
                        {"name": "Ports", "value": str(scan_data.get("ports_found", 0))},
                        {"name": "Vulnerabilities", "value": str(scan_data.get("vulnerabilities_found", 0))},
                    ],
                }
            ],
        }

        return await self._send(payload)

    async def _send(self, payload: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=self._verify) as client:
                resp = await client.post(self._webhook_url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error("Teams webhook failed: %s", e)
            return False
