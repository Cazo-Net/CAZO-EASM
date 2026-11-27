"""Optional integrations with well-known open-source scanners.

Each tool is used only when its binary is installed in the image *and* the
matching setting allows it, and only against targets that already passed
the platform's scope gate. Nothing here installs software at runtime.

* subfinder (ProjectDiscovery): passive subdomain sources. Used by
  ``asset_discovery`` when ``SCAN_ENABLE_SUBFINDER`` is on and the binary
  exists. It queries third-party data sets, never the customer's hosts.
* nuclei (ProjectDiscovery): template checks. Off by default
  (``SCAN_ENABLE_NUCLEI``). When on, it runs a *safe* subset: exposure,
  misconfiguration, panel, technology and token templates, with every
  intrusive, brute-force, fuzzing, DoS, default-login and out-of-band tag
  excluded, interactsh disabled, redirects not followed, and a request rate
  cap (``NUCLEI_RATE_LIMIT``).
* nmap: service/version detection on ports already found open (see
  ``fast_port_scanner._nmap_enrich``).

Not integrated (yet): httpx and naabu would duplicate the built-in
fingerprinting and port scanning; amass is slow and heavy for a request
path. They can be added the same way if the image grows a scan fleet.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from app.core.target_guard import host_in_scope, normalize_target
from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import ScannerCategory, register_scanner
from app.scanners.v2.secret_patterns import redact

logger = logging.getLogger(__name__)

NUCLEI_SAFE_TAGS = "exposure,exposures,misconfig,misconfiguration,panel,tech,token,config,ssl,takeover,disclosure"
NUCLEI_EXCLUDED_TAGS = (
    "intrusive,dos,fuzz,fuzzing,bruteforce,brute-force,default-login,rce,sqli,xss,lfi,rfi,"
    "ssrf,oast,oob,headless,code,file-upload,auth-bypass,injection,cmd"
)


def _setting(name: str, default: Any) -> Any:
    try:
        from app.config import settings
        return getattr(settings, name, default)
    except Exception:  # noqa: BLE001
        return default


async def _run(cmd: List[str], timeout: float, stdin: Optional[bytes] = None) -> Optional[bytes]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (FileNotFoundError, PermissionError) as exc:
        logger.info("Cannot run %s: %s", cmd[0], exc)
        return None
    try:
        out, _ = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
        return out
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await asyncio.shield(proc.wait())
        raise


async def subfinder_subdomains(domain: str, timeout: float = 150) -> List[str]:
    """Passive subdomains from subfinder, or [] when unavailable/disabled."""
    if not _setting("SCAN_ENABLE_SUBFINDER", True):
        return []
    binary = shutil.which("subfinder")
    if not binary:
        return []
    try:
        out = await _run([binary, "-d", domain, "-silent", "-timeout", "30", "-max-time", "2"], timeout)
    except asyncio.TimeoutError:
        logger.warning("subfinder timed out for %s", domain)
        return []
    if not out:
        return []
    root = normalize_target(domain)
    names = {line.strip().lower() for line in out.decode("utf-8", "replace").splitlines()}
    return sorted(n for n in names if n and "*" not in n and host_in_scope(n, root))


@register_scanner(
    name="nuclei-safe",
    category=ScannerCategory.WEB_EXPOSURE,
    version="1.0.0",
    priority=ScannerPriority.NORMAL,
    description="Optional nuclei run with non-intrusive templates only (off unless SCAN_ENABLE_NUCLEI)",
    capabilities=["template_checks"],
)
class NucleiSafeScanner(EnhancedBaseScanner):
    name = "nuclei-safe"
    version = "1.0.0"
    category = ScannerCategory.WEB_EXPOSURE
    priority = ScannerPriority.NORMAL

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_retries = 0
        self.timeout = max(float(self.timeout), float(self.config.get("pipeline_timeout_s", 900)) * 0.5)

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        enabled = bool(self.config.get("nuclei_enabled", _setting("SCAN_ENABLE_NUCLEI", False)))
        binary = shutil.which("nuclei")
        if not enabled or not binary:
            return ScanResult(success=True, scanner=self.name, target=target, data={
                "vulnerabilities": [], "status": "disabled" if not enabled else "not_installed",
            })

        root = normalize_target(kwargs.get("root_domain") or target)
        targets = []
        for url in kwargs.get("web_targets") or [f"https://{target}"]:
            from urllib.parse import urlsplit
            host = urlsplit(url).hostname or ""
            if host and host_in_scope(host, root):
                targets.append(url)
        targets = targets[: int(self.config.get("max_web_targets", 20))]
        if not targets:
            return ScanResult(success=True, scanner=self.name, target=target, data={"vulnerabilities": []})

        rate = int(_setting("NUCLEI_RATE_LIMIT", 10))
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("\n".join(targets))
            list_path = fh.name
        cmd = [
            binary, "-l", list_path, "-jsonl", "-silent", "-nc", "-duc", "-ni", "-or",
            "-tags", NUCLEI_SAFE_TAGS, "-etags", NUCLEI_EXCLUDED_TAGS,
            "-severity", "low,medium,high,critical",
            "-pt", "http,ssl",
            "-rl", str(rate), "-c", "5", "-bs", "5", "-timeout", "10", "-retries", "1",
        ]
        try:
            out = await _run(cmd, timeout=self.timeout - 5)
        except asyncio.TimeoutError:
            out = None
        finally:
            try:
                os.unlink(list_path)
            except OSError:
                pass

        findings = parse_nuclei_jsonl((out or b"").decode("utf-8", "replace"), root)
        return ScanResult(success=True, scanner=self.name, target=target, data={
            "vulnerabilities": findings, "targets": len(targets), "status": "ran",
        })


def parse_nuclei_jsonl(text: str, root_domain: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        info = row.get("info") or {}
        host = row.get("host") or ""
        from urllib.parse import urlsplit
        hostname = urlsplit(host).hostname if "://" in host else host.split(":")[0]
        if hostname and not host_in_scope(hostname, root_domain):
            continue
        extracted = [redact(str(x)) if len(str(x)) > 12 else str(x) for x in (row.get("extracted-results") or [])]
        findings.append({
            "template_id": f"nuclei/{row.get('template-id', 'unknown')}",
            "name": info.get("name") or row.get("template-id", "nuclei finding"),
            "severity": (info.get("severity") or "info").lower(),
            "vuln_type": "nuclei",
            "host": hostname or root_domain,
            "matched_at": row.get("matched-at") or host,
            "description": (info.get("description") or "").strip()[:1000],
            "reference": info.get("reference") or [],
            "tags": info.get("tags") if isinstance(info.get("tags"), list) else str(info.get("tags") or "").split(","),
            "extracted_results": extracted[:10],
            "curl_command": "",
            "source": "nuclei-safe",
        })
    return findings
