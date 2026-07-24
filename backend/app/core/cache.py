"""Lightweight caching layer.

Provides a small, dependency-free async cache decorator used to memoize
expensive reads (dashboard stats, asset graph, timeline). Two backends:

- ``MemoryCache``: per-process async TTL cache (default; always available).
- ``RedisCache``: optional distributed cache when ``settings.REDIS_URL`` is set.

If Redis is unavailable the decorator transparently falls back to the in-memory
cache, and if caching is disabled entirely the wrapped function runs untouched.
This keeps hot paths fast without coupling the app to a running Redis.
"""
import asyncio
import functools
import json
import logging
import time
from typing import Callable, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class _BaseCache:
    async def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    async def set(self, key: str, value: str, ttl: int) -> None:
        raise NotImplementedError


class MemoryCache(_BaseCache):
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        async with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)


class RedisCache(_BaseCache):
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client = None
        self._unavailable = False

    def _get_client(self):
        if self._unavailable:
            return None
        if self._client is None:
            try:
                import redis.asyncio as aioredis

                self._client = aioredis.from_url(self._redis_url, socket_connect_timeout=1)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis cache unavailable, falling back to memory: %s", exc)
                self._unavailable = True
                return None
        return self._client

    async def get(self, key: str) -> Optional[str]:
        client = self._get_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis get failed, ignoring cache: %s", exc)
            return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            await client.set(key, value, ex=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis set failed, ignoring cache: %s", exc)


_cache_backend: Optional[_BaseCache] = None


def get_cache_backend() -> Optional[_BaseCache]:
    global _cache_backend
    if _cache_backend is not None:
        return _cache_backend
    redis_url = getattr(settings, "REDIS_URL", None)
    if redis_url:
        _cache_backend = RedisCache(redis_url)
    else:
        _cache_backend = MemoryCache()
    return _cache_backend


def _default_key_builder(fn: Callable, args: tuple, kwargs: dict, prefix: str) -> str:
    parts = [prefix, fn.__module__, fn.__qualname__]
    try:
        serialized = json.dumps([args, kwargs], default=str, sort_keys=True)
    except (TypeError, ValueError):
        serialized = str((args, kwargs))
    # Hash to keep keys bounded in length.
    import hashlib

    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
    parts.append(digest)
    return ":".join(parts)


def cached(ttl: int = 60, prefix: str = "cache", key_builder: Optional[Callable] = None):
    """Async cache decorator for read endpoints / services.

    The wrapped coroutine's return value must be JSON-serializable. On cache
    miss the function runs; on hit the cached JSON is parsed and returned. If
    the cache backend errors, the function still executes (fail-open).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not getattr(settings, "CACHE_ENABLED", True):
                return await fn(*args, **kwargs)

            backend = get_cache_backend()
            if backend is None:
                return await fn(*args, **kwargs)

            key = (key_builder or _default_key_builder)(fn, args, kwargs, prefix)
            try:
                cached_value = await backend.get(key)
                if cached_value is not None:
                    return json.loads(cached_value)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cache read failed for %s: %s", key, exc)

            result = await fn(*args, **kwargs)
            try:
                await backend.set(key, json.dumps(result, default=str), ttl)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cache write failed for %s: %s", key, exc)
            return result

        return wrapper

    return decorator
