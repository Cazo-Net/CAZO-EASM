"""Blockchain module: organization isolation, honest data, and the watch engine.

* Watches, alerts and cases belong to one organization. Another
  organization gets 404 (not 403) for each of them, sees nothing in lists,
  and cannot spoof ``org_id``/``user_id`` through the request.
* Shared, global stores (graph, v2 alerts, travel-rule compliance, the
  OpenSearch index) are for platform superusers only.
* With no data-source key, lookups answer 503 "not configured" instead of
  inventing balances and transactions.
* Sanctions come from the downloaded OFAC list. The old hardcoded table
  flagged the Uniswap V3 factory as a sanctioned exchange; it must not.
"""
from datetime import datetime, timezone

import pytest

from app.models.user import User
from app.schemas.blockchain import Chain, TransactionStatus, TransactionSummary
from app.services.blockchain import sanctions
from app.services.blockchain.providers.base import ChainProvider, registry

PW = "TestPass123!"

WATCHED = "0x1111111111111111111111111111111111111111"
FRIEND = "0x2222222222222222222222222222222222222222"
SANCTIONED = "0x098b716b8aaf21512996dc57eb0615e2383e2f96"  # on the OFAC SDN list
UNISWAP_V3_FACTORY = "0x1f98431c8ad98523631ae4a59f267346ea31f984"


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _owner_with_org(client, email, name):
    h = _register_login(client, email)
    assert client.post("/api/v1/organizations", headers=h, json={"name": name}).status_code in (200, 201)
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _me(client, h):
    return client.get("/api/v1/auth/me", headers=h).json()


def _tx(h, frm, to, ts):
    return TransactionSummary(
        hash=h, chain=Chain.ETHEREUM, status=TransactionStatus.SUCCESS, block_number=1,
        timestamp=datetime.fromtimestamp(ts, tz=timezone.utc), from_address=frm, to_address=to, value="1.0",
    )


class FakeEthProvider(ChainProvider):
    """Stands in for Etherscan so tests never touch the network."""

    chain = Chain.ETHEREUM

    def __init__(self):
        self.txs = {
            WATCHED: [
                _tx("0xaaa2", SANCTIONED, WATCHED, 1_700_000_200),  # inbound from a sanctioned address
                _tx("0xaaa1", WATCHED, FRIEND, 1_700_000_100),
            ],
        }

    async def get_wallet_summary(self, address):
        raise NotImplementedError

    async def get_transactions(self, address, page=1, page_size=20):
        return list(self.txs.get(address.lower(), []))[:page_size]

    async def get_transaction(self, tx_hash):
        raise NotImplementedError

    async def get_token_balances(self, address):
        return []

    async def get_contract_detail(self, address):
        return None


@pytest.fixture
def fake_ofac(monkeypatch):
    sanctions._reset_cache_for_tests()

    async def _download(family):
        return {SANCTIONED} if family == "evm" else {"1ExampleSanctionedBtcAddressxxxxx"}

    monkeypatch.setattr(sanctions, "_download", _download)
    yield
    sanctions._reset_cache_for_tests()


@pytest.fixture
def fake_eth(monkeypatch, fake_ofac):
    original = registry.get(Chain.ETHEREUM)
    fake = FakeEthProvider()
    registry.register(fake)
    yield fake
    registry.register(original)


# ── Isolation ────────────────────────────────────────────────────────────────

