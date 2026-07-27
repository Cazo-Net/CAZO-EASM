"""Scan pipeline framework with staged execution, progress tracking, and cancellation.

The pipeline orchestrates scanners in dependency-ordered stages:
  Stage 1: Asset Discovery (subdomains, WHOIS, zone transfer)
  Stage 2: DNS Intelligence (records, reverse DNS, validation)
  Stage 3: Network Intelligence (ports, services, banners)
  Stage 4: Technology Fingerprinting (headers, patterns, CMS)
  Stage 5: Certificate Analysis (TLS, chain, transparency)
  Stage 6: Vulnerability Assessment (findings, CVE correlation)
  Stage 7: Risk Evaluation (scoring, prioritization)
  Stage 8: Graph Mapping (relationships, ownership)

Each stage runs its scanners concurrently within the stage, and stages
execute sequentially so downstream scanners can consume upstream results.
"""
from __future__ import annotations

import asyncio
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from app.scanners.v2.base import ScanResult
from app.scanners.v2.registry import (
    ScannerCategory, ScannerPlugin, registry,
)

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    ASSET_DISCOVERY = "asset_discovery"
    DNS_INTELLIGENCE = "dns_intelligence"
    NETWORK_INTELLIGENCE = "network_intelligence"
    TECHNOLOGY_FINGERPRINT = "technology_fingerprint"
    CERTIFICATE_ANALYSIS = "certificate_analysis"
    VULNERABILITY_ASSESSMENT = "vulnerability_assessment"
    RISK_EVALUATION = "risk_evaluation"
    GRAPH_MAPPING = "graph_mapping"


STAGE_CATEGORIES: Dict[PipelineStage, List[ScannerCategory]] = {
    PipelineStage.ASSET_DISCOVERY: [
        ScannerCategory.ASSET_DISCOVERY, ScannerCategory.SUBDOMAIN, ScannerCategory.WHOIS,
    ],
    PipelineStage.DNS_INTELLIGENCE: [
        ScannerCategory.DNS_INTELLIGENCE, ScannerCategory.DNS,
    ],
    PipelineStage.NETWORK_INTELLIGENCE: [
        ScannerCategory.NETWORK_INTELLIGENCE, ScannerCategory.PORT,
    ],
    PipelineStage.TECHNOLOGY_FINGERPRINT: [
        ScannerCategory.TECHNOLOGY_FINGERPRINT, ScannerCategory.TECHNOLOGY,
    ],
    PipelineStage.CERTIFICATE_ANALYSIS: [
        ScannerCategory.CERTIFICATE_ANALYSIS, ScannerCategory.SSL,
    ],
    PipelineStage.VULNERABILITY_ASSESSMENT: [
        ScannerCategory.VULNERABILITY_ASSESSMENT, ScannerCategory.VULNERABILITY,
    ],
    PipelineStage.RISK_EVALUATION: [
        ScannerCategory.RISK_EVALUATION,
    ],
    PipelineStage.GRAPH_MAPPING: [
        ScannerCategory.GRAPH_MAPPING,
    ],
}

# Default stage execution order
DEFAULT_STAGE_ORDER = [
    PipelineStage.ASSET_DISCOVERY,
    PipelineStage.DNS_INTELLIGENCE,
    PipelineStage.NETWORK_INTELLIGENCE,
    PipelineStage.TECHNOLOGY_FINGERPRINT,
    PipelineStage.CERTIFICATE_ANALYSIS,
    PipelineStage.VULNERABILITY_ASSESSMENT,
    PipelineStage.RISK_EVALUATION,
    PipelineStage.GRAPH_MAPPING,
]


