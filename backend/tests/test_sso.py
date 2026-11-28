"""Single sign-on (OIDC): settings, domain verification, the sign-in flow,
token validation, provisioning, enforcement and tenant isolation."""
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.models.audit import AuditEvent
from app.models.sso import OrgSsoConfig, SsoDomain, SsoLoginState
from app.models.user import User
from app.services import sso

PW = "TestPass123!"
ISSUER = "https://8.8.4.4"  # a public IP literal: passes the public-address check without DNS
CLIENT_ID = "cazo-client"


def _pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**jwk.construct(_pem(KEY), "RS256").public_key().to_dict(), "kid": "k1", "use": "sig"}


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _owner_with_org(client, email, name):
    h = _register_login(client, email)
    assert client.post("/api/v1/organizations", headers=h, json={"name": name}).status_code in (200, 201)
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


@pytest.fixture
def idp(monkeypatch):
    """A fake identity provider and DNS. ``box['claims']`` is what the next ID token says."""
    box = {"claims": {}, "key": KEY, "kid": "k1", "alg": "RS256", "token_status": 200, "txt": {}, "requests": [],
           "issuer_in_doc": ISSUER}

    def handler(request: httpx.Request) -> httpx.Response:
        box["requests"].append(request)
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": box["issuer_in_doc"], "authorization_endpoint": ISSUER + "/authorize",
                "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/keys",
            })
        if path == "/keys":
            return httpx.Response(200, json={"keys": [JWK]})
        if path == "/token":
            if box["token_status"] != 200:
                return httpx.Response(box["token_status"], json={"error": "invalid_grant"})
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": "u-1", "iat": now, "exp": now + 300, **box["claims"]}
            token = jwt.encode(claims, _pem(box["key"]), algorithm=box["alg"], headers={"kid": box["kid"]})
            return httpx.Response(200, json={"id_token": token, "access_token": "at"})
        return httpx.Response(404)

    monkeypatch.setattr(sso, "_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(sso, "_lookup_txt", lambda name: box["txt"].get(name, []))
    sso._discovery_cache.clear()
    return box


def _setup(client, h, idp, domain="acme.io", **settings):
    """Claim and verify a domain, then save SSO settings (on by default)."""
    d = client.post("/api/v1/sso/domains", headers=h, json={"domain": domain}).json()
    idp["txt"][d["dns_record"]["name"]] = [d["dns_record"]["value"]]
    assert client.post(f"/api/v1/sso/domains/{d['id']}/verify", headers=h).json()["verified"] is True
    body = {"issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": "s3cret-value", "enabled": True, **settings}
    r = client.put("/api/v1/sso", headers=h, json=body)
    assert r.status_code == 200, r.text
    return d


def _sign_in(client, idp, email, **claims):
    """Run the whole flow. Returns the final response (exchange, or the error redirect)."""
    r = client.post("/api/v1/auth/sso/start", json={"email": email})
    assert r.status_code == 200, r.text
    q = parse_qs(urlsplit(r.json()["url"]).query)
    idp["claims"] = {"email": email, "nonce": q["nonce"][0], **claims}
    cb = client.get("/api/v1/auth/sso/callback", params={"state": q["state"][0], "code": "abc"}, follow_redirects=False)
    assert cb.status_code == 303
    location = cb.headers["location"]
    if "sso_error=" in location:
        return cb
    return client.post("/api/v1/auth/sso/exchange", json={"code": location.split("#code=")[1]})


def _error(resp):
    return resp.headers["location"].split("sso_error=")[1]


# ── Settings and domains ─────────────────────────────────────────────────


def test_settings_require_permission_and_hide_the_secret(client, db_session, idp):
    assert client.get("/api/v1/sso").status_code in (401, 403)
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    state = client.get("/api/v1/sso", headers=h).json()
    assert state["config"]["has_secret"] is True and "s3cret-value" not in str(state)
    assert state["redirect_uri"].endswith("/api/v1/auth/sso/callback")
    row = db_session.query(OrgSsoConfig).first()
    assert "s3cret-value" not in row.client_secret_encrypted

    _register_login(client, "view@acme.io")
    u = _user(db_session, "view@acme.io")
    u.organization_id, u.role = _user(db_session, "own@acme.io").organization_id, "viewer"
    db_session.commit()
    viewer = {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": "view@acme.io", "password": PW}).json()["access_token"]}
    assert client.get("/api/v1/sso", headers=viewer).status_code == 403
    assert client.put("/api/v1/sso", headers=viewer, json={"issuer": ISSUER, "client_id": "x", "client_secret": "y"}).status_code == 403

    actions = {a for (a,) in db_session.query(AuditEvent.action).all()}
    assert {"sso.domain.add", "sso.domain.verify", "sso.config.update"} <= actions
    assert "s3cret-value" not in str([e.detail for e in db_session.query(AuditEvent).all()])


def test_cannot_turn_on_without_a_verified_domain(client, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    body = {"issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": "s", "enabled": True}
    assert client.put("/api/v1/sso", headers=h, json=body).status_code == 422
    d = client.post("/api/v1/sso/domains", headers=h, json={"domain": "ACME.io"}).json()
    assert d["domain"] == "acme.io" and d["verified"] is False
    # The DNS record is not there yet.
    r = client.post(f"/api/v1/sso/domains/{d['id']}/verify", headers=h).json()
    assert r["verified"] is False and r["error"]
    assert client.put("/api/v1/sso", headers=h, json=body).status_code == 422
    assert client.put("/api/v1/sso", headers=h, json={**body, "enabled": False}).status_code == 200


@pytest.mark.parametrize("body", [
    {"issuer": "http://8.8.4.4"},
    {"issuer": "https://127.0.0.1"},
    {"issuer": "https://10.0.0.8"},
    {"issuer": "https://user:pw@8.8.4.4"},
    {"default_role": "owner"},
    {"enforce": True, "enabled": False},
    {"client_secret": ""},
])
def test_invalid_settings_are_rejected(client, idp, body):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    d = client.post("/api/v1/sso/domains", headers=h, json={"domain": "acme.io"}).json()
    idp["txt"][d["dns_record"]["name"]] = [d["dns_record"]["value"]]
    client.post(f"/api/v1/sso/domains/{d['id']}/verify", headers=h)
    payload = {"issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": "s", "enabled": True, **body}
    assert client.put("/api/v1/sso", headers=h, json=payload).status_code == 422


def test_issuer_mismatch_in_discovery_is_rejected(client, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    idp["issuer_in_doc"] = "https://evil.example"
    d = client.post("/api/v1/sso/domains", headers=h, json={"domain": "acme.io"}).json()
    idp["txt"][d["dns_record"]["name"]] = [d["dns_record"]["value"]]
    client.post(f"/api/v1/sso/domains/{d['id']}/verify", headers=h)
    body = {"issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": "s", "enabled": True}
    assert client.put("/api/v1/sso", headers=h, json=body).status_code == 422


def test_changing_issuer_requires_the_secret_again(client, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    body = {"issuer": "https://8.8.8.8", "client_id": CLIENT_ID, "enabled": False}
    assert client.put("/api/v1/sso", headers=h, json=body).status_code == 422
    assert client.put("/api/v1/sso", headers=h, json={**body, "issuer": ISSUER}).status_code == 200


def test_a_domain_can_be_verified_by_one_organization_only(client, idp):
    a = _owner_with_org(client, "a@acme.io", "Acme")
    b = _owner_with_org(client, "b@globex.io", "Globex")
    da = _setup(client, a, idp)
    db_ = client.post("/api/v1/sso/domains", headers=b, json={"domain": "acme.io"}).json()
    idp["txt"][db_["dns_record"]["name"]] = [db_["dns_record"]["value"]]
    assert client.post(f"/api/v1/sso/domains/{db_['id']}/verify", headers=b).status_code == 409
    # And one organization cannot touch another's domain rows or settings.
    assert client.post(f"/api/v1/sso/domains/{da['id']}/verify", headers=b).status_code == 404
    assert client.delete(f"/api/v1/sso/domains/{da['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/sso", headers=b).json()["config"] is None


def test_removing_the_last_verified_domain_turns_sso_off(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    d = _setup(client, h, idp, enforce=True)
    r = client.delete(f"/api/v1/sso/domains/{d['id']}", headers=h).json()
    assert r["sso_turned_off"] is True
    cfg = client.get("/api/v1/sso", headers=h).json()["config"]
    assert cfg["enabled"] is False and cfg["enforce"] is False


# ── Sign-in ──────────────────────────────────────────────────────────────


def test_start_builds_the_authorization_url(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    r = client.post("/api/v1/auth/sso/start", json={"email": "Jane@Acme.io"})
    url = urlsplit(r.json()["url"])
    q = parse_qs(url.query)
    assert url.netloc == "8.8.4.4" and url.path == "/authorize"
    assert q["client_id"] == [CLIENT_ID] and q["response_type"] == ["code"]
    assert q["code_challenge_method"] == ["S256"] and "openid" in q["scope"][0]
    assert q["redirect_uri"][0].endswith("/api/v1/auth/sso/callback")
    row = db_session.query(SsoLoginState).first()
    assert row.state_hash != q["state"][0]  # only a hash is stored
    assert client.post("/api/v1/auth/sso/start", json={"email": "x@unknown.io"}).status_code == 404


def test_new_person_is_created_with_the_default_role(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp, default_role="analyst")
    r = _sign_in(client, idp, "jane@acme.io", name="Jane Doe")
    assert r.status_code == 200 and r.json()["access_token"]
    jane = _user(db_session, "jane@acme.io")
    assert jane.organization_id == _user(db_session, "own@acme.io").organization_id
    assert jane.role == "analyst" and jane.full_name == "Jane Doe" and jane.hashed_password is None
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "jane@acme.io"
    assert db_session.query(AuditEvent).filter(AuditEvent.action == "sso.user_provisioned").count() == 1
    # A person created by SSO has no password to sign in with.
    assert client.post("/api/v1/auth/login", json={"email": "jane@acme.io", "password": PW}).status_code == 401


def test_existing_member_signs_in_and_state_is_single_use(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    start = client.post("/api/v1/auth/sso/start", json={"email": "own@acme.io"}).json()["url"]
    q = parse_qs(urlsplit(start).query)
    idp["claims"] = {"email": "own@acme.io", "nonce": q["nonce"][0]}
    params = {"state": q["state"][0], "code": "abc"}
    first = client.get("/api/v1/auth/sso/callback", params=params, follow_redirects=False)
    handoff = first.headers["location"].split("#code=")[1]
    replay = client.get("/api/v1/auth/sso/callback", params=params, follow_redirects=False)
    assert _error(replay) == "expired"
    assert client.post("/api/v1/auth/sso/exchange", json={"code": handoff}).status_code == 200
    assert client.post("/api/v1/auth/sso/exchange", json={"code": handoff}).status_code == 401  # one use
    assert db_session.query(User).count() == 1


def test_email_outside_the_verified_domains_is_refused(client, db_session, idp):
    """An organization's provider cannot vouch for another company's addresses."""
    a = _owner_with_org(client, "a@acme.io", "Acme")
    _owner_with_org(client, "victim@globex.io", "Globex")
    _setup(client, a, idp)
    start = client.post("/api/v1/auth/sso/start", json={"email": "a@acme.io"}).json()["url"]
    q = parse_qs(urlsplit(start).query)
    idp["claims"] = {"email": "victim@globex.io", "nonce": q["nonce"][0]}
    r = client.get("/api/v1/auth/sso/callback", params={"state": q["state"][0], "code": "abc"}, follow_redirects=False)
    assert _error(r) == "domain"


def test_account_in_another_organization_is_not_moved(client, db_session, idp):
    a = _owner_with_org(client, "a@acme.io", "Acme")
    _owner_with_org(client, "bob@acme.io", "Bob's own org")  # same domain, different organization
    _register_login(client, "solo@acme.io")  # no organization at all
    _setup(client, a, idp)
    assert _error(_sign_in(client, idp, "bob@acme.io")) == "other_org"
    assert _error(_sign_in(client, idp, "solo@acme.io")) == "no_account"
    assert _user(db_session, "solo@acme.io").organization_id is None


def test_auto_provision_off_and_inactive_accounts(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp, auto_provision=False)
    assert _error(_sign_in(client, idp, "new@acme.io")) == "no_account"
    assert _user(db_session, "new@acme.io") is None
    client.put("/api/v1/sso", headers=h, json={"issuer": ISSUER, "client_id": CLIENT_ID, "enabled": True})
    assert _sign_in(client, idp, "new@acme.io").status_code == 200
    u = _user(db_session, "new@acme.io")
    u.is_active = False
    db_session.commit()
    assert _error(_sign_in(client, idp, "new@acme.io")) == "inactive"


@pytest.mark.parametrize("tamper,expected", [
    ({"key": OTHER_KEY}, "provider"),             # signed by someone else
    ({"claims": {"aud": "another-app"}}, "provider"),
    ({"claims": {"iss": "https://evil.example"}}, "provider"),
    ({"claims": {"exp": 1}}, "provider"),
    ({"claims": {"nonce": "wrong"}}, "provider"),
    ({"claims": {"email_verified": False}}, "provider"),
    ({"token_status": 400}, "provider"),
])
def test_bad_tokens_are_refused(client, db_session, idp, tamper, expected):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    start = client.post("/api/v1/auth/sso/start", json={"email": "jane@acme.io"}).json()["url"]
    q = parse_qs(urlsplit(start).query)
    idp["claims"] = {"email": "jane@acme.io", "nonce": q["nonce"][0], **tamper.get("claims", {})}
    for key in ("key", "token_status"):
        if key in tamper:
            idp[key] = tamper[key]
    r = client.get("/api/v1/auth/sso/callback", params={"state": q["state"][0], "code": "abc"}, follow_redirects=False)
    assert _error(r) == expected
    assert _user(db_session, "jane@acme.io") is None


def test_unsigned_and_symmetric_tokens_are_refused(client, db_session, idp, monkeypatch):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    cfg = db_session.query(OrgSsoConfig).first()
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "exp": now + 300, "email": "jane@acme.io", "nonce": "n"}
    doc = sso.discover(ISSUER)
    # HS256 signed with the public key material (the classic algorithm-confusion attack).
    forged = jwt.encode(claims, "anything", algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(sso.SsoError):
        sso._validate_id_token(cfg, doc, forged, "n")
    with pytest.raises(sso.SsoError):
        sso._validate_id_token(cfg, doc, "not.a.token", "n")


def test_provider_error_and_unknown_state(client, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    r = client.get("/api/v1/auth/sso/callback", params={"state": "nope", "code": "abc"}, follow_redirects=False)
    assert _error(r) == "expired"
    start = client.post("/api/v1/auth/sso/start", json={"email": "jane@acme.io"}).json()["url"]
    state = parse_qs(urlsplit(start).query)["state"][0]
    r = client.get("/api/v1/auth/sso/callback", params={"state": state, "error": "access_denied"}, follow_redirects=False)
    assert _error(r) == "denied"
    assert client.post("/api/v1/auth/sso/exchange", json={"code": "guess"}).status_code == 401


def test_member_with_two_factor_still_gets_the_second_step(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    u = _user(db_session, "own@acme.io")
    u.totp_enabled, u.totp_secret = True, "JBSWY3DPEHPK3PXP"
    db_session.commit()
    r = _sign_in(client, idp, "own@acme.io")
    assert r.status_code == 200 and r.json()["requires_2fa"] is True and r.json()["access_token"] is None


# ── Enforcement ──────────────────────────────────────────────────────────


def test_enforcement_blocks_passwords_for_members_but_not_the_owner(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _register_login(client, "member@acme.io")
    _register_login(client, "contractor@other.io")
    org = _user(db_session, "own@acme.io").organization_id
    for email in ("member@acme.io", "contractor@other.io"):
        u = _user(db_session, email)
        u.organization_id, u.role = org, "analyst"
        db_session.commit()
    _setup(client, h, idp, enforce=True)

    blocked = client.post("/api/v1/auth/login", json={"email": "member@acme.io", "password": PW})
    assert blocked.status_code == 403 and "single sign-on" in blocked.json()["detail"]
    # A wrong password still gets the ordinary answer: no hint about SSO.
    assert client.post("/api/v1/auth/login", json={"email": "member@acme.io", "password": "wrong"}).status_code == 401
    # The owner keeps a way in; a guest on a domain the provider cannot sign in keeps their password.
    assert client.post("/api/v1/auth/login", json={"email": "own@acme.io", "password": PW}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "contractor@other.io", "password": PW}).status_code == 200
    assert _sign_in(client, idp, "member@acme.io").status_code == 200

    client.put("/api/v1/sso", headers=h, json={"issuer": ISSUER, "client_id": CLIENT_ID, "enabled": True, "enforce": False})
    assert client.post("/api/v1/auth/login", json={"email": "member@acme.io", "password": PW}).status_code == 200


def test_disabled_sso_stops_sign_in(client, db_session, idp):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    _setup(client, h, idp)
    start = client.post("/api/v1/auth/sso/start", json={"email": "own@acme.io"}).json()["url"]
    q = parse_qs(urlsplit(start).query)
    client.put("/api/v1/sso", headers=h, json={"issuer": ISSUER, "client_id": CLIENT_ID, "enabled": False})
    idp["claims"] = {"email": "own@acme.io", "nonce": q["nonce"][0]}
    r = client.get("/api/v1/auth/sso/callback", params={"state": q["state"][0], "code": "abc"}, follow_redirects=False)
    assert _error(r) == "off"
    assert client.post("/api/v1/auth/sso/start", json={"email": "own@acme.io"}).status_code == 404
    assert db_session.query(SsoDomain).count() == 1
