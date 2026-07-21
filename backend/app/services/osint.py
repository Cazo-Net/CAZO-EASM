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

import socket
import ssl
import json
import re
import logging
import concurrent.futures as cf
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import requests

log = logging.getLogger("osint")

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
except Exception:  # pragma: no cover - cryptography is a hard dep of FastAPI stack
    x509 = None

_USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (compatible; CAZO-EASM-OSINT/1.0; +https://cazo.io)"
}
_TIMEOUT = 20

# Common ports probed for the Shodan-style "ports/services/tech" view.
_PROBE_PORTS = [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432, 6379, 27017, 3389]

_CVE_PRODUCT_KEYWORDS = [
    "nginx", "apache", "iis", "openssl", "wordpress", "drupal", "joomla",
    "php", "tomcat", "jetty", "nodejs", "express", "django", "flask",
    "spring", "rails", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "nginx", "cloudflare", "aws", "azure", "google cloud",
]


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
    sources_status: Dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _http_get(url: str, params: Optional[dict] = None, timeout: int = _TIMEOUT):
    return requests.get(url, params=params, headers=_USER_AGENT, timeout=timeout)


def _normalize_domain(raw: str) -> str:
    raw = (raw or "").strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0]
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def _resolve_dns(domain: str) -> Dict[str, List[str]]:
    records: Dict[str, List[str]] = {}
    types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
    try:
        import dns.resolver  # type: ignore

        for t in types:
            try:
                ans = dns.resolver.resolve(domain, t, lifetime=8)
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


def _grab_cert_sans(domain: str, port: int = 443) -> Optional[Dict[str, object]]:
    if not x509:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((domain, port), timeout=10) as sock:
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
    try:
        with socket.create_connection((host, port), timeout=6) as sock:
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
    # 1) hackertarget hostsearch (free, key-free)
    try:
        r = _http_get("https://api.hackertarget.com/hostsearch/", params={"q": domain})
        if r.status_code == 200 and r.text:
            body = r.text.strip()
            # Detect rate-limit or error responses (hackertarget returns 200 with error text)
            if body.lower().startswith("api count exceeded") or body.lower().startswith("error"):
                status["hackertarget"] = "rate_limited"
                log.warning("hackertarget rate limited for %s", domain)
            else:
                for line in body.splitlines():
                    if "," in line:
                        host, ip = line.split(",", 1)
                        host = host.strip().lower()
                        ip = ip.strip()
                        if host.endswith(domain) or domain in host:
                            if host not in found:
                                found[host] = SubdomainResult(hostname=host, sources=["hackertarget"])
                            if ip and ip not in found[host].ips:
                                found[host].ips.append(ip)
                status["hackertarget"] = "ok" if found else "no_results"
        else:
            status["hackertarget"] = f"http_{r.status_code}"
    except Exception as e:
        status["hackertarget"] = f"error: {type(e).__name__}"

    # 2) certspotter SANs (free, key-free) -> subdomains + certs
    try:
        r = _http_get(
            "https://api.certspotter.com/v1/issuances",
            params={"domain": domain, "include_subdomains": "true", "expand": "dns_names"},
        )
        if r.status_code == 200:
            for entry in r.json():
                for name in entry.get("dns_names", []):
                    name = name.lstrip("*.").lower()
                    if name.endswith(domain) or domain in name:
                        if name not in found:
                            found[name] = SubdomainResult(hostname=name, sources=["certspotter"])
                        elif "certspotter" not in found[name].sources:
                            found[name].sources.append("certspotter")
            status["certspotter"] = "ok" if any(s.sources == ["certspotter"] for s in found.values()) else "no_results"
        else:
            status["certspotter"] = f"http_{r.status_code}"
    except Exception as e:
        status["certspotter"] = f"error: {type(e).__name__}"

    # Ensure the apex domain is present.
    if domain not in found:
        found[domain] = SubdomainResult(hostname=domain, sources=["apex"])

    # Resolve DNS for all discovered hostnames to populate IPs.
    for sub in found.values():
        if not sub.ips:
            try:
                infos = socket.getaddrinfo(sub.hostname, None)
                resolved = sorted({i[4][0] for i in infos})
                sub.ips = resolved
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
    # Build probe targets: hostname + resolved IPs from all subdomains.
    hosts = [s.hostname for s in subdomains[:8]]
    ips: List[str] = []
    for s in subdomains[:8]:
        for ip in s.ips:
            if ip not in ips:
                ips.append(ip)
    # If no IPs resolved yet, resolve them now.
    if not ips:
        for host in hosts[:3]:
            try:
                infos = socket.getaddrinfo(host, None)
                for info in infos:
                    ip = info[4][0]
                    if ip not in ips:
                        ips.append(ip)
            except Exception:
                pass
    probe_targets = list(dict.fromkeys(hosts + ips))[:8]
    if not probe_targets:
        status["port-scan"] = "no_targets"
        return []
    results: List[PortResult] = []
    seen_ports = set()
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
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
    return results


def _collect_vulns(technologies: List[str], status: Dict[str, str]) -> List[VulnResult]:
    vulns: List[VulnResult] = []
    seen = set()
    # CISA KEV catalog (free).
    kev_ids = set()
    try:
        r = _http_get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
        if r.status_code == 200:
            cat = r.json().get("vulnerabilities", [])
            for v in cat:
                kev_ids.add(v.get("cveID"))
            status["cisa-kev"] = "ok"
        else:
            status["cisa-kev"] = f"http_{r.status_code}"
    except Exception as e:
        status["cisa-kev"] = f"error: {type(e).__name__}"

    # NVD keyword search — ONLY for actually detected technologies.
    # Never append hardcoded keywords; if no tech detected, skip NVD entirely.
    if not technologies:
        status["nvd"] = "skipped_no_tech"
        log.info("NVD lookup skipped for %s: no technologies detected", "unknown")
        return vulns

    keywords = list(dict.fromkeys(technologies))[:6]  # keep NVD calls bounded (rate limits)
    try:
        for kw in keywords:
            try:
                r = _http_get(
                    "https://services.nvd.nist.gov/rest/json/cves/2.0",
                    params={"keywordSearch": kw, "resultsPerPage": 5},
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
# Public entrypoint
# --------------------------------------------------------------------------- #
def lookup_domain(raw_query: str) -> IntelResult:
    """Run the full key-free OSINT aggregation for a domain/company."""
    domain = _normalize_domain(raw_query)
    result = IntelResult(query=domain)
    if not domain:
        result.sources_status["input"] = "empty"
        return result

    # DNS + subdomains run first (subdomains uses network too).
    result.dns_records = _resolve_dns(domain)
    result.subdomains = _collect_subdomains(domain, result.sources_status)

    # Certificates + ports can run with subdomain context.
    result.certificates = _collect_certificates(domain, result.sources_status)
    result.ports = _collect_ports(result.subdomains, result.sources_status)

    # Technology inference feeds vulnerability lookup.
    result.technologies = _infer_technologies(result.certificates, result.ports, result.subdomains)
    result.vulnerabilities = _collect_vulns(result.technologies, result.sources_status)

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
    }
