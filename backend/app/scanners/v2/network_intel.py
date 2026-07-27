"""Enhanced network intelligence scanner — delegates to the fast port scanner.

This scanner acts as the v2 pipeline entry point for port scanning.
It delegates to FastPortScanner for the actual scanning work and
normalizes the results for the pipeline context.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)


@register_scanner(
    name="network-intelligence",
    category=ScannerCategory.NETWORK_INTELLIGENCE,
    version="3.0.0",
    priority=ScannerPriority.HIGH,
    description="Network intelligence with fast port scanning and service fingerprinting",
    capabilities=[
        "port_discovery", "service_fingerprinting", "banner_grabbing",
        "tls_detection", "version_detection", "full_port_scan",
    ],
)
class NetworkIntelligenceScanner(EnhancedBaseScanner):
    """Delegates to FastPortScanner and normalizes output for the pipeline."""

    name = "network-intelligence"
    version = "3.0.0"
    category = ScannerCategory.NETWORK_INTELLIGENCE
    priority = ScannerPriority.HIGH

    def __init__(self, config=None):
        # Port scanning needs more than the default 10s base scanner timeout
        cfg = dict(config or {})
        cfg["timeout"] = max(float(cfg.get("timeout", 10)), 120)
        super().__init__(cfg)
        self._fast_scanner = None

    def _get_fast_scanner(self):
        if self._fast_scanner is None:
            from app.scanners.v2.fast_port_scanner import FastPortScanner
            self._fast_scanner = FastPortScanner(self.config)
        return self._fast_scanner

    async def scan(self, target: str, **kwargs) -> ScanResult:
        context = kwargs.get("context")
        scan_type = kwargs.get("scan_type", "full")
        explicit_ports = kwargs.get("port_list")

        fast = self._get_fast_scanner()
        result = await fast.scan(
            target,
            context=context,
            scan_type=scan_type,
            port_list=explicit_ports,
        )

        # Normalize for pipeline context: map hostname -> port list
        if result.success and result.data:
            hosts = result.data.get("hosts", {})
            normalized = {}
            for hostname, port_list in hosts.items():
                if isinstance(port_list, list):
                    normalized[hostname] = port_list
            result.data["hosts"] = normalized

        return result

    def validate_target(self, target: str) -> bool:
        import re
        ip_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        host_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$"
        return bool(re.match(ip_pattern, target) or re.match(host_pattern, target))
