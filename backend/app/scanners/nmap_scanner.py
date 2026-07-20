"""nmap-backed high-fidelity port scanner.

This scanner shells out to the real nmap binary (bundled under tools/ or
resolved from PATH) to produce results that match what a security analyst
sees when they run nmap by hand:

    - full TCP connect/service discovery with -sV fingerprinting
    - real service names, products and versions (e.g.
      ``Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)``)
    - optional -O OS detection (host-level)
    - optional NSE host scripts (e.g. smb-security-mode)

It is used for "full" scans. The pure-Python :class:`PortScanner` remains the
fallback (and the scanner for "quick" scans) so the platform still works on
hosts/environments where spawning an external binary is undesirable.

Results are emitted in the SAME shape as PortScanner so storage, the API and
the UI are unchanged::

    {"port", "protocol", "state", "service", "version", "product", "banner"}
"""
import asyncio
import os
import shutil
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _resolve_nmap() -> Optional[str]:
    """Locate the nmap binary.

    Order: explicit config/env path -> project-bundled copies -> PATH.
    """
    candidate = getattr(settings, "NMAP_PATH", "nmap") or "nmap"
    if candidate and candidate != "nmap" and os.path.isfile(candidate):
        return candidate

    here = os.path.dirname(os.path.abspath(__file__))
    # Walk upward looking for a ``tools`` directory that ships nmap. This is
    # robust to repo layouts where ``tools/`` is either beside the backend
    # package or beside the monorepo root.
    search_roots = [here]
    cur = here
    for _ in range(6):
        cur = os.path.dirname(cur)
        search_roots.append(cur)

    bundled: List[str] = []
    for root in search_roots:
        bundled.extend([
            os.path.join(root, "tools", "bin", "nmap.exe"),
            os.path.join(root, "tools", "bin", "nmap"),
            os.path.join(root, "tools", "nmap_raw", "nmap-7.92", "nmap.exe"),
            os.path.join(root, "tools", "nmap_raw", "nmap-7.92", "nmap"),
        ])
    for b in bundled:
        if os.path.isfile(b):
            return b

    found = shutil.which("nmap")
    if found:
        return found
    return None


@register_scanner(
    name="ports-nmap",
    category=ScannerCategory.PORT,
    description="nmap-backed port + service/version + OS detection for full scans.",
)
class NmapPortScanner(BaseScanner):
    """Runs the real nmap binary for high-fidelity port scanning."""

    _binary: Optional[str] = None
    _sem: Optional[asyncio.Semaphore] = None

    def __init__(self, config: dict = None):
        super().__init__(config)
        # nmap full scans need far more headroom than the 30s base timeout.
        self.timeout = float(self.config.get("timeout", settings.NMAP_TIMEOUT))
        self.max_concurrency = int(self.config.get("max_concurrency", settings.NMAP_MAX_CONCURRENCY))
        self.os_detection = bool(self.config.get("os_detection", settings.NMAP_OS_DETECTION))
        self.top_ports = int(self.config.get("top_ports", settings.NMAP_TOP_PORTS))

        binary = _resolve_nmap()
        if binary:
            NmapPortScanner._binary = binary
        self.binary = NmapPortScanner._binary

    def available(self) -> bool:
        return bool(self.binary) and os.path.isfile(self.binary or "")

    def validate_target(self, target: str) -> bool:
        import re
        ip = re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        )
        host = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
        return bool(ip.match(target) or host.match(target))

    @staticmethod
    def _port_arg(port_list: Optional[List[int]], scan_type: str, top_ports: int) -> str:
        if port_list:
            ports = sorted(set(int(p) for p in port_list))
            # nmap accepts comma-separated lists; chunk very large lists to keep
            # the command line reasonable.
            if len(ports) > 2000:
                return f"1-{max(ports)}"
            return ",".join(str(p) for p in ports)
        if scan_type == "full":
            return f"1-10000"
        return f"--top-ports {top_ports}"

    async def scan(
        self,
        target: str,
        ports: Optional[str] = None,
        scan_type: str = "full",
        port_list: Optional[List[int]] = None,
        os_detection: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        if not self.available():
            raise RuntimeError("nmap binary not available")
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid target: {target}"))

        if NmapPortScanner._sem is None:
            NmapPortScanner._sem = asyncio.Semaphore(self.max_concurrency)

        if port_list is not None:
            port_arg = self._port_arg(port_list, scan_type, self.top_ports)
        elif ports:
            port_arg = ports
        elif scan_type == "full":
            port_arg = "1-10000"
        else:
            port_arg = f"--top-ports {self.top_ports}"

        opts = [
            "-oX", "-",        # XML to stdout
            "-Pn",             # skip host discovery (we know it's up)
            "-sV",             # service/version detection
            "-T4",             # aggressive timing
            "--open",          # only report open ports
            "--host-timeout", "180s",
            "--max-rtt-timeout", "1000ms",
            "--max-retries", "2",
            "-p", port_arg,
        ]
        if os_detection or self.os_detection:
            opts.append("-O")

        cmd = [self.binary, *opts, target]

        async with NmapPortScanner._sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
            except FileNotFoundError as e:
                raise RuntimeError(f"nmap binary not found: {self.binary}") from e

        xml_data = stdout.decode("utf-8", errors="replace")
        if not xml_data.strip():
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"nmap produced no output (rc={proc.returncode}): {err[:500]}")

        return self._parse(target, xml_data)

    # ── XML parsing ──────────────────────────────────────────────────────
    def _parse(self, target: str, xml_data: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            raise RuntimeError(f"failed to parse nmap XML: {e}") from e

        open_ports: List[Dict[str, Any]] = []
        os_info: Optional[Dict[str, Any]] = None
        scripts: Dict[str, str] = {}

        for host in root.iter("host"):
            # OS detection
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
                    "vendor": osclass.get("vendor") if osclass is not None else None,
                    "cpe": cpe,
                }

            # Host scripts (e.g. smb-security-mode)
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
                service = ""
                product = ""
                version = ""
                extrainfo = ""
                cpe = None
                if service_el is not None:
                    service = service_el.get("name", "") or ""
                    product = service_el.get("product", "") or ""
                    version = service_el.get("version", "") or ""
                    extrainfo = service_el.get("extrainfo", "") or ""
                    cpe_el = service_el.find("cpe")
                    if cpe_el is not None:
                        cpe = cpe_el.text

                # Build a human-readable version string "like nmap".
                full_version = " ".join(p for p in [product, version, extrainfo] if p).strip()

                # Banner stays port-specific (CPE / service fingerprint). Host
                # scripts are surfaced separately in the top-level `scripts`
                # field, not duplicated onto every port.
                banner = cpe or ""

                open_ports.append({
                    "port": port_id,
                    "protocol": protocol,
                    "state": "open",
                    "service": service or "unknown",
                    "version": full_version[:200],
                    "product": product,
                    "banner": banner[:500],
                })

        open_ports.sort(key=lambda x: x["port"])
        return {
            "success": True,
            "target": target,
            "ports": open_ports,
            "open_ports": len(open_ports),
            "scanner": "nmap",
            "os": os_info,
            "scripts": scripts,
            "capabilities": {
                "os_detection": "nmap" if os_info else "unsupported",
                "udp_scan": "unsupported",
                "service_fp": "nmap-sV",
            },
        }
