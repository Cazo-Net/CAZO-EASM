"""Regression tests for the login / privilege fixes.

Covers: 2FA enforced at login, passkeys disabled, refresh needs a session,
case-insensitive emails, API-key auth, org role escalation, invitation
binding, and login required on the blockchain / dark-web routers.
"""
import pyotp

PW = "TestPass123!"


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _me(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).json()


def test_email_is_case_insensitive(client):
    r = client.post("/api/v1/auth/register", json={"email": "Mixed@Case.io", "password": PW})
    assert r.status_code == 200 and r.json()["email"] == "mixed@case.io"
    assert client.post("/api/v1/auth/register", json={"email": "MIXED@case.io", "password": PW}).status_code == 400
    assert client.post("/api/v1/auth/login", json={"email": "mixed@CASE.io", "password": PW}).status_code == 200


def test_login_with_2fa_returns_no_tokens_until_code(client):
    h = _register_login(client, "mfa@test.io")
    uri = client.post("/api/v1/auth/2fa/setup", headers=h).json()["provisioning_uri"]
    secret = pyotp.parse_uri(uri).secret
    assert client.post("/api/v1/auth/2fa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()}).status_code == 200

    step1 = client.post("/api/v1/auth/login", json={"email": "mfa@test.io", "password": PW}).json()
    assert step1["requires_2fa"] is True
    assert not step1.get("access_token") and not step1.get("refresh_token")
    # The mfa_token is not a session token.
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {step1['mfa_token']}"}).status_code == 401

    bad = client.post("/api/v1/auth/2fa/verify-login", json={"mfa_token": step1["mfa_token"], "code": "000000"})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/2fa/verify-login",
                     json={"mfa_token": step1["mfa_token"], "code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_passkey_login_is_disabled(client):
    assert client.post("/api/v1/passkeys/authenticate/complete", json={"credential_id": "x"}).status_code == 501
    assert client.post("/api/v1/passkeys/authenticate/begin?email=a@b.io").status_code == 501


def test_token_without_version_is_rejected(client):
    from app.core.security import create_access_token
    h = _register_login(client, "tv@test.io")
    uid = _me(client, h)["id"]
    legacy = create_access_token({"sub": uid})
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401


def test_refresh_requires_session(client):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.config import settings
    h = _register_login(client, "rs@test.io")
    uid = _me(client, h)["id"]
    # A validly signed refresh token that was never issued to a session.
    forged = jwt.encode(
        {"sub": uid, "tv": 0, "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(days=3)},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": forged}).status_code == 401


def _org_with_members(client, db_session):
    from app.models.user import User
    owner = _register_login(client, "owner@test.io")
    org_id = client.post("/api/v1/organizations", headers=owner, json={"name": "Acme"}).json()["id"]
    admin = _register_login(client, "admin@test.io")
    viewer = _register_login(client, "viewer@test.io")
    for email, role in (("admin@test.io", "admin"), ("viewer@test.io", "viewer")):
        u = db_session.query(User).filter(User.email == email).first()
        u.organization_id, u.role = org_id, role
    db_session.commit()
    return org_id, owner, admin, viewer


def test_admin_cannot_take_or_remove_ownership(client, db_session):
    org_id, owner, admin, _ = _org_with_members(client, db_session)
    owner_id, admin_id = _me(client, owner)["id"], _me(client, admin)["id"]
    base = f"/api/v1/organizations/{org_id}/members"
    assert client.put(f"{base}/{admin_id}/role", headers=admin, json={"role": "owner"}).status_code == 400
    assert client.put(f"{base}/{owner_id}/role", headers=admin, json={"role": "viewer"}).status_code == 403
    assert client.delete(f"{base}/{owner_id}", headers=admin).status_code == 403


def test_viewer_cannot_manage_webhooks_or_keys(client, db_session):
    _, _, _, viewer = _org_with_members(client, db_session)
    r = client.post("/api/v1/webhooks", headers=viewer,
                    json={"name": "x", "url": "https://example.com/h", "events": ["scan.completed"]})
    assert r.status_code == 403
    assert client.post("/api/v1/api-keys/v2", headers=viewer, json={"name": "k"}).status_code == 403


def test_org_admin_cannot_read_platform_logs(client, db_session):
    _, _, admin, _ = _org_with_members(client, db_session)
    assert client.get("/api/v1/logs/", headers=admin).status_code == 403


def test_invitation_only_for_invited_email(client, db_session):
    from app.models.auth_models import Invitation
    owner = _register_login(client, "inv-owner@test.io")
    client.post("/api/v1/organizations", headers=owner, json={"name": "Inv Org"})
    assert client.post("/api/v1/invitations", headers=owner,
                       json={"email": "invitee@test.io", "role": "admin"}).status_code == 200
    token = db_session.query(Invitation).filter(Invitation.email == "invitee@test.io").first().token
    outsider = _register_login(client, "outsider@test.io")
    assert client.post(f"/api/v1/invitations/accept?token={token}", headers=outsider).status_code == 403


def test_api_key_authenticates_and_cannot_manage_account(client, db_session):
    owner = _register_login(client, "keys@test.io")
    client.post("/api/v1/organizations", headers=owner, json={"name": "Keys Org"})
    key = client.post("/api/v1/api-keys/v2", headers=owner, json={"name": "ci", "scopes": ["read"]}).json()["key"]
    assert client.get("/api/v1/scans", headers={"X-API-Key": key}).status_code == 200
    assert client.post("/api/v1/projects", headers={"X-API-Key": key}, json={"name": "p"}).status_code == 403
    assert client.post("/api/v1/api-keys", headers={"X-API-Key": key}, json={"name": "x"}).status_code == 403
    assert client.get("/api/v1/scans", headers={"X-API-Key": "easm_bogus"}).status_code == 401


def test_blockchain_and_darkweb_require_login(client):
    assert client.get("/api/v1/blockchain/cases").status_code == 401
    assert client.get("/api/v1/darkweb/monitors").status_code == 401


def test_email_change_requires_password(client):
    h = _register_login(client, "chg@test.io")
    assert client.put("/api/v1/users/me", headers=h, json={"email": "new@test.io"}).status_code == 400
    r = client.put("/api/v1/users/me", headers=h, json={"email": "new@test.io", "current_password": PW})
    assert r.status_code == 200 and r.json()["email_verified"] is False
