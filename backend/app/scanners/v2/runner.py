"""Enhanced scan runner — enterprise-grade orchestration engine.

Ties together:
- Plugin registry for dynamic scanner discovery
- Pipeline framework for staged execution
- Shared context for inter-stage data flow
- Progress tracking and cancellation
- Metrics collection
"""
from __future__ import annotations

import asyncio
import time
import logging
from typing import Any, Callable, Dict, Optional, Set

from app.scanners.v2.pipeline import ScanPipeline, PipelineStage, PipelineResult
from app.scanners.v2.risk_engine import risk_engine
from app.scanners.v2.graph_intel import build_graph_from_scan

logger = logging.getLogger(__name__)

# Default pipeline-level timeout (seconds). Prevents a single hung scanner
# from blocking the entire pipeline indefinitely.
_PIPELINE_TIMEOUT = 300  # 5 minutes


class EnhancedScanRunner:
    """Enterprise-grade scan orchestrator using the v2 scanner framework.

    Usage:
        runner = EnhancedScanRunner()
        result = await runner.run_scan("example.com", config={...})
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._pipeline = ScanPipeline(config=self.config)

    async def run_scan(
        self,
        domain: str,
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        included_scanners: Optional[Set[str]] = None,
        excluded_scanners: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Execute a full scan pipeline and return comprehensive results."""
        cfg = {**self.config, **(config or {})}
        cfg.setdefault("scan_type", "full")
        start_time = time.monotonic()
        pipeline_timeout = cfg.get("pipeline_timeout", _PIPELINE_TIMEOUT)

        # Execute pipeline with global timeout
        try:
            pipeline_result = await asyncio.wait_for(
                self._pipeline.execute(
                    target=domain,
                    config=cfg,
                    progress_callback=progress_callback,
                    included_scanners=included_scanners,
                    excluded_scanners=excluded_scanners,
                ),
                timeout=pipeline_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Pipeline timed out after %ds for %s", pipeline_timeout, domain,
            )
            raise TimeoutError(
                f"Scan pipeline timed out after {pipeline_timeout}s for {domain}"
            )

        # Transform pipeline results into expected format
        all_data = self._transform_pipeline_results(pipeline_result, domain)

        # Calculate risk score
        risk_result = risk_engine.calculate(all_data)

        # Build attack surface graph
        graph = build_graph_from_scan(all_data, domain)
        graph_data = graph.get_attack_surface_map()

        # Build final result
        total_duration = (time.monotonic() - start_time) * 1000

        result = {
            "domain": domain,
            "scan_type": "full",
            "profile": cfg.get("profile"),
            "duration_ms": round(total_duration, 2),
            "pipeline": pipeline_result.to_dict(),
            "risk_score": risk_result,
            "graph": graph_data,
            "assets": all_data,
            "summary": self._build_summary(pipeline_result, risk_result, all_data),
        }

        return result

    async def run_quick_scan(
        self,
        domain: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a lightweight quick scan."""
        from app.scanners.v2.profiles import resolve_profile

        quick_config = {
            **resolve_profile("quick").to_config(),
            "timeout": 10,
            "max_retries": 1,
            "scan_type": "quick",
            "scanner_concurrency": 5,
            **(config or {}),
        }
        quick_config.setdefault("pipeline_timeout", quick_config.get("pipeline_timeout_s", 300))

        # Only run essential stages
        essential_stages = [
            PipelineStage.ASSET_DISCOVERY,
            PipelineStage.DNS_INTELLIGENCE,
            PipelineStage.NETWORK_INTELLIGENCE,
        ]

        pipeline = ScanPipeline(stages=essential_stages, config=quick_config)
        pipeline_timeout = quick_config.get("pipeline_timeout", 300)  # 5 min for quick
        try:
            pipeline_result = await asyncio.wait_for(
                pipeline.execute(target=domain, config=quick_config),
                timeout=pipeline_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Quick pipeline timed out after %ds for %s", pipeline_timeout, domain)
            raise TimeoutError(f"Quick scan pipeline timed out after {pipeline_timeout}s")
        all_data = self._transform_pipeline_results(pipeline_result, domain)
        risk_result = risk_engine.calculate(all_data)

        return {
            "domain": domain,
            "scan_type": "quick",
            "pipeline": pipeline_result.to_dict(),
            "risk_score": risk_result,
            "assets": all_data,
            "summary": self._build_summary(pipeline_result, risk_result, all_data),
        }

    def _transform_pipeline_results(
        self,
        pipeline_result: PipelineResult,
        domain: str,
    ) -> Dict[str, Any]:
        """Transform pipeline scanner-by-scanner results into data-type-keyed format."""
        from app.scanners.v2.normalize import transform_pipeline_results

        return transform_pipeline_results(pipeline_result, domain)

    def _build_summary(
        self,
        pipeline_result: PipelineResult,
        risk_result: Dict[str, Any],
        all_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build human-readable scan summary."""
        subdomains = all_data.get("subdomains", [])
        if isinstance(subdomains, dict):
            sub_count = len(subdomains)
        elif isinstance(subdomains, list):
            sub_count = len(subdomains)
        else:
            sub_count = 0

        ports_data = all_data.get("ports", {})
        open_ports = 0
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if isinstance(port_list, list):
                    open_ports += len(port_list)

        tech_data = all_data.get("technologies", {})
        tech_count = 0
        if isinstance(tech_data, dict):
            for host, techs in tech_data.items():
                if isinstance(techs, list):
                    tech_count += len(techs)

        vulns = all_data.get("vulnerabilities", []) or []
        by_sev: Dict[str, int] = {}
        for v in vulns:
            sev = v.get("severity", "unknown") if isinstance(v, dict) else "unknown"
            by_sev[sev] = by_sev.get(sev, 0) + 1

        return {
            "total_subdomains": sub_count,
            "total_findings": len(vulns),
            "findings_by_severity": by_sev,
            "total_web_services": len(all_data.get("http_services", []) or []),
            "total_open_ports": open_ports,
            "total_technologies": tech_count,
            "risk_score": risk_result.get("risk_score", 0),
            "risk_label": risk_result.get("severity", "Unknown"),
            "total_scanners_run": pipeline_result.total_scanners,
            "successful_scanners": pipeline_result.total_successful,
            "failed_scanners": pipeline_result.total_failed,
            "pipeline_duration_ms": round(pipeline_result.total_duration_ms, 2),
        }


# Singleton
enhanced_runner = EnhancedScanRunner()
