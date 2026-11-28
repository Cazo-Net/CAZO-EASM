"""Regression tests for the 2026-11-28 bug hunt.

Covers: webhook URLs that point at internal addresses (SSRF), blockchain
investigation cases leaking between organizations, and the size cap on the
unauthenticated client-error log endpoint.
"""
import asyncio

import httpx
import pytest

PW = "TestPass123!"


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _owner_with_org(client, email, name):
    h = _register_login(client, email)
    assert client.post("/api/v1/organizations", headers=h, json={"name": name}).status_code in (200, 201)
    # Sign in again so the session reflects the new organization.
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:6379/",
    "http://localhost:8000/api",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/hook",
    "http://[::1]:9000/",
    "http://2130706433/",
    "http://metadata.google.internal/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_x",
    "https://user:pass@hooks.example.com/x",
])
def test_webhook_rejects_internal_or_odd_urls(client, url):
    h = _owner_with_org(client, "hookowner@test.io", "Hooks")
    r = client.post("/api/v1/webhooks", headers=h, json={"url": url, "event_types": ["scan.completed"]})
    assert r.status_code == 400, (url, r.text)


def test_webhook_update_cannot_switch_to_internal_url(client):
    h = _owner_with_org(client, "hookowner2@test.io", "Hooks2")
    r = client.post("/api/v1/webhooks", headers=h, json={"url": "https://8.8.8.8/hook"})
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    r = client.put(f"/api/v1/webhooks/{wid}", headers=h, json={"url": "http://127.0.0.1:6379/"})
    assert r.status_code == 400


def test_webhook_delivery_refuses_internal_host_even_if_saved():
    """A URL saved before the check existed (or a DNS change) is still blocked at send time."""
    from app.services.webhook_dispatch import dispatch_webhook

    class FakeHook:
        id = "hook-1234567890"
        organization_id = "org"
        url = "http://127.0.0.1:1/never"
        content_type = "application/json"
        custom_headers = {"X-CAZO-Signature": "forged", "Host": "evil"}
        last_error = None

        def matches_event(self, _):
            return True

        def check_rate_limit(self):
            return True

        def sign_payload(self, _):
            return "sig"

        def record_success(self):
            raise AssertionError("must not deliver")

        def record_failure(self, err):
            self.last_error = err

    sent = []
    real_send = httpx.AsyncClient.send

    async def spy(self, request, **kw):
        sent.append(request)
        return await real_send(self, request, **kw)

    hook = FakeHook()
    import app.services.webhook_dispatch as wd
    wd.RETRY_BASE_DELAY = 0
    httpx.AsyncClient.send = spy
    try:
        ok = asyncio.run(dispatch_webhook(hook, "scan.completed", {}))
    finally:
        httpx.AsyncClient.send = real_send
    assert ok is False
    assert "non-public host" in (hook.last_error or "")
    # Custom headers can never replace the signature.
    assert all(r.headers.get("X-CAZO-Signature") == "sha256=sig" for r in sent)


def test_blockchain_cases_are_per_organization(client):
    alice = _owner_with_org(client, "alice-bc@test.io", "Alice BC")
    bob = _owner_with_org(client, "bob-bc@test.io", "Bob BC")

    # A client-supplied org_id is ignored.
    r = client.post("/api/v1/blockchain/cases", headers=alice,
                    json={"title": "alice case", "org_id": "someone-else", "created_by": "spoof"})
    assert r.status_code == 200, r.text
    case = r.json()
    assert case["org_id"] and case["org_id"] != "someone-else"
    assert case["created_by"] != "spoof"
    cid = case["id"]

    assert client.get(f"/api/v1/blockchain/cases/{cid}", headers=alice).status_code == 200
    assert cid in [c["id"] for c in client.get("/api/v1/blockchain/cases", headers=alice).json()["cases"]]

    assert client.get(f"/api/v1/blockchain/cases/{cid}", headers=bob).status_code == 404
    assert cid not in [c["id"] for c in client.get("/api/v1/blockchain/cases", headers=bob).json()["cases"]]
    assert client.put(f"/api/v1/blockchain/cases/{cid}", headers=bob, json={"title": "pwned"}).status_code == 404
    assert client.post(f"/api/v1/blockchain/cases/{cid}/annotations", headers=bob, json={"content": "x"}).status_code == 404
    assert client.post(f"/api/v1/blockchain/cases/{cid}/members", headers=bob, json={"user_id": "x"}).status_code == 404
    # A bad role is a 422, not a server error.
    assert client.post(f"/api/v1/blockchain/cases/{cid}/members", headers=alice,
                       json={"user_id": "x", "role": "nope"}).status_code == 422
    assert client.get("/api/v1/blockchain/cases/stats", headers=alice).status_code == 200


def test_client_error_log_is_size_capped(client):
    assert client.post("/api/v1/logs/client-error", json={"message": "TypeError: x"}).status_code == 200
    assert client.post("/api/v1/logs/client-error", json={"message": "A" * 200_000}).status_code == 422
