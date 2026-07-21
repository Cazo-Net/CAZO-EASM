"""Integration tests for the new foundation modules via the API.

Covers authorized scopes, asset inventory/graph, scoring, and the change
timeline. Uses the shared TestClient (which points at the on-disk SQLite test
database) and the ``auth_headers`` fixture from conftest.

Note: scans run real external scanners, so we don't trigger a full scan here;
instead we seed minimal data through the repository/service layer directly to
validate the read paths and authorization.
"""
import pytest
from app.repositories.assets import upsert_asset, upsert_relationship, get_asset_graph
from app.services.scoring import compute_asset_scores, score_health, score_exposure
from app.models.asset_inventory import Asset, AssetRelationship


@pytest.fixture
def org_user(client, auth_headers):
    # Pull the created user's organization from the auth flow is not exposed;
    # instead create an org-bound user via the API is not available, so we
    # attach an organization to the registered user directly in a session.
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        if not user.organization_id:
            from app.models.organization import Organization
            import uuid

            org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
            db.add(org)
            db.commit()
            db.refresh(org)
            user.organization_id = org.id
        # Scope management requires MANAGE_ORG (admin). Promote the fixture user
        # so integration tests can exercise the authorized-scope CRUD flow.
        user.role = "admin"
        db.commit()
        db.refresh(user)
        return {"user_id": user.id, "org_id": user.organization_id, "headers": auth_headers}
    finally:
        db.close()


def test_scope_crud_and_enforcement(client, org_user):
    h = org_user["headers"]
    org_id = org_user["org_id"]

    # Create a scope.
    resp = client.post(
        "/api/v1/scopes",
        headers=h,
        json={"scope_type": "domain", "value": "example.com"},
    )
    assert resp.status_code == 201, resp.text
    scope_id = resp.json()["id"]

    # List scopes.
    resp = client.get("/api/v1/scopes", headers=h)
    assert resp.status_code == 200
    assert any(s["id"] == scope_id for s in resp.json())

    # Check endpoint: authorized.
    resp = client.post("/api/v1/scopes/check", headers=h, json={"scope_type": "domain", "value": "example.com"})
    assert resp.status_code == 200
    assert resp.json()["authorized"] is True

    # Check endpoint: not authorized.
    resp = client.post("/api/v1/scopes/check", headers=h, json={"scope_type": "domain", "value": "evil.com"})
    assert resp.json()["authorized"] is False

    # Invalid scope value rejected.
    resp = client.post("/api/v1/scopes", headers=h, json={"scope_type": "ip", "value": "not-an-ip"})
    assert resp.status_code == 422

    # Delete scope.
    resp = client.delete(f"/api/v1/scopes/{scope_id}", headers=h)
    assert resp.status_code == 204

    resp = client.get("/api/v1/scopes", headers=h)
    assert not any(s["id"] == scope_id for s in resp.json())


def test_asset_inventory_and_graph(client, org_user):
    h = org_user["headers"]
    org_id = org_user["org_id"]
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        host = upsert_asset(db, org_id, "host", "app.example.com", label="app.example.com")
        ip = upsert_asset(db, org_id, "ip", "10.0.0.1", label="10.0.0.1")
        upsert_relationship(db, org_id, host.id, ip.id, "resolves_to")
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/assets/inventory", headers=h)
    assert resp.status_code == 200
    values = {a["value"] for a in resp.json()}
    assert "app.example.com" in values

    resp = client.get("/api/v1/assets/inventory/graph", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["counts"]["nodes"] >= 2
    assert body["counts"]["edges"] >= 1


def test_scoring_endpoint(client, org_user):
    h = org_user["headers"]
    org_id = org_user["org_id"]
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        upsert_asset(db, org_id, "host", "secure.example.com",
                     attributes={"open_ports": [443], "services": ["https"]})
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/assets/scores/recompute", headers=h)
    assert resp.status_code == 200
    assert resp.json()["scored"] >= 1

    resp = client.get("/api/v1/assets/scores", headers=h)
    assert resp.status_code == 200
    assert any(s["exposure_score"] is not None for s in resp.json())


def test_timeline_endpoint_empty(client, org_user):
    h = org_user["headers"]
    resp = client.get("/api/v1/assets/timeline", headers=h)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_discovery_plugins_listed(client, auth_headers):
    resp = client.get("/api/v1/scans/discovery/plugins", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["plugins"]) >= 7
