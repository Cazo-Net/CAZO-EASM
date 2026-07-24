"""Scanner v2 adapter — bridges v2 pipeline to v1 ScanRunner interface.

Provides backward-compatible `ScanRunner`-like API while using the v2
plugin registry, pipeline, risk engine, and graph engine under the hood.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from app.scanners.v2.runner import EnhancedScanRunner

logger = logging.getLogger(__name__)


class V2ScanRunner:
    """Backward-compatible adapter wrapping the v2 scanner pipeline.

    Exposes the same public API as the v1 `ScanRunner` so existing callers
    (scan_service, API routes, tests) continue to work unchanged.

    Usage (drop-in replacement for v1 ScanRunner):
        from app.scanners.v2_runner import V2ScanRunner
        runner = V2ScanRunner()
        result = await runner.run_full_scan("example.com", progress_callback=cb)
    """

    def __init__(self) -> None:
        self._enhanced = EnhancedScanRunner()

    async def run_full_scan(
        self,
        domain: str,
        progress_callback: Optional[Callable] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a full scan using the v2 pipeline."""
        options = options or {}

        # Map v1 options to v2 config
        config = {
            "timeout": options.get("timeout", 30),
            "max_retries": options.get("max_retries", 2),
            "scanner_concurrency": options.get("scanner_concurrency", 10),
            "top_ports": options.get("ports") or [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432],
            "max_subdomains": options.get("max_subdomains", 0),
        }

        # Build pipeline stage filter from v1 options
        included = None
        excluded = None

        port_mode = options.get("port_mode", "full")
        if port_mode == "quick":
            config["top_ports"] = [80, 443, 8080, 8443]

        # Wrap v1-style progress callback to v2 style
        async def _v2_progress(stage: str, message: str, progress: float, metadata: dict = None) -> None:
            if progress_callback:
                pct = int(progress * 100)
                await progress_callback(pct, f"[v2] {message}")

        result = await self._enhanced.run_scan(
            domain=domain,
            config=config,
            progress_callback=_v2_progress if progress_callback else None,
            included_scanners=included,
            excluded_scanners=excluded,
        )

        # Re-format output to match v1 ScanRunner structure
        return self._format_v1_output(result, domain)

    async def run_quick_scan(
        self,
        domain: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute a quick scan using a lightweight v2 pipeline."""
        async def _v2_progress(stage: str, message: str, progress: float, metadata: dict = None) -> None:
            if progress_callback:
                pct = int(progress * 100)
                await progress_callback(pct, f"[v2] {message}")

        result = await self._enhanced.run_quick_scan(domain=domain)
        return self._format_v1_output(result, domain)

    def _format_v1_output(self, result: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Re-format v2 result to match v1 ScanRunner output structure."""
        pipeline = result.get("pipeline", {})
        risk = result.get("risk_score", {})
        graph = result.get("graph", {})
        assets = result.get("assets", {})

        # Extract assets from v2 nested structure
        subdomains_data = assets.get("subdomains", {})
        if isinstance(subdomains_data, dict):
            subdomain_list = subdomains_data.get("discovered_subdomains", [])
            if not subdomain_list:
                subdomain_list = sorted(set(
                    k for k in subdomains_data.keys()
                    if k not in ("source_counts", "total", "discovery_sources", "discovery_time_ms")
                ))
        elif isinstance(subdomains_data, list):
            subdomain_list = subdomains_data
        else:
            subdomain_list = []

        ports_data = assets.get("ports", {})
        dns_data = assets.get("dns", {})
        tech_data = assets.get("technologies", {})
        certs_data = assets.get("certificates", {})
        whois_data = assets.get("whois", {})

        return {
            "success": True,
            "domain": domain,
            "scan_engine": "v2",
            "subdomains": subdomain_list,
            "dns_records": dns_data if isinstance(dns_data, dict) else {},
            "ssl_certificates": certs_data if isinstance(certs_data, dict) else {},
            "ports": ports_data if isinstance(ports_data, dict) else {},
            "technologies": tech_data if isinstance(tech_data, dict) else {},
            "vulnerabilities": assets.get("vulnerabilities", []),
            "whois": whois_data,
            "risk_score": risk,
            "graph": graph,
            "scanner_status": self._build_scanner_status(pipeline),
            "errors": pipeline.get("errors", []) if isinstance(pipeline, dict) else [],
            "pipeline_summary": pipeline.get("summary", {}) if isinstance(pipeline, dict) else {},
            "started_at": pipeline.get("started_at"),
            "completed_at": pipeline.get("completed_at"),
        }

    def _build_scanner_status(self, pipeline: Dict[str, Any]) -> Dict[str, str]:
        """Build scanner_status dict from pipeline results."""
        status = {}
        stages = pipeline.get("stages", {})
        for stage_name, stage_data in stages.items():
            if isinstance(stage_data, dict):
                if stage_data.get("success"):
                    status[stage_name] = "ok"
                else:
                    status[stage_name] = f"failed: {stage_data.get('error', 'unknown')}"
            else:
                status[stage_name] = "unknown"
        return status
