"""OSINT lookup engine: public, passive intelligence about a domain.

Everything here comes from third-party public datasets or public DNS. The
engine never opens a connection to the target's own servers:
port, banner and web checks belong to the scan engines. Each fact carries the
source it came from and a link a person can open to check it.

Sources (see ``SOURCE_CATALOG``):

* Subdomains      -> crt.sh and Cert Spotter (certificate transparency),
                     HackerTarget host search, AlienVault OTX passive DNS,
                     RapidDNS, Wayback Machine
* Certificates    -> crt.sh (falls back to Cert Spotter)
* DNS / email     -> public DNS (A/AAAA/MX/NS/TXT/CNAME/CAA/SOA, DMARC, SPF, DKIM)
* Exposure        -> Shodan InternetDB (open ports, CPEs, CVEs Shodan matched
                     from the versions it observed) + Shodan CVEDB for CVSS,
                     EPSS and CISA KEV status
* Registration    -> RDAP (registrar, dates, DNSSEC, abuse contact)
* Hosting / rep.  -> ipinfo, RDAP for IP networks, GreyNoise Community,
                     AbuseIPDB (key), HackerTarget reverse IP
* Takeover risk   -> dangling CNAMEs (public DNS)
* Look-alikes     -> typo/homoglyph/TLD variants that resolve (public DNS)
* Company profile -> Wikidata (founded, industry, owners, parent, HQ, size)
                     matched by the official website, and GLEIF (legal entity
                     and parent companies) via the company's LEI
* Breaches        -> Have I Been Pwned (site breaches free; domain search needs key)
* Blocklists      -> URLhaus, ThreatFox (abuse.ch key)

A source that needs a key and has none reports ``needs_key``; it never
returns invented results.
"""
from __future__ import annotations

import concurrent.futures as cf
import ipaddress
import logging
import re
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

log = logging.getLogger("osint")

# Bump when the result shape or meaning changes so cached results from an
# older engine are not served.
ENGINE_VERSION = 3

_USER_AGENT = {
    "User-Agent": "CAZO-EASM-OSINT/2.0 (+https://cazoeasm.io)",
}
_TIMEOUT = 15
_OVERALL_TIMEOUT = 120

_MAX_RESOLVE = 60          # subdomains resolved via public DNS
_MAX_IPS = 12              # IPs enriched with InternetDB
_MAX_REP_IPS = 4           # IPs checked for reputation
_MAX_REVERSE_IPS = 3       # IPs checked for co-hosted domains
_MAX_CVE_DETAILS = 40      # CVEs enriched via CVEDB
_MAX_CERTS = 50
_MAX_COHOSTED = 50

_SERVICE_NAMES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 111: "RPC", 135: "MSRPC", 139: "NetBIOS", 143: "IMAP",
    161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB", 465: "SMTPS",
    587: "SMTP", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    2049: "NFS", 2375: "Docker", 2376: "Docker-TLS", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5601: "Kibana", 5900: "VNC",
    5985: "WinRM", 6379: "Redis", 6443: "Kubernetes", 8080: "HTTP-ALT",
    8443: "HTTPS-ALT", 9200: "Elasticsearch", 11211: "Memcached",
    27017: "MongoDB",
}

# Services that should almost never face the internet.
_RISKY_PORTS = {
    23: "Telnet", 135: "MSRPC", 139: "NetBIOS", 445: "SMB", 1433: "MSSQL",
    1521: "Oracle", 2049: "NFS", 2375: "Docker API", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 5985: "WinRM",
    6379: "Redis", 9200: "Elasticsearch", 11211: "Memcached", 27017: "MongoDB",
}

# Providers recognised from passive signals (CNAME targets, NS, ASN org).
_CDN_SIGNATURES = {
    "Cloudflare": ("cloudflare", "cdn.cloudflare.net", "as13335"),
    "Akamai": ("akamai", "edgekey.net", "edgesuite.net", "akamaiedge.net"),
    "Amazon CloudFront": ("cloudfront.net",),
    "Fastly": ("fastly", "fastly.net"),
    "Imperva Incapsula": ("incapdns.net", "incapsula", "imperva"),
    "Azure Front Door": ("azurefd.net", "azureedge.net"),
    "Google Cloud CDN": ("googleusercontent.com", "ghs.googlehosted.com"),
    "Sucuri": ("sucuri",),
    "StackPath": ("stackpathdns.com", "stackpath"),
    "Vercel": ("vercel-dns.com", "vercel"),
    "Netlify": ("netlify",),
}


# --------------------------------------------------------------------------- #
# Source catalog
# --------------------------------------------------------------------------- #
def _settings():
    from app.config import settings
    return settings


def _key(name: str) -> str:
    return (getattr(_settings(), name, "") or "").strip()


# id -> description. ``link`` is a page a person can open for the queried
# domain; "{domain}" is substituted. ``key_env`` names the env var holding a
# key; ``key_required`` says whether the source works without it.
SOURCE_CATALOG: Dict[str, Dict[str, Any]] = {
    "crtsh": {"name": "crt.sh (certificate transparency)", "category": "subdomains, certificates",
              "home": "https://crt.sh/", "link": "https://crt.sh/?q=%25.{domain}"},
    "certspotter": {"name": "Cert Spotter (certificate transparency)", "category": "subdomains, certificates",
                    "home": "https://sslmate.com/certspotter/",
                    "link": "https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"},
    "hackertarget": {"name": "HackerTarget host search", "category": "subdomains",
                     "home": "https://hackertarget.com/find-dns-host-records/",
                     "link": "https://api.hackertarget.com/hostsearch/?q={domain}"},
    "alienvault": {"name": "AlienVault OTX passive DNS", "category": "subdomains",
                   "home": "https://otx.alienvault.com/", "link": "https://otx.alienvault.com/indicator/domain/{domain}",
                   "key_env": "OTX_API_KEY", "key_required": False},
    "rapiddns": {"name": "RapidDNS", "category": "subdomains",
                 "home": "https://rapiddns.io/", "link": "https://rapiddns.io/subdomain/{domain}?full=1"},
    "wayback": {"name": "Internet Archive Wayback Machine", "category": "historical hosts",
                "home": "https://web.archive.org/", "link": "https://web.archive.org/web/*/*.{domain}*"},
    "dns": {"name": "Public DNS", "category": "DNS records, email security",
            "home": "https://dns.google/", "link": "https://dns.google/query?name={domain}"},
    "shodan-internetdb": {"name": "Shodan InternetDB", "category": "open ports, products, CVEs",
                          "home": "https://internetdb.shodan.io/", "link": "https://internetdb.shodan.io/"},
    "shodan-cvedb": {"name": "Shodan CVEDB (CVSS, EPSS, CISA KEV)", "category": "CVE details",
                     "home": "https://cvedb.shodan.io/", "link": "https://cvedb.shodan.io/"},
    "rdap": {"name": "RDAP (registry WHOIS)", "category": "registration",
             "home": "https://about.rdap.org/", "link": "https://rdap.org/domain/{domain}"},
    "ipinfo": {"name": "ipinfo.io", "category": "hosting, ASN, location",
               "home": "https://ipinfo.io/", "link": "https://ipinfo.io/",
               "key_env": "IPINFO_TOKEN", "key_required": False},
    "greynoise": {"name": "GreyNoise Community", "category": "IP reputation",
                  "home": "https://viz.greynoise.io/", "link": "https://viz.greynoise.io/",
                  "key_env": "GREYNOISE_API_KEY", "key_required": False},
    "abuseipdb": {"name": "AbuseIPDB", "category": "IP reputation",
                  "home": "https://www.abuseipdb.com/", "link": "https://www.abuseipdb.com/",
                  "key_env": "ABUSEIPDB_API_KEY", "key_required": True},
    "reverse-ip": {"name": "HackerTarget reverse IP", "category": "co-hosted domains",
                   "home": "https://hackertarget.com/reverse-ip-lookup/",
                   "link": "https://hackertarget.com/reverse-ip-lookup/"},
    "rdap-ip": {"name": "RDAP (IP network owner)", "category": "netblocks, hosting",
                "home": "https://about.rdap.org/", "link": "https://rdap.org/"},
    "takeover": {"name": "Dangling CNAME check (public DNS)", "category": "subdomain takeover risk",
                 "home": "https://github.com/EdOverflow/can-i-take-over-xyz",
                 "link": "https://github.com/EdOverflow/can-i-take-over-xyz"},
    "lookalikes": {"name": "Look-alike domains (public DNS)", "category": "typosquatting, phishing",
                   "home": "https://dnstwister.report/", "link": "https://dnstwister.report/search?ed={domain}"},
    "wikidata": {"name": "Wikidata (company profile)", "category": "founded, industry, owners",
                 "home": "https://www.wikidata.org/",
                 "link": "https://www.wikidata.org/w/index.php?search=haswbstatement%3AP856%3Dhttps%3A%2F%2F{domain}"},
    "gleif": {"name": "GLEIF (legal entity, LEI)", "category": "legal entity, parent companies",
              "home": "https://search.gleif.org/", "link": "https://search.gleif.org/"},
    "hibp": {"name": "Have I Been Pwned: breached sites", "category": "breaches of this domain's site",
             "home": "https://haveibeenpwned.com/PwnedWebsites", "link": "https://haveibeenpwned.com/PwnedWebsites"},
    "hibp-domain": {"name": "Have I Been Pwned: domain search", "category": "breached email addresses",
                    "home": "https://haveibeenpwned.com/DomainSearch",
                    "link": "https://haveibeenpwned.com/DomainSearch",
                    "key_env": "HIBP_API_KEY", "key_required": True},
    "urlhaus": {"name": "abuse.ch URLhaus", "category": "malware URLs, blocklists",
                "home": "https://urlhaus.abuse.ch/", "link": "https://urlhaus.abuse.ch/host/{domain}/",
                "key_env": "ABUSECH_AUTH_KEY", "key_required": True},
    "threatfox": {"name": "abuse.ch ThreatFox", "category": "threat indicators",
                  "home": "https://threatfox.abuse.ch/", "link": "https://threatfox.abuse.ch/browse/",
                  "key_env": "ABUSECH_AUTH_KEY", "key_required": True},
}