def test_watches_and_alerts_are_per_organization(client, fake_eth):
    alice = _owner_with_org(client, "alice-w@test.io", "Alice W")
    bob = _owner_with_org(client, "bob-w@test.io", "Bob W")

    # org_id / user_id in the body are ignored: the watch lands in Alice's org.
    r = client.post("/api/v1/blockchain/watches", headers=alice, json={
        "address": WATCHED.upper().replace("0X", "0x"), "chain": "ethereum", "label": "Treasury",
        "org_id": "someone-else", "user_id": "spoof",
    })
    assert r.status_code == 201, r.text
    watch = r.json()
    wid = watch["id"]
    assert watch["address"] == WATCHED
    assert watch["last_status"]["result"] == "ok"

    # The first check screens recent history: the sanctioned sender is flagged.
    alerts = client.get("/api/v1/blockchain/alerts", headers=alice).json()["alerts"]
    assert [a["alert_type"] for a in alerts] == ["sanctioned_counterparty"]
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["counterparty"] == SANCTIONED
    aid = alerts[0]["id"]

    # Bob sees nothing and can touch nothing.
    assert client.get("/api/v1/blockchain/watches", headers=bob).json()["watches"] == []
    assert client.get("/api/v1/blockchain/alerts", headers=bob).json()["alerts"] == []
    assert client.get("/api/v1/blockchain/alerts/stats", headers=bob).json()["total"] == 0
    assert client.post(f"/api/v1/blockchain/watches/{wid}/check", headers=bob).status_code == 404
    assert client.patch(f"/api/v1/blockchain/watches/{wid}", headers=bob, json={"is_active": False}).status_code == 404
    assert client.delete(f"/api/v1/blockchain/watches/{wid}", headers=bob).status_code == 404
    assert client.post(f"/api/v1/blockchain/alerts/{aid}/acknowledge", headers=bob).status_code == 404
    # Query-string org_id no longer widens anything.
    assert client.get("/api/v1/blockchain/alerts?org_id=" + "x", headers=bob).json()["alerts"] == []

    # Alice's data is untouched by Bob's attempts.
    w = client.get("/api/v1/blockchain/watches", headers=alice).json()["watches"]
    assert len(w) == 1 and w[0]["is_active"] is True and w[0]["open_alerts"] == 1

    # Same address in Bob's own org is allowed and independent.
    r = client.post("/api/v1/blockchain/watches", headers=bob, json={"address": WATCHED, "chain": "ethereum"})
    assert r.status_code == 201
    assert client.post("/api/v1/blockchain/watches", headers=alice,
                       json={"address": WATCHED, "chain": "ethereum"}).status_code == 409

    assert client.post(f"/api/v1/blockchain/alerts/{aid}/acknowledge", headers=alice).status_code == 200
    assert client.get("/api/v1/blockchain/alerts/stats", headers=alice).json()["unacknowledged"] == 0


def test_case_members_and_assignees_must_be_in_the_same_org(client):
    alice = _owner_with_org(client, "alice-cm@test.io", "Alice CM")
    bob = _owner_with_org(client, "bob-cm@test.io", "Bob CM")
    bob_id = _me(client, bob)["id"]
    alice_id = _me(client, alice)["id"]

    # Cannot pull a user from another organization into a case.
    assert client.post("/api/v1/blockchain/cases", headers=alice,
                       json={"title": "x", "assigned_to": bob_id}).status_code == 422
    r = client.post("/api/v1/blockchain/cases", headers=alice, json={
        "title": "Incident 42", "addresses": [{"chain": "ethereum", "address": WATCHED, "note": "drained"}],
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert client.post(f"/api/v1/blockchain/cases/{cid}/members", headers=alice,
                       json={"user_id": bob_id}).status_code == 422
    assert client.put(f"/api/v1/blockchain/cases/{cid}", headers=alice,
                      json={"assigned_to": bob_id}).status_code == 422
    assert client.put(f"/api/v1/blockchain/cases/{cid}", headers=alice,
                      json={"assigned_to": alice_id, "status": "in_review"}).status_code == 200
    # A bad address in a case is rejected.
    assert client.put(f"/api/v1/blockchain/cases/{cid}", headers=alice,
                      json={"addresses": [{"chain": "ethereum", "address": "0xnothex"}]}).status_code == 422

    # Persisted, with notes and an audit trail.
    assert client.post(f"/api/v1/blockchain/cases/{cid}/annotations", headers=alice,
                       json={"content": "Funds moved to exchange"}).status_code == 200
    detail = client.get(f"/api/v1/blockchain/cases/{cid}", headers=alice).json()
    assert detail["case"]["status"] == "in_review"
    assert detail["case"]["addresses"][0]["address"] == WATCHED
    assert [a["content"] for a in detail["annotations"]] == ["Funds moved to exchange"]
    assert {e["action"] for e in detail["audit"]} >= {"created", "updated", "annotation_added"}

    # Bob cannot see or delete it.
    assert client.get(f"/api/v1/blockchain/cases/{cid}", headers=bob).status_code == 404
    assert client.delete(f"/api/v1/blockchain/cases/{cid}", headers=bob).status_code == 404
    assert client.get("/api/v1/blockchain/cases/stats", headers=bob).json()["total"] == 0
    assert client.delete(f"/api/v1/blockchain/cases/{cid}", headers=alice).status_code == 204
    assert client.get(f"/api/v1/blockchain/cases/{cid}", headers=alice).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/blockchain/alerts/v2"),
    ("get", "/api/v1/blockchain/alerts/v2/stats"),
    ("get", "/api/v1/blockchain/compliance/cases"),
    ("get", "/api/v1/blockchain/compliance/messages"),
    ("get", "/api/v1/blockchain/compliance/stats"),
    ("get", "/api/v1/blockchain/compliance/vasps"),
    ("get", "/api/v1/blockchain/graph/watches"),
    ("post", "/api/v1/blockchain/graph/watch"),
    ("get", "/api/v1/blockchain/search/unified?q=x"),
])
def test_global_stores_are_superuser_only(client, db_session, method, path):
    h = _owner_with_org(client, "owner-glob@test.io", "Glob")
    kwargs = {"json": {"address": WATCHED}} if method == "post" else {}
    assert getattr(client, method)(path, headers=h, **kwargs).status_code == 403

    user = db_session.query(User).filter(User.email == "owner-glob@test.io").first()
    user.role = "superuser"
    db_session.commit()
    assert getattr(client, method)(path, headers=h, **kwargs).status_code != 403


