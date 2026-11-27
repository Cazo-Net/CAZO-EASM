"""Deeper scanning: profiles, web exposure checks, secret redaction, scope."""
from __future__ import annotations

import asyncio
import datetime as dt

import httpx
import pytest

from app.scanners.v2 import profiles
from app.scanners.v2.exposure_rules import Probe, find_rule
from app.scanners.v2.normalize import (
    normalize_finding, transform_pipeline_results, web_targets_from_ports,
)
from app.scanners.v2.pipeline import PipelineResult, PipelineStage, StageResult
from app.scanners.v2.ratelimit import BudgetExhausted, HostRateLimiter
from app.scanners.v2.secret_patterns import find_secrets, redact
from app.scanners.v2.base import ScanResult

AWS_KEY = "AKIAIOSFODNN7EXAMPLQ"


# ── Profiles ────────────────────────────────────────────────────────────────

def test_full_scan_profile_checks_far_more_than_ten_ports():
    p = profiles.resolve_profile("full")
    assert p.name == "standard"
    assert len(p.ports) > 1000
    assert set(range(1, 1025)) <= set(p.ports)
    for port in (22, 443, 3306, 5432, 6379, 9200, 27017, 2375, 11211):
        assert port in p.ports


def test_quick_and_deep_profiles():
    assert len(profiles.resolve_profile("quick").ports) < 40
    deep = profiles.resolve_profile("full", {"depth": "deep"})
    assert deep.name == "deep"
    assert set(range(1, 10001)) <= set(deep.ports)


def test_profile_timeout_stays_inside_queue_job_timeout(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "SCAN_TIMEOUT_FULL_MINUTES", 10)
    p = profiles.resolve_profile("full", {"depth": "deep"})
    assert p.pipeline_timeout_s <= 10 * 60 - 120


def test_v2_runner_no_longer_forces_ten_ports(monkeypatch):
    from app.scanners.v2_runner import V2ScanRunner

    captured = {}

    async def fake_run_scan(self, domain, config=None, progress_callback=None,
                            included_scanners=None, excluded_scanners=None):
        captured["config"] = config
        captured["excluded"] = excluded_scanners
        return {"pipeline": {}, "assets": {}, "risk_score": {}, "graph": {}}

    monkeypatch.setattr("app.scanners.v2.runner.EnhancedScanRunner.run_scan", fake_run_scan)
    asyncio.run(V2ScanRunner().run_full_scan("example.com", options={"port_mode": "full"}))
    assert len(captured["config"]["top_ports"]) > 1000
    assert captured["config"]["pipeline_timeout"] > 300
    assert "nmap-intelligence" in captured["excluded"]

    asyncio.run(V2ScanRunner().run_full_scan("example.com", options={"depth": "deep"}))
    assert captured["config"]["profile"] == "deep"


# ── Secrets ─────────────────────────────────────────────────────────────────

def test_secrets_are_found_and_redacted():
    text = f'const cfg = {{aws: "{AWS_KEY}", stripe: "sk_live_{"a1B2" * 6}"}};'
    hits = find_secrets(text)
    ids = {h["rule_id"] for h in hits}
    assert {"aws-access-key-id", "stripe-secret-key"} <= ids
    for h in hits:
        assert AWS_KEY not in h["redacted"]
        assert "…" in h["redacted"]
        assert len(h["fingerprint"]) == 16


def test_placeholders_are_not_secrets():
    assert find_secrets("DB_PASSWORD=changeme\nAPI_KEY=your_api_key_here\n") == []


def test_redact_short_values():
    assert "secret" not in redact("secret12")


# ── Exposure rules ──────────────────────────────────────────────────────────

def _probe(text: str, ct: str = "text/plain", status: int = 200, body: bytes | None = None) -> Probe:
    return Probe(status, {"content-type": ct}, body if body is not None else text.encode(), text)


def test_env_rule_needs_real_env_content():
    rule = find_rule("exposure/env-file")
    assert rule.check(_probe("APP_KEY=base64:abc\nDB_PASSWORD=s3cr3t-Value\n"))
    assert not rule.check(_probe("<!doctype html><html>APP=1\nB=2</html>", "text/html"))
    assert not rule.check(_probe("Not found"))


