"""TTL cache abstraction for the FastAPI proxy.

Phase 2A.2 deliberately ships only an in-memory implementation — Cloud Run
min-instance=0 means warm instances handle bursts but cold starts miss the
cache. Phase 2B may swap in Memorystore (Redis) by providing another
`Cache` implementation; route code uses the Protocol so the swap is
transparent.

Cache key namespacing prevents detail/list ID collisions: a job_id "1777023"
and a category_id "1777023" produce different keys via the `detail:` /
`list:` prefix. Negative cache entries (404 / 429 / 5xx) live in a separate
short-TTL cache so transient upstream failures don't shadow a healthy entry
for the full positive TTL.

Codex review feedback (Phase 2A.2):
- Distinct TTLs per resource type (detail 10-15 min, list 5 min) — Jobcan
  detail pages change less frequently than category aggregations
- Negative cache for 4xx/5xx — return the cached failure for a short window
  to avoid hammering Jobcan during an outage
- maxsize bound (LRU eviction) — unbounded TTLCache leaks memory under
  pathological key churn (e.g. ID enumeration attack)
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from cachetools import TTLCache


@dataclass(frozen=True)
class CacheConfig:
    """TTL and capacity settings for the proxy cache.

    Defaults reflect Codex Q7 guidance: detail pages cache longer than
    list pages because they change less often, negative entries are
    short-lived to recover quickly when Jobcan returns to health.

    `timer` defaults to `time.monotonic` for production (immune to
    system clock jumps). Tests inject `time.time` so freezegun can step
    over TTL boundaries — freezegun freezes the wall clock but not the
    monotonic clock by design.
    """

    detail_ttl: float = 600.0  # 10 minutes
    list_ttl: float = 300.0  # 5 minutes
    negative_ttl: float = 60.0  # 1 minute for cached failures
    maxsize: int = 1000
    timer: Callable[[], float] = field(default=time.monotonic)


class Cache(Protocol):
    """Cache surface used by the route layer.

    Implementations are responsible for namespacing keys themselves —
    callers pass the raw resource id, not a fully-qualified key.
    """

    def get_detail(self, job_id: str) -> str | None: ...
    def set_detail(self, job_id: str, html: str) -> None: ...
    def get_list(self, category_id: str) -> str | None: ...
    def set_list(self, category_id: str, html: str) -> None: ...
    def get_negative(self, kind: str, key: str) -> int | None: ...
    def set_negative(self, kind: str, key: str, status_code: int) -> None: ...
    def clear(self) -> None: ...


class InMemoryCache:
    """Thread-safe wrapper around three TTLCache instances.

    cachetools.TTLCache is NOT thread-safe on its own. Under Cloud Run
    concurrency > 1 (default 80), simultaneous get/set on the same key
    can corrupt the underlying ordered dict. A single lock around all
    three caches is simpler than per-cache locks and is not a hot path
    bottleneck for this workload (latency is dominated by Jobcan fetch).
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        self.config = config or CacheConfig()
        self._detail: TTLCache[str, str] = TTLCache(
            maxsize=self.config.maxsize,
            ttl=self.config.detail_ttl,
            timer=self.config.timer,
        )
        self._list: TTLCache[str, str] = TTLCache(
            maxsize=self.config.maxsize,
            ttl=self.config.list_ttl,
            timer=self.config.timer,
        )
        self._negative: TTLCache[str, int] = TTLCache(
            maxsize=self.config.maxsize,
            ttl=self.config.negative_ttl,
            timer=self.config.timer,
        )
        self._lock = threading.Lock()

    def get_detail(self, job_id: str) -> str | None:
        with self._lock:
            return self._detail.get(job_id)

    def set_detail(self, job_id: str, html: str) -> None:
        with self._lock:
            self._detail[job_id] = html

    def get_list(self, category_id: str) -> str | None:
        with self._lock:
            return self._list.get(category_id)

    def set_list(self, category_id: str, html: str) -> None:
        with self._lock:
            self._list[category_id] = html

    def get_negative(self, kind: str, key: str) -> int | None:
        with self._lock:
            return self._negative.get(f"{kind}:{key}")

    def set_negative(self, kind: str, key: str, status_code: int) -> None:
        with self._lock:
            self._negative[f"{kind}:{key}"] = status_code

    def clear(self) -> None:
        with self._lock:
            self._detail.clear()
            self._list.clear()
            self._negative.clear()
