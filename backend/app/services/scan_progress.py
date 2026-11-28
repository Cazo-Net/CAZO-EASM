"""Scan progress updates that never block the event loop.

Scans run as asyncio tasks, by default inside the API process (the embedded
worker). The old progress callbacks committed to the database directly on the
event loop, once per call. The v1 engine calls it many times a second on big
scans, and every commit stalled every other request in that process for the
length of a database round trip.

This writer:

* commits on a worker thread (``asyncio.to_thread``),
* never runs two commits at once on the same session (a lock), and
* skips updates that would not change what the user sees: same percentage,
  or less than ``min_interval`` seconds since the last write (100% is always
  written).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


def make_progress_writer(db: Any, scan: Any, min_interval: float = 1.0) -> Callable[[int, str], Awaitable[None]]:
    lock = asyncio.Lock()
    state = {"last_pct": None, "last_at": 0.0}

    def _commit(pct: int) -> None:
        try:
            scan.progress = pct
            db.commit()
        except Exception:  # noqa: BLE001 — progress must never fail a scan
            logger.debug("progress update failed", exc_info=True)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass

    async def progress_callback(progress: int, message: str = "") -> None:
        try:
            pct = max(0, min(100, int(progress)))
        except (TypeError, ValueError):
            return
        now = time.monotonic()
        if pct == state["last_pct"]:
            return
        if pct < 100 and now - state["last_at"] < min_interval:
            return
        state["last_pct"], state["last_at"] = pct, now
        async with lock:
            await asyncio.to_thread(_commit, pct)

    return progress_callback
