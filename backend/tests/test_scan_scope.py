"""Scope enforcement at scan time: public-target guard, verified ownership,
DNS TXT verification, and the API paths that start scans."""
import asyncio
import uuid

import pytest

from app.config import settings
from app.core import target_guard
from app.core.scope import DnsTxtScopeVerifier, authorize_scan_target, scope_mode
from app.models.scan import Scan, ScanJob
from app.models.scope import AuthorizedScope
from tests.conftest import TestingSessionLocal


@pytest.fixture
def public_dns(monkeypatch):
    """Every name resolves to a public address unless a test overrides it."""
    answers = {}
    monkeypatch.setattr(
        target_guard, "resolve_host",
        lambda host, timeout=4.0: answers.get(host, ["93.184.215.14"]),
    )
    return answers


@pytest.fixture
def verified_mode(monkeypatch, public_dns):
    monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "verified")
    return public_dns


@pytest.fixture
def org_user(client, auth_headers):
    from app.models.organization import Organization
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        org = Organization(name="Scope Org", slug=f"scope-org-{uuid.uuid4().hex[:8]}")
        db.add(org)
        db.commit()
        user.organization_id = org.id
        user.role = "admin"
        db.commit()
        return {"user_id": user.id, "org_id": org.id, "headers": auth_headers}
    finally:
        db.close()


def _fake_txt(monkeypatch, records):
    class _R:
        def __init__(self, value):
            self.strings = [value.encode()]

    def resolve(name, rtype, lifetime=5):
        if name in records:
            return [_R(v) for v in records[name]]
        import dns.resolver
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr("dns.resolver.resolve", resolve)


# ── Public-target guard ───────────────────────────────────────────────


class TestTargetGuard:
    def test_normalizes_urls(self):
        assert target_guard.normalize_target("https://App.Example.com:8443/x?y") == "app.example.com"
        assert target_guard.normalize_target("example.com.") == "example.com"

    @pytest.mark.parametrize("target", [
        "127.0.0.1", "10.1.2.3", "192.168.0.10", "169.254.169.254", "100.64.0.1",
        "::1", "fd00::1", "::ffff:10.0.0.1", "0.0.0.0",
    ])
    def test_blocks_private_ip_literals(self, target):
        assert not target_guard.check_public_target(target).allowed

    @pytest.mark.parametrize("target", [
        "localhost", "db.internal", "metadata.google.internal", "printer.local",
        "postgres.railway.internal", "intranet",
    ])
    def test_blocks_internal_names(self, target):
        assert not target_guard.check_public_target(target, resolve=False).allowed

    def test_blocks_names_resolving_to_private_addresses(self, public_dns):
        public_dns["sneaky.example.com"] = ["93.184.215.14", "10.0.0.5"]
        check = target_guard.check_public_target("sneaky.example.com")
        assert not check.allowed and "10.0.0.5" in check.reason

    def test_allows_public_and_unresolvable_names(self, public_dns):
        assert target_guard.check_public_target("example.com").allowed
        public_dns["new.example.com"] = []
        assert target_guard.check_public_target("new.example.com").allowed

    def test_rejects_garbage(self):
        assert not target_guard.check_public_target("not a domain").allowed
        assert not target_guard.check_public_target("").allowed


# ── authorize_scan_target ─────────────────────────────────────────────


