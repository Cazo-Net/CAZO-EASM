"""Turn per-scanner pipeline output into the shape the rest of the app stores.

This used to live inside ``EnhancedScanRunner`` and silently dropped every
vulnerability-stage result (security findings, exposure checks, cloud
buckets, CVE correlation), nested certificates under port numbers so the
SSL table stored empty rows, and ignored nmap's service versions. It is
also used *during* the pipeline so later stages see what earlier stages
found (``scan_results`` for security-findings and CVE correlation).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.scanners.v2.profiles import WEB_PORTS

TLS_PORTS = frozenset({
    443, 465, 636, 993, 995, 2083, 2087, 2096, 4443, 5986, 6443, 7443, 8443,
    8834, 9443, 10443, 12443,
})
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}

_SUBDOMAIN_SCANNERS = ("advanced-asset-discovery", "subdomain-intelligence")
_FINDING_SCANNERS = (
    "web-exposure", "security-findings", "exposure-validation", "cve-correlation",
    "nuclei-safe", "cloud_buckets", "certificate-intelligence",
)


def _flatten_cert(cert: Dict[str, Any]) -> Dict[str, Any]:
    """certificate-intelligence -> SSLCertificate column names."""
    def _name(d: Any) -> Optional[str]:
        if isinstance(d, dict):
            return d.get("commonName") or d.get("organizationName") or ", ".join(f"{k}={v}" for k, v in d.items())
        return d

    def _iso(s: Any) -> Optional[str]:
        if not s or not isinstance(s, str):
            return None
        from datetime import datetime
        for fmt in ("%b %d %H:%M:%S %Y %Z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s.replace("  ", " "), fmt).isoformat()
            except ValueError:
                continue
        try:
            datetime.fromisoformat(s)
            return s
        except ValueError:
            return None

    out = dict(cert)
    out["issuer"] = _name(cert.get("issuer"))
    out["subject"] = _name(cert.get("subject"))
    out["not_before"] = _iso(cert.get("not_before"))
    out["not_after"] = _iso(cert.get("not_after"))
    out["san_names"] = cert.get("san_names") or cert.get("san") or []
    out["version"] = cert.get("version") or cert.get("protocol")
    return out


def _merge_ports(existing: List[Dict[str, Any]], extra: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_port = {p.get("port"): dict(p) for p in existing if isinstance(p, dict)}
    for p in extra:
        if not isinstance(p, dict) or p.get("port") is None:
            continue
        cur = by_port.get(p["port"])
        if cur is None:
            by_port[p["port"]] = dict(p)
            continue
        # nmap -sV knows versions better than a banner guess.
        for key in ("service", "product", "version"):
            if p.get(key) and (not cur.get(key) or cur.get(key) == "unknown"):
                cur[key] = p[key]
            elif key in ("product", "version") and p.get(key):
                cur[key] = p[key]
    return sorted(by_port.values(), key=lambda x: x.get("port") or 0)


def normalize_finding(raw: Dict[str, Any], scanner: str, default_host: str) -> Optional[Dict[str, Any]]:
    """Map the different finding dialects onto the Vulnerability columns."""
    if not isinstance(raw, dict):
        return None
    if scanner == "cloud_buckets":
        if not raw.get("is_listing"):
            return None  # an existing private bucket with a guessed name is not a finding
        name = raw.get("bucket") or raw.get("account") or ""
        return {
            "template_id": f"cloud/{raw.get('provider', 'storage')}-public-listing",
            "name": f"Publicly listable cloud storage: {name}",
            "severity": "high",
            "vuln_type": "cloud_storage",
            "host": default_host,
            "matched_at": raw.get("url", ""),
            "description": (
                f"Storage container '{name}' ({raw.get('provider')}) lists its contents to anyone. "
                "Its name matches this domain; confirm it belongs to you before acting."
            ),
            "tags": ["cloud", "exposure", "needs-ownership-check"],
            "extracted_results": [f"HTTP {raw.get('status_code')}"],
            "reference": [],
            "source": scanner,
        }
    if "template_id" in raw and "name" in raw:
        f = dict(raw)
        f.setdefault("host", default_host)
        f.setdefault("matched_at", f.get("host", default_host))
        f.setdefault("source", scanner)
        return f
    # exposure-validation dialect
    url = raw.get("url") or ""
    details_host = (raw.get("details") or {}).get("subdomain") if isinstance(raw.get("details"), dict) else None
    host = raw.get("host") or details_host or default_host
    if url:
        from urllib.parse import urlsplit
        host = urlsplit(url).hostname or host
    category = raw.get("category") or "exposure"
    key = raw.get("header") or raw.get("path") or ""
    details = raw.get("details")
    return {
        "template_id": f"{scanner}/{category}" + (f"/{key.strip('/')}" if key else ""),
        "name": raw.get("description") or category.replace("_", " "),
        "severity": raw.get("severity", "info"),
        "vuln_type": category,
        "host": host,
        "matched_at": url or host,
        "description": raw.get("description", ""),
        "tags": [category],
        "extracted_results": [str(details)[:500]] if details else [],
        "reference": [],
        "source": scanner,
    }


def _dedupe_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for f in sorted(findings, key=lambda f: _SEV_RANK.get(f.get("severity", "unknown"), 9)):
        key = (f.get("template_id"), f.get("host"), str(f.get("matched_at", "")).rstrip("/"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def transform_pipeline_results(pipeline_result: Any, domain: str) -> Dict[str, Any]:
    transformed: Dict[str, Any] = {
        "subdomains": [],
        "ports": {},
        "dns": {},
        "technologies": {},
        "certificates": {},
        "whois": None,
        "vulnerabilities": [],
        "http_services": [],
    }
    nmap_ports: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []

    for stage_result in pipeline_result.stages.values():
        for scanner_name, sr in stage_result.scanner_results.items():
            if not sr.success or not sr.data:
                continue
            data = sr.data

            if scanner_name in _SUBDOMAIN_SCANNERS:
                subs = data.get("subdomains", data.get("discovered_subdomains", []))
                if isinstance(subs, list):
                    transformed["subdomains"].extend(s for s in subs if isinstance(s, str))
                elif isinstance(subs, dict):
                    transformed["subdomains"].extend(subs.keys())

            elif scanner_name == "network-intelligence":
                hosts = data.get("hosts", data.get("services", {}))
                if isinstance(hosts, dict):
                    for host, port_list in hosts.items():
                        if isinstance(port_list, list):
                            transformed["ports"][host] = _merge_ports(transformed["ports"].get(host, []), port_list)

            elif scanner_name == "nmap-intelligence":
                nmap_ports = [p for p in data.get("ports", []) if isinstance(p, dict)]

            elif scanner_name == "technology-intelligence":
                hosts = data.get("hosts", data.get("technologies", {}))
                if isinstance(hosts, dict):
                    for host, techs in hosts.items():
                        if isinstance(techs, list):
                            _merge_techs(transformed["technologies"], host, techs)

            elif scanner_name == "certificate-intelligence":
                certs = data.get("hosts") or {domain: data.get("certificates", {})}
                for host, per_port in (certs or {}).items():
                    if not isinstance(per_port, dict) or not per_port:
                        continue
                    if "issuer" in per_port or "subject" in per_port:
                        chosen = per_port
                    else:  # {"443": {...}, "8443": {...}}
                        chosen = per_port.get("443") or next(iter(per_port.values()))
                    if isinstance(chosen, dict):
                        transformed["certificates"][host] = _flatten_cert(chosen)

            elif "dns" in scanner_name.lower():
                hosts = data.get("hosts", data.get("dns", {}))
                if isinstance(hosts, dict):
                    transformed["dns"].update(hosts)

            if scanner_name == "web-exposure":
                transformed["http_services"].extend(data.get("http_services", []))
                for host, techs in (data.get("technologies") or {}).items():
                    _merge_techs(transformed["technologies"], host, techs)

            if scanner_name in _FINDING_SCANNERS:
                raw_list = data.get("vulnerabilities") or data.get("findings") or data.get("buckets") or []
                for raw in raw_list:
                    f = normalize_finding(raw, scanner_name, domain)
                    if f:
                        findings.append(f)

    if nmap_ports:
        transformed["ports"][domain] = _merge_ports(transformed["ports"].get(domain, []), nmap_ports)

    # Service banners carry versions (OpenSSH 8.2p1, nginx 1.18.0): expose them
    # as technologies so CVE correlation and the inventory see them.
    for host, port_list in transformed["ports"].items():
        techs = []
        for p in port_list:
            product = (p.get("product") or "").strip()
            version = (p.get("version") or "").strip()
            if product and len(product) <= 60 and version and version[0].isdigit():
                techs.append({"name": product, "category": "network_service",
                              "version": version.split()[0][:40], "confidence": 80,
                              "port": p.get("port")})
        if techs:
            _merge_techs(transformed["technologies"], host, techs)

    transformed["subdomains"] = sorted(set(transformed["subdomains"]))
    from app.scanners.finding_catalog import polish_findings
    transformed["vulnerabilities"] = polish_findings(_dedupe_findings(findings))
    return transformed


def _merge_techs(store: Dict[str, List[Dict[str, Any]]], host: str, techs: List[Dict[str, Any]]) -> None:
    merged = store.setdefault(host, [])
    index = {str(t.get("name", "")).lower(): t for t in merged}
    for t in techs:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        key = str(t["name"]).lower()
        cur = index.get(key)
        if cur is None:
            entry = dict(t)
            merged.append(entry)
            index[key] = entry
        elif t.get("version") and not cur.get("version"):
            cur["version"] = t["version"]


def scan_results_view(transformed: Dict[str, Any]) -> Dict[str, Any]:
    """The legacy key names security-findings and CVE correlation read."""
    return {
        "ports": transformed.get("ports", {}),
        "ssl_certificates": transformed.get("certificates", {}),
        "technologies": transformed.get("technologies", {}),
        "dns_records": transformed.get("dns", {}),
        "subdomains": transformed.get("subdomains", []),
    }


def web_targets_from_ports(ports_by_host: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Base URLs for every open port that speaks HTTP(S)."""
    urls: List[str] = []
    for host, port_list in sorted(ports_by_host.items()):
        for p in port_list or []:
            port = p.get("port")
            if not isinstance(port, int):
                continue
            http = p.get("http") or {}
            service = str(p.get("service") or "").lower()
            is_web = bool(http.get("detected")) or service.startswith("http") or port in WEB_PORTS
            if not is_web:
                continue
            tls = bool((p.get("tls") or {}).get("enabled")) or service in ("https", "https-alt", "ssl/http") or port in TLS_PORTS
            scheme = "https" if tls else "http"
            default = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
            urls.append(f"{scheme}://{host}" if default else f"{scheme}://{host}:{port}")
    # Probe HTTPS before HTTP so the HTTP->HTTPS redirect is recognised as a duplicate.
    return sorted(dict.fromkeys(urls), key=lambda u: (not u.startswith("https"), u))


def tls_endpoints_from_ports(ports_by_host: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = []
    for host, port_list in sorted(ports_by_host.items()):
        for p in port_list or []:
            port = p.get("port")
            if not isinstance(port, int):
                continue
            if (p.get("tls") or {}).get("enabled") or port in TLS_PORTS:
                out.append((host, port))
    return list(dict.fromkeys(out))
