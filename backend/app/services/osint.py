"""Key-free, open-source internet intelligence engine (Shodan-style).

Aggregates public OSINT for any domain / company from truly key-free sources:

* Subdomains & DNS  -> hackertarget hostsearch + live DNS resolution
* Certificates      -> certspotter API + live TLS cert grab (SAN parse)
* Vulnerabilities   -> NVD CVE API 2.0 (keyword) + CISA KEV catalog
* Ports/Services    -> live probe of resolved IPs (HTTP title + TLS handshake
                       + common-port banner grab)

No API keys required. Every source degrades gracefully; a partial result is
always returned. Designed to be called from a request path via a threadpool.
"""
from __future__ import annotations

import functools
import socket
import ssl
import re
import logging
import time
import warnings
import concurrent.futures as cf
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import requests
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

log = logging.getLogger("osint")

try:
    from cryptography import x509
except Exception:  # pragma: no cover - cryptography is a hard dep of FastAPI stack
    x509 = None

_USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (compatible; CAZO-EASM-OSINT/1.0; +https://cazo.io)",
}
_TIMEOUT = 15

# Common ports probed for the Shodan-style "ports/services/tech" view.
_PROBE_PORTS = [80, 443, 22, 8080, 8443]

# Maximum subdomains to resolve DNS for (keeps lookup fast).
_MAX_DNS_RESOLUTIONS = 20

# Maximum hosts to probe for open ports.
_MAX_PORT_PROBE_HOSTS = 3

# Hard overall timeout for the entire lookup (seconds).
_OVERALL_TIMEOUT = 300

_CVE_PRODUCT_KEYWORDS = [
    "nginx", "apache", "iis", "openssl", "wordpress", "drupal", "joomla",
    "php", "tomcat", "jetty", "nodejs", "express", "django", "flask",
    "spring", "rails", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "nginx", "cloudflare", "aws", "azure", "google cloud",
]

# In-memory cache for CISA KEV catalog (avoid re-downloading 30MB each lookup).
_KEV_CACHE: Optional[set] = None
_KEV_CACHE_TS: float = 0


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class SubdomainResult:
    hostname: str
    ips: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


@dataclass
class CertResult:
    issuer: Optional[str] = None
    subject: Optional[str] = None
    san: List[str] = field(default_factory=list)
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    serial: Optional[str] = None
    source: Optional[str] = None


@dataclass
class PortResult:
    port: int
    state: str  # open | closed | filtered
    service: Optional[str] = None
    banner: Optional[str] = None
    tls: bool = False
    title: Optional[str] = None


@dataclass
class VulnResult:
    cve_id: str
    description: str
    severity: Optional[str] = None
    cvss: Optional[float] = None
    published: Optional[str] = None
    is_kev: bool = False
    source: str = "NVD"


@dataclass
class IntelResult:
    query: str
    subdomains: List[SubdomainResult] = field(default_factory=list)
    dns_records: Dict[str, List[str]] = field(default_factory=dict)
    certificates: List[CertResult] = field(default_factory=list)
    ports: List[PortResult] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    vulnerabilities: List[VulnResult] = field(default_factory=list)
    ip_reputation: List[Dict[str, object]] = field(default_factory=list)
    whois: Optional[Dict[str, object]] = None
    historical_subdomains: List[str] = field(default_factory=list)
    reverse_ip: List[str] = field(default_factory=list)
    sources_status: Dict[str, str] = field(default_factory=dict)
    # Advanced intelligence
    email_security: Optional[object] = None
    waf_cdn: Optional[object] = None
    security_headers: Optional[object] = None
    sensitive_paths: List[object] = field(default_factory=list)
    web_fingerprint: Optional[object] = None
    reverse_dns_range: List[str] = field(default_factory=list)
    risk_score: Optional[object] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _http_get(url: str, params: Optional[dict] = None, timeout: int = _TIMEOUT):
    """HTTP GET with Connection: close to prevent socket reuse issues."""
    try:
        resp = requests.get(
            url, params=params, headers=_USER_AGENT, timeout=timeout,
            allow_redirects=True,
        )
        return resp
    except requests.exceptions.ConnectionError:
        raise
    except Exception:
        raise


