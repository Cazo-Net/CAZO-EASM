"""Dark web & threat intelligence: real sources only, scope-gated, tenant-isolated."""
import uuid

import pytest

from app.config import settings
from app.models.organization import Organization
from app.models.scope import AuthorizedScope
from app.models.threat_intel import ThreatIntelFinding, ThreatIntelMonitor
from app.models.user import User
from app.services import threat_intel as ti
from tests.conftest import TestingSessionLocal

BREACH = {
    "Name": "Acme2024", "Title": "Acme Forum", "Domain": "acmeforum.test", "BreachDate": "2024-05-01",
    "AddedDate": "2024-06-01T00:00:00Z", "PwnCount": 1200, "Description": "<p>Forum <b>breach</b></p>",
    "DataClasses": ["Email addresses", "Passwords"], "IsVerified": True, "IsFabricated": False,
    "IsSpamList": False,
}


class FakeHttp:
    """Routes ``ti.http_request`` calls to canned responses; records every call."""

    def __init__(self):
        self.calls = []
        self.routes = {}

    def __call__(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for prefix, result in self.routes.items():
            if url.startswith(prefix):
                return result(url, kw) if callable(result) else result
        return ti.HttpResult(404, None)


@pytest.fixture
def fake_http(monkeypatch):
    fh = FakeHttp()
    monkeypatch.setattr(ti, "http_request", fh)
    # No real DNS in tests: every look-alike is unregistered unless a test says otherwise.
    monkeypatch.setattr(ti, "_resolve", lambda name, rtype: None)
    monkeypatch.setattr(ti, "_breach_catalog_cache", (0.0, {}))
    monkeypatch.setattr(ti, "_kev_cache", (0.0, []))
    return fh


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "HIBP_API_KEY", "test-hibp", raising=False)
    monkeypatch.setattr(settings, "ABUSECH_AUTH_KEY", "test-abuse", raising=False)


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.setattr(settings, "HIBP_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "ABUSECH_AUTH_KEY", "", raising=False)


@pytest.fixture
def org(client, auth_headers):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        o = Organization(name="TI Org", slug=f"ti-org-{uuid.uuid4().hex[:8]}")
        db.add(o)
        db.commit()
        user.organization_id = o.id
        user.role = "admin"
        db.add(AuthorizedScope(organization_id=o.id, scope_type="wildcard", value="*.acme.test", verified=True))
        db.commit()
        return {"org_id": o.id, "user_id": user.id, "headers": auth_headers}
    finally:
        db.close()


def _h(org):
    h = org["headers"]
    return {k: v for k, v in h.items() if k.lower() == "authorization"}


# ── Unit: sources ─────────────────────────────────────────────────────


def test_sources_without_keys_are_not_configured(no_keys):
    cat = {s["id"]: s for s in ti.source_catalog()}
    assert cat["hibp_breaches"]["configured"] is True
    assert cat["hibp_accounts"]["configured"] is False
    assert cat["urlhaus"]["configured"] is False
    assert cat["darkweb_forums"]["configured"] is False and cat["darkweb_forums"]["commercial"]


def test_keyed_sources_return_nothing_without_key(no_keys, fake_http):
    assert ti.check_hibp_account("a@acme.test") == ([], "not_configured")
    assert ti.check_hibp_domain_search("acme.test") == ([], "not_configured")
    assert ti.check_urlhaus("acme.test") == ([], "not_configured")
    assert ti.check_threatfox("acme.test") == ([], "not_configured")
    assert fake_http.calls == []  # nothing was even requested


def test_hibp_account_maps_real_breach(keys, fake_http):
    fake_http.routes[f"{ti.HIBP_BASE}/breachedaccount/"] = ti.HttpResult(200, [BREACH])
    found, status = ti.check_hibp_account("ceo@acme.test")
    assert status == "ok"
    (f,) = found
    assert f.source == "hibp" and f.category == "breach_account"
    assert f.severity == "high"  # passwords exposed
    assert f.summary == "Forum breach"
    assert f.reference_url.endswith("#Acme2024")
    _, _, kw = fake_http.calls[0]
    assert kw["headers"]["hibp-api-key"] == "test-hibp"


def test_hibp_account_not_found_is_clean(keys, fake_http):
    assert ti.check_hibp_account("x@acme.test") == ([], "ok")


def test_hibp_domain_search_groups_by_breach(keys, fake_http):
    fake_http.routes[f"{ti.HIBP_BASE}/breacheddomain/"] = ti.HttpResult(200, {"alice": ["Acme2024"], "bob": ["Acme2024"]})
    fake_http.routes[f"{ti.HIBP_BASE}/breaches"] = ti.HttpResult(200, [BREACH])
    found, status = ti.check_hibp_domain_search("acme.test")
    assert status == "ok"
    (f,) = found
    assert f.data["affected_addresses"] == ["alice@acme.test", "bob@acme.test"]


def test_hibp_domain_search_unverified(keys, fake_http):
    fake_http.routes[f"{ti.HIBP_BASE}/breacheddomain/"] = ti.HttpResult(403, None)
    assert ti.check_hibp_domain_search("acme.test") == ([], "domain_not_verified_in_hibp")


def test_threatfox_drops_substring_matches(keys, fake_http):
    fake_http.routes[ti.THREATFOX_URL] = ti.HttpResult(200, {"query_status": "ok", "data": [
        {"id": 1, "ioc": "c2.acme.test:443", "malware_printable": "Cobalt Strike", "threat_type": "botnet_cc"},
        {"id": 2, "ioc": "notacme.test", "malware_printable": "X"},
    ]})
    found, _ = ti.check_threatfox("acme.test")
    assert [f.data["ioc"] for f in found] == ["c2.acme.test:443"]


def test_lookalike_candidates_and_registered(monkeypatch, fake_http):
    cands = dict(ti.lookalike_candidates("acme.com"))
    assert "acme.com" not in cands
    assert cands["acm.com"] == "omission" and cands["acme.net"] == "tld-swap"
    registered = {"acme.net": {"A": ["203.0.113.5"], "MX": ["mx.acme.net"]}}
    monkeypatch.setattr(ti, "_resolve", lambda n, t: registered[n].get(t, []) if n in registered else None)
    found, _ = ti.check_lookalikes("acme.com")
    assert [f.subject for f in found] == ["acme.com"]
    assert found[0].data["lookalike"] == "acme.net" and found[0].severity == "medium"


def test_sample_data_is_always_labelled():
    for f in ti.sample_findings():
        assert f["is_sample"] is True
        assert f["subject"].split(".")[-2] == "example"  # reserved example domains only


# ── API ───────────────────────────────────────────────────────────────


def test_old_fabricated_search_is_gone(client, org):
    assert client.get("/api/v1/darkweb/search?q=acme", headers=_h(org)).status_code == 404


def test_monitor_requires_scope(client, org, fake_http):
    r = client.post("/api/v1/darkweb/monitors", json={"kind": "email", "value": "someone@gmail.com"}, headers=_h(org))
    assert r.status_code == 403
    r = client.post("/api/v1/darkweb/monitors", json={"kind": "domain", "value": "other.test"}, headers=_h(org))
    assert r.status_code == 403
    r = client.post("/api/v1/darkweb/monitors", json={"kind": "email", "value": "not-an-email"}, headers=_h(org))
    assert r.status_code == 400


def test_monitor_check_stores_sourced_findings(client, org, keys, fake_http):
    fake_http.routes[f"{ti.HIBP_BASE}/breachedaccount/"] = ti.HttpResult(200, [BREACH])
    r = client.post("/api/v1/darkweb/monitors", json={"kind": "email", "value": "CEO@Acme.test"}, headers=_h(org))
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["value"] == "ceo@acme.test"

    r = client.post(f"/api/v1/darkweb/monitors/{mid}/check", headers=_h(org))
    assert r.status_code == 200, r.text
    assert r.json()["new"] == 1 and r.json()["status"] == {"hibp_accounts": "ok"}
    # A second check updates instead of duplicating.
    r = client.post(f"/api/v1/darkweb/monitors/{mid}/check", headers=_h(org))
    assert r.json()["new"] == 0

    r = client.get("/api/v1/darkweb/findings", headers=_h(org))
    body = r.json()
    assert body["is_sample"] is False and body["total"] == 1
    f = body["findings"][0]
    assert f["source"] == "hibp" and f["reference_url"] and f["times_seen"] == 2

    r = client.patch(f"/api/v1/darkweb/findings/{f['id']}", json={"status": "resolved"}, headers=_h(org))
    assert r.json()["status"] == "resolved"


def test_findings_are_isolated_per_org(client, org):
    db = TestingSessionLocal()
    try:
        other = Organization(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.commit()
        m = ThreatIntelMonitor(organization_id=other.id, kind="domain", value="other.test")
        db.add(m)
        db.commit()
        f = ThreatIntelFinding(organization_id=other.id, monitor_id=m.id, source="hibp", category="breach_site",
                               subject="other.test", title="secret", severity="high", fingerprint="x" * 64)
        db.add(f)
        db.commit()
        mid, fid = m.id, f.id
    finally:
        db.close()
    assert client.get("/api/v1/darkweb/findings", headers=_h(org)).json()["total"] == 0
    assert client.get("/api/v1/darkweb/monitors", headers=_h(org)).json()["total"] == 0
    assert client.post(f"/api/v1/darkweb/monitors/{mid}/check", headers=_h(org)).status_code == 404
    assert client.patch(f"/api/v1/darkweb/findings/{fid}", json={"status": "resolved"}, headers=_h(org)).status_code == 404
    assert client.delete(f"/api/v1/darkweb/monitors/{mid}", headers=_h(org)).status_code == 404


def test_revoked_scope_stops_lookups(client, org, keys, fake_http):
    r = client.post("/api/v1/darkweb/monitors", json={"kind": "domain", "value": "acme.test"}, headers=_h(org))
    mid = r.json()["id"]
    db = TestingSessionLocal()
    try:
        db.query(AuthorizedScope).filter(AuthorizedScope.organization_id == org["org_id"]).delete()
        db.commit()
    finally:
        db.close()
    r = client.post(f"/api/v1/darkweb/monitors/{mid}/check", headers=_h(org))
    assert r.json()["status"]["scope"] == "not_authorized"
    assert fake_http.calls == []


def test_sources_and_sample_endpoints(client, org, no_keys):
    src = client.get("/api/v1/darkweb/sources", headers=_h(org)).json()["sources"]
    assert any(s["id"] == "hibp_accounts" and not s["configured"] for s in src)
    sample = client.get("/api/v1/darkweb/sample", headers=_h(org)).json()
    assert sample["is_sample"] is True and "SAMPLE" in sample["notice"]


def test_exploited_matches_scan_cves(client, org, fake_http):
    from app.models.scan import Scan
    from app.models.vulnerability import Vulnerability

    db = TestingSessionLocal()
    try:
        scan = Scan(domain="acme.test", organization_id=org["org_id"], status="completed")
        db.add(scan)
        db.commit()
        db.add(Vulnerability(scan_id=scan.id, template_id="CVE-2021-44228", name="Log4Shell", severity="critical",
                             host="app.acme.test", organization_id=org["org_id"], status="open"))
        db.commit()
    finally:
        db.close()
    fake_http.routes[ti.KEV_URL] = ti.HttpResult(200, {"vulnerabilities": [
        {"cveID": "CVE-2021-44228", "vendorProject": "Apache", "product": "Log4j2", "dateAdded": "2021-12-10"},
        {"cveID": "CVE-2099-0001", "vendorProject": "Other", "product": "Thing", "dateAdded": "2021-01-01"},
    ]})
    fake_http.routes[ti.EPSS_URL] = ti.HttpResult(200, {"data": [
        {"cve": "CVE-2021-44228", "epss": "0.97", "percentile": "0.99"}]})
    body = client.get("/api/v1/darkweb/exploited", headers=_h(org)).json()
    assert [c["cve_id"] for c in body["confirmed"]] == ["CVE-2021-44228"]
    assert body["confirmed"][0]["hosts"] == ["app.acme.test"]
    assert body["confirmed"][0]["epss"] == 0.97
