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
from typing import Any, Protocol

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

    Phase 2A.3 (#3 cleanup): `get(kind, key)` / `set(kind, key, value)` are
    the kind-dispatched API that the common pre-fetch helper uses. The
    explicit detail/list helpers stay for callers that already pin a
    resource type at the call site.
    """

    def get(self, kind: str, key: str) -> str | None: ...
    def set(self, kind: str, key: str, html: str) -> None: ...
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

    # Phase 2A.3 cleanup (code-review #8): the three (cache, key) pairs are
    # the only thing that distinguishes get_detail / get_list / get_negative.
    # Centralising the lock-and-delegate boilerplate here means cross-cutting
    # concerns (metrics, eviction warnings, debug logs) can be added in one
    # place instead of six. Public API stays unchanged so callers and tests
    # don't move.
    def _get(self, store: TTLCache[str, Any], key: str) -> Any:
        with self._lock:
            return store.get(key)

    def _set(self, store: TTLCache[str, Any], key: str, value: Any) -> None:
        with self._lock:
            store[key] = value

    def _store_for(self, kind: str) -> TTLCache[str, Any]:
        """Dispatch from kind to the underlying positive-cache TTLCache.

        Phase 2A.3 (#3 cleanup): lets the route helper take `kind` as a
        single parameter instead of branching on it. Unknown kinds raise
        rather than silently mis-cache — a typo would otherwise corrupt
        a different resource type's namespace.
        """
        if kind == "detail":
            return self._detail
        if kind == "list":
            return self._list
        raise ValueError(f"unknown cache kind: {kind!r}")

    def get(self, kind: str, key: str) -> str | None:
        return self._get(self._store_for(kind), key)

    def set(self, kind: str, key: str, html: str) -> None:
        self._set(self._store_for(kind), key, html)

    def get_detail(self, job_id: str) -> str | None:
        return self._get(self._detail, job_id)

    def set_detail(self, job_id: str, html: str) -> None:
        self._set(self._detail, job_id, html)

    def get_list(self, category_id: str) -> str | None:
        return self._get(self._list, category_id)

    def set_list(self, category_id: str, html: str) -> None:
        self._set(self._list, category_id, html)

    def get_negative(self, kind: str, key: str) -> int | None:
        return self._get(self._negative, f"{kind}:{key}")

    def set_negative(self, kind: str, key: str, status_code: int) -> None:
        self._set(self._negative, f"{kind}:{key}", status_code)

    def clear(self) -> None:
        with self._lock:
            self._detail.clear()
            self._list.clear()
            self._negative.clear()