class TestAuthorizeScanTarget:
    def _org(self, db):
        from app.models.organization import Organization

        org = Organization(name="O", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(org)
        db.commit()
        return org

    def test_default_mode(self, monkeypatch):
        monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "")
        monkeypatch.setattr(settings, "REQUIRE_VERIFIED_SCOPE", False)
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        assert scope_mode() == "verified"
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        assert scope_mode() == "open"

    def test_open_mode_still_blocks_internal_targets(self, db_session, monkeypatch, public_dns):
        monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "open")
        org = self._org(db_session)
        assert authorize_scan_target(db_session, org.id, "example.com").authorized
        assert not authorize_scan_target(db_session, org.id, "127.0.0.1").authorized

    def test_requires_organization(self, db_session, verified_mode):
        assert not authorize_scan_target(db_session, None, "example.com").authorized

    def test_unknown_target_auto_registers_unverified_scope(self, db_session, verified_mode):
        from app.models.user import User

        org = self._org(db_session)
        admin = User(email=f"{uuid.uuid4().hex[:8]}@t.test", hashed_password="x", full_name="A",
                     organization_id=org.id, role="admin")
        db_session.add(admin)
        db_session.commit()
        auth = authorize_scan_target(db_session, org.id, "Example.com", actor_id=admin.id)
        assert not auth.authorized
        assert auth.verification["record_name"] == "_cazo-verify.example.com"
        assert auth.verification["record_value"].startswith("cazo-verify=")
        scope = db_session.query(AuthorizedScope).filter_by(organization_id=org.id).one()
        assert scope.value == "*.example.com" and scope.verified is False

        # A second attempt reuses the same pending scope and token.
        again = authorize_scan_target(db_session, org.id, "api.example.com")
        assert again.scope_id == scope.id
        assert again.verification["record_value"] == auth.verification["record_value"]
        assert db_session.query(AuthorizedScope).count() == 1

    def test_verified_scope_allows_target_and_subdomains(self, db_session, verified_mode):
        org = self._org(db_session)
        db_session.add(AuthorizedScope(organization_id=org.id, scope_type="wildcard",
                                       value="*.example.com", verified=True))
        db_session.commit()
        assert authorize_scan_target(db_session, org.id, "example.com").authorized
        assert authorize_scan_target(db_session, org.id, "shop.example.com").authorized
        assert not authorize_scan_target(db_session, org.id, "example.org", auto_register=False).authorized

    def test_other_orgs_verification_does_not_count(self, db_session, verified_mode):
        a, b = self._org(db_session), self._org(db_session)
        db_session.add(AuthorizedScope(organization_id=a.id, scope_type="wildcard",
                                       value="*.example.com", verified=True))
        db_session.commit()
        assert not authorize_scan_target(db_session, b.id, "example.com").authorized

    def test_registered_mode(self, db_session, monkeypatch, public_dns):
        monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "registered")
        org = self._org(db_session)
        assert not authorize_scan_target(db_session, org.id, "example.com").authorized
        assert db_session.query(AuthorizedScope).count() == 0  # never auto-registers
        db_session.add(AuthorizedScope(organization_id=org.id, scope_type="domain", value="example.com"))
        db_session.commit()
        assert authorize_scan_target(db_session, org.id, "example.com").authorized

    def test_verified_scope_cannot_whitelist_internal_resolution(self, db_session, verified_mode):
        org = self._org(db_session)
        db_session.add(AuthorizedScope(organization_id=org.id, scope_type="wildcard",
                                       value="*.example.com", verified=True))
        db_session.commit()
        verified_mode["internal.example.com"] = ["10.0.0.7"]
        assert not authorize_scan_target(db_session, org.id, "internal.example.com").authorized


class TestDnsTxtVerifier:
    def test_matches_only_the_scopes_own_token(self, monkeypatch):
        scope = AuthorizedScope(scope_type="wildcard", value="*.example.com", verification_token="tok123")
        _fake_txt(monkeypatch, {"_cazo-verify.example.com": ["cazo-verify=tok123"]})
        assert DnsTxtScopeVerifier().verify(scope)
        _fake_txt(monkeypatch, {"_cazo-verify.example.com": ["cazo-verify=someone-elses"]})
        assert not DnsTxtScopeVerifier().verify(scope)

    def test_lookup_failure_is_not_verification(self, monkeypatch):
        scope = AuthorizedScope(scope_type="domain", value="example.com",
                                verification_token="t", verified=True)
        _fake_txt(monkeypatch, {})
        assert not DnsTxtScopeVerifier().verify(scope)


# ── API ───────────────────────────────────────────────────────────────


