"""Regression tests for bugs found in the 2026-11-28 click-through QA pass."""
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability


def _org_user(client, auth_headers, db_session):
    resp = client.post("/api/v1/organizations", json={"name": "QA Org"}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    db_session.expire_all()
    return db_session.query(User).filter(User.email == auth_headers["email"]).one()


def test_findings_without_subdomain_are_listed_for_all_scans(client, auth_headers, db_session):
    # A finding on a host that is not one of the scan's subdomains is stored
    # with subdomain_id=None. The "All scans" findings list and the severity
    # summary used to drop it, so the totals did not match the per-scan view.
    user = _org_user(client, auth_headers, db_session)
    scan = Scan(domain="qa.example.com", organization_id=user.organization_id,
                status="completed", progress=100, created_by=user.id)
    db_session.add(scan)
    db_session.flush()
    db_session.add(Vulnerability(
        scan_id=scan.id, subdomain_id=None, template_id="exposed-env",
        name="Exposed .env file", severity="critical", host="qa.example.com",
        organization_id=user.organization_id,
    ))
    db_session.commit()

    listed = client.get("/api/v1/assets/vulnerabilities", headers=auth_headers)
    assert listed.status_code == 200
    assert [v["name"] for v in listed.json()] == ["Exposed .env file"]

    summary = client.get("/api/v1/assets/vulnerabilities/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["total"] == 1
    assert summary.json()["critical"] == 1


def test_unsupported_report_format_is_422_not_500(client, auth_headers, db_session):
    # The reports dialog offered "HTML", which the report service cannot build,
    # so the request failed with a 500.
    user = _org_user(client, auth_headers, db_session)
    scan = Scan(domain="qa.example.com", organization_id=user.organization_id,
                status="completed", progress=100, created_by=user.id)
    db_session.add(scan)
    db_session.commit()
    resp = client.post(f"/api/v1/reports?scan_id={scan.id}&format=html", headers=auth_headers)
    assert resp.status_code == 422
    assert "json" in resp.json()["detail"]