@dataclass
class StageResult:
    """Results from a single pipeline stage."""
    stage: PipelineStage
    scanner_results: Dict[str, ScanResult] = field(default_factory=dict)
    duration_ms: float = 0.0
    total_scanners: int = 0
    successful: int = 0
    failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "success": self.successful > 0 or self.total_scanners == 0,
            "duration_ms": round(self.duration_ms, 2),
            "total_scanners": self.total_scanners,
            "successful": self.successful,
            "failed": self.failed,
            "results": {k: v.to_dict() for k, v in self.scanner_results.items()},
        }


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    target: str
    stages: Dict[str, StageResult] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    total_scanners: int = 0
    total_successful: int = 0
    total_failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "total_scanners": self.total_scanners,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
        }

    def get_stage_data(self, stage: PipelineStage) -> Dict[str, Any]:
        """Aggregate data from all scanners in a stage."""
        result = self.stages.get(stage.value)
        if not result:
            return {}
        combined: Dict[str, Any] = {}
        for scanner_name, sr in result.scanner_results.items():
            if sr.success and sr.data:
                combined[scanner_name] = sr.data
        return combined

    def get_all_data(self) -> Dict[str, Any]:
        """Flatten all stage data into a single dict keyed by scanner name."""
        combined: Dict[str, Any] = {}
        for stage_result in self.stages.values():
            for scanner_name, sr in stage_result.scanner_results.items():
                if sr.success and sr.data:
                    combined[scanner_name] = sr.data
        return combined


@dataclass
class PipelineContext:
    """Shared context passed between stages for data flow."""
    target: str
    config: Dict[str, Any] = field(default_factory=dict)
    # Accumulated data from previous stages
    discovered_assets: List[Dict[str, Any]] = field(default_factory=list)
    dns_results: Dict[str, Any] = field(default_factory=dict)
    network_results: Dict[str, Any] = field(default_factory=dict)
    tech_results: Dict[str, Any] = field(default_factory=dict)
    cert_results: Dict[str, Any] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    # Cross-stage metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_discovered_assets(self, assets: List[Dict[str, Any]]) -> None:
        existing = {(a.get("hostname"), a.get("ip")) for a in self.discovered_assets}
        for asset in assets:
            key = (asset.get("hostname"), asset.get("ip"))
            if key not in existing:
                self.discovered_assets.append(asset)
                existing.add(key)


# Type alias for progress callbacks
ProgressCallback = Callable[[str, str, float, Dict[str, Any]], None]


