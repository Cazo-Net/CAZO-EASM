"""V2 Nmap Intelligence Scanner — high-fidelity port/service/OS detection via nmap binary."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import xml.etree.ElementTree as ET
import logging
from typing import Any, Dict, List, Optional

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory
from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_nmap() -> Optional[str]:
    candidate = getattr(settings, "NMAP_PATH", "nmap") or "nmap"
    if candidate and candidate != "nmap" and os.path.isfile(candidate):
        return candidate
    found = shutil.which("nmap")
    return found


@register_scanner(
    name="nmap-intelligence",
    category=ScannerCategory.NETWORK_INTELLIGENCE,
    version="2.0.0",
    priority=ScannerPriority.HIGH,
    description="nmap-backed port + service/version + OS detection",
    capabilities=["port_scan", "service_detection", "os_detection", "nse_scripts"],
)
class NmapIntelligenceScanner(EnhancedBaseScanner):
    name = "nmap-intelligence"
    version = "2.0.0"
    category = ScannerCategory.NETWORK_INTELLIGENCE
    priority = ScannerPriority.HIGH

    _binary: Optional[str] = None
    _sem: Optional[asyncio.Semaphore] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.timeout = float((self.config or {}).get("timeout", getattr(settings, "NMAP_TIMEOUT", 30)))
        self.max_concurrency = int((self.config or {}).get("max_concurrency", getattr(settings, "NMAP_MAX_CONCURRENCY", 3)))
        self.os_detection = bool((self.config or {}).get("os_detection", getattr(settings, "NMAP_OS_DETECTION", False)))
        self.top_ports = int((self.config or {}).get("top_ports", getattr(settings, "NMAP_TOP_PORTS", 100)))
        if NmapIntelligenceScanner._binary is None:
            NmapIntelligenceScanner._binary = _resolve_nmap()
        self.binary = NmapIntelligenceScanner._binary

    def available(self) -> bool:
        return bool(self.binary) and os.path.isfile(self.binary or "")

    def validate_target(self, target: str) -> bool:
        ip = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$")
        host = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
        return bool(ip.match(target) or host.match(target))

    async def scan(self, target: str, **kwargs) -> ScanResult:
        if not self.available():
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=["nmap binary not available"])
        if not self.validate_target(target):
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Invalid target: {target}"])

        scan_type = kwargs.get("scan_type", "full")
        port_list = kwargs.get("port_list")
        os_detection = kwargs.get("os_detection", self.os_detection)

        if NmapIntelligenceScanner._sem is None:
            NmapIntelligenceScanner._sem = asyncio.Semaphore(self.max_concurrency)

        port_arg = self._port_arg(port_list, scan_type)
        opts = [
            "-oX", "-", "-Pn", "-sV", "-T4", "--open",
            "--host-timeout", "30s", "--max-rtt-timeout", "1000ms",
            "--max-retries", "2", "-p", port_arg,
        ]
        if os_detection:
            opts.append("-O")

        cmd = [self.binary, *opts, target]

        async with NmapIntelligenceScanner._sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            except FileNotFoundError:
                return ScanResult(success=False, scanner=self.name, target=target,
                                  errors=[f"nmap binary not found: {self.binary}"])
            except asyncio.TimeoutError:
                return ScanResult(success=False, scanner=self.name, target=target,
                                  errors=["nmap scan timed out"])

        xml_data = stdout.decode("utf-8", errors="replace")
        if not xml_data.strip():
            err = stderr.decode("utf-8", errors="replace").strip()
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"nmap no output (rc={proc.returncode}): {err[:500]}"])

        return self._parse(target, xml_data)

    def _port_arg(self, port_list, scan_type):
        if port_list:
            ports = sorted(set(int(p) for p in port_list))
            if len(ports) > 2000:
                return f"1-{max(ports)}"
            return ",".join(str(p) for p in ports)
        if scan_type == "full":
            return "1-10000"
        return f"--top-ports {self.top_ports}"

    def _parse(self, target: str, xml_data: str) -> ScanResult:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            return ScanResult(success=False, scanner=self.name, target=target,
                              errors=[f"Failed to parse nmap XML: {e}"])

        open_ports = []
        os_info = None
        scripts: Dict[str, str] = {}

        for host in root.iter("host"):
            osmatch = host.find("os/osmatch")
            if osmatch is not None:
                osclass = osmatch.find("osclass")
                cpe = None
                if osclass is not None:
                    cpe_el = osclass.find("cpe")
                    cpe = cpe_el.text if cpe_el is not None else None
                os_info = {
                    "name": osmatch.get("name"),
                    "accuracy": osmatch.get("accuracy"),
                    "family": osclass.get("osfamily") if osclass is not None else None,
                    "cpe": cpe,
                }

            hostscript = host.find("hostscript")
            if hostscript is not None:
                for script in hostscript.iter("script"):
                    sid = script.get("id")
                    output = script.get("output")
                    if sid and output:
                        scripts[sid] = output.replace("\n", " | ")

            ports_el = host.find("ports")
            if ports_el is None:
                continue
            for port_el in ports_el.iter("port"):
                state_el = port_el.find("state")
                if state_el is None or state_el.get("state") != "open":
                    continue
                port_id = int(port_el.get("portid", "0"))
                protocol = port_el.get("protocol", "tcp")
                service_el = port_el.find("service")
                service = product = version = extrainfo = ""
                cpe = None
                if service_el is not None:
                    service = service_el.get("name", "") or ""
                    product = service_el.get("product", "") or ""
                    version = service_el.get("version", "") or ""
                    extrainfo = service_el.get("extrainfo", "") or ""
                    cpe_el = service_el.find("cpe")
                    if cpe_el is not None:
                        cpe = cpe_el.text
                full_version = " ".join(p for p in [product, version, extrainfo] if p).strip()
                open_ports.append({
                    "port": port_id, "protocol": protocol, "state": "open",
                    "service": service or "unknown", "version": full_version[:200],
                    "product": product, "banner": (cpe or "")[:500],
                })

        open_ports.sort(key=lambda x: x["port"])
        return ScanResult(
            success=True, scanner=self.name, target=target,
            data={
                "ports": open_ports,
                "open_ports": len(open_ports),
                "os": os_info,
                "scripts": scripts,
            },
        )