def test_git_and_archive_rules():
    assert find_rule("exposure/git-repository").check(_probe("ref: refs/heads/main\n"))
    assert not find_rule("exposure/git-repository").check(_probe("<html>ref: refs/heads</html>", "text/html"))
    archive = find_rule("exposure/backup-archive")
    assert archive.check(_probe("", "application/zip", body=b"PK\x03\x04rest"))
    assert not archive.check(_probe("<html>", "text/html", body=b"<html>"))


def test_rate_limiter_budget():
    lim = HostRateLimiter(concurrency=2, rps=0, budget=2)

    async def go():
        for _ in range(2):
            async with lim.slot("a.example.com"):
                pass
        with pytest.raises(BudgetExhausted):
            async with lim.slot("a.example.com"):
                pass

    asyncio.run(go())


# ── Web exposure scanner against a fake site ────────────────────────────────

def _site(requests_seen, soft404=False):
    page = (
        "<html><head><title>Acme Portal</title><meta name='generator' content='WordPress 6.4.2'>"
        "<script src='/static/app.js'></script><script src='https://cdn.thirdparty.net/x.js'></script>"
        "</head><body>hi</body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(str(request.url))
        host, path = request.url.host, request.url.path
        if host != "app.example.com":
            return httpx.Response(200, text="should never be fetched")
        if soft404:
            return httpx.Response(200, text="<html><title>Acme</title>Welcome</html>",
                                  headers={"content-type": "text/html"})
        if path == "/":
            return httpx.Response(200, text=page, headers={
                "content-type": "text/html", "server": "nginx/1.18.0",
                "set-cookie": "sessionid=abc; Path=/",
            })
        if path == "/static/app.js":
            return httpx.Response(200, text=f'var k="{AWS_KEY}";',
                                  headers={"content-type": "application/javascript"})
        if path == "/.env":
            return httpx.Response(200, text=f"APP_ENV=production\nAWS_ACCESS_KEY_ID={AWS_KEY}\n")
        if path == "/.git/HEAD":
            return httpx.Response(200, text="ref: refs/heads/main\n")
        if path == "/old":
            return httpx.Response(302, headers={"location": "https://other-company.com/"})
        return httpx.Response(404, text="nope")

    return handler


def _scanner(handler, **cfg):
    from app.scanners.v2.web_exposure import WebExposureScanner
    return WebExposureScanner({
        "_transport": httpx.MockTransport(handler), "_event_hooks": {},
        "http_rps_per_host": 0, "max_requests_per_host": 500, **cfg,
    })


def test_web_exposure_finds_confirmed_exposures_and_redacts():
    seen = []
    scanner = _scanner(_site(seen))
    res = asyncio.run(scanner.scan(
        "example.com", root_domain="example.com",
        web_targets=["https://app.example.com", "https://evil.other.com"],
    ))
    assert res.success
    ids = {f["template_id"] for f in res.data["findings"]}
    assert "exposure/env-file" in ids
    assert "exposure/git-repository" in ids
    assert "secrets/aws-access-key-id" in ids
    assert "headers/missing-hsts" in ids
    assert "headers/version-disclosure" in ids
    assert "headers/insecure-session-cookie" in ids

    env = next(f for f in res.data["findings"] if f["template_id"] == "exposure/env-file")
    assert env["severity"] == "critical"
    blob = repr(res.data)
    assert AWS_KEY not in blob, "raw secret must never be stored"

    # Scope: nothing outside the authorized domain was contacted, including
    # the third-party script and the out-of-scope target.
    assert seen and all("app.example.com" in u for u in seen)
    svc = res.data["http_services"][0]
    assert svc["title"] == "Acme Portal"
    techs = {t["name"].lower(): t.get("version") for t in res.data["technologies"]["app.example.com"]}
    assert techs.get("nginx") == "1.18.0"
    assert techs.get("wordpress") == "6.4.2"


def test_soft_404_site_produces_no_path_findings():
    seen = []
    scanner = _scanner(_site(seen, soft404=True))
    res = asyncio.run(scanner.scan("example.com", root_domain="example.com",
                                   web_targets=["https://app.example.com"]))
    path_hits = [f for f in res.data["findings"]
                 if f["template_id"].startswith(("exposure/", "panel/"))]
    assert path_hits == []


def test_request_budget_caps_load_per_host():
    seen = []
    scanner = _scanner(_site(seen), max_requests_per_host=15)
    asyncio.run(scanner.scan("example.com", root_domain="example.com",
                             web_targets=["https://app.example.com"]))
    assert len(seen) <= 15


def test_redirects_off_scope_are_not_followed():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "app.example.com" and request.url.path == "/":
            return httpx.Response(302, headers={"location": "https://other-company.com/"})
        return httpx.Response(200, text="x")

    scanner = _scanner(handler)
    res = asyncio.run(scanner.scan("example.com", root_domain="example.com",
                                   web_targets=["https://app.example.com"]))
    assert not any("other-company.com" in u for u in seen)
    assert res.data["http_services"][0]["redirects_off_scope_to"] == "https://other-company.com/"


# ── Normalisation: findings and certificates reach storage ──────────────────

def _pipeline(*scanner_data):
    pr = PipelineResult(target="example.com")
    st = StageResult(stage=PipelineStage.VULNERABILITY_ASSESSMENT)
    for name, data in scanner_data:
        st.scanner_results[name] = ScanResult(success=True, scanner=name, target="example.com", data=data)
    pr.stages["x"] = st
    return pr


def test_transform_keeps_vulnerability_stage_findings():
    pr = _pipeline(
        ("web-exposure", {"findings": [{"template_id": "exposure/env-file", "name": "env", "severity": "critical",
                                         "host": "app.example.com", "matched_at": "https://app.example.com/.env"}],
                          "http_services": [{"url": "https://app.example.com"}],
                          "technologies": {"app.example.com": [{"name": "nginx", "version": "1.18.0"}]}}),
        ("exposure-validation", {"findings": [{"category": "cors_misconfiguration", "severity": "high",
                                               "url": "https://example.com", "description": "CORS reflects"}]}),
        ("cloud_buckets", {"buckets": [
            {"provider": "aws_s3", "bucket": "example-backup", "url": "https://example-backup.s3.amazonaws.com",
             "is_listing": True, "status_code": 200},
            {"provider": "aws_s3", "bucket": "example", "url": "https://example.s3.amazonaws.com",
             "is_listing": False, "status_code": 403},
        ]}),
        ("certificate-intelligence", {"hosts": {"example.com": {"443": {
            "subject": {"commonName": "example.com"}, "issuer": {"commonName": "R3"},
            "not_before": "2026-01-01T00:00:00+00:00", "not_after": "2026-04-01T00:00:00+00:00",
            "san": ["example.com"], "protocol": "TLSv1.3", "is_valid": True, "grade": "A"}}},
            "findings": []}),
        ("network-intelligence", {"hosts": {"example.com": [
            {"port": 22, "service": "ssh", "product": "OpenSSH", "version": "8.2p1 Ubuntu"}]}}),
    )
    out = transform_pipeline_results(pr, "example.com")
    ids = {v["template_id"] for v in out["vulnerabilities"]}
    assert "exposure/env-file" in ids
    assert any(i.startswith("exposure-validation/cors_misconfiguration") for i in ids)
    assert "cloud/aws_s3-public-listing" in ids
    assert len([i for i in ids if i.startswith("cloud/")]) == 1, "private guessed buckets are not findings"
    cert = out["certificates"]["example.com"]
    assert cert["issuer"] == "R3" and cert["not_after"].startswith("2026-04-01")
    dt.datetime.fromisoformat(cert["not_before"])
    techs = {t["name"]: t.get("version") for t in out["technologies"]["example.com"]}
    assert techs["OpenSSH"] == "8.2p1"
    assert out["http_services"]


def test_web_targets_from_ports():
    urls = web_targets_from_ports({
        "app.example.com": [{"port": 443}, {"port": 80}, {"port": 8080, "http": {"detected": True}},
                            {"port": 22, "service": "ssh"}],
    })
    assert urls == ["https://app.example.com", "http://app.example.com", "http://app.example.com:8080"]


def test_normalize_finding_passthrough():
    f = normalize_finding({"template_id": "x", "name": "y", "severity": "low"}, "security-findings", "example.com")
    assert f["host"] == "example.com"


# ── Optional tools ──────────────────────────────────────────────────────────

def test_nuclei_output_is_scoped_and_redacted():
    from app.scanners.v2.external_tools import parse_nuclei_jsonl
    lines = "\n".join([
        '{"template-id":"exposed-env","info":{"name":"Env","severity":"high","tags":["exposure"]},'
        f'"host":"https://app.example.com","matched-at":"https://app.example.com/.env","extracted-results":["{AWS_KEY}"]}}',
        '{"template-id":"x","info":{"name":"X","severity":"high"},"host":"https://elsewhere.org"}',
    ])
    out = parse_nuclei_jsonl(lines, "example.com")
    assert len(out) == 1
    assert AWS_KEY not in repr(out)


def test_nuclei_is_off_by_default():
    from app.scanners.v2.external_tools import NucleiSafeScanner
    res = asyncio.run(NucleiSafeScanner({}).scan("example.com"))
    assert res.data["vulnerabilities"] == []
    assert res.data["status"] in ("disabled", "not_installed")


# ── TLS certificate parsing ─────────────────────────────────────────────────

def test_certificate_parsing_and_hostname_match():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from app.scanners.v2.cert_intel import _hostname_matches, _parse_der_certificate

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.com")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(1234).not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("*.example.com"), x509.DNSName("example.com")]), False)
        .sign(key, hashes.SHA256())
    )
    info = _parse_der_certificate(cert.public_bytes(serialization.Encoding.DER))
    assert info["key_type"] == "RSA" and info["key_bits"] == 2048
    assert info["issuer"] == info["subject"]
    assert 28 <= info["_days_left"] <= 30
    assert _hostname_matches("api.example.com", info["san"], None)
    assert not _hostname_matches("a.b.example.com", info["san"], None)
    assert not _hostname_matches("example.org", info["san"], None)