class ScanPipeline:
    """Orchestrates scanner execution through staged pipeline.

    Usage:
        pipeline = ScanPipeline()
        result = await pipeline.execute("example.com", config={...}, progress_callback=...)
    """

    def __init__(
        self,
        stages: Optional[List[PipelineStage]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.stages = stages or DEFAULT_STAGE_ORDER
        self.config = config or {}
        self._cancelled = False
        self._stage_concurrency = self.config.get("stage_concurrency", 1)
        self._scanner_concurrency = self.config.get("scanner_concurrency", 10)

    async def execute(
        self,
        target: str,
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        included_scanners: Optional[Set[str]] = None,
        excluded_scanners: Optional[Set[str]] = None,
    ) -> PipelineResult:
        """Execute the full pipeline against ``target``."""
        cfg = {**self.config, **(config or {})}
        context = PipelineContext(target=target, config=cfg)
        result = PipelineResult(target=target)
        pipeline_start = time.monotonic()

        total_stages = len(self.stages)

        for stage_idx, stage in enumerate(self.stages):
            if self._cancelled:
                logger.info("Pipeline cancelled at stage %s", stage.value)
                break

            # Notify progress
            if progress_callback:
                stage_progress = stage_idx / total_stages
                progress_callback(
                    stage.value,
                    f"Starting stage: {stage.value}",
                    stage_progress,
                    {"stage": stage_idx + 1, "total_stages": total_stages},
                )

            stage_result = await self._execute_stage(
                stage, target, context, cfg, included_scanners, excluded_scanners
            )
            result.stages[stage.value] = stage_result
            result.total_scanners += stage_result.total_scanners
            result.total_successful += stage_result.successful
            result.total_failed += stage_result.failed

            # Post-stage hook: update context with stage results
            self._update_context(stage, stage_result, context)

        result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000

        if progress_callback:
            progress_callback(
                "complete",
                "Pipeline complete",
                1.0,
                result.to_dict(),
            )

        return result

    async def _execute_stage(
        self,
        stage: PipelineStage,
        target: str,
        context: PipelineContext,
        config: Dict[str, Any],
        included: Optional[Set[str]],
        excluded: Optional[Set[str]],
    ) -> StageResult:
        """Execute all scanners in a stage concurrently."""
        stage_result = StageResult(stage=stage)
        categories = STAGE_CATEGORIES.get(stage, [])

        # Collect plugins for this stage
        plugins: List[ScannerPlugin] = []
        for cat in categories:
            plugins.extend(registry.by_category(cat))

        # Filter by include/exclude
        if included:
            plugins = [p for p in plugins if p.name in included]
        if excluded:
            plugins = [p for p in plugins if p.name not in excluded]

        if not plugins:
            return stage_result

        stage_result.total_scanners = len(plugins)
        stage_start = time.monotonic()

        # Execute scanners with bounded concurrency
        semaphore = asyncio.Semaphore(self._scanner_concurrency)

        async def _run_plugin(plugin: ScannerPlugin) -> tuple[str, ScanResult]:
            async with semaphore:
                instance = plugin.instantiate(config)
                # Pass scan_type and port_list from config to scanners
                extra = {}
                if "scan_type" in config:
                    extra["scan_type"] = config["scan_type"]
                if "top_ports" in config:
                    extra["port_list"] = config["top_ports"]
                return plugin.name, await instance.run(target, context=context, **extra)

        tasks = [_run_plugin(p) for p in plugins]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, Exception):
                stage_result.failed += 1
                logger.error("Scanner task raised: %s", outcome)
                continue
            name, scan_result = outcome
            stage_result.scanner_results[name] = scan_result
            if scan_result.success:
                stage_result.successful += 1
            else:
                stage_result.failed += 1

        stage_result.duration_ms = (time.monotonic() - stage_start) * 1000
        return stage_result

    def _update_context(
        self,
        stage: PipelineStage,
        stage_result: StageResult,
        context: PipelineContext,
    ) -> None:
        """Extract data from stage results and populate context for downstream stages."""
        for scanner_name, sr in stage_result.scanner_results.items():
            if not sr.success:
                continue

            if stage == PipelineStage.ASSET_DISCOVERY:
                if "subdomains" in sr.data:
                    subs = sr.data["subdomains"]
                    if isinstance(subs, list):
                        context.add_discovered_assets([
                            {"hostname": s, "source": scanner_name} for s in subs
                        ])

            elif stage == PipelineStage.DNS_INTELLIGENCE:
                context.dns_results[scanner_name] = sr.data

            elif stage == PipelineStage.NETWORK_INTELLIGENCE:
                context.network_results[scanner_name] = sr.data

            elif stage == PipelineStage.TECHNOLOGY_FINGERPRINT:
                context.tech_results[scanner_name] = sr.data

            elif stage == PipelineStage.CERTIFICATE_ANALYSIS:
                context.cert_results[scanner_name] = sr.data

            elif stage == PipelineStage.VULNERABILITY_ASSESSMENT:
                if "findings" in sr.data:
                    context.findings.extend(sr.data["findings"])

    def cancel(self) -> None:
        """Signal pipeline to stop after current stage."""
        self._cancelled = True

    def list_stages(self) -> List[Dict[str, Any]]:
        """Return metadata about each stage and its available scanners."""
        result = []
        for stage in self.stages:
            categories = STAGE_CATEGORIES.get(stage, [])
            plugins = []
            for cat in categories:
                plugins.extend(registry.by_category(cat))
            result.append({
                "stage": stage.value,
                "categories": [c.value for c in categories],
                "scanners": [p.to_dict() for p in plugins],
            })
        return result
