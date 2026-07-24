from app.scanners.base import BaseScanner
from app.scanners.subdomain import SubdomainScanner
from app.scanners.subdomain_bruteforce import SubdomainBruteforceScanner
from app.scanners.subdomain_permutations import SubdomainPermutationScanner
from app.scanners.dns import DNSScanner
from app.scanners.whois import WhoisScanner
from app.scanners.ssl_check import SSLScanner
from app.scanners.ports import PortScanner
from app.scanners.tech import TechScanner
from app.scanners.security_findings import SecurityFindingsScanner
from app.scanners.runner import ScanRunner
from app.scanners.registry import registry, discovery_manifest

# ── Scanner v2 imports ──
from app.scanners.v2.base import EnhancedBaseScanner, ScanResult as ScanResultV2, ScannerMetrics
from app.scanners.v2.registry import registry as v2_registry, ScannerCategory as ScannerCategoryV2
from app.scanners.v2.pipeline import ScanPipeline, PipelineStage, PipelineResult
from app.scanners.v2.risk_engine import risk_engine
from app.scanners.v2.asset_discovery import AdvancedAssetDiscoveryScanner
from app.scanners.v2.subdomain_intel import SubdomainIntelligenceScanner
from app.scanners.v2.network_intel import NetworkIntelligenceScanner
from app.scanners.v2.tech_intel import TechnologyIntelligenceScanner
from app.scanners.v2.cert_intel import CertificateIntelligenceScanner
from app.scanners.v2.graph_intel import AttackSurfaceGraph, build_graph_from_scan
from app.scanners.v2.monitoring import ContinuousMonitor
from app.scanners.v2.ai_analyst import SecurityAnalyst
from app.scanners.v2.runner import EnhancedScanRunner, enhanced_runner
from app.scanners.v2_runner import V2ScanRunner
from app.scanners.v2.dns_intel import DNSIntelligenceScanner
from app.scanners.v2.nmap_intel import NmapIntelligenceScanner
from app.scanners.v2.zone_transfer import ZoneTransferScanner
from app.scanners.v2.whois_intel import WhoisIntelligenceScanner
from app.scanners.v2.cve_intel import CVECorrelationScanner
from app.scanners.v2.security_intel import SecurityFindingsScanner as SecurityFindingsV2


def load_plugins() -> None:
    """Ensure all built-in discovery plugins are registered.

    Scanner modules self-register on import; this function exists so callers
    can force registration deterministically and is safe to call repeatedly.
    """
    return None


__all__ = [
    # ── v1 scanners ──
    "BaseScanner",
    "SubdomainScanner",
    "SubdomainBruteforceScanner",
    "SubdomainPermutationScanner",
    "DNSScanner",
    "WhoisScanner",
    "SSLScanner",
    "PortScanner",
    "TechScanner",
    "SecurityFindingsScanner",
    "ScanRunner",
    "registry",
    "discovery_manifest",
    "load_plugins",
    # ── v2 scanners ──
    "EnhancedBaseScanner",
    "ScanResultV2",
    "ScannerMetrics",
    "v2_registry",
    "ScannerCategoryV2",
    "ScanPipeline",
    "PipelineStage",
    "PipelineResult",
    "risk_engine",
    "AdvancedAssetDiscoveryScanner",
    "SubdomainIntelligenceScanner",
    "NetworkIntelligenceScanner",
    "TechnologyIntelligenceScanner",
    "CertificateIntelligenceScanner",
    "AttackSurfaceGraph",
    "build_graph_from_scan",
    "ContinuousMonitor",
    "SecurityAnalyst",
    "EnhancedScanRunner",
    "enhanced_runner",
    "V2ScanRunner",
    "DNSIntelligenceScanner",
    "NmapIntelligenceScanner",
    "ZoneTransferScanner",
    "WhoisIntelligenceScanner",
    "CVECorrelationScanner",
    "SecurityFindingsV2",
]
