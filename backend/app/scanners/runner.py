import asyncio
from typing import Any, Dict, List
from datetime import datetime, timezone
from app.scanners.subdomain import SubdomainScanner
from app.scanners.dns import DNSScanner
from app.scanners.whois import WhoisScanner
from app.scanners.ssl_check import SSLScanner
from app.scanners.ports import PortScanner
from app.scanners.tech import TechScanner
from app.scanners.nuclei_scanner import NucleiScanner
from app.risk_scorer import calculate_risk
import logging

logger = logging.getLogger(__name__)


class ScanRunner:
    """Orchestrates all scanner modules for a complete scan."""
    
    def __init__(self):
        self.subdomain_scanner = SubdomainScanner()
        self.dns_scanner = DNSScanner()
        self.whois_scanner = WhoisScanner()
        self.ssl_scanner = SSLScanner()
        self.port_scanner = PortScanner()
        self.tech_scanner = TechScanner()
        self.nuclei_scanner = NucleiScanner()
    
    async def run_full_scan(
        self,
        domain: str,
        progress_callback=None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a complete scan pipeline."""
        results = {
            "domain": domain,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "subdomains": [],
            "dns_records": {},
            "ssl_certificates": {},
            "ports": {},
            "technologies": {},
            "vulnerabilities": {},
            "whois": None,
            "errors": []
        }
        
        try:
            # Step 1: Discover subdomains from multiple sources
            if progress_callback:
                await progress_callback(5, "Discovering subdomains...")
            
            subdomains = set()
            subdomains.add(domain)
            
            # Source: Multi-source (crt.sh + HackerTarget + AlienVault)
            try:
                subdomain_result = await self.subdomain_scanner.run_with_retry(domain)
                if subdomain_result.get("success"):
                    subdomains.update(subdomain_result.get("subdomains", []))
            except Exception as e:
                results["errors"].append({"scanner": "subdomain", "error": str(e)})
            
            subdomains = sorted(subdomains)
            results["subdomains"] = subdomains
            
            # Step 2: WHOIS on main domain
            if progress_callback:
                await progress_callback(15, "Running WHOIS lookup...")
            
            try:
                whois_result = await self.whois_scanner.run_with_retry(domain)
                if whois_result.get("success"):
                    results["whois"] = whois_result.get("data")
            except Exception as e:
                results["errors"].append({"scanner": "whois", "error": str(e)})
            
            # Step 3: Process each subdomain
            http_urls = []
            total = len(subdomains)
            
            for idx, subdomain in enumerate(subdomains):
                progress = 20 + int((idx / total) * 55)
                
                if progress_callback:
                    await progress_callback(progress, f"Scanning {subdomain} ({idx + 1}/{total})...")
                
                # DNS
                try:
                    dns_result = await self.dns_scanner.run_with_retry(subdomain)
                    if dns_result.get("success"):
                        results["dns_records"][subdomain] = dns_result.get("records", {})
                except Exception as e:
                    results["errors"].append({"scanner": "dns", "target": subdomain, "error": str(e)})
                
                # SSL
                try:
                    ssl_result = await self.ssl_scanner.run_with_retry(subdomain)
                    if ssl_result.get("success"):
                        results["ssl_certificates"][subdomain] = ssl_result.get("certificate")
                except Exception as e:
                    results["errors"].append({"scanner": "ssl", "target": subdomain, "error": str(e)})
                
                # Ports
                try:
                    port_result = await self.port_scanner.run_with_retry(subdomain, scan_type="quick")
                    if port_result.get("success"):
                        results["ports"][subdomain] = port_result.get("ports", [])
                        # Track HTTP URLs for nuclei
                        for port_info in port_result.get("ports", []):
                            port = port_info.get("port")
                            if port in (80, 443, 8080, 8443):
                                scheme = "https" if port in (443, 8443) else "http"
                                http_urls.append(f"{scheme}://{subdomain}")
                except Exception as e:
                    results["errors"].append({"scanner": "ports", "target": subdomain, "error": str(e)})
                
                # Technology detection
                try:
                    tech_result = await self.tech_scanner.run_with_retry(subdomain)
                    if tech_result.get("success"):
                        results["technologies"][subdomain] = tech_result.get("technologies", [])
                except Exception as e:
                    results["errors"].append({"scanner": "tech", "target": subdomain, "error": str(e)})
            
            # Step 4: Nuclei vulnerability scanning
            if progress_callback:
                await progress_callback(80, "Running vulnerability scans...")
            
            if http_urls:
                try:
                    nuclei_result = await self.nuclei_scanner.run_with_retry(
                        domain,
                        urls=http_urls[:50]  # Limit to 50 URLs
                    )
                    if nuclei_result.get("success"):
                        vulns = nuclei_result.get("vulnerabilities", [])
                        if vulns:
                            results["vulnerabilities"][domain] = vulns
                except Exception as e:
                    results["errors"].append({"scanner": "nuclei", "error": str(e)})
            
            # Step 5: Calculate risk score
            if progress_callback:
                await progress_callback(95, "Calculating risk score...")
            
            risk = calculate_risk(results)
            results["risk_score"] = {
                "overall": risk["risk_score"],
                "label": risk["label"],
                "breakdown": {f["category"]: f["points"] for f in risk["findings"]},
                "factors": [f["detail"] for f in risk["findings"]],
            }
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["success"] = True
            
            if progress_callback:
                await progress_callback(100, "Scan completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results
    
    async def run_quick_scan(
        self,
        domain: str,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Run a quick scan — reduced port set, skip nuclei, skip WHOIS."""
        from app.scanners.subdomain import SubdomainScanner
        from app.scanners.dns import DNSScanner
        from app.scanners.ssl_check import SSLScanner
        from app.scanners.ports import PortScanner
        from app.scanners.tech import TechScanner

        results: Dict[str, Any] = {
            "success": True,
            "subdomains": [],
            "dns_records": {},
            "ssl_certificates": {},
            "ports": {},
            "technologies": {},
            "vulnerabilities": {},
            "risk_score": {},
        }

        try:
            if progress_callback:
                await progress_callback(5, "Starting quick scan...")

            # Step 1: Subdomain discovery only (crt.sh, skip OTX/HackerTarget for speed)
            subdomain_scanner = SubdomainScanner()
            subdomains = await subdomain_scanner.scan(domain, use_all_sources=False)
            results["subdomains"] = subdomains

            if progress_callback:
                await progress_callback(30, f"Found {len(subdomains)} subdomains")

            # Step 2: Quick port scan (top 10 ports only)
            port_scanner = PortScanner()
            quick_ports = [80, 443, 22, 8080, 8443, 21, 25, 53, 3306, 5432]

            # Step 3: DNS + SSL + Tech + Quick ports per subdomain
            total = max(len(subdomains), 1)
            for i, sub in enumerate(subdomains[:20]):  # Limit to top 20 subdomains for quick scan
                hostname = sub if isinstance(sub, str) else sub.get("hostname", sub)
                pct = 30 + int((i / total) * 60)
                if progress_callback:
                    await progress_callback(pct, f"Scanning {hostname}")

                # DNS
                dns_scanner = DNSScanner()
                dns = await dns_scanner.scan(hostname)
                if dns:
                    results["dns_records"][hostname] = dns

                # SSL
                ssl_scanner = SSLScanner()
                cert = await ssl_scanner.scan(hostname)
                if cert:
                    results["ssl_certificates"][hostname] = cert

                # Quick port scan
                port_result = await port_scanner.scan(hostname, quick_ports)
                if port_result:
                    results["ports"][hostname] = port_result

                # Tech detection
                tech_scanner = TechScanner()
                techs = await tech_scanner.scan(hostname)
                if techs:
                    results["technologies"][hostname] = techs

            # Step 4: Risk score (skip nuclei for quick scan)
            from app.risk_scorer import calculate_risk
            results["risk_score"] = calculate_risk(results)

            if progress_callback:
                await progress_callback(100, "Quick scan completed")

            return results

        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results
