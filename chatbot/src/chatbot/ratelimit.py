"""Minimal per-IP rate limiting.

This is a coarse cost-runaway brake, not a real defense: the `TTLCache` is
in-memory, so limits reset on cold start and are NOT shared across Cloud Run
instances — `--max-instances` is the actual ceiling on total throughput.
`X-Forwarded-For` is also spoofable by any client that talks to the service
directly rather than through the intended frontends. Accepted tradeoff for
Phase A (see implementation plan §5.3); a shared store (Firestore/Redis)
would be the follow-up if this needs to be a real defense.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from cachetools import TTLCache


class RateLimiter:
    """Fixed-window per-key request counter backed by a TTL cache.

    Each key gets a list of hit timestamps; the whole list expires
    `window_seconds` after the *first* hit in the window (TTLCache expires
    based on insertion time, not last access) — a fresh window then starts
    on the next request. Simple fixed-window semantics, not sliding-window;
    sufficient for a coarse brake.
    """

    def __init__(
        self,
        *,
        window_seconds: int,
        max_requests: int,
        timer: Callable[[], float] = time.time,
    ) -> None:
        self._max_requests = max_requests
        self._timer = timer
        # `timer` must drive both the TTLCache's own expiration clock and the
        # timestamps we record — passing it through here (instead of letting
        # TTLCache default to its own `time.monotonic`) is what makes the
        # limiter's window behavior deterministically testable.
        self._hits: TTLCache[str, list[float]] = TTLCache(
            maxsize=10_000, ttl=window_seconds, timer=timer
        )

    def check(self, key: str) -> bool:
        """Record a hit for `key`; return True if the caller should be allowed."""
        hits = self._hits.get(key)
        if hits is None:
            hits = []
            self._hits[key] = hits
        hits.append(self._timer())
        return len(hits) <= self._max_requests
