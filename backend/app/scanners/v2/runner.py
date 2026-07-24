"""Enhanced scan runner — enterprise-grade orchestration engine.

Ties together:
- Plugin registry for dynamic scanner discovery
- Pipeline framework for staged execution
- Shared context for inter-stage data flow
- Progress tracking and cancellation
- Metrics collection
"""
from __future__ import annotations

import time
import logging
from typing import Any, Callable, Dict, Optional, Set

from app.scanners.v2.pipeline import ScanPipeline, PipelineStage, PipelineResult
from app.scanners.v2.risk_engine import risk_engine
from app.scanners.v2.graph_intel import build_graph_from_scan

logger = logging.getLogger(__name__)


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
        start_time = time.monotonic()

        # Execute pipeline
        pipeline_result = await self._pipeline.execute(
            target=domain,
            config=cfg,
            progress_callback=progress_callback,
            included_scanners=included_scanners,
            excluded_scanners=excluded_scanners,
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
        quick_config = {
            "timeout": 15,
            "max_retries": 1,
            "top_ports": [80, 443, 8080, 8443],
            "scanner_concurrency": 5,
            **(config or {}),
        }

        # Only run essential stages
        essential_stages = [
            PipelineStage.ASSET_DISCOVERY,
            PipelineStage.DNS_INTELLIGENCE,
            PipelineStage.NETWORK_INTELLIGENCE,
        ]

        pipeline = ScanPipeline(stages=essential_stages, config=quick_config)
        pipeline_result = await pipeline.execute(target=domain, config=quick_config)
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
        transformed: Dict[str, Any] = {
            "subdomains": [],
            "ports": {},
            "dns": {},
            "technologies": {},
            "certificates": {},
            "whois": None,
            "vulnerabilities": [],
        }

        for stage_name, stage_result in pipeline_result.stages.items():
            for scanner_name, sr in stage_result.scanner_results.items():
                if not sr.success or not sr.data:
                    continue
                data = sr.data

                # Asset discovery -> subdomains list
                if scanner_name in ("advanced-asset-discovery", "subdomain-intelligence"):
                    subs = data.get("subdomains", data.get("discovered_subdomains", []))
                    if isinstance(subs, list):
                        transformed["subdomains"].extend(subs)
                    elif isinstance(subs, dict):
                        transformed["subdomains"].extend(subs.keys())

                # Network intelligence -> ports
                elif scanner_name == "network-intelligence":
                    hosts = data.get("hosts", data.get("services", {}))
                    if isinstance(hosts, dict):
                        for host, port_list in hosts.items():
                            if isinstance(port_list, list):
                                transformed["ports"][host] = port_list
                    elif isinstance(hosts, list):
                        for item in hosts:
                            if isinstance(item, dict):
                                host = item.get("host", item.get("hostname", ""))
                                port_list = item.get("ports", item.get("open_ports", []))
                                if host and port_list:
                                    transformed["ports"][host] = port_list

                # Technology fingerprint -> technologies
                elif scanner_name == "technology-intelligence":
                    hosts = data.get("hosts", data.get("technologies", {}))
                    if isinstance(hosts, dict):
                        for host, techs in hosts.items():
                            if isinstance(techs, list):
                                transformed["technologies"][host] = techs
                    elif isinstance(hosts, list):
                        for item in hosts:
                            if isinstance(item, dict):
                                host = item.get("host", item.get("hostname", ""))
                                techs = item.get("technologies", [])
                                if host and techs:
                                    transformed["technologies"][host] = techs

                # Certificate intelligence -> certificates
                elif scanner_name == "certificate-intelligence":
                    certs = data.get("certificates", data.get("hosts", {}))
                    if isinstance(certs, dict):
                        for host, cert in certs.items():
                            transformed["certificates"][host] = cert

                # DNS intelligence -> dns records
                elif "dns" in scanner_name.lower():
                    hosts = data.get("hosts", data.get("dns", {}))
                    if isinstance(hosts, dict):
                        transformed["dns"].update(hosts)

        # Deduplicate subdomains
        transformed["subdomains"] = sorted(set(transformed["subdomains"]))

        return transformed

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

        return {
            "total_subdomains": sub_count,
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