# Shown so customers know what exists but is not integrated (paid / licensed).
SUBSCRIPTION_SOURCES = [
    {"name": "Spamhaus DBL / ZEN", "why": "Domain and IP blocklists; commercial use needs a Spamhaus DQS subscription.",
     "home": "https://www.spamhaus.com/data-access/"},
    {"name": "Google Web Risk", "why": "Unsafe-site lists for commercial products (Safe Browsing is non-commercial only); paid Google Cloud API.",
     "home": "https://cloud.google.com/web-risk"},
    {"name": "OpenCorporates / national company registries (e.g. SSM Malaysia)",
     "why": "Official incorporation dates, directors and shareholders; commercial API access is paid.",
     "home": "https://opencorporates.com/"},
    {"name": "SecurityTrails / DomainTools", "why": "Historical DNS and WHOIS history; paid API.",
     "home": "https://securitytrails.com/"},
]

# CNAME targets whose service can be claimed by someone else when the
# resource is gone (target does not resolve). Source: can-i-take-over-xyz.
_TAKEOVER_SERVICES = {
    "azurewebsites.net": "Azure App Service", "cloudapp.net": "Azure Cloud Services",
    "cloudapp.azure.com": "Azure VM", "trafficmanager.net": "Azure Traffic Manager",
    "blob.core.windows.net": "Azure Blob Storage", "azure-api.net": "Azure API Management",
    "azureedge.net": "Azure CDN", "azurecontainer.io": "Azure Container Instances",
    "s3.amazonaws.com": "AWS S3", "s3-website": "AWS S3 website", "elasticbeanstalk.com": "AWS Elastic Beanstalk",
    "herokuapp.com": "Heroku", "herokudns.com": "Heroku", "github.io": "GitHub Pages",
    "ghost.io": "Ghost", "myshopify.com": "Shopify", "surge.sh": "Surge", "bitbucket.io": "Bitbucket",
    "pantheonsite.io": "Pantheon", "unbouncepages.com": "Unbounce", "readthedocs.io": "Read the Docs",
    "helpscoutdocs.com": "Help Scout", "zendesk.com": "Zendesk", "wordpress.com": "WordPress.com",
    "netlify.app": "Netlify", "netlify.com": "Netlify", "fly.dev": "Fly.io", "ngrok.io": "ngrok",
    "webflow.io": "Webflow", "strikinglydns.com": "Strikingly", "launchrock.com": "LaunchRock",
}

def _source_link(source_id: str, domain: str) -> Optional[str]:
    meta = SOURCE_CATALOG.get(source_id)
    if not meta:
        return None
    return meta["link"].replace("{domain}", quote(domain))


def build_sources(domain: str, status: Dict[str, str]) -> List[Dict[str, Any]]:
    """Describe every source: what it is, what it returned and where to check it."""
    out: List[Dict[str, Any]] = []
    for sid, meta in SOURCE_CATALOG.items():
        key_env = meta.get("key_env")
        has_key = bool(key_env and _key(key_env))
        if key_env and meta.get("key_required") and not has_key and sid not in status:
            status[sid] = "needs_key"
        out.append({
            "id": sid,
            "name": meta["name"],
            "category": meta["category"],
            "status": status.get(sid, "not_run"),
            "link": _source_link(sid, domain),
            "home": meta["home"],
            "key_env": key_env,
            "key_required": bool(meta.get("key_required")),
            "key_configured": has_key if key_env else None,
            "passive": True,
        })
    return out


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class SubdomainResult:
    hostname: str
    ips: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    cname: Optional[str] = None


@dataclass
class CertResult:
    issuer: Optional[str] = None
    subject: Optional[str] = None
    san: List[str] = field(default_factory=list)
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    serial: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class PortResult:
    port: int
    state: str  # open | closed | filtered
    service: Optional[str] = None
    banner: Optional[str] = None
    tls: bool = False
    title: Optional[str] = None
    ip: Optional[str] = None
    hostnames: List[str] = field(default_factory=list)
    source: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class VulnResult:
    cve_id: str
    description: str
    severity: Optional[str] = None
    cvss: Optional[float] = None
    published: Optional[str] = None
    is_kev: bool = False
    source: str = "Shodan InternetDB"
    epss: Optional[float] = None
    ips: List[str] = field(default_factory=list)
    confidence: str = "potential"   # potential = matched from an observed version, not verified
    source_url: Optional[str] = None
    reference_url: Optional[str] = None


@dataclass
class IntelResult:
    query: str
    subdomains: List[SubdomainResult] = field(default_factory=list)
    dns_records: Dict[str, List[str]] = field(default_factory=dict)
    certificates: List[CertResult] = field(default_factory=list)
    ports: List[PortResult] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    technology_details: List[Dict[str, Any]] = field(default_factory=list)
    vulnerabilities: List[VulnResult] = field(default_factory=list)
    ip_reputation: List[Dict[str, Any]] = field(default_factory=list)
    whois: Optional[Dict[str, Any]] = None
    historical_subdomains: List[str] = field(default_factory=list)
    reverse_ip: List[str] = field(default_factory=list)
    cohosted_domains: List[Dict[str, Any]] = field(default_factory=list)
    sources_status: Dict[str, str] = field(default_factory=dict)
    # Advanced intelligence
    email_security: Optional[object] = None
    waf_cdn: Optional[object] = None
    security_headers: Optional[object] = None
    sensitive_paths: List[object] = field(default_factory=list)
    web_fingerprint: Optional[object] = None
    reverse_dns_range: List[str] = field(default_factory=list)
    risk_score: Optional[object] = None
    # Deeper passive intelligence
    ip_networks: List[Dict[str, Any]] = field(default_factory=list)
    takeover_candidates: List[Dict[str, Any]] = field(default_factory=list)
    lookalikes: List[Dict[str, Any]] = field(default_factory=list)
    breaches: List[Dict[str, Any]] = field(default_factory=list)
    threat_reports: List[Dict[str, Any]] = field(default_factory=list)
    company: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _http_get(url: str, params: Optional[dict] = None, timeout: int = _TIMEOUT,
              headers: Optional[dict] = None):
    h = dict(_USER_AGENT)
    if headers:
        h.update(headers)
    return requests.get(url, params=params, headers=h, timeout=timeout, allow_redirects=True)


def _http_status(code: int) -> str:
    if code == 429:
        return "rate_limited"
    if code in (401, 403):
        return "needs_key" if code == 401 else "refused"
    return f"http_{code}"


def _in_domain(host: str, domain: str) -> bool:
    """True when ``host`` is ``domain`` or one of its subdomains (no substring matches)."""
    host = (host or "").strip().lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def _clean_host(name: str) -> str:
    name = (name or "").strip().lower().rstrip(".")
    while name.startswith("*."):
        name = name[2:]
    return name


def _is_public_ip(ip: str) -> bool:
    try:
        from app.core.target_guard import is_blocked_ip
        ipaddress.ip_address(ip)
        return not is_blocked_ip(ip)
    except Exception:
        return False


