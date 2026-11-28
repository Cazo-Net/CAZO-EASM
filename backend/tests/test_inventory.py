"""Asset inventory: dedupe across scans, history, lifecycle, alerts, limits.

No network: ASN lookups are stubbed and email goes to a recording provider.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.core.security import create_access_token
from app.models.asset import Subdomain
from app.models.asset_change import AssetChange
from app.models.asset_inventory import Asset
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.port import Port
from app.models.scan import Scan
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.services import inventory as inv
from app.services import inventory_alerts as alerts

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr("app.repositories.assets.resolve_asn", lambda ip: None)


@pytest.fixture
def outbox(monkeypatch):
    """Record emails instead of sending them."""
    import app.services.email.sender as sender

    sent = []

    class _Recorder:
        def send_async(self, to, subject, html_body, **_):
            sent.append({"to": to, "subject": subject, "html": html_body})

        def send(self, to, subject, html_body, **_):
            sent.append({"to": to, "subject": subject, "html": html_body})
            return True

    monkeypatch.setattr(sender, "_email_service", _Recorder())
    return sent


def _org(db, name="Acme"):
    org = Organization(name=name, slug=f"{name.lower()}-{time.time_ns()}")
    db.add(org)
    db.commit()
    return org


def _user(db, org, role="owner", email=None):
    u = User(
        email=email or f"{role}-{time.time_ns()}@example.test", hashed_password="x",
        full_name=role.title(), role=role, organization_id=org.id, is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _headers(user):
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role, "tv": user.token_version or 0})
    return {"Authorization": f"Bearer {token}"}


def _scan(db, org, hosts, *, domain="example.com", scan_type="full", when=None, vulns=()):
    """hosts: {hostname: {"ports": [(n, service)], "cert": (serial, not_after), "tech": [(name, ver)], "ips": [...]}}"""
    when = when or datetime.now(timezone.utc)
    scan = Scan(domain=domain, organization_id=org.id, status="completed",
                scan_type=scan_type, completed_at=when, engine="v2")
    db.add(scan)
    db.flush()
    for hostname, spec in hosts.items():
        sub = Subdomain(scan_id=scan.id, hostname=hostname, is_alive=True,
                        ip_addresses=spec.get("ips", []))
        db.add(sub)
        db.flush()
        for number, service in spec.get("ports", []):
            db.add(Port(subdomain_id=sub.id, port_number=number, state="open", service=service))
        if spec.get("cert"):
            serial, not_after = spec["cert"]
            db.add(SSLCertificate(subdomain_id=sub.id, issuer="Test CA", subject=hostname,
                                  serial_number=serial, not_after=not_after, grade="A"))
        for name, version in spec.get("tech", []):
            db.add(Technology(subdomain_id=sub.id, name=name, version=version))
    for host, name, severity in vulns:
        db.add(Vulnerability(scan_id=scan.id, template_id=name.lower().replace(" ", "-"),
                             name=name, severity=severity, host=host, organization_id=org.id))
    db.commit()
    return scan


def _assets(db, org, asset_type=None):
    q = db.query(Asset).filter(Asset.organization_id == org.id)
    if asset_type:
        q = q.filter(Asset.asset_type == asset_type)
    return {a.value: a for a in q.all()}


BASE = {
    "example.com": {"ports": [(443, "https")], "cert": ("AA01", NOW + timedelta(days=200)),
                    "tech": [("nginx", "1.24")], "ips": ["203.0.113.10"]},
    "api.example.com": {"ports": [(443, "https"), (22, "ssh")], "ips": ["203.0.113.11"]},
}


class TestDedupe:
    def test_same_asset_across_scans_is_one_row(self, db_session):
        org = _org(db_session)
        t0 = NOW - timedelta(days=3)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=t0))
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW))

        assert set(_assets(db_session, org, "host")) == {"example.com", "api.example.com"}
        assert set(_assets(db_session, org, "service")) == {
            "example.com:443/tcp", "api.example.com:443/tcp", "api.example.com:22/tcp"}
        assert set(_assets(db_session, org, "domain")) == {"example.com"}
        assert set(_assets(db_session, org, "certificate")) == {"AA01"}
        assert set(_assets(db_session, org, "technology")) == {"example.com|nginx"}
        assert set(_assets(db_session, org, "ip")) == {"203.0.113.10", "203.0.113.11"}

        host = _assets(db_session, org, "host")["api.example.com"]
        assert inv._aware(host.first_seen) == t0
        assert inv._aware(host.last_seen) == NOW
        assert host.attributes["open_ports"] == [22, 443]

    def test_sync_is_idempotent_per_scan(self, db_session):
        org = _org(db_session)
        scan = _scan(db_session, org, BASE)
        first = inv.sync_scan(db_session, scan)
        again = inv.sync_scan(db_session, scan)
        assert first.new_assets > 0 and again.skipped
        assert db_session.query(AssetChange).count() == len(first.events)

    def test_hostnames_are_case_insensitive(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, {"API.Example.com.": {}}))
        inv.sync_scan(db_session, _scan(db_session, org, {"api.example.com": {}}))
        assert set(_assets(db_session, org, "host")) == {"api.example.com"}


class TestChanges:
    def test_first_scan_is_a_quiet_baseline(self, db_session):
        org = _org(db_session)
        res = inv.sync_scan(db_session, _scan(db_session, org, BASE))
        assert {e.event for e in res.events} >= {"asset_new", "service_new", "cert_new", "tech_new"}
        assert res.alerts == {}

    def test_new_host_and_port_raise_alerts(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=1)))
        later = {**BASE, "vpn.example.com": {"ports": [(3389, "ms-wbt-server")]},
                 "api.example.com": {"ports": [(443, "https"), (22, "ssh"), (6379, "redis")]}}
        res = inv.sync_scan(db_session, _scan(db_session, org, later))

        assert [i["key"] for i in res.alerts["new_asset"]] == ["vpn.example.com"]
        assert sorted(i["key"] for i in res.alerts["new_service"]) == [
            "api.example.com:6379/tcp", "vpn.example.com:3389/tcp"]
        redis = next(e for e in res.events if e.entity_key == "api.example.com:6379/tcp")
        assert redis.severity == "medium" and redis.asset_id

    def test_technology_version_and_ip_changes_are_history_only(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=1)))
        later = {**BASE, "example.com": {**BASE["example.com"], "tech": [("nginx", "1.26")],
                                         "ips": ["198.51.100.7"]}}
        res = inv.sync_scan(db_session, _scan(db_session, org, later))
        assert {e.event for e in res.events} == {"tech_changed", "ip_changed", "asset_new"}
        assert res.alerts == {}

    def test_missing_needs_two_full_scans_and_quick_scans_do_not_count(self, db_session):
        org = _org(db_session)
        only_apex = {"example.com": BASE["example.com"]}
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=4)))

        quick = inv.sync_scan(db_session, _scan(db_session, org, only_apex, scan_type="quick",
                                                when=NOW - timedelta(days=3)))
        assert _assets(db_session, org, "host")["api.example.com"].miss_count == 0
        assert "asset_disappeared" not in quick.alerts

        one = inv.sync_scan(db_session, _scan(db_session, org, only_apex, when=NOW - timedelta(days=2)))
        host = _assets(db_session, org, "host")["api.example.com"]
        assert host.state == "active" and host.miss_count == 1
        assert "asset_disappeared" not in one.alerts

        two = inv.sync_scan(db_session, _scan(db_session, org, only_apex, when=NOW - timedelta(days=1)))
        host = _assets(db_session, org, "host")["api.example.com"]
        assert host.state == "missing" and host.missing_since is not None
        assert [i["key"] for i in two.alerts["asset_disappeared"]] == ["api.example.com"]
        # last_seen still says when it was really last observed.
        assert inv._aware(host.last_seen) == NOW - timedelta(days=4)
        # Its services went with it, without their own alert.
        assert _assets(db_session, org, "service")["api.example.com:22/tcp"].state == "missing"

        back = inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW))
        assert _assets(db_session, org, "host")["api.example.com"].state == "active"
        assert any(e.event == "asset_reappeared" for e in back.events)
        assert [i["key"] for i in back.alerts["new_asset"]] == ["api.example.com"]

    def test_closed_port_is_recorded(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=3)))
        closed = {**BASE, "api.example.com": {"ports": [(443, "https")]}}
        inv.sync_scan(db_session, _scan(db_session, org, closed, when=NOW - timedelta(days=2)))
        res = inv.sync_scan(db_session, _scan(db_session, org, closed, when=NOW - timedelta(days=1)))
        assert [e.entity_key for e in res.events if e.event == "service_closed"] == ["api.example.com:22/tcp"]
        assert _assets(db_session, org, "host")["api.example.com"].attributes["open_ports"] == [443]

    def test_scanning_a_subdomain_does_not_hide_its_siblings(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=3)))
        for d in (2, 1):
            inv.sync_scan(db_session, _scan(db_session, org, {"api.example.com": {}},
                                            domain="api.example.com", when=NOW - timedelta(days=d)))
        assert _assets(db_session, org, "host")["example.com"].state == "active"

    def test_other_root_domains_are_untouched(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=3)))
        for d in (2, 1):
            inv.sync_scan(db_session, _scan(db_session, org, {"other.org": {}}, domain="other.org",
                                            when=NOW - timedelta(days=d)))
        assert all(a.state == "active" for a in _assets(db_session, org, "host").values())


class TestCertificates:
    def test_replaced_certificate(self, db_session):
        org = _org(db_session)
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW - timedelta(days=1)))
        renewed = {**BASE, "example.com": {**BASE["example.com"], "cert": ("BB02", NOW + timedelta(days=365))}}
        res = inv.sync_scan(db_session, _scan(db_session, org, renewed))
        change = res.alerts["certificate_changed"][0]
        assert change["detail"]["old"]["serial"] == "AA01" and change["detail"]["new"]["serial"] == "BB02"
        certs = _assets(db_session, org, "certificate")
        assert certs["AA01"].state == "missing" and certs["BB02"].state == "active"

    def test_expiry_alerts_once_per_step(self, db_session):
        org = _org(db_session)
        soon = {"example.com": {"cert": ("CC03", NOW + timedelta(days=20, hours=1))}}
        first = inv.sync_scan(db_session, _scan(db_session, org, soon, when=NOW))
        assert first.alerts["certificate_expiring"][0]["detail"]["days_left"] == 20
        again = inv.sync_scan(db_session, _scan(db_session, org, soon, when=NOW + timedelta(hours=1)))
        assert "certificate_expiring" not in again.alerts
        # 14 days later it is inside the 7-day step: one more alert.
        later = inv.sync_scan(db_session, _scan(db_session, org, soon, when=NOW + timedelta(days=14)))
        assert len(later.alerts["certificate_expiring"]) == 1

    def test_expiry_bucket(self):
        assert inv.expiry_bucket(45, 30) is None
        assert inv.expiry_bucket(30, 30) == 30
        assert inv.expiry_bucket(10, 30) == 14
        assert inv.expiry_bucket(0, 30) == 1
        assert inv.expiry_bucket(-2, 30) == 0
        assert inv.expiry_bucket(50, 60) == 60

    def test_daily_check_alerts_between_scans(self, db_session, outbox):
        org = _org(db_session)
        owner = _user(db_session, org)
        inv.sync_scan(db_session, _scan(db_session, org, {
            "example.com": {"cert": ("DD04", NOW + timedelta(days=10))}}, when=NOW - timedelta(days=80)))
        assert alerts.run_certificate_expiry_check(db_session) == 1
        note = db_session.query(Notification).filter(Notification.user_id == owner.id).one()
        assert note.type == "inventory_cert_expiring"
        assert len(outbox) == 1 and outbox[0]["to"] == owner.email
        assert alerts.run_certificate_expiry_check(db_session) == 0


class TestFindings:
    def test_new_critical_finding_alerts_once(self, db_session):
        org = _org(db_session)
        vulns = [("api.example.com", "Exposed .env file", "critical"),
                 ("api.example.com", "Missing header", "low")]
        first = inv.sync_scan(db_session, _scan(db_session, org, BASE, vulns=vulns, when=NOW - timedelta(days=1)))
        assert [i["detail"]["name"] for i in first.alerts["new_critical_finding"]] == ["Exposed .env file"]
        second = inv.sync_scan(db_session, _scan(db_session, org, BASE, vulns=vulns))
        assert "new_critical_finding" not in second.alerts

    def test_severity_threshold_is_per_org(self, db_session):
        org = _org(db_session)
        alerts.save_settings(db_session, org.id, {"finding_min_severity": "high"}, None)
        res = inv.sync_scan(db_session, _scan(db_session, org, BASE, vulns=[
            ("example.com", "Open admin panel", "high")]))
        assert len(res.alerts["new_critical_finding"]) == 1


class TestPlanLimit:
    def test_hosts_beyond_the_plan_are_not_added(self, db_session, monkeypatch):
        org = _org(db_session)
        owner = _user(db_session, org)
        monkeypatch.setattr(settings, "BILLING_ENFORCE_LIMITS", True)
        monkeypatch.setattr(inv, "_host_budget", lambda db, org_id: (
            3, max(0, 3 - inv.count_inventory_hosts(db, org_id))))
        hosts = {"example.com": {"ports": [(443, "https")]},
                 **{f"h{i}.example.com": {"ports": [(80, "http")]} for i in range(5)}}
        scan = _scan(db_session, org, hosts)
        res = inv.process_completed_scan(db_session, scan)

        kept = _assets(db_session, org, "host")
        assert len(kept) == 3 and "example.com" in kept
        assert res.hosts_over_limit == 3
        # Nothing belonging to a skipped host leaks in.
        assert all(s.split(":")[0] in kept for s in _assets(db_session, org, "service"))
        note = db_session.query(Notification).filter(Notification.user_id == owner.id).one()
        assert note.type == "inventory_plan_limit"

    def test_billing_host_count_uses_the_inventory(self, db_session):
        from app.billing.entitlements import count_hosts

        org = _org(db_session)
        for d in (3, 2, 1):
            inv.sync_scan(db_session, _scan(db_session, org, BASE if d == 3 else {
                "example.com": BASE["example.com"]}, when=NOW - timedelta(days=d)))
        # api.example.com went missing, so it no longer counts.
        assert count_hosts(db_session, org.id) == 1


class TestAlertDelivery:
    def _changed(self, db, org):
        inv.process_completed_scan(db, _scan(db, org, BASE, when=NOW - timedelta(days=1)))
        later = {**BASE, "vpn.example.com": {"ports": [(3389, "rdp")]}}
        return inv.process_completed_scan(db, _scan(db, org, later))

    def test_admins_get_in_app_and_email(self, db_session, outbox):
        org = _org(db_session)
        owner, member = _user(db_session, org, "owner"), _user(db_session, org, "member")
        self._changed(db_session, org)

        notes = db_session.query(Notification).filter(Notification.user_id == owner.id).all()
        assert {n.type for n in notes} == {"inventory_new_asset", "inventory_new_service"}
        assert all(n.organization_id == org.id for n in notes)
        assert db_session.query(Notification).filter(Notification.user_id == member.id).count() == 0
        assert {m["to"] for m in outbox} == {owner.email}
        assert any("vpn.example.com" in m["html"] for m in outbox)

    def test_org_can_turn_email_off_and_notify_everyone(self, db_session, outbox):
        org = _org(db_session)
        _user(db_session, org, "owner")
        member = _user(db_session, org, "member")
        alerts.save_settings(db_session, org.id, {
            "recipients": "all",
            "rules": {"new_asset": {"email": False}, "new_service": {"in_app": False, "email": False}},
        }, None)
        self._changed(db_session, org)
        notes = db_session.query(Notification).filter(Notification.user_id == member.id).all()
        assert [n.type for n in notes] == ["inventory_new_asset"]
        assert outbox == []

    def test_master_switch_silences_everything(self, db_session, outbox):
        org = _org(db_session)
        _user(db_session, org, "owner")
        alerts.save_settings(db_session, org.id, {"enabled": False}, None)
        self._changed(db_session, org)
        assert db_session.query(Notification).count() == 0 and outbox == []
        # History is still kept.
        assert db_session.query(AssetChange).filter(AssetChange.event == "asset_new").count() > 0

    def test_extra_mailboxes_get_the_email(self, db_session, outbox):
        org = _org(db_session)
        owner = _user(db_session, org, "owner")
        alerts.save_settings(db_session, org.id, {"extra_emails": ["SOC@client.test", owner.email]}, None)
        self._changed(db_session, org)
        to = [m["to"] for m in outbox]
        assert to.count("soc@client.test") == 2 and to.count(owner.email) == 2

    def test_alerts_never_reach_another_organization(self, db_session, outbox):
        org, other = _org(db_session, "Acme"), _org(db_session, "Globex")
        _user(db_session, org, "owner")
        outsider = _user(db_session, other, "owner")
        self._changed(db_session, org)
        assert db_session.query(Notification).filter(Notification.user_id == outsider.id).count() == 0
        assert outsider.email not in {m["to"] for m in outbox}

    def test_settings_validation(self, db_session):
        org = _org(db_session)
        for bad in ({"extra_emails": ["not-an-email"]}, {"extra_emails": ["a@b.co\nBcc: x@y.z"]},
                    {"cert_expiry_days": 0}, {"finding_min_severity": "low"},
                    {"recipients": "everyone"}, {"rules": {"nope": {"email": True}}},
                    {"extra_emails": [f"u{i}@x.test" for i in range(11)]}):
            with pytest.raises(ValueError):
                alerts.save_settings(db_session, org.id, bad, None)
            db_session.rollback()


class TestApi:
    def _seed(self, db):
        org, other = _org(db, "Acme"), _org(db, "Globex")
        owner, member = _user(db, org, "owner"), _user(db, org, "viewer")
        outsider = _user(db, other, "owner")
        inv.sync_scan(db, _scan(db, org, BASE, when=NOW - timedelta(days=1)))
        inv.sync_scan(db, _scan(db, org, {**BASE, "vpn.example.com": {"ports": [(3389, "rdp")]}}))
        inv.sync_scan(db, _scan(db, other, {"globex.io": {"ports": [(443, "https")]}}, domain="globex.io"))
        return org, other, owner, member, outsider

    def test_list_filter_and_summary(self, client, db_session):
        org, _, owner, _, _ = self._seed(db_session)
        h = _headers(owner)
        body = client.get("/api/v1/inventory/assets?type=host", headers=h).json()
        assert body["total"] == 3
        assert {i["value"] for i in body["items"]} == {"example.com", "api.example.com", "vpn.example.com"}
        api = next(i for i in body["items"] if i["value"] == "api.example.com")
        assert api["services"] == 2

        assert client.get("/api/v1/inventory/assets?q=VPN", headers=h).json()["total"] == 2
        assert client.get("/api/v1/inventory/assets?q=%25", headers=h).json()["total"] == 0
        assert client.get("/api/v1/inventory/assets?type=nope", headers=h).status_code == 422

        s = client.get("/api/v1/inventory/summary", headers=h).json()
        assert s["by_type"]["host"]["active"] == 3 and s["root_domains"] == ["example.com"]
        assert s["needs_rebuild"] is False

    def test_detail_and_history(self, client, db_session):
        org, _, owner, _, _ = self._seed(db_session)
        host = _assets(db_session, org, "host")["vpn.example.com"]
        body = client.get(f"/api/v1/inventory/assets/{host.id}", headers=_headers(owner)).json()
        assert body["asset"]["value"] == "vpn.example.com"
        assert [c["value"] for c in body["children"]] == ["vpn.example.com:3389/tcp"]
        assert {e["event"] for e in body["history"]} == {"asset_new", "service_new"}

        changes = client.get("/api/v1/inventory/changes?alert=new_service", headers=_headers(owner)).json()
        assert all(c["event"] == "service_new" for c in changes["items"]) and changes["total"] == 4

    def test_tenant_isolation(self, client, db_session):
        org, other, owner, _, outsider = self._seed(db_session)
        h = _headers(outsider)
        listing = client.get("/api/v1/inventory/assets?state=all&limit=200", headers=h).json()
        assert {i["root_domain"] for i in listing["items"]} == {"globex.io"}
        for asset in _assets(db_session, org).values():
            assert client.get(f"/api/v1/inventory/assets/{asset.id}", headers=h).status_code == 404
        changes = client.get("/api/v1/inventory/changes?limit=200", headers=h).json()
        assert {c["root_domain"] for c in changes["items"]} == {"globex.io"}
        csv_text = client.get("/api/v1/inventory/assets/export?state=all", headers=h).text
        assert "globex.io" in csv_text and "example.com" not in csv_text

    def test_requires_sign_in(self, client):
        for path in ("summary", "assets", "changes", "alert-settings", "assets/export"):
            assert client.get(f"/api/v1/inventory/{path}").status_code in (401, 403)

    def test_only_admins_change_alert_settings(self, client, db_session):
        org, _, owner, member, _ = self._seed(db_session)
        update = {"cert_expiry_days": 45, "extra_emails": ["soc@client.test"],
                  "rules": {"asset_disappeared": {"email": True}}}
        assert client.put("/api/v1/inventory/alert-settings", json=update,
                          headers=_headers(member)).status_code == 403
        saved = client.put("/api/v1/inventory/alert-settings", json=update, headers=_headers(owner))
        assert saved.status_code == 200
        body = saved.json()
        assert body["cert_expiry_days"] == 45 and body["rules"]["asset_disappeared"] == {"in_app": True, "email": True}
        assert body["rules"]["new_asset"] == {"in_app": True, "email": True}

        seen = client.get("/api/v1/inventory/alert-settings", headers=_headers(member)).json()
        assert seen["can_edit"] is False and seen["extra_emails"] == []
        assert client.put("/api/v1/inventory/alert-settings", json={"extra_emails": ["bad"]},
                          headers=_headers(owner)).status_code == 422

    def test_csv_export_neutralises_formulas(self, client, db_session):
        org = _org(db_session)
        owner = _user(db_session, org)
        inv.sync_scan(db_session, _scan(db_session, org, {
            "example.com": {"ports": [(8080, "=cmd|'/c calc'!A1")]}}))
        text = client.get("/api/v1/inventory/assets/export?type=service", headers=_headers(owner)).text
        assert "'=cmd" in text and ",=cmd" not in text


class TestRebuild:
    def test_rebuild_folds_old_scans_in_order_without_alerts(self, client, db_session, outbox):
        org = _org(db_session)
        owner = _user(db_session, org)
        t0, t1 = NOW - timedelta(days=30), NOW - timedelta(days=2)
        _scan(db_session, org, {"example.com": {}}, when=t0)
        _scan(db_session, org, BASE, when=t1)
        h = _headers(owner)
        assert client.get("/api/v1/inventory/summary", headers=h).json()["needs_rebuild"] is True

        stats = client.post("/api/v1/inventory/rebuild", headers=h).json()
        assert stats["scans_processed"] == 2
        hosts = _assets(db_session, org, "host")
        assert inv._aware(hosts["example.com"].first_seen) == t0
        assert inv._aware(hosts["example.com"].last_seen) == t1
        assert inv._aware(hosts["api.example.com"].first_seen) == t1
        assert db_session.query(Notification).count() == 0 and outbox == []
        assert client.post("/api/v1/inventory/rebuild", headers=h).json()["scans_processed"] == 0

    def test_legacy_assets_are_adopted_not_duplicated(self, db_session):
        org = _org(db_session)
        db_session.add(Asset(organization_id=org.id, asset_type="host", value="api.example.com",
                             label="api.example.com", first_seen=NOW - timedelta(days=90),
                             last_seen=NOW - timedelta(days=90)))
        db_session.commit()
        res = inv.sync_scan(db_session, _scan(db_session, org, BASE))
        hosts = _assets(db_session, org, "host")
        assert inv._aware(hosts["api.example.com"].first_seen) == NOW - timedelta(days=90)
        assert hosts["api.example.com"].root_domain == "example.com"
        # example.com is new next to a known host; services have no history yet, so they stay quiet.
        assert [i["key"] for i in res.alerts["new_asset"]] == ["example.com"]
        assert "new_service" not in res.alerts

    def test_older_scan_processed_late_does_not_undo_newer_state(self, db_session):
        org = _org(db_session)
        old = _scan(db_session, org, {"example.com": {"ports": [(21, "ftp")]},
                                      "old.example.com": {}}, when=NOW - timedelta(days=10))
        inv.sync_scan(db_session, _scan(db_session, org, BASE, when=NOW))
        res = inv.sync_scan(db_session, old)
        hosts = _assets(db_session, org, "host")
        assert inv._aware(hosts["example.com"].first_seen) == NOW - timedelta(days=10)
        assert inv._aware(hosts["example.com"].last_seen) == NOW
        assert hosts["example.com"].attributes["open_ports"] == [443]
        assert hosts["api.example.com"].miss_count == 0
        assert "asset_disappeared" not in res.alerts