def test_viewer_cannot_create_watches(client, db_session, fake_eth):
    h = _owner_with_org(client, "viewer-w@test.io", "Viewer W")
    user = db_session.query(User).filter(User.email == "viewer-w@test.io").first()
    user.role = "viewer"
    db_session.commit()
    assert client.post("/api/v1/blockchain/watches", headers=h,
                       json={"address": WATCHED, "chain": "ethereum"}).status_code == 403
    assert client.get("/api/v1/blockchain/watches", headers=h).status_code == 200


def test_blockchain_requires_login(client):
    assert client.get("/api/v1/blockchain/watches").status_code == 401
    assert client.get("/api/v1/blockchain/wallet/" + WATCHED).status_code == 401


# ── Watch engine ─────────────────────────────────────────────────────────────

def test_new_activity_raises_one_alert_and_is_not_repeated(client, fake_eth):
    h = _owner_with_org(client, "engine@test.io", "Engine")
    wid = client.post("/api/v1/blockchain/watches", headers=h,
                      json={"address": WATCHED, "chain": "ethereum"}).json()["id"]
    baseline = {a["id"] for a in client.get("/api/v1/blockchain/alerts", headers=h).json()["alerts"]}

    # Nothing new: no new alert.
    r = client.post(f"/api/v1/blockchain/watches/{wid}/check", headers=h)
    assert r.status_code == 200 and r.json()["new_alerts"] == 0

    fake_eth.txs[WATCHED].insert(0, _tx("0xaaa3", WATCHED, FRIEND, 1_700_000_300))
    r = client.post(f"/api/v1/blockchain/watches/{wid}/check", headers=h).json()
    assert r["new_transactions"] == 1 and r["new_alerts"] == 1
    new = [a for a in client.get("/api/v1/blockchain/alerts", headers=h).json()["alerts"] if a["id"] not in baseline]
    assert len(new) == 1
    assert new[0]["alert_type"] == "new_transaction"
    assert new[0]["severity"] == "medium"  # outgoing
    assert new[0]["reference_url"] == "https://etherscan.io/tx/0xaaa3"

    # Checking again does not duplicate it.
    assert client.post(f"/api/v1/blockchain/watches/{wid}/check", headers=h).json()["new_alerts"] == 0


def test_run_due_watches_checks_every_org(client, db_session, fake_eth):
    from app.models.blockchain import BlockchainAlert, BlockchainWatch
    from app.services.blockchain.watch_engine import run_due_watches

    a = _owner_with_org(client, "due-a@test.io", "Due A")
    b = _owner_with_org(client, "due-b@test.io", "Due B")
    for h in (a, b):
        client.post("/api/v1/blockchain/watches", headers=h, json={"address": WATCHED, "chain": "ethereum"})
    db_session.query(BlockchainWatch).update({BlockchainWatch.last_checked_at: datetime(2020, 1, 1, tzinfo=timezone.utc)})
    db_session.commit()
    fake_eth.txs[WATCHED].insert(0, _tx("0xbbb1", FRIEND, WATCHED, 1_700_000_400))
    assert run_due_watches(db_session) == 2
    rows = db_session.query(BlockchainAlert).filter(BlockchainAlert.alert_type == "new_transaction").all()
    assert len(rows) == 2 and len({r.organization_id for r in rows}) == 2
    assert all(r.severity == "info" for r in rows)  # inbound only


