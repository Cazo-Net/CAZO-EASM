import asyncio
import socket
import shutil
from typing import Any, Dict, List
from app.scanners.base import BaseScanner
import logging

logger = logging.getLogger(__name__)

try:
    import nmap as nmap_module
    NMAP_AVAILABLE = shutil.which("nmap") is not None
except ImportError:
    NMAP_AVAILABLE = False
    nmap_module = None


class PortScanner(BaseScanner):
    """Port scanner with nmap + Python socket fallback."""

    COMMON_PORTS = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
        993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1723: "PPTP",
        3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
        6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
        27017: "MongoDB", 9200: "Elasticsearch", 5601: "Kibana",
    }

    def validate_target(self, target: str) -> bool:
        import re
        ip_regex = re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        )
        hostname_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(ip_regex.match(target) or hostname_regex.match(target))

    async def _python_scan(self, target: str, ports: List[int]) -> List[Dict[str, Any]]:
        """Fallback: scan ports using Python asyncio sockets."""
        results = []

        async def check_port(port: int):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(target, port),
                    timeout=2,
                )
                writer.close()
                await writer.wait_closed()
                service = self.COMMON_PORTS.get(port, "unknown")
                results.append({
                    "port": port,
                    "protocol": "tcp",
                    "state": "open",
                    "service": service,
                    "version": "",
                    "product": "",
                })
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass

        tasks = [check_port(p) for p in ports]
        await asyncio.gather(*tasks)
        return sorted(results, key=lambda x: x["port"])

    async def _nmap_scan(self, target: str, port_arg: str) -> List[Dict[str, Any]]:
        """Nmap-based scan."""
        nm = nmap_module.PortScanner()
        arguments = f"-sV -sC --open -p {port_arg} -T4"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: nm.scan(target, arguments=arguments),
        )

        ports_found = []
        if target in nm.all_hosts():
            for proto in nm[target].all_protocols():
                for port in sorted(nm[target][proto].keys()):
                    port_info = nm[target][proto][port]
                    if port_info["state"] == "open":
                        ports_found.append({
                            "port": port,
                            "protocol": proto,
                            "state": "open",
                            "service": port_info.get("name", "unknown"),
                            "version": port_info.get("version", ""),
                            "product": port_info.get("product", ""),
                        })
        return ports_found

    async def scan(
        self,
        target: str,
        ports: str = None,
        scan_type: str = "quick",
        **kwargs,
    ) -> Dict[str, Any]:
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid target: {target}"))

        try:
            if NMAP_AVAILABLE and ports:
                port_list = [int(p.strip()) for p in ports.split(",") if p.strip().isdigit()]
                ports_found = await self._nmap_scan(target, ports)
            elif NMAP_AVAILABLE and scan_type == "full":
                ports_found = await self._nmap_scan(target, "1-1000")
            elif NMAP_AVAILABLE:
                ports_found = await self._nmap_scan(target, ",".join(str(p) for p in self.COMMON_PORTS.keys()))
            else:
                if ports:
                    port_list = [int(p.strip()) for p in ports.split(",") if p.strip().isdigit()]
                elif scan_type == "full":
                    port_list = list(range(1, 1001))
                else:
                    port_list = list(self.COMMON_PORTS.keys())
                ports_found = await self._python_scan(target, port_list)

            return {
                "success": True,
                "target": target,
                "ports": ports_found,
                "open_ports": len(ports_found),
                "scanner": "nmap" if NMAP_AVAILABLE else "python-socket",
            }

        except Exception as e:
            logger.error(f"Port scan error for {target}: {e}")
            return self._format_error(e)
