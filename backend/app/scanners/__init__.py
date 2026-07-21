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

# Importing the scanner modules above registers their plugins via the
# @register_scanner decorator side effects. ``load_plugins`` is a no-op hook
# kept for explicit initialization (and future entry-point discovery).
def load_plugins() -> None:
    """Ensure all built-in discovery plugins are registered.

    Scanner modules self-register on import; this function exists so callers
    can force registration deterministically and is safe to call repeatedly.
    """
    return None


__all__ = [
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
]
