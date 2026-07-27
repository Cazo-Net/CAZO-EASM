"""Distributed rate limiting.

Uses Redis when available (works across multiple workers/replicas) and falls
back to an in-memory store for local development.
"""

import time
import threading
import collections
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, window: int = 60):
        self.window = window
        self._redis = None
        self._local = collections.defaultdict(list)
        self._lock = threading.Lock()
        self._cleanup_counter = 0
        self._init_redis()

    def _init_redis(self):
        # Priority: Upstash Redis > local Redis > in-memory
        upstash = self._try_upstash()
        if upstash:
            self._redis = upstash
            return
        if not settings.REDIS_URL:
            return
        try:
            import redis

            client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            client.ping()
            self._redis = client
            logger.info("Rate limiter using Redis backend")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable for rate limiting (%s); using in-memory", exc)
            self._redis = None

    def _try_upstash(self):
        """Try Upstash Redis for rate limiting."""
        if not settings.UPSTASH_REDIS_URL:
            return None
        try:
            import httpx
            # Upstash REST API — lightweight ping
            r = httpx.get(
                f"{settings.UPSTASH_REDIS_URL}/ping",
                headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_TOKEN}"},
                timeout=3,
            )
            if r.status_code == 200:
                # Use the upstash-redis SDK client
                from upstash_redis import Redis
                client = Redis(url=settings.UPSTASH_REDIS_URL, token=settings.UPSTASH_REDIS_TOKEN)
                logger.info("Rate limiter using Upstash Redis backend")
                return client
        except Exception as exc:
            logger.debug("Upstash Redis unavailable for rate limiting: %s", exc)
        return None

    def reset(self) -> None:
        """Clear all rate-limit state (used by tests and admin tooling)."""
        with self._lock:
            self._local.clear()
            self._cleanup_counter = 0
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter("ratelimit:*"):
                    self._redis.delete(key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to reset Redis rate limit keys (%s)", exc)

    def is_allowed(self, key: str, max_requests: int) -> bool:
        if self._redis is not None:
            return self._allow_redis(key, max_requests)
        return self._allow_local(key, max_requests)

    def _allow_redis(self, key: str, max_requests: int) -> bool:
        redis_key = f"ratelimit:{key}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(redis_key, 1)
            pipe.expire(redis_key, self.window)
            count, _ = pipe.execute()
            return int(count) <= max_requests
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis rate limit error (%s); allowing request", exc)
            return True

    def _allow_local(self, key: str, max_requests: int) -> bool:
        now = time.time()
        with self._lock:
            self._local[key] = [t for t in self._local[key] if now - t < self.window]
            if len(self._local[key]) >= max_requests:
                return False
            self._local[key].append(now)

            self._cleanup_counter += 1
            if self._cleanup_counter % 100 == 0:
                expired = [
                    k for k, times in self._local.items()
                    if not times or all(now - t > self.window for t in times)
                ]
                for k in expired:
                    del self._local[k]
            return True


rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global rate_limiter
    if rate_limiter is None:
        rate_limiter = RateLimiter()
    return rate_limiter