def _dns_query(name: str, rtype: str, timeout: float = 4.0) -> List[str]:
    try:
        import dns.resolver  # type: ignore
        ans = dns.resolver.resolve(name, rtype, lifetime=timeout)
        return [r.to_text() for r in ans]
    except Exception:
        return []


def _dns_resolve(host: str, timeout: float = 5.0) -> list:
    """Resolve hostname to A records (socket.getaddrinfo-like tuples)."""
    return [("", 0, 0, "", (ip, 0)) for ip in _dns_query(host, "A", timeout)]


def _normalize_domain(raw: str) -> str:
    raw = (raw or "").strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0].split(":")[0].rstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    if "." not in raw and raw:
        for tld in ("com", "org", "net", "io", "co", "ai", "app", "dev", "my", "com.my", "sa", "ae"):
            candidate = f"{raw}.{tld}"
            if _dns_resolve(candidate, timeout=3):
                return candidate
    return raw


def _cvss_severity(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


def _parse_cpe(cpe: str) -> Dict[str, Optional[str]]:
    """``cpe:/a:nginx:nginx:1.18.0`` or ``cpe:2.3:a:...`` -> vendor/product/version."""
    parts = cpe.split(":")
    if cpe.startswith("cpe:2.3:"):
        parts = parts[1:]
    # parts: ['cpe', '/a', vendor, product, version?]
    vendor = parts[2] if len(parts) > 2 else None
    product = parts[3] if len(parts) > 3 else None
    version = parts[4] if len(parts) > 4 and parts[4] not in ("*", "-", "") else None
    return {"vendor": vendor, "product": product, "version": version}


# --------------------------------------------------------------------------- #
# Passive collectors. Each records its outcome in ``status[source_id]``.
# --------------------------------------------------------------------------- #
def _fetch_crtsh(domain: str, status: Dict[str, str]) -> List[dict]:
    try:
        r = _http_get("https://crt.sh/", params={"q": f"%.{domain}", "output": "json"}, timeout=30)
        if r.status_code == 200:
            rows = r.json() or []
            status["crtsh"] = "ok" if rows else "no_results"
            return rows
        status["crtsh"] = _http_status(r.status_code)
    except Exception as e:
        status["crtsh"] = f"error: {type(e).__name__}"
    return []


def _fetch_certspotter(domain: str, status: Dict[str, str]) -> List[dict]:
    try:
        r = _http_get("https://api.certspotter.com/v1/issuances",
                      params=[("domain", domain), ("include_subdomains", "true"),
                              ("expand", "dns_names"), ("expand", "issuer")])
        if r.status_code == 200:
            rows = r.json() or []
            status["certspotter"] = "ok" if rows else "no_results"
            return rows
        status["certspotter"] = _http_status(r.status_code)
    except Exception as e:
        status["certspotter"] = f"error: {type(e).__name__}"
    return []


def _src_hackertarget(domain: str, status: Dict[str, str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    try:
        r = _http_get("https://api.hackertarget.com/hostsearch/", params={"q": domain})
        body = (r.text or "").strip()
        if r.status_code != 200:
            status["hackertarget"] = _http_status(r.status_code)
        elif body.lower().startswith(("api count exceeded", "error")):
            status["hackertarget"] = "rate_limited" if "count" in body.lower() else "no_results"
        else:
            for line in body.splitlines():
                if "," in line:
                    host, ip = line.split(",", 1)
                    host = _clean_host(host)
                    if _in_domain(host, domain):
                        out.setdefault(host, [])
                        if ip.strip():
                            out[host].append(ip.strip())
            status["hackertarget"] = "ok" if out else "no_results"
    except Exception as e:
        status["hackertarget"] = f"error: {type(e).__name__}"
    return out


def _src_alienvault(domain: str, status: Dict[str, str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    headers = {"X-OTX-API-KEY": _key("OTX_API_KEY")} if _key("OTX_API_KEY") else None
    try:
        r = _http_get(f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns",
                      timeout=20, headers=headers)
        if r.status_code == 200:
            for entry in r.json().get("passive_dns", []) or []:
                host = _clean_host(entry.get("hostname", ""))
                if _in_domain(host, domain):
                    out.setdefault(host, [])
                    ip = (entry.get("address") or entry.get("ip") or "").strip()
                    if ip and _is_public_ip(ip) and ip not in out[host]:
                        out[host].append(ip)
            status["alienvault"] = "ok" if out else "no_results"
        else:
            status["alienvault"] = _http_status(r.status_code)
    except Exception as e:
        status["alienvault"] = f"error: {type(e).__name__}"
    return out


def _src_rapiddns(domain: str, status: Dict[str, str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    try:
        r = _http_get(f"https://rapiddns.io/subdomain/{domain}", params={"full": "1"}, timeout=20)
        if r.status_code == 200:
            for m in re.finditer(r"<td>([\w.-]+\." + re.escape(domain) + r")</td>", r.text or ""):
                host = _clean_host(m.group(1))
                if _in_domain(host, domain):
                    out.setdefault(host, [])
            status["rapiddns"] = "ok" if out else "no_results"
        else:
            status["rapiddns"] = _http_status(r.status_code)
    except Exception as e:
        status["rapiddns"] = f"error: {type(e).__name__}"
    return out


def _hosts_from_ct(domain: str, crtsh_rows: List[dict], spotter_rows: List[dict]):
    crt: Dict[str, List[str]] = {}
    spot: Dict[str, List[str]] = {}
    for row in crtsh_rows:
        for part in str(row.get("name_value", "")).split("\n"):
            host = _clean_host(part)
            if _in_domain(host, domain):
                crt.setdefault(host, [])
    for row in spotter_rows:
        for name in row.get("dns_names", []) or []:
            host = _clean_host(name)
            if _in_domain(host, domain):
                spot.setdefault(host, [])
    return crt, spot


def _certs_from_ct(domain: str, crtsh_rows: List[dict], spotter_rows: List[dict]) -> List[CertResult]:
    """Most recent unique certificates from CT logs that cover the domain, newest first."""
    certs: List[CertResult] = []
    seen = set()

    def covers(names) -> bool:
        return any(_in_domain(_clean_host(n), domain) for n in names)

    for row in sorted(crtsh_rows, key=lambda r: str(r.get("not_before", "")), reverse=True):
        if not covers(str(row.get("name_value", "")).split("\n")):
            continue
        serial = str(row.get("serial_number") or "").upper()
        if not serial or serial in seen:
            continue
        seen.add(serial)
        names = sorted({n.strip().lower() for n in str(row.get("name_value", "")).split("\n") if n.strip()})
        cid = row.get("id")
        certs.append(CertResult(
            issuer=row.get("issuer_name"),
            subject=f"CN={row.get('common_name')}" if row.get("common_name") else None,
            san=names,
            not_before=row.get("not_before"),
            not_after=row.get("not_after"),
            serial=serial,
            source="crtsh",
            source_url=f"https://crt.sh/?id={cid}" if cid else None,
        ))
        if len(certs) >= _MAX_CERTS:
            return certs
    if certs:
        return certs
    for row in sorted(spotter_rows, key=lambda r: str(r.get("not_before", "")), reverse=True):
        key = row.get("cert_sha256") or row.get("id")
        if not key or key in seen or not covers(row.get("dns_names", []) or []):
            continue
        seen.add(key)
        names = sorted({n.lower() for n in row.get("dns_names", []) or []})
        issuer = row.get("issuer") or {}
        certs.append(CertResult(
            issuer=issuer.get("name") if isinstance(issuer, dict) else None,
            subject=f"CN={names[0]}" if names else None,
            san=names,
            not_before=row.get("not_before"),
            not_after=row.get("not_after"),
            serial=None,
            source="certspotter",
            source_url=f"https://crt.sh/?sha256={row['cert_sha256']}" if row.get("cert_sha256") else None,
        ))
        if len(certs) >= _MAX_CERTS:
            break
    return certs


def _resolve_dns(domain: str) -> Dict[str, List[str]]:
    records: Dict[str, List[str]] = {}
    for t in ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "CAA", "SOA"):
        vals = [v.rstrip(".") for v in _dns_query(domain, t, 4.0)]
        if vals:
            records[t] = vals
    return records


def _resolve_host(sub: SubdomainResult) -> SubdomainResult:
    cname = _dns_query(sub.hostname, "CNAME", 3.0)
    if cname:
        sub.cname = cname[0].rstrip(".").lower()
    for ip in _dns_query(sub.hostname, "A", 3.0) + _dns_query(sub.hostname, "AAAA", 3.0):
        if ip not in sub.ips:
            sub.ips.append(ip)
    return sub


def _collect_wayback(domain: str, status: Dict[str, str]) -> List[str]:
    """Hostnames the Internet Archive has seen under the domain."""
    historical: List[str] = []
    try:
        r = _http_get(
            "https://web.archive.org/cdx/search/cdx",
            params={"url": f"*.{domain}", "output": "json", "limit": 2000, "fl": "original",
                    "collapse": "urlkey"},
            timeout=25,
        )
        if r.status_code == 200:
            seen = set()
            for row in (r.json() or [])[1:]:
                if row and row[0]:
                    m = re.match(r"(?:https?://)?([^:/?#]+)", row[0])
                    if m:
                        host = _clean_host(m.group(1))
                        if _in_domain(host, domain) and host not in seen:
                            seen.add(host)
                            historical.append(host)
            status["wayback"] = "ok" if historical else "no_results"
        else:
            status["wayback"] = _http_status(r.status_code)
    except Exception as e:
        status["wayback"] = f"error: {type(e).__name__}"
    return sorted(historical)


def _vcard_field(entity: dict, name: str) -> Optional[str]:
    card = entity.get("vcardArray")
    if isinstance(card, list) and len(card) > 1 and isinstance(card[1], list):
        for item in card[1]:
            if isinstance(item, list) and len(item) >= 4 and item[0] == name:
                val = item[3]
                if isinstance(val, list):
                    val = " ".join(str(v) for v in val if v)
                return str(val) if val else None
    return None


def _rdap_entities(entities: List[dict]):
    """Flatten RDAP entities (they nest, e.g. registrar -> abuse contact)."""
    for ent in entities or []:
        yield ent
        yield from _rdap_entities(ent.get("entities") or [])


def _collect_whois(domain: str, status: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Registration data via RDAP (rdap.org redirects to the registry's server)."""
    try:
        r = _http_get(f"https://rdap.org/domain/{domain}", timeout=20,
                      headers={"Accept": "application/rdap+json"})
        if r.status_code != 200:
            status["rdap"] = "no_results" if r.status_code == 404 else _http_status(r.status_code)
            return None
        data = r.json()
        events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", []) or []}
        registrar = registrar_iana = abuse_email = registrant_org = None
        for ent in _rdap_entities(data.get("entities") or []):
            roles = [v.lower() for v in ent.get("roles", []) or []]
            if "registrar" in roles and not registrar:
                registrar = _vcard_field(ent, "fn") or ent.get("handle")
                for pid in ent.get("publicIds", []) or []:
                    if "iana" in str(pid.get("type", "")).lower():
                        registrar_iana = pid.get("identifier")
            if "abuse" in roles and not abuse_email:
                abuse_email = _vcard_field(ent, "email")
            if "registrant" in roles and not registrant_org:
                registrant_org = _vcard_field(ent, "org") or _vcard_field(ent, "fn")
        secure = data.get("secureDNS") or {}
        self_link = next((ln.get("href") for ln in data.get("links", []) or []
                          if ln.get("rel") == "self" and ln.get("href")), None)
        status["rdap"] = "ok"
        return {
            "name": (data.get("ldhName") or domain).lower(),
            "status": data.get("status", []) or [],
            "nameservers": [str(n.get("ldhName", "")).lower() for n in data.get("nameservers", []) or []],
            "registration_date": events.get("registration"),
            "expiration_date": events.get("expiration"),
            "last_changed": events.get("last changed"),
            "registrar": registrar,
            "registrar_iana_id": registrar_iana,
            "registrant_org": registrant_org,
            "abuse_email": abuse_email,
            "dnssec": secure.get("delegationSigned"),
            "handle": data.get("handle"),
            "source": "rdap",
            "source_url": self_link or getattr(r, "url", None) or f"https://rdap.org/domain/{domain}",
        }
    except Exception as e:
        status["rdap"] = f"error: {type(e).__name__}"
    return None


def _collect_internetdb(ips: List[str], status: Dict[str, str]) -> Dict[str, dict]:
    """Shodan InternetDB: what Shodan's own crawlers last saw on each IP."""
    out: Dict[str, dict] = {}
    errors = 0

    def one(ip: str):
        try:
            r = _http_get(f"https://internetdb.shodan.io/{ip}", timeout=12)
            if r.status_code == 200:
                return ip, r.json(), None
            if r.status_code == 404:
                return ip, None, None
            return ip, None, _http_status(r.status_code)
        except Exception as e:
            return ip, None, f"error: {type(e).__name__}"

    last_err = None
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for ip, data, err in ex.map(one, ips):
            if data:
                out[ip] = data
            if err:
                errors += 1
                last_err = err
    if out:
        status["shodan-internetdb"] = "ok"
    elif errors and errors == len(ips):
        status["shodan-internetdb"] = last_err or "error"
    else:
        status["shodan-internetdb"] = "no_results" if ips else "no_targets"
    return out


def _collect_cve_details(cve_ids: List[str], status: Dict[str, str]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    if not cve_ids:
        status["shodan-cvedb"] = "no_targets"
        return out

    def one(cve: str):
        try:
            r = _http_get(f"https://cvedb.shodan.io/cve/{cve}", timeout=12)
            if r.status_code == 200:
                return cve, r.json()
        except Exception:
            pass
        return cve, None

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for cve, data in ex.map(one, cve_ids[:_MAX_CVE_DETAILS]):
            if data:
                out[cve] = data
    status["shodan-cvedb"] = "ok" if out else "error"
    return out


def _collect_ip_reputation(ips: List[str], status: Dict[str, str]) -> List[Dict[str, Any]]:
    """Hosting and reputation for each IP. Key-gated sources say so instead of guessing."""
    results: List[Dict[str, Any]] = []
    ipinfo_token = _key("IPINFO_TOKEN")
    abuse_key = _key("ABUSEIPDB_API_KEY")
    gn_key = _key("GREYNOISE_API_KEY")
    if not abuse_key:
        status["abuseipdb"] = "needs_key"

    for ip in ips:
        rep: Dict[str, Any] = {"ip": ip, "country": None, "org": None, "asn": None,
                               "abuse_confidence": None, "links": {}}
        try:
            r = _http_get(f"https://ipinfo.io/{ip}/json", timeout=12,
                          params={"token": ipinfo_token} if ipinfo_token else None)
            if r.status_code == 200:
                d = r.json()
                org = d.get("org") or ""
                m = re.match(r"^(AS\d+)\s+(.*)$", org)
                rep.update({
                    "country": d.get("country"), "city": d.get("city"), "region": d.get("region"),
                    "org": m.group(2) if m else (org or None), "asn": m.group(1) if m else None,
                    "hostname": d.get("hostname"), "anycast": bool(d.get("anycast")),
                })
                rep["links"]["ipinfo"] = f"https://ipinfo.io/{ip}"
                status["ipinfo"] = "ok"
            else:
                status.setdefault("ipinfo", _http_status(r.status_code))
        except Exception as e:
            status.setdefault("ipinfo", f"error: {type(e).__name__}")

        if abuse_key:
            try:
                r = _http_get("https://api.abuseipdb.com/api/v2/check", timeout=12,
                              params={"ipAddress": ip, "maxAgeInDays": 90},
                              headers={"Key": abuse_key, "Accept": "application/json"})
                if r.status_code == 200:
                    d = r.json().get("data", {}) or {}
                    rep.update({
                        "abuse_confidence": d.get("abuseConfidenceScore"),
                        "total_reports": d.get("totalReports"),
                        "usage_type": d.get("usageType"),
                        "is_whitelisted": d.get("isWhitelisted"),
                        "is_tor": d.get("isTor"),
                    })
                    rep["links"]["abuseipdb"] = f"https://www.abuseipdb.com/check/{ip}"
                    status["abuseipdb"] = "ok"
                else:
                    status.setdefault("abuseipdb", _http_status(r.status_code))
            except Exception as e:
                status.setdefault("abuseipdb", f"error: {type(e).__name__}")

        try:
            r = _http_get(f"https://api.greynoise.io/v3/community/{ip}", timeout=12,
                          headers={"key": gn_key} if gn_key else None)
            if r.status_code in (200, 404):
                d = r.json() if r.content else {}
                rep.update({
                    "noise": d.get("noise"), "riot": d.get("riot"),
                    "classification": d.get("classification"), "greynoise_name": d.get("name"),
                })
                rep["links"]["greynoise"] = f"https://viz.greynoise.io/ip/{ip}"
                status["greynoise"] = "ok"
            else:
                status.setdefault("greynoise", _http_status(r.status_code))
        except Exception as e:
            status.setdefault("greynoise", f"error: {type(e).__name__}")

        results.append(rep)
    return results


def _detect_cdn(texts: List[str]) -> Optional[str]:
    blob = " ".join(t.lower() for t in texts if t)
    for name, sigs in _CDN_SIGNATURES.items():
        if any(s in blob for s in sigs):
            return name
    return None


def _collect_reverse_ip(ips: List[str], domain: str, cdn_ips: set,
                        status: Dict[str, str]) -> List[Dict[str, Any]]:
    """Other domains on the same IPs. Skipped for CDN/shared-edge IPs, where it is noise."""
    out: List[Dict[str, Any]] = []
    seen = set()
    targets = [ip for ip in ips if ip not in cdn_ips and ":" not in ip][:_MAX_REVERSE_IPS]
    if not targets:
        status["reverse-ip"] = "skipped_cdn" if ips else "no_targets"
        return out
    for ip in targets:
        try:
            r = _http_get("https://api.hackertarget.com/reverseiplookup/", params={"q": ip}, timeout=15)
            body = (r.text or "").strip()
            if r.status_code != 200:
                status["reverse-ip"] = _http_status(r.status_code)
                continue
            if body.lower().startswith(("api count exceeded", "error", "no dns")):
                status.setdefault("reverse-ip", "rate_limited" if "count" in body.lower() else "no_results")
                continue
            for line in body.splitlines():
                host = _clean_host(line)
                if host and host not in seen and "." in host:
                    seen.add(host)
                    out.append({
                        "domain": host, "ip": ip, "same_domain": _in_domain(host, domain),
                        "source": "reverse-ip",
                        "source_url": f"https://hackertarget.com/reverse-ip-lookup/?q={ip}",
                    })
            status["reverse-ip"] = "ok"
        except Exception as e:
            status["reverse-ip"] = f"error: {type(e).__name__}"
        if len(out) >= _MAX_COHOSTED:
            break
    status.setdefault("reverse-ip", "no_results")
    return out[:_MAX_COHOSTED]


def _dns_exists(name: str) -> Optional[bool]:
    """True if the name exists, False on NXDOMAIN, None when DNS could not tell."""
    try:
        import dns.resolver  # type: ignore
        dns.resolver.resolve(name, "A", lifetime=4)
        return True
    except Exception as e:  # noqa: BLE001
        import dns.resolver  # type: ignore
        if isinstance(e, dns.resolver.NXDOMAIN):
            return False
        if isinstance(e, dns.resolver.NoAnswer):
            return True
        return None


def _collect_takeover(subs: List[SubdomainResult], status: Dict[str, str]) -> List[Dict[str, Any]]:
    """Subdomains whose CNAME points at a name that no longer exists."""
    cands = [s for s in subs if s.cname and not s.ips]
    out: List[Dict[str, Any]] = []

    def check(sub: SubdomainResult):
        exists = _dns_exists(sub.cname)
        if exists is not False:
            return None
        service = next((name for suffix, name in _TAKEOVER_SERVICES.items() if suffix in sub.cname), None)
        return {
            "hostname": sub.hostname, "cname": sub.cname, "service": service,
            "severity": "high" if service else "medium",
            "detail": (f"{sub.hostname} points to {sub.cname}, which does not exist. "
                       + (f"If the {service} resource was deleted, someone else may be able to claim it "
                          "and serve content on your subdomain." if service else
                          "Dangling DNS record: remove it or restore the target.")),
            "source": "takeover",
            "source_url": f"https://dns.google/query?name={quote(sub.hostname)}&rr_type=CNAME",
        }

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        out = [r for r in ex.map(check, cands) if r]
    status["takeover"] = f"{len(out)} found" if out else ("ok" if cands else "no_targets")
    return out


def _collect_ip_networks(ips: List[str], status: Dict[str, str]) -> List[Dict[str, Any]]:
    """Owner of the network block for each IP, from the regional registry's RDAP."""
    out: List[Dict[str, Any]] = []

    def one(ip: str):
        try:
            r = _http_get(f"https://rdap.org/ip/{ip}", timeout=15, headers={"Accept": "application/rdap+json"})
            if r.status_code != 200:
                return ip, None, _http_status(r.status_code)
            d = r.json()
            cidrs = [f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}"
                     for c in d.get("cidr0_cidrs", []) or [] if c.get("length") is not None]
            org = None
            for ent in _rdap_entities(d.get("entities") or []):
                roles = [v.lower() for v in ent.get("roles", []) or []]
                if "registrant" in roles or "administrative" in roles:
                    org = _vcard_field(ent, "fn") or ent.get("handle")
                    if org:
                        break
            self_link = next((ln.get("href") for ln in d.get("links", []) or []
                              if ln.get("rel") == "self" and ln.get("href")), None)
            return ip, {
                "ip": ip, "network_name": d.get("name"), "handle": d.get("handle"),
                "range": f"{d.get('startAddress')} - {d.get('endAddress')}" if d.get("startAddress") else None,
                "cidr": cidrs, "country": d.get("country"), "owner": org, "type": d.get("type"),
                "source": "rdap-ip", "source_url": self_link or f"https://rdap.org/ip/{ip}",
            }, None
        except Exception as e:  # noqa: BLE001
            return ip, None, f"error: {type(e).__name__}"

    errs = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for _ip, data, err in ex.map(one, ips):
            if data:
                out.append(data)
            elif err:
                errs.append(err)
    status["rdap-ip"] = "ok" if out else (errs[-1] if errs else "no_targets")
    return out


_WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
_GLEIF_API = "https://api.gleif.org/api/v1"


def _wikidata_company(domain: str, status: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """The Wikidata item whose *official website* (P856) is this domain."""
    sites = " ".join(f"<{scheme}://{host}{slash}>" for scheme in ("https", "http")
                     for host in (domain, f"www.{domain}") for slash in ("", "/"))
    query = f"""
SELECT ?item ?itemLabel ?itemDescription ?inception ?industryLabel ?ownerLabel ?parentLabel
       ?founderLabel ?countryLabel ?hqLabel ?employees ?lei ?exchangeLabel ?ticker WHERE {{
  VALUES ?site {{ {sites} }}
  ?item wdt:P856 ?site .
  OPTIONAL {{ ?item wdt:P571 ?inception }}
  OPTIONAL {{ ?item wdt:P452 ?industry }}
  OPTIONAL {{ ?item wdt:P127 ?owner }}
  OPTIONAL {{ ?item wdt:P749 ?parent }}
  OPTIONAL {{ ?item wdt:P112 ?founder }}
  OPTIONAL {{ ?item wdt:P17 ?country }}
  OPTIONAL {{ ?item wdt:P159 ?hq }}
  OPTIONAL {{ ?item wdt:P1128 ?employees }}
  OPTIONAL {{ ?item wdt:P1278 ?lei }}
  OPTIONAL {{ ?item p:P414 ?listing . ?listing ps:P414 ?exchange . OPTIONAL {{ ?listing pq:P249 ?ticker }} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 200"""
    try:
        r = _http_get(_WIKIDATA_SPARQL, params={"query": query, "format": "json"}, timeout=25,
                      headers={"Accept": "application/sparql-results+json"})
        if r.status_code != 200:
            status["wikidata"] = _http_status(r.status_code)
            return None
        rows = (r.json().get("results") or {}).get("bindings") or []
    except Exception as e:  # noqa: BLE001
        status["wikidata"] = f"error: {type(e).__name__}"
        return None
    items: Dict[str, Dict[str, Any]] = {}

    def val(row, k):
        v = row.get(k, {}).get("value")
        return v.strip() if isinstance(v, str) and v.strip() else None

    for row in rows:
        qid = (val(row, "item") or "").rsplit("/", 1)[-1]
        if not qid:
            continue
        it = items.setdefault(qid, {
            "name": val(row, "itemLabel"), "description": val(row, "itemDescription"),
            "wikidata_id": qid, "founded": None, "industries": [], "owners": [], "parents": [],
            "founders": [], "countries": [], "headquarters": [], "employees": None, "lei": None,
            "listings": [],
        })
        inc = val(row, "inception")
        if inc and (not it["founded"] or inc < it["founded"]):
            it["founded"] = inc
        for key, field_ in (("industryLabel", "industries"), ("ownerLabel", "owners"), ("parentLabel", "parents"),
                            ("founderLabel", "founders"), ("countryLabel", "countries"), ("hqLabel", "headquarters")):
            v = val(row, key)
            if v and not re.fullmatch(r"Q\d+", v) and v not in it[field_]:
                it[field_].append(v)
        emp = val(row, "employees")
        if emp:
            try:
                n = int(float(emp))
                it["employees"] = max(it["employees"] or 0, n)
            except ValueError:
                pass
        if val(row, "lei"):
            it["lei"] = val(row, "lei")
        ex = val(row, "exchangeLabel")
        if ex:
            listing = f"{ex}: {val(row, 'ticker')}" if val(row, "ticker") else ex
            if listing not in it["listings"]:
                it["listings"].append(listing)
    if not items:
        status["wikidata"] = "no_results"
        return None
    # Prefer the most complete record (a company over, say, a product with the same website).
    ranked = sorted(items.values(), key=lambda i: -sum(bool(i[k]) for k in (
        "founded", "industries", "owners", "parents", "founders", "countries", "headquarters", "lei")))
    best = ranked[0]
    if best["founded"]:
        best["founded"] = best["founded"][:10]
    best["also_linked"] = [{"name": i["name"], "wikidata_id": i["wikidata_id"]} for i in ranked[1:5]]
    best["source_url"] = f"https://www.wikidata.org/wiki/{best['wikidata_id']}"
    status["wikidata"] = "ok"
    return best


def _gleif_entity(lei: str, status: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Legal entity and its parent companies from GLEIF's free LEI API."""
    def name_of(rec: dict) -> Optional[str]:
        return (((rec.get("attributes") or {}).get("entity") or {}).get("legalName") or {}).get("name")

    try:
        r = _http_get(f"{_GLEIF_API}/lei-records/{quote(lei)}", timeout=15,
                      headers={"Accept": "application/vnd.api+json"})
        if r.status_code != 200:
            status["gleif"] = "no_results" if r.status_code == 404 else _http_status(r.status_code)
            return None
        rec = r.json().get("data") or {}
        attrs = rec.get("attributes") or {}
        ent = attrs.get("entity") or {}
        addr = ent.get("legalAddress") or {}
        out: Dict[str, Any] = {
            "lei": lei,
            "legal_name": name_of(rec),
            "jurisdiction": ent.get("jurisdiction"),
            "legal_form": ((ent.get("legalForm") or {}).get("id")),
            "status": ent.get("status"),
            "created": (ent.get("creationDate") or "")[:10] or None,
            "registered_as": ent.get("registeredAs"),
            "city": addr.get("city"), "country": addr.get("country"),
            "direct_parent": None, "ultimate_parent": None,
            "source_url": f"https://search.gleif.org/#/record/{lei}",
        }
        for rel in ("direct-parent", "ultimate-parent"):
            try:
                pr = _http_get(f"{_GLEIF_API}/lei-records/{quote(lei)}/{rel}", timeout=15,
                               headers={"Accept": "application/vnd.api+json"})
                if pr.status_code == 200:
                    pdata = pr.json().get("data") or {}
                    out[rel.replace("-", "_")] = {"legal_name": name_of(pdata), "lei": pdata.get("id"),
                                                  "source_url": f"https://search.gleif.org/#/record/{pdata.get('id')}"}
            except Exception:  # noqa: BLE001
                pass
        status["gleif"] = "ok"
        return out
    except Exception as e:  # noqa: BLE001
        status["gleif"] = f"error: {type(e).__name__}"
        return None


def _collect_company(wd: Optional[Dict[str, Any]], whois: Optional[Dict[str, Any]],
                     status: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Who is behind the domain: only records explicitly tied to it, never a name guess."""
    legal = None
    if wd and wd.get("lei"):
        legal = _gleif_entity(wd["lei"], status)
    else:
        status["gleif"] = "no_targets"
    registrant = (whois or {}).get("registrant_org")
    if registrant and re.search(r"redacted|privacy|proxy|withheld|not disclosed", registrant, re.I):
        registrant = None
    if not wd and not legal and not registrant:
        return None
    return {
        "name": (legal or {}).get("legal_name") or (wd or {}).get("name") or registrant,
        "wikidata": wd,
        "legal_entity": legal,
        "domain_registrant": registrant,
        "domain_registered": (whois or {}).get("registration_date"),
        "note": "Linked through the company's official website on Wikidata and its LEI in GLEIF. "
                "The domain registration date is when the domain was registered, not when the company was founded.",
    }


def _ti_status(st: str) -> str:
    return "needs_key" if st == "not_configured" else st


def _collect_threat_intel(domain: str, status: Dict[str, str]):
    """Breaches, blocklists and look-alikes via the shared threat-intel source functions."""
    from app.services import threat_intel as ti

    breaches: List[Dict[str, Any]] = []
    reports: List[Dict[str, Any]] = []
    lookalikes: List[Dict[str, Any]] = []

    def run(fn, *args):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            return [], f"error: {type(e).__name__}"

    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        jobs = {
            "hibp": ex.submit(run, ti.check_hibp_site_breaches, domain),
            "hibp-domain": ex.submit(run, ti.check_hibp_domain_search, domain),
            "urlhaus": ex.submit(run, ti.check_urlhaus, domain),
            "threatfox": ex.submit(run, ti.check_threatfox, domain),
            "lookalikes": ex.submit(run, ti.check_lookalikes, domain),
        }
        results = {k: f.result() for k, f in jobs.items()}

    for sid, (findings, st) in results.items():
        status[sid] = ("ok" if findings else "no_results") if st == "ok" else _ti_status(st)
        for f in findings:
            item = {"title": f.title, "summary": f.summary, "severity": f.severity,
                    "observed_at": f.observed_at, "source": sid, "source_url": f.reference_url}
            if sid in ("hibp", "hibp-domain"):
                item.update({"name": f.key, "kind": "site" if sid == "hibp" else "addresses",
                             "data_classes": f.data.get("data_classes") or f.data.get("DataClasses"),
                             "pwn_count": f.data.get("accounts_in_breach"),
                             "breach_date": f.data.get("breach_date"),
                             "affected_count": f.data.get("affected_count")})
                breaches.append(item)
            elif sid == "lookalikes":
                d = f.data or {}
                lookalikes.append({"domain": d.get("lookalike"), "technique": d.get("technique"),
                                   "a_records": d.get("a_records", []), "mx_records": d.get("mx_records", []),
                                   "severity": f.severity, "source": sid, "source_url": f.reference_url})
            else:
                item["category"] = f.category
                reports.append(item)
    return breaches, reports, lookalikes


# --------------------------------------------------------------------------- #
# Passive risk assessment: only facts with a source behind them count.
# --------------------------------------------------------------------------- #
def compute_passive_risk(result: IntelResult):
    from app.services.osint_advanced import RiskScoreResult

    risk = RiskScoreResult()
    score = 0
    findings: List[Dict[str, Any]] = []

    def add(points: int, severity: str, detail: str, source: str, url: Optional[str] = None):
        nonlocal score
        score += points
        findings.append({"severity": severity, "detail": detail, "source": source, "source_url": url})

    kev = [v for v in result.vulnerabilities if v.is_kev]
    crit = [v for v in result.vulnerabilities if not v.is_kev and (v.cvss or 0) >= 9.0]
    if kev:
        add(30, "critical",
            f"{len(kev)} CVE(s) on CISA's Known Exploited list match software Shodan saw on this domain's IPs "
            f"({', '.join(v.cve_id for v in kev[:3])}). Version-based match: confirm with a scan.",
            "Shodan InternetDB + CISA KEV", kev[0].source_url)
    if crit:
        add(15, "high",
            f"{len(crit)} critical-severity CVE(s) (CVSS 9+) match observed software versions. "
            "Version-based match: confirm with a scan.",
            "Shodan InternetDB", crit[0].source_url)
    elif result.vulnerabilities and not kev:
        add(5, "medium",
            f"{len(result.vulnerabilities)} CVE(s) match observed software versions (version-based, unverified).",
            "Shodan InternetDB", result.vulnerabilities[0].source_url)

    risky = sorted({(p.port, _RISKY_PORTS[p.port]) for p in result.ports if p.port in _RISKY_PORTS})
    if risky:
        p0 = next(p for p in result.ports if p.port == risky[0][0])
        add(min(30, 10 * len(risky)), "high",
            "Exposed sensitive service(s) seen by Shodan: " + ", ".join(f"{n} ({p})" for p, n in risky),
            "Shodan InternetDB", p0.source_url)
    risk.exposed_services = len({(p.ip, p.port) for p in result.ports})

    es = result.email_security
    if es is not None:
        if not getattr(es, "dmarc_record", None):
            add(8, "medium", "No DMARC record: anyone can send email that claims to be from this domain.",
                "Public DNS", _source_link("dns", f"_dmarc.{result.query}"))
        elif getattr(es, "dmarc_policy", None) == "none":
            add(4, "low", "DMARC policy is p=none (monitoring only, spoofed mail is not blocked).",
                "Public DNS", _source_link("dns", f"_dmarc.{result.query}"))
        spf = getattr(es, "spf_record", None)
        if not spf:
            add(5, "medium", "No SPF record.", "Public DNS", _source_link("dns", result.query))
        elif getattr(es, "spf_all", None) == "+all":
            add(10, "high", "SPF ends in +all, which authorises every server on the internet to send as this domain.",
                "Public DNS", _source_link("dns", result.query))

    w = result.whois or {}
    if w:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for key, label in (("expiration_date", "exp"), ("registration_date", "reg")):
            raw = w.get(key)
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            days = (dt - now).days
            if label == "exp" and days < 30:
                add(15, "high", f"Domain registration expires in {days} days ({raw[:10]}).", "RDAP", w.get("source_url"))
            elif label == "reg" and -days < 90:
                add(10, "medium", f"Domain registered {-days} days ago (very new).", "RDAP", w.get("source_url"))
        if w.get("dnssec") is False:
            add(2, "info", "DNSSEC is not enabled for this domain.", "RDAP", w.get("source_url"))
    if "CAA" not in (result.dns_records or {}) and result.dns_records:
        add(1, "info", "No CAA record: any certificate authority may issue certificates for this domain.",
            "Public DNS", _source_link("dns", result.query))

    for rep in result.ip_reputation:
        ac = rep.get("abuse_confidence")
        if isinstance(ac, (int, float)) and ac >= 50:
            add(10, "high", f"{rep['ip']} has an AbuseIPDB confidence score of {ac}%.", "AbuseIPDB",
                rep.get("links", {}).get("abuseipdb"))
        if rep.get("classification") == "malicious":
            add(10, "high", f"GreyNoise classifies {rep['ip']} as malicious.", "GreyNoise",
                rep.get("links", {}).get("greynoise"))

    for t in result.takeover_candidates:
        add(15 if t.get("service") else 5, t["severity"], t["detail"], "Public DNS", t.get("source_url"))
    for rep in result.threat_reports:
        sev = rep.get("severity") or "high"
        add(20 if sev in ("critical", "high") else 8, sev, rep["title"],
            SOURCE_CATALOG.get(rep["source"], {}).get("name", rep["source"]), rep.get("source_url"))
    site_breaches = [b for b in result.breaches if b.get("kind") == "site"]
    addr_breaches = [b for b in result.breaches if b.get("kind") == "addresses"]
    if site_breaches:
        add(8, "medium", f"This domain's site appears in {len(site_breaches)} known breach(es): "
            + ", ".join(b["name"] for b in site_breaches[:3]), "Have I Been Pwned", site_breaches[0].get("source_url"))
    if addr_breaches:
        total = sum(b.get("affected_count") or 0 for b in addr_breaches)
        add(8, "medium", f"{total} email address(es) at this domain appear in {len(addr_breaches)} breach(es).",
            "Have I Been Pwned", addr_breaches[0].get("source_url"))
    mx_lookalikes = [lk for lk in result.lookalikes if lk.get("mx_records")]
    if mx_lookalikes:
        add(min(10, 3 * len(mx_lookalikes)), "medium",
            f"{len(mx_lookalikes)} registered look-alike domain(s) can receive email (possible phishing): "
            + ", ".join(lk["domain"] for lk in mx_lookalikes[:3]), "Public DNS", mx_lookalikes[0].get("source_url"))
    if es is not None:
        if getattr(es, "spf_multiple", False):
            add(5, "medium", "More than one SPF record: receivers treat SPF as broken.", "Public DNS",
                _source_link("dns", result.query))
        lookups = getattr(es, "spf_lookups", None) or 0
        if lookups > 10:
            add(4, "medium", f"SPF needs {lookups} DNS lookups at the top level (limit is 10), so it may fail.",
                "Public DNS", _source_link("dns", result.query))
        pct = getattr(es, "dmarc_pct", None)
        if getattr(es, "dmarc_record", None) and pct is not None and pct < 100 and es.dmarc_policy in ("quarantine", "reject"):
            add(2, "low", f"DMARC enforcement applies to only {pct}% of failing mail (pct={pct}).",
                "Public DNS", _source_link("dns", f"_dmarc.{result.query}"))

    risk.score = min(score, 100)
    risk.findings = findings
    risk.dns_misconfigs = sum(1 for f in findings if f["source"] == "Public DNS")
    risk.grade = ("A" if score <= 15 else "B" if score <= 30 else "C" if score <= 50
                  else "D" if score <= 70 else "F")
    result.sources_status["risk-score"] = f"{risk.score}/100 ({risk.grade})"
    return risk


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def lookup_domain(raw_query: str) -> IntelResult:
    """Collect passive public intelligence about a domain.

    Only third-party datasets and public DNS are queried; the target's own
    servers are never contacted (live checks are the scan engines' job).
    """
    try:
        domain = _normalize_domain(raw_query)
    except Exception:
        domain = (raw_query or "").strip().lower()
    result = IntelResult(query=domain)
    status = result.sources_status
    if not domain:
        status["input"] = "empty"
        return result
    status["_domain"] = domain
    deadline = time.time() + _OVERALL_TIMEOUT

    def left() -> float:
        return max(1.0, deadline - time.time())

    # ---- Phase 1: independent third-party sources --------------------------
    from app.services.osint_advanced import _collect_email_security

    with cf.ThreadPoolExecutor(max_workers=9) as ex:
        f = {
            "crtsh": ex.submit(_fetch_crtsh, domain, status),
            "certspotter": ex.submit(_fetch_certspotter, domain, status),
            "hackertarget": ex.submit(_src_hackertarget, domain, status),
            "alienvault": ex.submit(_src_alienvault, domain, status),
            "rapiddns": ex.submit(_src_rapiddns, domain, status),
            "wayback": ex.submit(_collect_wayback, domain, status),
            "dns": ex.submit(_resolve_dns, domain),
            "rdap": ex.submit(_collect_whois, domain, status),
            "email": ex.submit(_collect_email_security, domain, status),
            "ti": ex.submit(_collect_threat_intel, domain, status),
            "wikidata": ex.submit(_wikidata_company, domain, status),
        }

        def get(name, default):
            try:
                return f[name].result(timeout=left())
            except Exception as e:
                log.info("osint %s failed for %s: %s", name, domain, e)
                return default

        crtsh_rows = get("crtsh", [])
        spotter_rows = get("certspotter", [])
        ht = get("hackertarget", {})
        otx = get("alienvault", {})
        rd = get("rapiddns", {})
        result.historical_subdomains = get("wayback", [])
        result.dns_records = get("dns", {})
        result.whois = get("rdap", None)
        result.email_security = get("email", None)
        result.breaches, result.threat_reports, result.lookalikes = get("ti", ([], [], []))
        wd = get("wikidata", None)

    status["dns"] = "ok" if result.dns_records else "no_results"
    result.company = _collect_company(wd, result.whois, status)

    # ---- Phase 2: merge subdomains, resolve via public DNS ------------------
    found: Dict[str, SubdomainResult] = {}

    def merge(source: str, hosts: Dict[str, List[str]]):
        for host, ips in hosts.items():
            sub = found.setdefault(host, SubdomainResult(hostname=host))
            if source not in sub.sources:
                sub.sources.append(source)
            for ip in ips:
                if ip and ip not in sub.ips:
                    sub.ips.append(ip)

    crt_hosts, spot_hosts = _hosts_from_ct(domain, crtsh_rows, spotter_rows)
    merge("crtsh", crt_hosts)
    merge("certspotter", spot_hosts)
    merge("hackertarget", ht)
    merge("alienvault", otx)
    merge("rapiddns", rd)
    if domain not in found:
        found[domain] = SubdomainResult(hostname=domain, sources=["dns"])

    # Apex first, then hosts seen by the most sources.
    subs = sorted(found.values(), key=lambda s: (s.hostname != domain, -len(s.sources), s.hostname))
    # Third-party IPs can be stale: resolve the busiest names now and keep live answers.
    # Third-party IPs can be stale (and may now belong to someone else), so the
    # busiest names are resolved now and only live answers feed the exposure
    # lookups below.
    to_resolve = subs[:_MAX_RESOLVE]
    for s in to_resolve:
        s.ips = []
    with cf.ThreadPoolExecutor(max_workers=15) as ex:
        list(ex.map(_resolve_host, to_resolve))
    result.takeover_candidates = _collect_takeover(to_resolve, status)
    result.subdomains = subs

    result.certificates = _certs_from_ct(domain, crtsh_rows, spotter_rows)

    # ---- Phase 3: what is exposed on the IPs (third-party view) -------------
    ips: List[str] = []
    for s in to_resolve:
        for ip in s.ips:
            if ip not in ips and _is_public_ip(ip):
                ips.append(ip)
    ips_v4 = [ip for ip in ips if ":" not in ip]

    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        f_idb = ex.submit(_collect_internetdb, ips_v4[:_MAX_IPS], status)
        f_rep = ex.submit(_collect_ip_reputation, ips_v4[:_MAX_REP_IPS], status)
        f_net = ex.submit(_collect_ip_networks, ips[:_MAX_REP_IPS], status)
        try:
            idb = f_idb.result(timeout=left())
        except Exception:
            idb = {}
        try:
            result.ip_reputation = f_rep.result(timeout=left()) or []
        except Exception:
            result.ip_reputation = []
        try:
            result.ip_networks = f_net.result(timeout=left()) or []
        except Exception:
            result.ip_networks = []

    host_by_ip: Dict[str, List[str]] = {}
    for s in subs:
        for ip in s.ips:
            host_by_ip.setdefault(ip, []).append(s.hostname)

    cve_ips: Dict[str, List[str]] = {}
    tech_seen: Dict[str, Dict[str, Any]] = {}
    for ip, data in idb.items():
        for port in sorted(data.get("ports", []) or []):
            result.ports.append(PortResult(
                port=int(port), state="open", service=_SERVICE_NAMES.get(int(port)),
                tls=int(port) in (443, 8443, 993, 995, 465), ip=ip,
                hostnames=sorted(set(host_by_ip.get(ip, [])) | set(data.get("hostnames", []) or []))[:10],
                source="shodan-internetdb", source_url=f"https://internetdb.shodan.io/{ip}",
            ))
        for cpe in data.get("cpes", []) or []:
            p = _parse_cpe(str(cpe))
            if not p.get("product"):
                continue
            entry = tech_seen.setdefault(str(cpe), {
                "name": p["product"].replace("_", " "), "vendor": p["vendor"], "version": p["version"],
                "cpe": str(cpe), "ips": [], "source": "shodan-internetdb",
                "source_url": f"https://internetdb.shodan.io/{ip}",
            })
            if ip not in entry["ips"]:
                entry["ips"].append(ip)
        for cve in data.get("vulns", []) or []:
            cve_ips.setdefault(str(cve).upper(), []).append(ip)
    status.setdefault("shodan-internetdb", "no_targets")
    result.technology_details = sorted(tech_seen.values(), key=lambda t: t["name"])
    result.technologies = sorted({t["name"].lower() for t in result.technology_details})

    # CDN / edge provider from passive signals only.
    cdn_texts = [s.cname or "" for s in subs] + result.dns_records.get("NS", []) + result.dns_records.get("CNAME", [])
    cdn_ips = set()
    for rep in result.ip_reputation:
        name = _detect_cdn([rep.get("org") or "", rep.get("asn") or "", rep.get("hostname") or ""])
        if name:
            cdn_ips.add(rep["ip"])
            cdn_texts.append(name.lower())
    for ip, data in idb.items():
        if "cdn" in [str(t).lower() for t in data.get("tags", []) or []]:
            cdn_ips.add(ip)
    cdn = _detect_cdn(cdn_texts)
    if cdn:
        from app.services.osint_advanced import WafCdnResult
        result.waf_cdn = WafCdnResult(cdn=cdn)

    # ---- Phase 4: CVE details + co-hosted domains ---------------------------
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        f_cve = ex.submit(_collect_cve_details, sorted(cve_ips), status)
        f_rev = ex.submit(_collect_reverse_ip, ips_v4, domain, cdn_ips, status)
        try:
            details = f_cve.result(timeout=left())
        except Exception:
            details = {}
        try:
            result.cohosted_domains = f_rev.result(timeout=left()) or []
        except Exception:
            result.cohosted_domains = []
    result.reverse_ip = [c["domain"] for c in result.cohosted_domains]

    for cve, cips in cve_ips.items():
        d = details.get(cve) or {}
        cvss = d.get("cvss_v3") if d.get("cvss_v3") is not None else d.get("cvss")
        try:
            cvss = float(cvss) if cvss is not None else None
        except (TypeError, ValueError):
            cvss = None
        result.vulnerabilities.append(VulnResult(
            cve_id=cve,
            description=str(d.get("summary") or "")[:400],
            severity=_cvss_severity(cvss),
            cvss=cvss,
            published=d.get("published_time"),
            is_kev=bool(d.get("kev")),
            epss=d.get("epss"),
            ips=sorted(set(cips)),
            source="Shodan InternetDB",
            confidence="potential",
            source_url=f"https://internetdb.shodan.io/{cips[0]}",
            reference_url=f"https://nvd.nist.gov/vuln/detail/{cve}",
        ))
    result.vulnerabilities.sort(key=lambda v: (not v.is_kev, -(v.cvss or 0), v.cve_id))

    try:
        result.risk_score = compute_passive_risk(result)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("risk score failed for %s: %s", domain, e)
    return result


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def intel_to_dict(result: IntelResult) -> dict:
    domain = result.query
    return {
        "engine_version": ENGINE_VERSION,
        "query": domain,
        "passive": True,
        "subdomains": [
            {"hostname": s.hostname, "ips": s.ips, "sources": s.sources, "cname": s.cname,
             "source_links": {src: _source_link(src, domain) for src in s.sources if _source_link(src, domain)}}
            for s in result.subdomains
        ],
        "dns_records": result.dns_records,
        "certificates": [_dc_to_dict(c) for c in result.certificates],
        "ports": [_dc_to_dict(p) for p in result.ports],
        "technologies": result.technologies,
        "technology_details": result.technology_details,
        "vulnerabilities": [_dc_to_dict(v) for v in result.vulnerabilities],
        "sources_status": result.sources_status,
        "sources": build_sources(domain, result.sources_status),
        "ip_reputation": result.ip_reputation,
        "whois": result.whois,
        "historical_subdomains": result.historical_subdomains,
        "reverse_ip": result.reverse_ip,
        "cohosted_domains": result.cohosted_domains,
        "email_security": _dc_to_dict(result.email_security) if result.email_security else None,
        "waf_cdn": _dc_to_dict(result.waf_cdn) if result.waf_cdn else None,
        "security_headers": _dc_to_dict(result.security_headers) if result.security_headers else None,
        "sensitive_paths": [_dc_to_dict(p) for p in result.sensitive_paths] if result.sensitive_paths else [],
        "web_fingerprint": _dc_to_dict(result.web_fingerprint) if result.web_fingerprint else None,
        "reverse_dns_range": result.reverse_dns_range,
        "risk_score": _dc_to_dict(result.risk_score) if result.risk_score else None,
        "ip_networks": result.ip_networks,
        "takeover_candidates": result.takeover_candidates,
        "lookalikes": result.lookalikes,
        "breaches": result.breaches,
        "threat_reports": result.threat_reports,
        "company": result.company,
        "subscription_sources": SUBSCRIPTION_SOURCES,
    }


def _pick(cls, data: dict):
    names = set(getattr(cls, "__dataclass_fields__", {}))
    return cls(**{k: v for k, v in (data or {}).items() if k in names})


def intel_from_dict(data: dict) -> IntelResult:
    """Rebuild an IntelResult from ``intel_to_dict`` output (e.g. a cached result)."""
    intel = IntelResult(query=data.get("query", ""))
    intel.subdomains = [_pick(SubdomainResult, s) for s in data.get("subdomains", []) or []]
    intel.certificates = [_pick(CertResult, c) for c in data.get("certificates", []) or []]
    intel.ports = [_pick(PortResult, p) for p in data.get("ports", []) or []]
    intel.vulnerabilities = [_pick(VulnResult, v) for v in data.get("vulnerabilities", []) or []]
    intel.technologies = list(data.get("technologies", []) or [])
    intel.technology_details = list(data.get("technology_details", []) or [])
    intel.dns_records = dict(data.get("dns_records", {}) or {})
    intel.sources_status = dict(data.get("sources_status", {}) or {})
    intel.ip_reputation = list(data.get("ip_reputation", []) or [])
    intel.whois = data.get("whois")
    intel.historical_subdomains = list(data.get("historical_subdomains", []) or [])
    intel.reverse_ip = list(data.get("reverse_ip", []) or [])
    intel.cohosted_domains = list(data.get("cohosted_domains", []) or [])
    for name in ("ip_networks", "takeover_candidates", "lookalikes", "breaches", "threat_reports"):
        setattr(intel, name, list(data.get(name, []) or []))
    intel.company = data.get("company")
    return intel


def _dc_to_dict(obj) -> Any:
    """Convert a dataclass to a plain dict, handling nested objects."""
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            if hasattr(val, "__dataclass_fields__"):
                d[f] = _dc_to_dict(val)
            elif isinstance(val, list) and val and hasattr(val[0], "__dataclass_fields__"):
                d[f] = [_dc_to_dict(v) for v in val]
            else:
                d[f] = val
        return d
    return obj