class TestScanApiEnforcement:
    def test_unverified_domain_gets_403_with_txt_record(self, client, org_user, verified_mode):
        resp = client.post("/api/v1/scans", headers=org_user["headers"],
                           json={"domain": "example.com", "scan_type": "quick"})
        assert resp.status_code == 403, resp.text
        detail = resp.json()["detail"]
        assert "not verified" in detail["msg"]
        assert detail["verification"]["record_name"] == "_cazo-verify.example.com"

        db = TestingSessionLocal()
        try:
            assert db.query(Scan).count() == 0
        finally:
            db.close()

    def test_private_target_rejected(self, client, org_user, verified_mode):
        resp = client.post("/api/v1/scans", headers=org_user["headers"],
                           json={"domain": "169.254.169.254", "scan_type": "quick"})
        assert resp.status_code in (403, 422)

    def test_verify_then_scan_is_queued(self, client, org_user, verified_mode, monkeypatch):
        monkeypatch.setattr(settings, "SCAN_EXECUTION_MODE", "queue")
        h = org_user["headers"]
        first = client.post("/api/v1/scans", headers=h, json={"domain": "example.com", "scan_type": "quick"})
        detail = first.json()["detail"]
        scope_id = detail["scope_id"]

        # Not published yet -> 422 with the record to add.
        _fake_txt(monkeypatch, {})
        resp = client.post(f"/api/v1/scopes/{scope_id}/verify", headers=h)
        assert resp.status_code == 422, resp.text

        _fake_txt(monkeypatch, {"_cazo-verify.example.com": [detail["verification"]["record_value"]]})
        resp = client.post(f"/api/v1/scopes/{scope_id}/verify", headers=h)
        assert resp.status_code == 200, resp.text
        assert resp.json()["verified"] is True and resp.json()["verification_method"] == "dns_txt"

        resp = client.post("/api/v1/scans", headers=h, json={"domain": "example.com", "scan_type": "quick"})
        assert resp.status_code == 200, resp.text
        scan_id = resp.json()["id"]
        db = TestingSessionLocal()
        try:
            job = db.query(ScanJob).filter(ScanJob.scan_id == scan_id).one()
            assert job.status == "pending"
        finally:
            db.close()

        # Cancel while queued.
        resp = client.post(f"/api/v1/scans/{scan_id}/cancel", headers=h)
        assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
        db = TestingSessionLocal()
        try:
            assert db.query(ScanJob).filter(ScanJob.scan_id == scan_id).one().status == "cancelled"
        finally:
            db.close()

    def test_scope_list_shows_verification_record(self, client, org_user, verified_mode):
        h = org_user["headers"]
        resp = client.post("/api/v1/scopes", headers=h, json={"scope_type": "wildcard", "value": "*.example.net"})
        assert resp.status_code == 201
        assert resp.json()["verification"]["record_name"] == "_cazo-verify.example.net"
        listed = client.get("/api/v1/scopes", headers=h).json()
        assert listed[0]["verification"]["record_value"] == resp.json()["verification"]["record_value"]

    def test_v2_scan_needs_create_permission_and_scope(self, client, org_user, verified_mode):
        resp = client.post("/api/v1/scanner-v2/scan", headers=org_user["headers"],
                           json={"domain": "example.com", "scan_type": "quick"})
        assert resp.status_code == 403
        assert "verification" in resp.json()["detail"]

    def test_schedule_requires_scope_and_is_tenant_scoped(self, client, org_user, verified_mode):
        h = org_user["headers"]
        resp = client.post("/api/v1/scanner-v2/schedule", headers=h,
                           json={"domain": "example.com", "interval_hours": 6})
        assert resp.status_code == 403

        db = TestingSessionLocal()
        try:
            db.query(AuthorizedScope).filter_by(organization_id=org_user["org_id"]).update({"verified": True})
            db.commit()
        finally:
            db.close()
        resp = client.post("/api/v1/scanner-v2/schedule", headers=h,
                           json={"domain": "example.com", "interval_hours": 6})
        assert resp.status_code == 200, resp.text
        sched_id = resp.json()["id"]
        assert any(s["id"] == sched_id for s in client.get("/api/v1/scanner-v2/schedules", headers=h).json())
        assert client.delete(f"/api/v1/scanner-v2/schedule/{sched_id}", headers=h).status_code == 204
        assert client.delete(f"/api/v1/scanner-v2/schedule/{sched_id}", headers=h).status_code == 404

    def test_scan_queue_health(self, client):
        resp = client.get("/health/scans")
        assert resp.status_code == 200
        body = resp.json()
        assert "execution_mode" in body and "queue" in body


# ── Review follow-ups ─────────────────────────────────────────────────