# ── Pipeline hands later stages what earlier stages found ───────────────────

def test_stage_kwargs_feed_web_tls_and_vuln_stages():
    from app.scanners.v2.pipeline import PipelineContext, ScanPipeline

    ctx = PipelineContext(target="example.com")
    ctx.discovered_assets = [{"hostname": "example.com"}, {"hostname": "api.example.com"}]
    pr = PipelineResult(target="example.com")
    st = StageResult(stage=PipelineStage.NETWORK_INTELLIGENCE)
    st.scanner_results["network-intelligence"] = ScanResult(
        success=True, scanner="network-intelligence", target="example.com",
        data={"hosts": {"example.com": [{"port": 443}, {"port": 6379, "service": "redis"}],
                        "api.example.com": [{"port": 8443}]}},
    )
    pr.stages["network_intelligence"] = st
    pipe = ScanPipeline()

    web = pipe._stage_kwargs(PipelineStage.WEB_EXPOSURE, "example.com", ctx, {}, pr)
    assert web["root_domain"] == "example.com"
    assert "https://example.com" in web["web_targets"]
    assert "https://api.example.com:8443" in web["web_targets"]
    assert not any(":6379" in u for u in web["web_targets"])

    tls = pipe._stage_kwargs(PipelineStage.CERTIFICATE_ANALYSIS, "example.com", ctx, {"tls_max_endpoints": 10}, pr)
    assert ("api.example.com", 8443) in tls["tls_endpoints"]

    vuln = pipe._stage_kwargs(PipelineStage.VULNERABILITY_ASSESSMENT, "example.com", ctx, {}, pr)
    assert 6379 in vuln["open_ports"]
    assert "example.com" in vuln["scan_results"]["ports"]
    assert vuln["subdomains"] == ["api.example.com"]