def _dns_resolve(host: str, timeout: float = 5.0) -> list:
    """Resolve hostname to A records using dnspython."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(host, "A", lifetime=timeout)
        return [("", 0, 0, "", (r.to_text(), 0)) for r in answers]
    except Exception:
        return []


def _normalize_domain(raw: str) -> str:
    raw = (raw or "").strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0]
    if raw.startswith("www."):
        raw = raw[4:]
    # If no TLD (bare company name like "stripe"), try common TLDs
    if "." not in raw:
        _TLDS = [
            "com", "org", "net", "io", "co", "dev", "app", "tech", "ai",
            "pro", "me", "us", "uk", "ca", "de", "fr", "jp", "au", "in",
            "xyz", "info", "biz", "cloud", "site", "online", "store",
            "digital", "live", "systems", "solutions", "services",
            "security", "network", "computer", "software", "group",
            "company", "enterprises", "consulting", "global", "world",
            "one", "hub", "lab", "space", "works", "tools", "expert",
            "team", "agency", "studio", "media", "design", "creative",
            "finance", "bank", "pay", "money", "capital", "ventures",
            "edu", "gov", "mil", "int", "jobs", "mobi", "name", "museum",
            "aero", "coop", "travel", "asia", "cat", "tel", "post",
            "cc", "ws", "tv", "fm", "am", "fm", "to", "ly", "sh",
        ]
        for tld in _TLDS:
            candidate = f"{raw}.{tld}"
            try:
                if _dns_resolve(candidate, timeout=3):
                    raw = candidate
                    break
            except Exception:
                continue
    return raw


def _resolve_dns(domain: str) -> Dict[str, List[str]]:
    records: Dict[str, List[str]] = {}
    types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
    try:
        import dns.resolver  # type: ignore

        for t in types:
            try:
                ans = dns.resolver.resolve(domain, t, lifetime=3)
                records[t] = [r.to_text().rstrip(".") for r in ans]
            except Exception:
                continue
    except Exception:
        # Fallback to socket for A records.
        try:
            infos = socket.getaddrinfo(domain, None)
            records["A"] = sorted({i[4][0] for i in infos})
        except Exception:
            pass
    return records


@functools.lru_cache(maxsize=4096)
def _connectable(host: str) -> bool:
    """Never open a socket to an internal name or an address inside our own network."""
    from app.core.target_guard import check_public_target

    return check_public_target(host).allowed


def _grab_cert_sans(domain: str, port: int = 443) -> Optional[Dict[str, object]]:
    if not x509:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if not _connectable(domain):
        return None
    try:
        with socket.create_connection((domain, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ss:
                der = ss.getpeercert(binary_form=True)
                cert = x509.load_der_x509_certificate(der)
                san = cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName
                ).value.get_values_for_type(x509.DNSName)
                issuer = cert.issuer.rfc4514_string()
                subject = cert.subject.rfc4514_string()
                not_before = cert.not_valid_before_utc.isoformat()
                not_after = cert.not_valid_after_utc.isoformat()
                serial = format(cert.serial_number, "X")
                return {
                    "issuer": issuer,
                    "subject": subject,
                    "san": list(san),
                    "not_before": not_before,
                    "not_after": not_after,
                    "serial": serial,
                }
    except Exception:
        return None
    return None


def _probe_port(host: str, port: int) -> PortResult:
    svc = {80: "HTTP", 443: "HTTPS", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
           22: "SSH", 21: "FTP", 25: "SMTP", 53: "DNS", 3306: "MySQL",
           5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB", 3389: "RDP"}.get(port)
    if not _connectable(host):
        return PortResult(port=port, state="filtered", service=svc)
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            banner = None
            title = None
            is_tls = port in (443, 8443)
            if is_tls:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with ctx.wrap_socket(sock, server_hostname=host) as ss:
                    try:
                        ss.sendall(
                            b"GET / HTTP/1.1\r\nHost: %s\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"
                            % host.encode()
                        )
                        data = ss.recv(2048)
                        banner = data.decode("utf-8", "ignore")[:400]
                    except Exception:
                        pass
            elif port in (80, 8080):
                try:
                    sock.sendall(
                        b"GET / HTTP/1.1\r\nHost: %s\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"
                        % host.encode()
                    )
                    data = sock.recv(2048)
                    banner = data.decode("utf-8", "ignore")[:400]
                except Exception:
                    pass
            else:
                try:
                    sock.settimeout(3)
                    sock.sendall(b"\r\n")
                    data = sock.recv(256)
                    banner = data.decode("utf-8", "ignore")[:200]
                except Exception:
                    pass
            if banner:
                m = re.search(r"<title[^>]*>(.*?)</title>", banner, re.I | re.S)
                if m:
                    title = m.group(1).strip()[:120]
            return PortResult(port=port, state="open", service=svc, banner=banner, tls=is_tls, title=title)
    except (ConnectionRefusedError, socket.timeout, OSError):
        return PortResult(port=port, state="closed", service=svc)
    except Exception:
        return PortResult(port=port, state="filtered", service=svc)


# --------------------------------------------------------------------------- #
# Source collectors (each returns data + updates sources_status)
# --------------------------------------------------------------------------- #
def _collect_subdomains(domain: str, status: Dict[str, str]) -> List[SubdomainResult]:
    found: Dict[str, SubdomainResult] = {}

    def _merge(source: str, hostnames: Dict[str, List[str]]):
        for host, ips in hostnames.items():
            if host not in found:
                found[host] = SubdomainResult(hostname=host, sources=[source], ips=ips)
            else:
                if source not in found[host].sources:
                    found[host].sources.append(source)
                for ip in ips:
                    if ip and ip not in found[host].ips:
                        found[host].ips.append(ip)

    # Run all HTTP sources concurrently
    def _src_hackertarget() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        try:
            r = _http_get("https://api.hackertarget.com/hostsearch/", params={"q": domain})
            if r.status_code == 200 and r.text:
                body = r.text.strip()
                if body.lower().startswith("api count exceeded") or body.lower().startswith("error"):
                    status["hackertarget"] = "rate_limited"
                else:
                    for line in body.splitlines():
                        if "," in line:
                            host, ip = line.split(",", 1)
                            host, ip = host.strip().lower(), ip.strip()
                            if host.endswith(domain) or domain in host:
                                result.setdefault(host, []).append(ip)
                    status["hackertarget"] = "ok" if result else "no_results"
            else:
                status["hackertarget"] = f"http_{r.status_code}"
        except Exception as e:
            status["hackertarget"] = f"error: {type(e).__name__}"
        return result

    def _src_certspotter() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        try:
            r = _http_get("https://api.certspotter.com/v1/issuances",
                          params={"domain": domain, "include_subdomains": "true", "expand": "dns_names"})
            if r.status_code == 200:
                for entry in r.json():
                    for name in entry.get("dns_names", []):
                        name = name.lstrip("*.").lower()
                        if name.endswith(domain) or domain in name:
                            result.setdefault(name, [])
                status["certspotter"] = "ok" if result else "no_results"
            else:
                status["certspotter"] = f"http_{r.status_code}"
        except Exception as e:
            status["certspotter"] = f"error: {type(e).__name__}"
        return result

    def _src_crtsh() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        try:
            r = _http_get("https://crt.sh/", params={"q": f".{domain}", "output": "json"}, timeout=20)
            if r.status_code == 200:
                for entry in r.json():
                    for part in entry.get("name_value", "").split("\n"):
                        part = part.strip().lstrip("*.").lower()
                        if part.endswith(domain) or domain in part:
                            result.setdefault(part, [])
                status["crtsh"] = "ok" if result else "no_results"
            else:
                status["crtsh"] = f"http_{r.status_code}"
        except Exception as e:
            status["crtsh"] = f"error: {type(e).__name__}"
        return result

    def _src_alienvault() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        try:
            r = _http_get(f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns", timeout=15)
            if r.status_code == 200:
                for entry in r.json().get("passive_dns", []):
                    hostname = entry.get("hostname", "").strip().lower()
                    ip = entry.get("ip", "")
                    if hostname.endswith(domain) or domain in hostname:
                        result.setdefault(hostname, []).append(ip)
                status["alienvault"] = "ok" if result else "no_results"
            else:
                status["alienvault"] = f"http_{r.status_code}"
        except Exception as e:
            status["alienvault"] = f"error: {type(e).__name__}"
        return result

    def _src_rapiddns() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        try:
            r = _http_get(f"https://rapiddns.io/subdomain/{domain}", params={"full": "1"}, timeout=20)
            if r.status_code == 200:
                for m in re.finditer(r"<td>([\w.-]+\." + re.escape(domain) + r")</td>", r.text):
                    sub = m.group(1).strip().lower()
                    result.setdefault(sub, [])
                status["rapiddns"] = "ok" if result else "no_results"
            else:
                status["rapiddns"] = f"http_{r.status_code}"
        except Exception as e:
            status["rapiddns"] = f"error: {type(e).__name__}"
        return result

    def _src_google_dns() -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for dns_type in ("A", "AAAA", "MX", "NS", "CNAME", "TXT"):
            try:
                r = _http_get("https://dns.google/resolve",
                              params={"name": domain, "type": dns_type}, timeout=15)
                if r.status_code == 200:
                    for ans in r.json().get("Answer", []):
                        data = ans.get("data", "").rstrip(".")
                        if dns_type == "MX" and " " in data:
                            data = data.split()[-1].rstrip(".")
                        if data and (data.endswith(domain) or domain in data):
                            result.setdefault(data, [])
            except Exception:
                pass
        status["google-dns"] = "ok" if result else "no_results"
        return result

    # Fire all HTTP sources concurrently (5 threads, ~4s max)
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {
            ex.submit(_src_hackertarget): "hackertarget",
            ex.submit(_src_certspotter): "certspotter",
            ex.submit(_src_alienvault): "alienvault",
            ex.submit(_src_rapiddns): "rapiddns",
            ex.submit(_src_google_dns): "google-dns",
        }
        for f in cf.as_completed(futures):
            try:
                data = f.result(timeout=20)
                _merge(futures[f], data)
            except Exception:
                pass

        # crt.sh only if certspotter failed (run concurrently with above)
        if status.get("certspotter", "").startswith("http_") or status.get("certspotter", "").startswith("error"):
            try:
                data = _src_crtsh()
                _merge("crtsh", data)
            except Exception:
                pass

    # DNS brute-force (top 30, concurrent — fast timeout)
    _DNS_PREFIXES = [
        "www", "mail", "ftp", "smtp", "webmail", "mx", "mx1", "mx2",
        "ns1", "ns2", "dns", "dns1", "dns2",
        "vpn", "remote", "gateway", "ssh",
        "api", "app", "web", "portal", "login", "sso",
        "admin", "cpanel", "whm",
        "dashboard", "console", "panel",
        "dev", "staging", "stage", "test", "beta",
        "blog", "docs", "help",
        "cdn", "static", "assets",
        "git", "gitlab", "jenkins",
        "monitor", "grafana", "status",
    ]
    _brute_candidates = [f"{prefix}.{domain}" for prefix in _DNS_PREFIXES if f"{prefix}.{domain}" not in found]

    def _try_brute(candidate: str) -> Optional[SubdomainResult]:
        try:
            if _dns_resolve(candidate, timeout=5):
                return SubdomainResult(hostname=candidate, sources=["dns-bruteforce"])
        except Exception:
            pass
        return None

    new_from_brute = 0
    with cf.ThreadPoolExecutor(max_workers=15) as ex:
        for result in ex.map(_try_brute, _brute_candidates):
            if result:
                found[result.hostname] = result
                new_from_brute += 1
    status["dns-bruteforce"] = f"{new_from_brute} found" if new_from_brute else "no_results"

    # Ensure the apex domain is present.
    if domain not in found:
        found[domain] = SubdomainResult(hostname=domain, sources=["apex"])

    # Resolve DNS for discovered hostnames (concurrent, capped).
    to_resolve = [s for s in found.values() if not s.ips][:_MAX_DNS_RESOLUTIONS]

    def _resolve_one(sub: SubdomainResult) -> SubdomainResult:
        try:
            infos = _dns_resolve(sub.hostname, timeout=3)
            sub.ips = sorted({i[4][0] for i in infos})
        except Exception:
            pass
        return sub

    with cf.ThreadPoolExecutor(max_workers=15) as ex:
        list(ex.map(_resolve_one, to_resolve))

    # Reverse DNS on discovered IPs (finds additional hostnames)
    all_ips = set()
    for s in found.values():
        for ip in s.ips:
            if ip:
                all_ips.add(ip)
    for ip in list(all_ips)[:_MAX_DNS_RESOLUTIONS]:
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            hostname = hostname.strip().lower()
            if (hostname.endswith(domain) or domain in hostname) and hostname not in found:
                found[hostname] = SubdomainResult(hostname=hostname, ips=[ip], sources=["reverse-dns"])
        except Exception:
            pass

    return list(found.values())


def _collect_certificates(domain: str, status: Dict[str, str]) -> List[CertResult]:
    certs: List[CertResult] = []
    # Live TLS grab on apex + www
    for host in (domain, f"www.{domain}"):
        info = _grab_cert_sans(host)
        if info:
            certs.append(CertResult(source="live-tls", **info))  # type: ignore[arg-type]
    if certs:
        status["live-tls"] = "ok"
    else:
        status["live-tls"] = "no-cert"
    return certs


def _collect_ports(subdomains: List[SubdomainResult], status: Dict[str, str]) -> List[PortResult]:
    # Build probe targets: top subdomains + their resolved IPs, capped.
    hosts = [s.hostname for s in subdomains[:_MAX_PORT_PROBE_HOSTS]]
    ips: List[str] = []
    for s in subdomains[:_MAX_PORT_PROBE_HOSTS]:
        for ip in s.ips:
            if ip not in ips:
                ips.append(ip)
    probe_targets = list(dict.fromkeys(hosts + ips))[:_MAX_PORT_PROBE_HOSTS + 2]
    if not probe_targets:
        status["port-scan"] = "no_targets"
        return []
    results: List[PortResult] = []
    seen_ports = set()
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = []
        for host in probe_targets:
            for port in _PROBE_PORTS:
                futs.append(ex.submit(_probe_port, host, port))
        for f in cf.as_completed(futs):
            res = f.result()
            if res.state == "open" and res.port not in seen_ports:
                results.append(res)
                seen_ports.add(res.port)
    status["port-scan"] = f"{len(results)} open"

    # 9) Shodan InternetDB — enrich each IP with known open ports + CPEs (concurrent)
    shodan_techs = []
    def _shodan_lookup(ip: str) -> dict:
        try:
            r = _http_get(f"https://internetdb.shodan.io/{ip}", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for data in ex.map(_shodan_lookup, ips[:10]):
            for port in data.get("ports", []):
                if port not in seen_ports:
                    svc = {80: "HTTP", 443: "HTTPS", 22: "SSH", 21: "FTP",
                           25: "SMTP", 53: "DNS", 3306: "MySQL", 5432: "PostgreSQL",
                           6379: "Redis", 27017: "MongoDB", 8080: "HTTP-ALT",
                           8443: "HTTPS-ALT", 3389: "RDP"}.get(port)
                    results.append(PortResult(port=port, state="open", service=svc, banner=None, tls=port in (443, 8443)))
                    seen_ports.add(port)
            for cpes in data.get("cpes", []):
                if isinstance(cpes, str) and cpes:
                    shodan_techs.append(cpes)
    if shodan_techs:
        status["shodan-internetdb"] = f"{len(shodan_techs)} cpes"
    else:
        status["shodan-internetdb"] = "ok" if ips else "no_targets"
    return results, shodan_techs


def _collect_vulns(technologies: List[str], status: Dict[str, str]) -> List[VulnResult]:
    global _KEV_CACHE, _KEV_CACHE_TS
    vulns: List[VulnResult] = []
    seen = set()

    # CISA KEV catalog — use in-memory cache (refresh every 6 hours).
    import time as _time
    kev_ids = _KEV_CACHE if _KEV_CACHE and (_time.time() - _KEV_CACHE_TS) < 21600 else None
    if kev_ids is None:
        kev_ids = set()
        try:
            r = _http_get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", timeout=30)
            if r.status_code == 200:
                for v in r.json().get("vulnerabilities", []):
                    kev_ids.add(v.get("cveID"))
                status["cisa-kev"] = "ok"
            else:
                status["cisa-kev"] = f"http_{r.status_code}"
        except Exception as e:
            status["cisa-kev"] = f"error: {type(e).__name__}"
        _KEV_CACHE = kev_ids
        _KEV_CACHE_TS = _time.time()

    # NVD keyword search — ONLY for actually detected technologies.
    if not technologies:
        status["nvd"] = "skipped_no_tech"
        return vulns

    keywords = list(dict.fromkeys(technologies))[:3]  # limit NVD calls (rate limits)
    try:
        for kw in keywords:
            try:
                r = _http_get(
                    "https://services.nvd.nist.gov/rest/json/cves/2.0",
                    params={"keywordSearch": kw, "resultsPerPage": 5},
                    timeout=20,
                )
                if r.status_code != 200:
                    continue
                for v in r.json().get("vulnerabilities", []):
                    cve = v["cve"]
                    cid = cve["id"]
                    if cid in seen:
                        continue
                    seen.add(cid)
                    descr = ""
                    for d in cve.get("descriptions", []):
                        if d.get("lang") == "en":
                            descr = d.get("value", "")
                            break
                    metrics = cve.get("metrics", {})
                    cvss = None
                    sev = None
                    if "cvssMetricV31" in metrics:
                        m = metrics["cvssMetricV31"][0]["cvssData"]
                        cvss = m.get("baseScore")
                        sev = m.get("baseSeverity")
                    elif "cvssMetricV30" in metrics:
                        m = metrics["cvssMetricV30"][0]["cvssData"]
                        cvss = m.get("baseScore")
                        sev = m.get("baseSeverity")
                    vulns.append(VulnResult(
                        cve_id=cid,
                        description=descr[:300],
                        severity=sev,
                        cvss=cvss,
                        published=cve.get("published"),
                        is_kev=cid in kev_ids,
                        source="NVD",
                    ))
            except Exception:
                continue
        status["nvd"] = f"{len(vulns)} cves" if vulns else "no_results"
    except Exception as e:
        status["nvd"] = f"error: {type(e).__name__}"
    return vulns


def _infer_technologies(certs: List[CertResult], ports: List[PortResult], subdomains: List[SubdomainResult]) -> List[str]:
    tech = set()
    for c in certs:
        if c.issuer:
            if "Let's Encrypt" in c.issuer:
                tech.add("Let's Encrypt")
            if "Cloudflare" in (c.issuer or ""):
                tech.add("Cloudflare")
    for p in ports:
        if p.service in ("HTTPS", "HTTP", "HTTP-ALT", "HTTPS-ALT"):
            if p.banner:
                for tok in ("nginx", "apache", "cloudflare", "iis", "openresty", "litespeed"):
                    if tok in p.banner.lower():
                        tech.add(tok)
                if "Server:" in p.banner:
                    m = re.search(r"Server:\s*([^\r\n]+)", p.banner)
                    if m:
                        tech.add(m.group(1).split("/")[0].strip())
    return sorted({t.lower() for t in tech})


# --------------------------------------------------------------------------- #
# IP Reputation, WHOIS, Wayback, Reverse IP collectors
# --------------------------------------------------------------------------- #
def _collect_ip_reputation(ips: List[str], status: Dict[str, str]) -> List[Dict[str, object]]:
    """Query free IP reputation sources for each resolved IP."""
    results = []
    for ip in ips[:4]:
        rep: Dict[str, object] = {"ip": ip, "abuse_confidence": 0, "is_tor": False, "country": None, "org": None}

        # IPinfo (free, no key)
        try:
            r = _http_get(f"https://ipinfo.io/{ip}/json", timeout=15)
            if r.status_code == 200:
                data = r.json()
                rep["country"] = data.get("country")
                rep["org"] = data.get("org")
                rep["city"] = data.get("city")
                rep["loc"] = data.get("loc")
                rep["hostname"] = data.get("hostname")
                status["ipinfo"] = "ok"
        except Exception:
            pass

        # AbuseIPDB free check (limited, no key for bulk)
        try:
            r = _http_get("https://api.abuseipdb.com/api/v2/check", params={"ipAddress": ip}, timeout=15)
            if r.status_code == 200:
                d = r.json().get("data", {})
                rep["abuse_confidence"] = d.get("abuseConfidenceScore", 0)
                rep["total_reports"] = d.get("totalReports", 0)
                rep["country_code"] = d.get("countryCode")
                rep["usage_type"] = d.get("usageType")
                rep["is_whitelisted"] = d.get("isWhitelisted", False)
                status["abuseipdb"] = "ok"
        except Exception:
            pass

        # GreyNoise Community (free, limited)
        try:
            r = _http_get(f"https://api.greynoise.io/v3/community/{ip}", timeout=15)
            if r.status_code == 200:
                d = r.json()
                rep["noise"] = d.get("noise", False)
                rep["riot"] = d.get("riot", False)
                rep["classification"] = d.get("classification")
                rep["name"] = d.get("name")
                status["greynoise"] = "ok"
        except Exception:
            pass

        results.append(rep)
    return results


def _collect_whois(domain: str, status: Dict[str, str]) -> Optional[Dict[str, object]]:
    """Collect WHOIS data via RDAP (free, no key)."""
    try:
        # Use RDAP (free protocol for domain registration data)
        r = _http_get(f"https://rdap.org/domain/{domain}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
            nameservers = [n.get("ldhName", "").lower() for n in data.get("nameservers", [])]
            status_entries = data.get("status", [])
            entities = data.get("entities", [])
            registrar = None
            for ent in entities:
                if "registrar" in [v.lower() for v in ent.get("roles", [])]:
                    registrar = ent.get("handle") or ent.get("vcardArray", [None, []])[1][0][3] if len(ent.get("vcardArray", [])) > 1 else None
                    break
            result = {
                "name": data.get("ldhName", domain),
                "status": status_entries,
                "nameservers": nameservers,
                "registration_date": events.get("registration"),
                "expiration_date": events.get("expiration"),
                "last_changed": events.get("last changed"),
                "registrar": registrar,
                "handle": data.get("handle"),
            }
            status["whois-rdap"] = "ok"
            return result
    except Exception as e:
        status["whois-rdap"] = f"error: {type(e).__name__}"
    return None


def _collect_wayback(domain: str, status: Dict[str, str]) -> List[str]:
    """Get historical subdomains from Wayback Machine CDX API."""
    historical = []
    try:
        r = _http_get(
            "https://web.archive.org/cdx/search/cdx",
            params={"url": f"*.{domain}", "output": "json", "limit": 200, "fl": "original", "collapse": "urlkey"},
            timeout=20,
        )
        if r.status_code == 200:
            rows = r.json()
            seen = set()
            for row in rows[1:]:  # skip header
                if row and row[0]:
                    url = row[0]
                    m = re.match(r"https?://([^:/]+)", url)
                    if m:
                        host = m.group(1).lower()
                        if host.endswith(domain) or domain in host:
                            if host not in seen:
                                seen.add(host)
                                historical.append(host)
            status["wayback"] = f"{len(historical)} found"
        else:
            status["wayback"] = f"http_{r.status_code}"
    except Exception as e:
        status["wayback"] = f"error: {type(e).__name__}"
    return historical


def _collect_reverse_ip(ips: List[str], domain: str, status: Dict[str, str]) -> List[str]:
    """Find other domains hosted on same IPs via hackertarget reverse IP."""
    reverse = []
    for ip in ips[:3]:
        try:
            r = _http_get(f"https://api.hackertarget.com/reverseiplookup/?q={ip}", timeout=15)
            if r.status_code == 200 and r.text and not r.text.lower().startswith("error"):
                for line in r.text.strip().splitlines():
                    host = line.strip().lower()
                    if host and (host.endswith(domain) or domain in host) and host not in reverse:
                        reverse.append(host)
                status["reverse-ip"] = "ok"
        except Exception:
            pass
    if not reverse:
        status["reverse-ip"] = "no_results"
    return reverse


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def lookup_domain(raw_query: str) -> IntelResult:
    """Run the full key-free OSINT aggregation for a domain/company.

    Designed to complete within _OVERALL_TIMEOUT seconds by running
    independent sources concurrently.
    """
    try:
        domain = _normalize_domain(raw_query)
    except Exception as e:
        log.warning("normalize_domain failed for %r: %s", raw_query, e)
        domain = (raw_query or "").strip().lower()
        domain = re.sub(r"^https?://", "", domain).split("/")[0]

    result = IntelResult(query=domain)
    if not domain:
        result.sources_status["input"] = "empty"
        return result

    result.sources_status["_domain"] = domain
    _deadline = time.time() + _OVERALL_TIMEOUT

    def _time_left() -> float:
        return max(0.5, _deadline - time.time())

    # ---- Phase 1: Subdomains + DNS + certs (concurrent) ----
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        f_subdomains = ex.submit(_collect_subdomains, domain, result.sources_status)
        f_dns = ex.submit(_resolve_dns, domain)
        f_certs = ex.submit(_collect_certificates, domain, result.sources_status)

        try:
            result.dns_records = f_dns.result(timeout=_time_left())
        except Exception:
            result.dns_records = {}
        try:
            result.subdomains = f_subdomains.result(timeout=_time_left())
        except Exception as e:
            log.warning("collect_subdomains failed: %s", e)
            result.subdomains = []
        try:
            result.certificates = f_certs.result(timeout=_time_left())
        except Exception:
            result.certificates = []

    # ---- Phase 2: Port scan + Shodan InternetDB (concurrent) ----
    try:
        ports_result = _collect_ports(result.subdomains, result.sources_status)
        result.ports = ports_result[0]
        shodan_techs = ports_result[1]
    except Exception:
        result.ports = []
        shodan_techs = []

    # ---- Phase 3: Tech + Vulns (sequential, fast) ----
    try:
        result.technologies = _infer_technologies(result.certificates, result.ports, result.subdomains)
    except Exception:
        result.technologies = []
    if shodan_techs:
        existing = {t.lower() for t in result.technologies}
        for tech in shodan_techs:
            parts = tech.split(":")
            if len(parts) >= 5:
                product = parts[4].lower()
                if product and product not in existing:
                    result.technologies.append(product)
                    existing.add(product)
    try:
        result.vulnerabilities = _collect_vulns(result.technologies, result.sources_status)
    except Exception:
        result.vulnerabilities = []

    # ---- Phase 4: IP reputation + WHOIS + Wayback + Reverse IP (concurrent) ----
    all_ips = []
    for s in result.subdomains[:5]:
        for ip in s.ips:
            if ip and ip not in all_ips:
                all_ips.append(ip)

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        f_ip = ex.submit(_collect_ip_reputation, all_ips[:4], result.sources_status)
        f_whois = ex.submit(_collect_whois, domain, result.sources_status)
        f_wb = ex.submit(_collect_wayback, domain, result.sources_status)
        f_rip = ex.submit(_collect_reverse_ip, all_ips[:3], domain, result.sources_status)

        try:
            result.ip_reputation = f_ip.result(timeout=_time_left())
        except Exception:
            result.ip_reputation = []
        try:
            result.whois = f_whois.result(timeout=_time_left())
        except Exception:
            result.whois = None
        try:
            result.historical_subdomains = f_wb.result(timeout=_time_left())
        except Exception:
            result.historical_subdomains = []
        try:
            result.reverse_ip = f_rip.result(timeout=_time_left())
        except Exception:
            result.reverse_ip = []

    # ---- Phase 5: Advanced intel (concurrent) ----
    try:
        from app.services.osint_advanced import (
            _collect_email_security,
            _collect_waf_cdn,
            _collect_security_headers,
            _collect_sensitive_paths,
            _collect_web_fingerprint,
            compute_risk_score,
        )

        with cf.ThreadPoolExecutor(max_workers=5) as ex:
            f_email = ex.submit(_collect_email_security, domain, result.sources_status)
            f_waf = ex.submit(_collect_waf_cdn, domain, result.sources_status)
            f_sech = ex.submit(_collect_security_headers, domain, result.sources_status)
            f_sp = ex.submit(_collect_sensitive_paths, domain, result.sources_status)
            f_fp = ex.submit(_collect_web_fingerprint, domain, result.sources_status)

            try:
                result.email_security = f_email.result(timeout=_time_left())
            except Exception as exc:
                log.debug("email_security intel failed for %s: %s", domain, exc)
            try:
                result.waf_cdn = f_waf.result(timeout=_time_left())
            except Exception as exc:
                log.debug("waf_cdn intel failed for %s: %s", domain, exc)
            try:
                result.security_headers = f_sech.result(timeout=_time_left())
            except Exception as exc:
                log.debug("security_headers intel failed for %s: %s", domain, exc)
            try:
                result.sensitive_paths = f_sp.result(timeout=_time_left())
            except Exception as exc:
                log.debug("sensitive_paths intel failed for %s: %s", domain, exc)
            try:
                result.web_fingerprint = f_fp.result(timeout=_time_left())
            except Exception as exc:
                log.debug("web_fingerprint intel failed for %s: %s", domain, exc)

        # Risk scoring
        try:
            result.risk_score = compute_risk_score(
                domain,
                result.email_security,
                result.waf_cdn,
                result.security_headers,
                result.sensitive_paths,
                result.web_fingerprint,
                len(result.subdomains),
                len(result.ports),
                len(result.vulnerabilities),
                result.whois,
                result.sources_status,
            )
        except Exception as e:
            log.warning("risk_score failed: %s", e)
    except ImportError:
        pass

    return result


def intel_to_dict(result: IntelResult) -> dict:
    return {
        "query": result.query,
        "subdomains": [
            {"hostname": s.hostname, "ips": s.ips, "sources": s.sources}
            for s in result.subdomains
        ],
        "dns_records": result.dns_records,
        "certificates": [
            {
                "issuer": c.issuer,
                "subject": c.subject,
                "san": c.san,
                "not_before": c.not_before,
                "not_after": c.not_after,
                "serial": c.serial,
                "source": c.source,
            }
            for c in result.certificates
        ],
        "ports": [
            {
                "port": p.port,
                "state": p.state,
                "service": p.service,
                "banner": p.banner,
                "tls": p.tls,
                "title": p.title,
            }
            for p in result.ports
        ],
        "technologies": result.technologies,
        "vulnerabilities": [
            {
                "cve_id": v.cve_id,
                "description": v.description,
                "severity": v.severity,
                "cvss": v.cvss,
                "published": v.published,
                "is_kev": v.is_kev,
                "source": v.source,
            }
            for v in result.vulnerabilities
        ],
        "sources_status": result.sources_status,
        "ip_reputation": result.ip_reputation,
        "whois": result.whois,
        "historical_subdomains": result.historical_subdomains,
        "reverse_ip": result.reverse_ip,
        # Advanced intelligence
        "email_security": _dc_to_dict(result.email_security) if result.email_security else None,
        "waf_cdn": _dc_to_dict(result.waf_cdn) if result.waf_cdn else None,
        "security_headers": _dc_to_dict(result.security_headers) if result.security_headers else None,
        "sensitive_paths": [_dc_to_dict(p) for p in result.sensitive_paths] if result.sensitive_paths else [],
        "web_fingerprint": _dc_to_dict(result.web_fingerprint) if result.web_fingerprint else None,
        "reverse_dns_range": result.reverse_dns_range,
        "risk_score": _dc_to_dict(result.risk_score) if result.risk_score else None,
    }


def _dc_to_dict(obj) -> dict:
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
