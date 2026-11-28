import asyncio
import copy
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from app.scanners.registry import registry, ScannerCategory
from app.scanners.subdomain import SubdomainScanner
from app.scanners.dns import DNSScanner
from app.scanners.whois import WhoisScanner
from app.scanners.ssl_check import SSLScanner
from app.scanners.ports import PortScanner
from app.scanners.nmap_scanner import NmapPortScanner
from app.scanners.tech import TechScanner
from app.scanners.security_findings import SecurityFindingsScanner
from app.scanners.zone_transfer import ZoneTransferScanner
from app.scanners.cve_correlation import CVECorrelationScanner
from app.scanners.relationships import RelationshipsScanner
from app.risk_scorer import calculate_risk
from app.config import settings
import logging

from app.core.target_guard import filter_probe_targets, probe_allowed

logger = logging.getLogger(__name__)

_SUBDOMAIN_CONCURRENCY = 75


def _plugin_instance(category: ScannerCategory, fallback) -> Optional[Any]:
    plugins = registry.by_category(category)
    if plugins:
        return plugins[0].instantiate()
    return fallback


class ScanRunner:
    """Orchestrates all scanner modules for a complete scan.

    Performance model: maximum parallelism at every level. WHOIS, zone
    transfer, and reverse DNS run concurrently with the main subdomain scan.
    Within each subdomain, DNS, SSL, Ports, and Tech run in parallel.
    """

    def __init__(self):
        self.subdomain_scanner = SubdomainScanner()
        self.dns_scanner = DNSScanner()
        self.whois_scanner = WhoisScanner()
        self.ssl_scanner = SSLScanner()
        self.port_scanner = PortScanner()
        self.nmap_scanner = NmapPortScanner()
        self.tech_scanner = TechScanner()
        self.security_findings_scanner = SecurityFindingsScanner()
        self.zone_transfer_scanner = ZoneTransferScanner()
        self.cve_scanner = CVECorrelationScanner()
        self.relationships_scanner = RelationshipsScanner()

    async def _port_scan_host(
        self,
        subdomain: str,
        port_mode: str,
        ports_list: Optional[List[int]],
    ) -> Dict[str, Any]:
        """Port-scan one host. Returns ``{"ports", "os", "scripts", "errors"}``."""
        out: Dict[str, Any] = {"ports": None, "os": None, "scripts": None, "errors": []}
        try:
            if port_mode == "full" and settings.USE_NMAP and self.nmap_scanner.available():
                # High-fidelity nmap path: real -sV service/version + OS.
                try:
                    r = await self.nmap_scanner.run_with_retry(
                        subdomain,
                        scan_type="full",
                        port_list=ports_list,
                    )
                    out["ports"] = r
                    out["os"] = r.get("os")
                    out["scripts"] = r.get("scripts")
                    return out
                except Exception as e:
                    # Fall through to the pure-Python scanner so a scan
                    # never completely loses port data because nmap choked.
                    logger.warning("nmap port scan failed for %s, falling back to python: %s",
                                   subdomain, e)
                    out["errors"].append(
                        {"scanner": "ports-nmap", "target": subdomain, "error": str(e)})

            # Pure-Python connect scanner (quick mode, or nmap fallback).
            out["ports"] = await self.port_scanner.run_with_retry(
                subdomain,
                scan_type="quick" if port_mode == "quick" else "full",
                port_list=ports_list if port_mode == "full" else None,
            )
        except Exception as e:
            out["errors"].append({"scanner": "ports", "target": subdomain, "error": str(e)})
        return out

    async def _scan_one_subdomain(
        self,
        subdomain: str,
        port_mode: str,
        ports_list: List[int],
        domain: str,
        port_cache: Optional[Dict[Any, "asyncio.Future"]] = None,
    ) -> Dict[str, Any]:
        """DNS, TLS, ports and web fingerprint for one host, in parallel.

        With ``port_cache`` (one dict per scan), hosts that resolve to exactly
        the same addresses share a single port scan: open/closed state belongs
        to the IP, not the name, and CDN or load-balanced estates often put
        dozens of names on the same few addresses. The port scan then waits
        for this host's DNS answer, which is fast next to a port scan.
        """
        result = {
            "subdomain": subdomain,
            "dns": None,
            "ssl": None,
            "ports": None,
            "tech": None,
            "os": None,
            "scripts": None,
            "san_hostnames": [],
            "ips": [],
            "errors": [],
        }
        dns_done = asyncio.Event()

        async def _dns():
            try:
                r = await self.dns_scanner.run_with_retry(subdomain)
                result["dns"] = r
                if r and r.get("success"):
                    result["ips"] = r.get("ips", [])
            except Exception as e:
                result["errors"].append({"scanner": "dns", "target": subdomain, "error": str(e)})
            finally:
                dns_done.set()

        async def _ssl():
            try:
                r = await self.ssl_scanner.run_with_retry(subdomain)
                result["ssl"] = r
                if r and r.get("success"):
                    result["san_hostnames"] = r.get("san_hostnames", [])
            except Exception as e:
                result["errors"].append({"scanner": "ssl", "target": subdomain, "error": str(e)})

        async def _ports():
            if port_cache is None:
                out = await self._port_scan_host(subdomain, port_mode, ports_list)
            else:
                await dns_done.wait()
                ips = tuple(sorted(set(result["ips"] or [])))
                key = ips if ips else ("host", subdomain)
                fut = port_cache.get(key)
                if fut is None:
                    fut = asyncio.ensure_future(self._port_scan_host(subdomain, port_mode, ports_list))
                    fut.scanned_host = subdomain  # type: ignore[attr-defined]
                    port_cache[key] = fut
                # shield: one host's cancellation must not cancel the shared scan
                shared = await asyncio.shield(fut)
                scanned_host = getattr(fut, "scanned_host", subdomain)
                if scanned_host == subdomain:
                    out = shared
                else:
                    out = copy.deepcopy(shared)
                    out["errors"] = []  # reported once, by the host that ran the scan
                    if isinstance(out.get("ports"), dict):
                        out["ports"]["shared_scan_of"] = scanned_host
            result["ports"] = out["ports"]
            result["os"] = out["os"]
            result["scripts"] = out["scripts"]
            result["errors"].extend(out["errors"])

        async def _tech():
            try:
                r = await self.tech_scanner.run_with_retry(subdomain)
                result["tech"] = r
            except Exception as e:
                result["errors"].append({"scanner": "tech", "target": subdomain, "error": str(e)})

        await asyncio.gather(_dns(), _ssl(), _ports(), _tech(), return_exceptions=True)
        return result

    async def run_full_scan(
        self,
        domain: str,
        progress_callback=None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        options = options or {}
        max_subdomains = options.get("max_subdomains", 0)
        port_mode = options.get("port_mode", "full")
        subdomain_tools = options.get("subdomain_tools", ["default", "bruteforce", "permutations"])

        results: Dict[str, Any] = {
            "domain": domain,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "subdomains": [],
            "dns_records": {},
            "ssl_certificates": {},
            "ports": {},
            "os_detection": {},
            "host_scripts": {},
            "technologies": {},
            "vulnerabilities": {},
            "whois": None,
            "errors": [],
            "scanner_status": {},
        }

        try:
            # Increase thread pool for high-concurrency scanning
            loop = asyncio.get_event_loop()
            executor = loop._default_executor
            if executor:
                executor._max_workers = 200

            # ── Step 1: Subdomain discovery + WHOIS (PARALLEL) ──
            if progress_callback:
                await progress_callback(5, "Discovering subdomains + WHOIS (parallel)...")

            subdomains = {domain}
            # Full scans are driven by the chosen port scanner's own range:
            #  - nmap (preferred) uses its top-N default (config.NMAP_TOP_PORTS)
            #  - python fallback uses its TOP_1000_PORTS
            # A custom port range supplied via scan options overrides both.
            custom_ports = options.get("ports")
            ports_list = custom_ports if custom_ports else None

            async def _run_source(name, scanner):
                try:
                    r = await scanner.run_with_retry(domain)
                    if r and r.get("success"):
                        return name, r.get("subdomains", []), "ok"
                    return name, [], "failed"
                except Exception as e:
                    return name, [], f"error: {type(e).__name__}"

            source_tasks = []
            if "default" in subdomain_tools:
                source_tasks.append(_run_source("subdomain-default", self.subdomain_scanner))
            if "bruteforce" in subdomain_tools:
                bf_plugin = registry.get("subdomain-bruteforce")
                if bf_plugin:
                    source_tasks.append(_run_source("subdomain-bruteforce", bf_plugin.instantiate()))
            if "permutations" in subdomain_tools:
                perm_plugin = registry.get("subdomain-permutations")
                if perm_plugin:
                    source_tasks.append(_run_source("subdomain-permutations", perm_plugin.instantiate()))

            # WHOIS runs in parallel with subdomain discovery
            whois_task = asyncio.create_task(self._safe_whois(domain))

            source_results = await asyncio.gather(*source_tasks, return_exceptions=True)
            for item in source_results:
                if isinstance(item, Exception):
                    results["errors"].append({"scanner": "subdomain-source", "error": str(item)})
                    continue
                name, found, status = item
                subdomains.update(found)
                results["scanner_status"][name] = f"ok ({len(found)} found)" if status == "ok" else status

            # Collect WHOIS result
            whois_result = await whois_task
            if whois_result and whois_result.get("success"):
                results["whois"] = whois_result.get("data")
                results["scanner_status"]["whois"] = "ok"
            else:
                results["scanner_status"]["whois"] = "failed"

            subdomains = sorted(subdomains)
            results["subdomains"] = subdomains
            if max_subdomains > 0:
                subdomains = subdomains[:max_subdomains]
                results["subdomains"] = subdomains
            total = len(subdomains)

            # ── Step 2: Scan ALL subdomains + Zone Transfer (PARALLEL) ──
            if progress_callback:
                await progress_callback(15, f"Scanning {total} subdomains (concurrent)...")

            sem = asyncio.Semaphore(_SUBDOMAIN_CONCURRENCY)
            all_san_hostnames: List[str] = []
            all_ips: List[str] = []
            counters = {"dns_ok": 0, "dns_fail": 0, "ssl_ok": 0, "ssl_fail": 0,
                        "port_ok": 0, "port_fail": 0, "tech_ok": 0, "tech_fail": 0}
            completed = 0
            # One port scan per distinct set of addresses (see _scan_one_subdomain).
            port_cache: Dict[Any, asyncio.Future] = {}

            async def _bounded_scan(subdomain):
                nonlocal completed
                # Discovered hosts are untrusted: only probe those under the
                # authorized domain that resolve to public addresses.
                if not await probe_allowed(subdomain, domain):
                    counters["skipped_out_of_scope"] = counters.get("skipped_out_of_scope", 0) + 1
                    return
                async with sem:
                    r = await self._scan_one_subdomain(subdomain, port_mode, ports_list, domain, port_cache)
                    completed += 1
                    if progress_callback and completed % max(total // 20, 1) == 0:
                        pct = 15 + int((completed / max(total, 1)) * 55)
                        await progress_callback(pct, f"Scanned {completed}/{total} subdomains...")

                    if r["dns"] and r["dns"].get("success"):
                        results["dns_records"][subdomain] = r["dns"].get("records", {})
                        all_ips.extend(r["dns"].get("ips", []))
                        counters["dns_ok"] += 1
                    else:
                        counters["dns_fail"] += 1

                    if r["ssl"] and r["ssl"].get("success"):
                        results["ssl_certificates"][subdomain] = r["ssl"].get("certificate")
                        counters["ssl_ok"] += 1
                        all_san_hostnames.extend(r["san_hostnames"])
                    else:
                        counters["ssl_fail"] += 1

                    if r["ports"] and r["ports"].get("success"):
                        results["ports"][subdomain] = r["ports"].get("ports", [])
                        if r.get("os"):
                            results["os_detection"][subdomain] = r["os"]
                        if r.get("scripts"):
                            results["host_scripts"][subdomain] = r["scripts"]
                        counters["port_ok"] += 1
                    else:
                        counters["port_fail"] += 1

                    if r["tech"] and r["tech"].get("success"):
                        results["technologies"][subdomain] = r["tech"].get("technologies", [])
                        counters["tech_ok"] += 1
                    else:
                        counters["tech_fail"] += 1

                    results["errors"].extend(r["errors"])

            # Zone transfer runs in parallel with main scan
            zone_transfer_task = asyncio.create_task(self._safe_zone_transfer(domain, results))

            scan_tasks = [_bounded_scan(sub) for sub in subdomains]
            await asyncio.gather(*scan_tasks, return_exceptions=True)

            for key, ok_key, fail_key in [
                ("dns", "dns_ok", "dns_fail"), ("ssl", "ssl_ok", "ssl_fail"),
                ("ports", "port_ok", "port_fail"), ("tech", "tech_ok", "tech_fail"),
            ]:
                ok, fail = counters[ok_key], counters[fail_key]
                total_sq = ok + fail
                results["scanner_status"][key] = f"ok ({ok}/{total_sq} hosts)" if total_sq > 0 else "ok"

            hosts_port_scanned = counters["port_ok"] + counters["port_fail"]
            if port_cache and hosts_port_scanned > len(port_cache):
                results["scanner_status"]["port-dedupe"] = (
                    f"ok ({len(port_cache)} port scans covered {hosts_port_scanned} hosts "
                    "that share addresses)"
                )

            if counters.get("skipped_out_of_scope"):
                results["scanner_status"]["scope-guard"] = (
                    f"ok ({counters['skipped_out_of_scope']} hosts recorded but not probed: "
                    "outside the authorized domain or not public)"
                )

            # Collect zone transfer result
            zt_result = await zone_transfer_task
            if zt_result:
                if zt_result.get("success") and zt_result.get("transfer_success"):
                    for hostname in zt_result.get("subdomains", []):
                        if hostname not in results["subdomains"]:
                            results["subdomains"].append(hostname)
                            zt_records = zt_result.get("records", {}).get(hostname, {})
                            if zt_records:
                                results["dns_records"][hostname] = zt_records
                    results["scanner_status"]["zone-transfer"] = f"ok ({zt_result.get('transfer_count', 0)} records)"
                else:
                    results["scanner_status"]["zone-transfer"] = "ok (blocked or not vulnerable)"

            # ── Step 3: Reverse DNS + SAN scanning (PARALLEL with each other) ──
            unique_ips = sorted(set(all_ips))
            unique_sans = sorted(set(all_san_hostnames) - set(subdomains))

            rev_and_san_tasks = []

            if unique_ips:
                if progress_callback:
                    await progress_callback(72, f"Reverse DNS on {len(unique_ips)} IPs + {len(unique_sans)} SANs...")

                async def _rev_dns_batch():
                    async def _rev_dns(ip):
                        try:
                            r = await self.dns_scanner.resolve_ip(ip)
                            if r and r.get("success"):
                                return [h.rstrip(".") for h in r.get("hostnames", []) if h]
                        except Exception as exc:
                            logger.debug("Reverse DNS failed for %s: %s", ip, exc)
                        return []

                    rev_results = await asyncio.gather(
                        *[_rev_dns(ip) for ip in unique_ips[:50]], return_exceptions=True
                    )
                    reverse_hostnames = set()
                    for item in rev_results:
                        if isinstance(item, list):
                            reverse_hostnames.update(h for h in item if h not in subdomains)
                    return reverse_hostnames

                rev_and_san_tasks.append(_rev_dns_batch())

            if unique_sans:
                results["subdomains"].extend(unique_sans)
                rev_and_san_tasks.append(self._scan_sans_batch(unique_sans, _bounded_scan))

            if rev_and_san_tasks:
                rev_results = await asyncio.gather(*rev_and_san_tasks, return_exceptions=True)
                # Scan reverse-DNS hostnames
                for item in rev_results:
                    if isinstance(item, set) and item:
                        rev_tasks = [_bounded_scan(h) for h in sorted(item)]
                        await asyncio.gather(*rev_tasks, return_exceptions=True)

            # ── Step 4: Vulnerability scanning + Relationships (PARALLEL) ──
            if progress_callback:
                await progress_callback(85, "Running vulnerability scan + relationships...")

            results["scanner_status"]["nuclei"] = "removed: replaced by pure code (security-findings + cve-correlation)"

            async def _findings():
                try:
                    r = await self.security_findings_scanner.run_with_retry(domain, scan_results=results)
                    if r and r.get("success"):
                        results["scanner_status"]["security-findings"] = f"ok ({r.get('count', 0)} findings)"
                        return r.get("vulnerabilities", [])
                    results["scanner_status"]["security-findings"] = "failed"
                except Exception as e:
                    results["scanner_status"]["security-findings"] = f"error: {e}"
                    results["errors"].append({"scanner": "security-findings", "error": str(e)})
                return []

            async def _cve():
                try:
                    r = await self.cve_scanner.run_with_retry(domain, scan_results=results)
                    if r and r.get("success"):
                        results["scanner_status"]["cve-correlation"] = f"ok ({len(r.get('vulnerabilities', []))} CVEs)"
                        return r.get("vulnerabilities", [])
                    results["scanner_status"]["cve-correlation"] = "failed"
                except Exception as e:
                    results["scanner_status"]["cve-correlation"] = f"error: {e}"
                    results["errors"].append({"scanner": "cve-correlation", "error": str(e)})
                return []

            async def _relationships():
                try:
                    rel_result = await self.relationships_scanner.run_with_retry(domain, scan_results=results)
                    if rel_result and rel_result.get("success"):
                        results["relationships"] = {
                            "ip_asn_mapping": rel_result.get("ip_asn_mapping", {}),
                            "hosting_providers": rel_result.get("hosting_providers", {}),
                            "registrar_clusters": rel_result.get("registrar_clusters", {}),
                            "relationships": rel_result.get("relationships", []),
                        }
                        results["scanner_status"]["relationships"] = f"ok ({len(rel_result.get('relationships', []))} edges)"
                    else:
                        results["scanner_status"]["relationships"] = "failed"
                except Exception as e:
                    results["scanner_status"]["relationships"] = f"error: {type(e).__name__}"
                    results["errors"].append({"scanner": "relationships", "error": str(e)})

            findings_list, cve_list, _ = await asyncio.gather(
                _findings(), _cve(), _relationships(), return_exceptions=True
            )
            merged_vulns = []
            if isinstance(findings_list, list):
                merged_vulns.extend(findings_list)
            if isinstance(cve_list, list):
                merged_vulns.extend(cve_list)
            # One vocabulary for findings (same ids, titles and severities as
            # Scanner v2), duplicates merged, then exploited CVEs flagged.
            from app.scanners.finding_catalog import polish_findings
            from app.scanners.exploit_intel import enrich_with_exploit_intel
            results["vulnerabilities"] = polish_findings(merged_vulns)
            if options.get("exploit_intel", True):
                results["scanner_status"]["exploit-intel"] = await enrich_with_exploit_intel(
                    results["vulnerabilities"])

            # ── Step 5: Risk score ──
            if progress_callback:
                await progress_callback(95, "Calculating risk score...")
            try:
                results["risk_score"] = calculate_risk(results)
            except Exception as e:
                logger.error(f"Risk score calculation failed: {e}")
                results["errors"].append({"scanner": "risk_score", "error": str(e)})

            results["success"] = True
            if progress_callback:
                await progress_callback(100, "Scan completed")
            return results

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    async def _safe_whois(self, domain: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.whois_scanner.run_with_retry(domain)
        except Exception as e:
            logger.warning(f"WHOIS failed: {e}")
            return None

    async def _safe_zone_transfer(self, domain: str, results: Dict) -> Optional[Dict[str, Any]]:
        try:
            return await self.zone_transfer_scanner.run_with_retry(domain)
        except Exception as e:
            logger.warning(f"Zone transfer failed: {e}")
            results["scanner_status"]["zone-transfer"] = f"error: {type(e).__name__}"
            results["errors"].append({"scanner": "zone-transfer", "error": str(e)})
            return None

    async def _scan_sans_batch(self, sans: List[str], bounded_scan_fn):
        tasks = [bounded_scan_fn(h) for h in sans]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run_quick_scan(
        self,
        domain: str,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Quick scan: top 20 subdomains, top 10 ports, no vuln scanning."""
        results: Dict[str, Any] = {
            "success": True,
            "domain": domain,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "subdomains": [],
            "dns_records": {},
            "ssl_certificates": {},
            "ports": {},
            "technologies": {},
            "vulnerabilities": {},
            "whois": None,
            "errors": [],
            "risk_score": {},
            "scanner_status": {},
        }

        try:
            if progress_callback:
                await progress_callback(5, "Starting quick scan...")

            subdomain_scanner = SubdomainScanner()
            subdomain_result = await subdomain_scanner.scan(domain, use_all_sources=False)
            subdomains = subdomain_result.get("subdomains", []) if isinstance(subdomain_result, dict) else []
            results["subdomains"] = subdomains
            if isinstance(subdomain_result, dict) and subdomain_result.get("success"):
                results["scanner_status"]["subdomain-default"] = f"ok ({len(subdomains)} found)"
            else:
                results["scanner_status"]["subdomain-default"] = "failed"

            if progress_callback:
                await progress_callback(30, f"Found {len(subdomains)} subdomains")

            quick_ports = [80, 443, 22, 8080, 8443, 21, 25, 53, 3306, 5432]
            scan_targets = await filter_probe_targets(subdomains[:20], domain)
            sem = asyncio.Semaphore(20)
            counters = {"dns_ok": 0, "dns_fail": 0, "ssl_ok": 0, "ssl_fail": 0,
                        "port_ok": 0, "port_fail": 0, "tech_ok": 0, "tech_fail": 0}

            async def _quick_one(hostname):
                async with sem:
                    async def _d():
                        try:
                            r = await self.dns_scanner.scan(hostname)
                            if isinstance(r, dict) and r.get("success"):
                                results["dns_records"][hostname] = r.get("records", {})
                                counters["dns_ok"] += 1
                            else:
                                counters["dns_fail"] += 1
                        except Exception as exc:
                            counters["dns_fail"] += 1
                            logger.debug("DNS scan failed for %s: %s", hostname, exc)

                    async def _s():
                        try:
                            r = await self.ssl_scanner.scan(hostname)
                            if isinstance(r, dict) and r.get("success"):
                                results["ssl_certificates"][hostname] = r.get("certificate")
                                counters["ssl_ok"] += 1
                            else:
                                counters["ssl_fail"] += 1
                        except Exception as exc:
                            counters["ssl_fail"] += 1
                            logger.debug("SSL scan failed for %s: %s", hostname, exc)

                    async def _p():
                        try:
                            port_scanner = PortScanner()
                            r = await port_scanner.scan(hostname, ports=",".join(str(p) for p in quick_ports))
                            if isinstance(r, dict) and r.get("success"):
                                results["ports"][hostname] = r.get("ports", [])
                                counters["port_ok"] += 1
                            else:
                                counters["port_fail"] += 1
                        except Exception as exc:
                            counters["port_fail"] += 1
                            logger.debug("Port scan failed for %s: %s", hostname, exc)

                    async def _t():
                        try:
                            r = await self.tech_scanner.scan(hostname)
                            if isinstance(r, dict) and r.get("success"):
                                results["technologies"][hostname] = r.get("technologies", [])
                                counters["tech_ok"] += 1
                            else:
                                counters["tech_fail"] += 1
                        except Exception as exc:
                            counters["tech_fail"] += 1
                            logger.debug("Tech scan failed for %s: %s", hostname, exc)

                    await asyncio.gather(_d(), _s(), _p(), _t(), return_exceptions=True)

            await asyncio.gather(*[_quick_one(sub) for sub in scan_targets], return_exceptions=True)

            for key in ("dns", "ssl", "ports", "tech"):
                ok = counters[f"{key}_ok"]
                fail = counters[f"{key}_fail"]
                tot = ok + fail
                results["scanner_status"][key] = f"ok ({ok}/{tot} hosts)" if tot > 0 else "ok"

            results["scanner_status"]["nuclei"] = "skipped: quick scan"
            results["scanner_status"]["security-findings"] = "skipped: quick scan"
            results["scanner_status"]["cve-correlation"] = "skipped: quick scan"
            results["scanner_status"]["whois"] = "skipped: quick scan"

            results["risk_score"] = calculate_risk(results)

            if progress_callback:
                await progress_callback(100, "Quick scan completed")
            return results

        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results