def test_invalid_address_is_rejected(client, fake_eth):
    h = _owner_with_org(client, "badaddr@test.io", "Bad Addr")
    for body in ({"address": "0x123", "chain": "ethereum"},
                 {"address": "not-a-wallet-at-all", "chain": "bitcoin"},
                 {"address": "0x" + "z" * 40, "chain": "polygon"}):
        assert client.post("/api/v1/blockchain/watches", headers=h, json=body).status_code == 422, body


# ── Honest data ──────────────────────────────────────────────────────────────

def test_no_etherscan_key_means_503_not_fake_numbers(client, monkeypatch, fake_ofac):
    h = _owner_with_org(client, "nokey@test.io", "No Key")
    provider = registry.get(Chain.ETHEREUM)
    monkeypatch.setattr(provider, "api_key", "")
    for path in (f"/api/v1/blockchain/wallet/{WATCHED}",
                 f"/api/v1/blockchain/wallet/{WATCHED}/transactions",
                 f"/api/v1/blockchain/wallet/{WATCHED}/tokens"):
        r = client.get(path, headers=h)
        assert r.status_code == 503, (path, r.text)
        assert r.json()["detail"]["code"] == "data_source_not_configured"
        assert r.json()["detail"]["setting"] == "ETHERSCAN_API_KEY"

    status = {c["chain"]: c for c in client.get("/api/v1/blockchain/chains", headers=h).json()["status"]}
    assert status["ethereum"]["live"] is False and status["ethereum"]["needs"] == "ETHERSCAN_API_KEY"
    assert status["bitcoin"]["live"] is True


def test_no_key_watch_records_status_without_alerts(client, monkeypatch, fake_ofac):
    from app.services.blockchain.providers.base import DataSourceUnavailable

    h = _owner_with_org(client, "nokeywatch@test.io", "No Key Watch")
    provider = registry.get(Chain.POLYGON)

    async def boom(*a, **k):
        raise DataSourceUnavailable(Chain.POLYGON, "not_configured", "needs key", setting="ETHERSCAN_API_KEY")

    monkeypatch.setattr(provider, "get_transactions", boom)
    r = client.post("/api/v1/blockchain/watches", headers=h, json={"address": FRIEND, "chain": "polygon"})
    assert r.status_code == 201
    assert r.json()["last_status"]["result"] == "not_configured"
    assert client.get("/api/v1/blockchain/alerts", headers=h).json()["alerts"] == []


def test_sanctions_come_from_the_live_list(client, fake_ofac):
    h = _owner_with_org(client, "sanc@test.io", "Sanc")
    hit = client.get(f"/api/v1/blockchain/wallet/{SANCTIONED}/sanctions?chain=ethereum", headers=h).json()
    assert hit["is_sanctioned"] is True and hit["source"].startswith("OFAC")
    # The Uniswap V3 factory used to be hardcoded as "Garantex". It is not sanctioned.
    miss = client.get(f"/api/v1/blockchain/wallet/{UNISWAP_V3_FACTORY}/sanctions?chain=ethereum", headers=h).json()
    assert miss["is_sanctioned"] is False
    # EVM lists apply on every EVM chain.
    assert client.get(f"/api/v1/blockchain/wallet/{SANCTIONED}/sanctions?chain=polygon",
                      headers=h).json()["is_sanctioned"] is True


def test_sanctions_list_down_means_unknown_not_clean(client, monkeypatch):
    sanctions._reset_cache_for_tests()

    async def down(family):
        raise RuntimeError("network down")

    monkeypatch.setattr(sanctions, "_download", down)
    h = _owner_with_org(client, "sancdown@test.io", "Sanc Down")
    r = client.get(f"/api/v1/blockchain/wallet/{SANCTIONED}/sanctions", headers=h).json()
    assert r["is_sanctioned"] is None and r["status"] == "unavailable"
    sanctions._reset_cache_for_tests()


def test_no_simulated_code_paths_remain():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / "blockchain"
    offenders = [str(p) for p in root.rglob("*.py") if "_simulated_" in p.read_text()]
    assert offenders == []


def test_anomaly_without_model_is_null_not_zero():
    from app.services.blockchain.ml.anomaly import AnomalyScorer
    assert AnomalyScorer().score({"tx_count": 3})["anomaly_score"] is None
