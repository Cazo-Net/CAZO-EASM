"""Unit tests for cross-cutting utilities: cache decorator and audit logging."""
import asyncio

from app.core.cache import cached, MemoryCache
from app.services.audit import log_event
from app.models.audit import AuditEvent


def test_memory_cache_set_get():
    cache = MemoryCache()
    asyncio.run(_run_cache(cache))


async def _run_cache(cache):
    assert await cache.get("missing") is None
    await cache.set("k", "v", ttl=60)
    assert await cache.get("k") == "v"


def test_cached_decorator_memoizes():
    asyncio.run(_run_decorator())


async def _run_decorator():
    calls = {"n": 0}

    @cached(ttl=30, prefix="test")
    async def expensive(x):
        calls["n"] += 1
        return {"x": x, "n": calls["n"]}

    a = await expensive(1)
    b = await expensive(1)
    # Same args -> cached, function executed once.
    assert a == b
    assert calls["n"] == 1


def test_audit_log_write(db_session):
    event = log_event(
        db_session,
        action="test.action",
        organization_id="org-x",
        actor_id="user-x",
        target_type="scan",
        target_id="scan-x",
        detail={"k": "v"},
    )
    assert event is not None
    assert event.id is not None
    fetched = db_session.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert fetched is not None
    assert fetched.action == "test.action"
    assert fetched.detail == {"k": "v"}
