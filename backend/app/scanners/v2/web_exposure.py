"""Web exposure scanner: fingerprint every in-scope web service and find
what it gives away to anyone on the internet.

For each web service the port scan found on an in-scope host it:

1. fetches the home page (following redirects only while they stay inside
   the authorized domain) and records status, title, server, technologies
   with versions, redirect chain and a body hash;
2. audits security headers, cookie flags and version disclosure;
3. requests a random path to learn how the site answers missing pages, so
   "soft 404" sites do not produce false positives;
4. checks a fixed list of paths for exposed secrets, source control,
   backups, debug endpoints, API specs, directory listings and admin
   panels, each confirmed by the response content (see exposure_rules);
5. reads the home page and a few same-site JavaScript files for leaked
   credentials, keeping only redacted previews and fingerprints.

Safety: single GET requests only, no logins, no form submission, no
payloads, bodies capped at 64 KB (2 MB for scripts), a per-host request
budget and rate, and every request passes the internal-address guard.
Hosts outside the authorized root domain are never contacted.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets as _secrets
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.target_guard import GUARDED_HOOKS, host_in_scope, normalize_target
from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.exposure_rules import (
    MAX_BODY_BYTES, RULES, ExposureRule, Probe, host_specific_rules, match_root_signatures,
)
from app.scanners.v2.ratelimit import BudgetExhausted, HostRateLimiter
from app.scanners.v2.registry import ScannerCategory, register_scanner
from app.scanners.v2.secret_patterns import find_secrets

logger = logging.getLogger(__name__)

USER_AGENT = "CAZO-EASM/2.1 (+https://cazoeasm.io; attack surface monitoring)"
MAX_SCRIPT_BYTES = 2 * 1024 * 1024
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

_TITLE_RE = re.compile(r"<title[^>]*>\s*([^<]{0,300}?)\s*</title>", re.I | re.S)
_SCRIPT_RE = re.compile(r"<script[^>]+src=[\"']([^\"'>]+)[\"']", re.I)
_GENERATOR_RE = re.compile(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']([^\"']+)", re.I)
_VERSION_IN_HEADER = re.compile(r"([A-Za-z][\w.\-]*?)[/ ]v?(\d+(?:\.\d+){1,3}[\w.\-]*)")
_PRIVATE_IP = re.compile(
    r"(?<![\d.])(10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\d.])"
)
_SESSION_COOKIE = re.compile(r"sess|sid|auth|token|jwt|login|remember", re.I)

_SECURITY_HEADERS = [
    # header, template id, title, severity, https only
    ("strict-transport-security", "headers/missing-hsts", "HSTS header missing", "medium", True),
    ("content-security-policy", "headers/missing-csp", "Content-Security-Policy header missing", "low", False),
    ("x-content-type-options", "headers/missing-xcto", "X-Content-Type-Options header missing", "low", False),
    ("referrer-policy", "headers/missing-referrer-policy", "Referrer-Policy header missing", "info", False),
]


def _finding(
    template_id: str, name: str, severity: str, host: str, url: str, description: str,
    *, category: str, remediation: str = "", evidence: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "template_id": template_id,
        "name": name,
        "severity": severity,
        "vuln_type": category,
        "host": host,
        "matched_at": url,
        "description": description + (f" Fix: {remediation}" if remediation else ""),
        "remediation": remediation,
        "tags": ["web-exposure", category, *(tags or [])],
        "extracted_results": evidence or [],
        "reference": [],
        "curl_command": f"curl -sk '{url}'" if url.startswith("http") else "",
        "source": "web-exposure",
    }


def _decode(body: bytes, headers: Dict[str, str]) -> str:
    ct = headers.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I)
    try:
        return body.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _norm_body_hash(text: str) -> str:
    # Remove things that change per request (the path we asked for, tokens, times).
    t = re.sub(r"[0-9a-f]{16,}|\d{2,}", "", text.lower())
    return hashlib.sha256(t.encode("utf-8", "replace")).hexdigest()


def parse_web_target(url: str) -> Tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = parts.scheme or "https"
    host = (parts.hostname or "").lower()
    port = parts.port or (443 if scheme == "https" else 80)
    return scheme, host, port


def _base(scheme: str, host: str, port: int) -> str:
    default = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    return f"{scheme}://{host}" if default else f"{scheme}://{host}:{port}"


@register_scanner(
    name="web-exposure",
    category=ScannerCategory.WEB_EXPOSURE,
    version="1.0.0",
    priority=ScannerPriority.HIGH,
    description=(
        "Fingerprints every in-scope web service and finds publicly exposed secrets, "
        "config, source control, backups, debug endpoints, directory listings and admin panels"
    ),
    capabilities=[
        "http_fingerprinting", "security_headers", "sensitive_file_detection",
        "directory_listing", "admin_panel_detection", "secret_detection",
    ],
)
class WebExposureScanner(EnhancedBaseScanner):
    name = "web-exposure"
    version = "1.0.0"
    category = ScannerCategory.WEB_EXPOSURE
    priority = ScannerPriority.HIGH

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = dict(config or {})
        super().__init__(cfg)
        # One long pass; a retry would repeat every request against the customer.
        self.max_retries = 0
        budget_s = float(cfg.get("pipeline_timeout_s", 900))
        self.timeout = max(float(cfg.get("timeout", 30)), budget_s * 0.5)
        self.max_targets = int(cfg.get("max_web_targets", 20))
        self.max_js = int(cfg.get("max_js_files", 5))
        self.exposure_checks = bool(cfg.get("exposure_checks", True))
        self.host_parallelism = int(cfg.get("web_host_parallelism", 8))
        self.limiter = HostRateLimiter(
            concurrency=int(cfg.get("http_concurrency_per_host", 3)),
            rps=float(cfg.get("http_rps_per_host", 5.0)),
            budget=int(cfg.get("max_requests_per_host", 220)),
        )
        self._transport = cfg.get("_transport")       # tests inject httpx.MockTransport
        self._hooks = cfg.get("_event_hooks", GUARDED_HOOKS)

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    # ── HTTP helpers ─────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = dict(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
            event_hooks=self._hooks,
        )
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def _get(self, client: httpx.AsyncClient, url: str, limit: int = MAX_BODY_BYTES) -> Optional[Probe]:
        host = urlsplit(url).hostname or ""
        try:
            async with self.limiter.slot(host):
                async with client.stream("GET", url) as resp:
                    chunks: List[bytes] = []
                    size = 0
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
                        size += len(chunk)
                        if size >= limit:
                            break
                    body = b"".join(chunks)[:limit]
                    headers = {k.lower(): v for k, v in resp.headers.items()}
                    if "set-cookie" in resp.headers:
                        headers["set-cookie"] = "\n".join(resp.headers.get_list("set-cookie"))
                    return Probe(resp.status_code, headers, body, _decode(body, headers))
        except BudgetExhausted:
            return None
        except (httpx.HTTPError, OSError, asyncio.TimeoutError) as exc:
            logger.debug("GET %s failed: %s", url, exc)
            return None

    async def _fetch_root(
        self, client: httpx.AsyncClient, base: str, root_domain: str,
    ) -> Tuple[Optional[Probe], str, List[str], Optional[str]]:
        """GET / following redirects only within the authorized domain."""
        url = base + "/"
        chain: List[str] = []
        for _ in range(6):
            probe = await self._get(client, url)
            if probe is None:
                return None, url, chain, None
            loc = probe.headers.get("location")
            if probe.status in (301, 302, 303, 307, 308) and loc:
                nxt = urljoin(url, loc)
                chain.append(f"{probe.status} {nxt}")
                nhost = urlsplit(nxt).hostname or ""
                if not host_in_scope(nhost, root_domain):
                    return probe, url, chain, nxt
                url = nxt
                continue
            return probe, url, chain, None
        return probe, url, chain, None

    # ── Main entry ───────────────────────────────────────────────────────

    async def scan(self, target: str, **kwargs) -> ScanResult:
        root_domain = normalize_target(kwargs.get("root_domain") or target)
        web_targets: List[str] = list(kwargs.get("web_targets") or [])
        if not web_targets:
            web_targets = [f"https://{target}", f"http://{target}"]

        # Scope gate: never contact a host outside the authorized domain,
        # whatever the caller passed in.
        in_scope: List[str] = []
        skipped: List[str] = []
        for u in dict.fromkeys(web_targets):
            _, host, _ = parse_web_target(u)
            (in_scope if host and host_in_scope(host, root_domain) else skipped).append(u)
        if skipped:
            logger.info("web-exposure: %d target(s) outside %s skipped", len(skipped), root_domain)
        in_scope = in_scope[: self.max_targets]

        findings: List[Dict[str, Any]] = []
        services: List[Dict[str, Any]] = []
        technologies: Dict[str, List[Dict[str, Any]]] = {}
        seen_final: Dict[str, str] = {}
        sem = asyncio.Semaphore(self.host_parallelism)
        started = time.monotonic()

        # Services on the same host run one after another (HTTPS first), so a
        # plain-HTTP copy of the same site is recognised and not checked twice.
        by_host: Dict[str, List[str]] = {}
        for u in sorted(in_scope, key=lambda u: (not u.startswith("https"), u)):
            by_host.setdefault(parse_web_target(u)[1], []).append(u)

        async with self._client() as client:
            async def _host(urls: List[str]) -> None:
                async with sem:
                    content_seen: Dict[str, str] = {}
                    for url in urls:
                        try:
                            svc, f, techs = await self._scan_service(
                                client, url, root_domain, seen_final, content_seen)
                        except Exception as exc:  # noqa: BLE001 — one service must not sink the scan
                            logger.warning("web-exposure failed for %s: %s", url, exc)
                            continue
                        if svc:
                            services.append(svc)
                            merged = technologies.setdefault(svc["host"], [])
                            names = {t["name"].lower() for t in merged}
                            merged.extend(t for t in techs if t["name"].lower() not in names)
                        findings.extend(f)

            await asyncio.gather(*(_host(urls) for urls in by_host.values()))

        findings = _dedupe(findings)
        findings.sort(key=lambda f: _SEV_RANK.get(f["severity"], 9))
        counts: Dict[str, int] = {}
        for f in findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "findings": findings,
                "vulnerabilities": findings,
                "http_services": sorted(services, key=lambda s: s["url"]),
                "technologies": technologies,
                "summary": {
                    "web_services": len(services),
                    "targets_requested": len(in_scope),
                    "targets_out_of_scope": len(skipped),
                    "findings": len(findings),
                    "severity_breakdown": counts,
                    "duration_s": round(time.monotonic() - started, 1),
                },
            },
        )

    async def _scan_service(
        self, client: httpx.AsyncClient, url: str, root_domain: str, seen_final: Dict[str, str],
        content_seen: Optional[Dict[str, str]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        scheme, host, port = parse_web_target(url)
        base = _base(scheme, host, port)
        root, final_url, chain, offscope = await self._fetch_root(client, base, root_domain)
        if root is None:
            return None, [], []

        findings: List[Dict[str, Any]] = []
        title_m = _TITLE_RE.search(root.text)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
        techs = self._technologies(root, final_url)
        svc = {
            "url": base,
            "host": host,
            "port": port,
            "scheme": scheme,
            "status": root.status,
            "final_url": final_url,
            "redirect_chain": chain,
            "redirects_off_scope_to": offscope,
            "title": title[:200],
            "server": root.headers.get("server", ""),
            "powered_by": root.headers.get("x-powered-by", ""),
            "content_type": root.headers.get("content-type", ""),
            "content_length": len(root.body),
            "body_sha256": hashlib.sha256(root.body).hexdigest(),
            "technologies": [t["name"] + (f" {t['version']}" if t.get("version") else "") for t in techs],
        }

        # A plain-HTTP service that just redirects to HTTPS on the same host
        # gets fingerprinted but not path-checked twice.
        f_scheme, f_host, f_port = parse_web_target(final_url)
        final_key = _base(f_scheme, f_host, f_port)
        duplicate = final_key != base and final_key in seen_final
        seen_final.setdefault(final_key, base)
        # Same page already served on another scheme/port of this host.
        if content_seen is not None:
            body_key = svc["body_sha256"]
            if root.status == 200 and body_key in content_seen and content_seen[body_key] != base:
                duplicate = True
                svc["same_content_as"] = content_seen[body_key]
            content_seen.setdefault(body_key, base)
        check_base = final_key if host_in_scope(f_host, root_domain) else base

        if offscope is None and not duplicate:
            findings += self._header_findings(root, host, final_url, f_scheme)
        for rule_id, rtitle, sev in match_root_signatures(root):
            findings.append(_finding(
                rule_id, rtitle, sev, host, final_url,
                f"{rtitle} at {final_url} (page title: {title or 'none'}).", category="admin_panel"
                if rule_id.startswith("panel/") else "exposure",
            ))
        if f_scheme == "http" and re.search(r"<input[^>]+type=[\"']?password", root.text, re.I):
            findings.append(_finding(
                "web/login-over-http", "Login form served over plain HTTP", "high", host, final_url,
                f"{final_url} serves a password form without TLS, so credentials cross the network in clear text.",
                category="transport", remediation="Redirect all HTTP traffic to HTTPS and enable HSTS.",
            ))

        # Secrets in what every visitor already downloads.
        if not duplicate:
            findings += await self._secret_findings(client, root, final_url, host, root_domain)

        if self.exposure_checks and not duplicate and offscope is None:
            findings += await self._path_checks(client, check_base, host)
        return svc, findings, techs

    # ── Fingerprinting ───────────────────────────────────────────────────

    def _technologies(self, probe: Probe, url: str) -> List[Dict[str, Any]]:
        techs: List[Dict[str, Any]] = []
        try:
            from app.scanners.v2.tech_intel import TechnologyIntelligenceScanner
            detector = TechnologyIntelligenceScanner.__new__(TechnologyIntelligenceScanner)
            for t in detector._detect_technologies(probe.headers, {}, probe.text[:50000], url):
                techs.append({"name": t["name"], "category": t["category"], "version": None,
                              "confidence": t.get("confidence", 75)})
        except Exception as exc:  # noqa: BLE001
            logger.debug("tech fingerprint failed for %s: %s", url, exc)

        def _add(name: str, version: Optional[str], category: str, confidence: int = 95) -> None:
            for t in techs:
                if t["name"].lower() == name.lower():
                    if version and not t.get("version"):
                        t["version"] = version
                    return
            techs.append({"name": name, "category": category, "version": version, "confidence": confidence})

        for header, category in (("server", "web_server"), ("x-powered-by", "framework"),
                                 ("x-aspnet-version", "framework"), ("x-generator", "cms")):
            value = probe.headers.get(header, "")
            if not value:
                continue
            m = _VERSION_IN_HEADER.search(value)
            if header == "x-aspnet-version":
                _add("ASP.NET", value.strip(), category)
            elif m:
                _add(m.group(1), m.group(2), category)
            else:
                _add(value.split("/")[0].strip()[:60], None, category, 80)
        gen = _GENERATOR_RE.search(probe.text)
        if gen:
            m = re.match(r"\s*([A-Za-z][\w .\-]*?)\s+v?(\d+(?:\.\d+)+)", gen.group(1))
            if m:
                _add(m.group(1).strip(), m.group(2), "cms")
            else:
                _add(gen.group(1).strip()[:60], None, "cms", 80)
        return techs

    def _header_findings(self, probe: Probe, host: str, url: str, scheme: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if probe.status >= 400 or "html" not in probe.headers.get("content-type", "html"):
            return out
        h = probe.headers
        for name, tid, title, sev, https_only in _SECURITY_HEADERS:
            if https_only and scheme != "https":
                continue
            if name not in h:
                out.append(_finding(tid, title, sev, host, url, f"{url} does not send {name}.",
                                    category="security_header",
                                    remediation=f"Add the {name} response header."))
        csp = h.get("content-security-policy", "")
        if "x-frame-options" not in h and "frame-ancestors" not in csp:
            out.append(_finding("headers/missing-clickjacking-protection", "No clickjacking protection", "low",
                                host, url, f"{url} sends neither X-Frame-Options nor CSP frame-ancestors.",
                                category="security_header",
                                remediation="Send X-Frame-Options: DENY or CSP frame-ancestors 'none'."))
        hsts = h.get("strict-transport-security", "")
        m = re.search(r"max-age=(\d+)", hsts)
        if scheme == "https" and m and int(m.group(1)) < 15552000:
            out.append(_finding("headers/weak-hsts", "HSTS max-age shorter than 180 days", "low", host, url,
                                f"HSTS max-age is {m.group(1)} seconds.", category="security_header",
                                remediation="Use max-age=31536000; includeSubDomains."))
        acao = h.get("access-control-allow-origin", "")
        if acao == "*" and h.get("access-control-allow-credentials", "").lower() == "true":
            out.append(_finding("headers/cors-wildcard-credentials", "CORS allows any origin with credentials",
                                "high", host, url, "Access-Control-Allow-Origin: * combined with credentials.",
                                category="cors"))
        disclosed = []
        for name in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"):
            if re.search(r"\d+\.\d+", h.get(name, "")):
                disclosed.append(f"{name}: {h[name][:80]}")
        if disclosed:
            out.append(_finding("headers/version-disclosure", "Software version disclosed in headers", "low",
                                host, url, "Response headers reveal exact software versions: " + "; ".join(disclosed) + ".",
                                category="information_disclosure", evidence=disclosed,
                                remediation="Hide version numbers (server_tokens off, expose_php Off, remove X-Powered-By)."))
        weak = []
        for line in h.get("set-cookie", "").split("\n"):
            if not line.strip():
                continue
            cname = line.split("=", 1)[0].strip()
            if not _SESSION_COOKIE.search(cname):
                continue
            low = line.lower()
            missing = [flag for flag, present in (
                ("Secure", "secure" in low or scheme != "https"),
                ("HttpOnly", "httponly" in low),
                ("SameSite", "samesite" in low),
            ) if not present]
            if missing:
                weak.append(f"{cname}: missing {', '.join(missing)}")
        if weak:
            out.append(_finding("headers/insecure-session-cookie", "Session cookie missing security flags", "low",
                                host, url, "Session-like cookies lack flags: " + "; ".join(weak) + ".",
                                category="security_header", evidence=weak,
                                remediation="Set Secure, HttpOnly and SameSite on session cookies."))
        leaked_ips = sorted(set(_PRIVATE_IP.findall(" ".join(f"{k}: {v}" for k, v in h.items()))))
        if leaked_ips:
            out.append(_finding("headers/internal-ip-disclosure", "Internal IP address disclosed in headers", "low",
                                host, url, "Headers reveal internal addresses: " + ", ".join(leaked_ips[:5]) + ".",
                                category="information_disclosure", evidence=leaked_ips[:5]))
        return out

    # ── Secrets in public content ────────────────────────────────────────

    async def _secret_findings(
        self, client: httpx.AsyncClient, root: Probe, page_url: str, host: str, root_domain: str,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        sources: List[Tuple[str, str]] = [(page_url, root.text)]
        scripts: List[str] = []
        for src in _SCRIPT_RE.findall(root.text):
            full = urljoin(page_url, src)
            shost = urlsplit(full).hostname or ""
            if full.startswith(("http://", "https://")) and host_in_scope(shost, root_domain):
                scripts.append(full)
        for js_url in list(dict.fromkeys(scripts))[: self.max_js]:
            probe = await self._get(client, js_url, limit=MAX_SCRIPT_BYTES)
            if probe and probe.status == 200 and not probe.text.lstrip().lower().startswith("<!doctype"):
                sources.append((js_url, probe.text))
        for src_url, text in sources:
            for s in find_secrets(text):
                out.append(_finding(
                    f"secrets/{s['rule_id']}", f"{s['name']} exposed in public content", s["severity"],
                    host, src_url,
                    f"A {s['name'].lower()} is visible to anyone who loads {src_url}. "
                    "Only a redacted preview is stored.",
                    category="secret_exposure",
                    remediation="Remove the secret from client-side code, revoke it, and issue a new one kept server-side.",
                    evidence=[f"{s['redacted']} (fingerprint {s['fingerprint']})"],
                    tags=[s["rule_id"]],
                ))
        return out

    # ── Path checks ──────────────────────────────────────────────────────

    async def _path_checks(self, client: httpx.AsyncClient, base: str, host: str) -> List[Dict[str, Any]]:
        # How does this site answer a page that cannot exist?
        canary = await self._get(client, f"{base}/cazo-{_secrets.token_hex(6)}-check")
        soft404_hash = _norm_body_hash(canary.text) if canary is not None and canary.status == 200 else None

        rules: List[ExposureRule] = list(RULES) + host_specific_rules(host)
        cache: Dict[str, Optional[Probe]] = {}
        out: List[Dict[str, Any]] = []

        for rule in rules:
            for path in rule.paths:
                if self.limiter.remaining(host) <= 0:
                    return out
                url = base + path
                if url not in cache:
                    cache[url] = await self._get(client, url)
                probe = cache[url]
                if probe is None or probe.status not in rule.statuses:
                    continue
                if soft404_hash and probe.status == 200 and _norm_body_hash(probe.text) == soft404_hash:
                    continue
                try:
                    hit = rule.check(probe)
                except Exception:  # noqa: BLE001
                    hit = False
                if not hit:
                    continue
                evidence = [f"HTTP {probe.status}, {len(probe.body)} bytes read"
                            + (" (truncated)" if len(probe.body) >= MAX_BODY_BYTES else "")]
                severity = rule.severity
                if rule.scan_for_secrets:
                    leaked = find_secrets(probe.text)
                    evidence += [f"{s['name']}: {s['redacted']} (fingerprint {s['fingerprint']})" for s in leaked]
                    if leaked and _SEV_RANK.get(severity, 9) > 0:
                        severity = "critical" if any(s["severity"] == "critical" for s in leaked) else "high"
                out.append(_finding(
                    rule.rule_id, rule.title, severity, host, url,
                    f"{rule.title}: {url} returned content matching the expected format.",
                    category=rule.category, remediation=rule.remediation, evidence=evidence,
                ))
                break  # one confirmed path per rule is enough
        return out


def _dedupe(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for f in findings:
        key = (f["template_id"], f["host"], f["matched_at"].rstrip("/"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
