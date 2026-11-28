"""Per-host politeness for active checks.

Exposure checks send a few dozen HTTP requests to each in-scope web
service. This limiter keeps that gentle: a small number of requests in
flight per host, a minimum gap between requests to the same host, and a hard
request budget per host for the whole scan. Once a host's budget is spent,
further checks against it are skipped rather than queued.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict


class BudgetExhausted(Exception):
    """The host has used its request budget for this scan."""


class HostRateLimiter:
    def __init__(self, concurrency: int = 3, rps: float = 5.0, budget: int = 120):
        self.concurrency = max(1, int(concurrency))
        self.interval = 1.0 / rps if rps and rps > 0 else 0.0
        self.budget = max(1, int(budget))
        self._sems: Dict[str, asyncio.Semaphore] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._next_at: Dict[str, float] = {}
        self._used: Dict[str, int] = {}

    def used(self, host: str) -> int:
        return self._used.get(host, 0)

    def remaining(self, host: str) -> int:
        return self.budget - self.used(host)

    @asynccontextmanager
    async def slot(self, host: str) -> AsyncIterator[None]:
        host = host.lower()
        if self._used.get(host, 0) >= self.budget:
            raise BudgetExhausted(host)
        self._used[host] = self._used.get(host, 0) + 1
        sem = self._sems.setdefault(host, asyncio.Semaphore(self.concurrency))
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with sem:
            if self.interval:
                async with lock:
                    now = time.monotonic()
                    wait = self._next_at.get(host, 0.0) - now
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._next_at[host] = max(now, self._next_at.get(host, 0.0)) + self.interval
            yield