def test_auto_register_requires_manage_org(client, verified_mode, org_user):
    """A member without scope-management rights cannot grow the scope list by asking for a scan."""
    from app.core.scope import authorize_scan_target
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = db.get(User, org_user["user_id"])
        user.role = "analyst"
        db.commit()
        auth = authorize_scan_target(db, org_user["org_id"], "newco.com", actor_id=user.id)
        assert not auth.authorized and auth.scope_id is None
        assert db.query(AuthorizedScope).filter(AuthorizedScope.organization_id == org_user["org_id"]).count() == 0

        user.role = "admin"
        db.commit()
        auth = authorize_scan_target(db, org_user["org_id"], "newco.com", actor_id=user.id)
        assert not auth.authorized and auth.scope_id and auth.verification
    finally:
        db.close()


def test_probe_allowed_only_in_scope_public_hosts(public_dns):
    public_dns["internal.acme.com"] = ["10.0.0.5"]
    public_dns["meta.acme.com"] = ["169.254.169.254"]

    async def run():
        return await target_guard.filter_probe_targets(
            ["www.acme.com", "internal.acme.com", "meta.acme.com", "other-company.com",
             "evilacme.com", "db.acme.com.internal", "10.1.2.3"],
            "acme.com",
        )

    assert asyncio.run(run()) == ["www.acme.com"]


def test_v2_pipeline_drops_unprobeable_discoveries(public_dns):
    from app.scanners.v2.pipeline import PipelineContext, ScanPipeline

    public_dns["vpn.acme.com"] = ["192.168.1.1"]
    ctx = PipelineContext(target="acme.com")
    ctx.add_discovered_assets([
        {"hostname": "www.acme.com"}, {"hostname": "vpn.acme.com"}, {"hostname": "cdn.partner.net"},
    ])
    asyncio.run(ScanPipeline()._gate_discovered_assets("acme.com", ctx))
    assert [a["hostname"] for a in ctx.discovered_assets] == ["www.acme.com"]
    assert ctx.metadata["skipped_out_of_scope"] == 2


def test_http_guard_blocks_redirect_to_internal_address(public_dns):
    import httpx

    target_guard._HOST_VERDICTS.clear()

    def handler(request):
        if request.url.host == "www.acme.com":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        raise AssertionError(f"request reached {request.url}")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
            event_hooks=target_guard.GUARDED_HOOKS,
        ) as c:
            await c.get("http://www.acme.com/")

    with pytest.raises(httpx.RequestError, match="non-public"):
        asyncio.run(run())


def test_osint_lookup_requires_scope(client, verified_mode, org_user, monkeypatch):
    from app.services import osint

    called = []
    monkeypatch.setattr(osint, "lookup_domain", lambda d: called.append(d) or osint.IntelResult(query=d))
    r = client.get("/api/v1/osint", params={"q": "someone-else.com"}, headers=org_user["headers"])
    assert r.status_code == 403 and called == []
    r = client.get("/api/v1/osint", params={"q": "127.0.0.1"}, headers=org_user["headers"])
    assert r.status_code == 403 and called == []

    db = TestingSessionLocal()
    try:
        db.add(AuthorizedScope(organization_id=org_user["org_id"], scope_type="wildcard",
                               value="*.mine.com", verified=True))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/osint", params={"q": "mine.com"}, headers=org_user["headers"])
    assert r.status_code == 200 and called == ["mine.com"]


def test_osint_sockets_refuse_internal_hosts(public_dns):
    from app.services import osint

    public_dns["intra.acme.com"] = ["10.9.9.9"]
    osint._connectable.cache_clear()
    assert osint._probe_port("intra.acme.com", 80).state == "filtered"
    assert osint._probe_port("127.0.0.1", 80).state == "filtered"
    assert osint._grab_cert_sans("169.254.169.254") is None
    osint._connectable.cache_clear()


def test_osint_import_needs_asset_or_scan_permission(client, verified_mode, org_user):
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        db.get(User, org_user["user_id"]).role = "viewer"
        db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/osint/import", params={"q": "mine.com"}, headers=org_user["headers"])
    assert r.status_code == 403 and isinstance(r.json()["detail"], str)  # permission, not scope
