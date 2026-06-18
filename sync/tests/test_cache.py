"""Tests for the TTL cache used by the FastAPI proxy."""

from __future__ import annotations

import time

from freezegun import freeze_time

from sync.cache import CacheConfig, InMemoryCache


def _short_ttl_cache() -> InMemoryCache:
    # Tight TTLs so freezegun can step over them in tests without the
    # numbers (10s/5s/2s) becoming noise. Production defaults live in
    # CacheConfig() and are tested separately for sanity.
    #
    # `timer=time.time` is required because freezegun freezes wall clock
    # but NOT time.monotonic (cachetools default). Production uses
    # time.monotonic for system-clock-jump immunity.
    return InMemoryCache(
        CacheConfig(
            detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time
        )
    )


def test_detail_cache_hit_returns_stored_html() -> None:
    cache = _short_ttl_cache()
    cache.set_detail("1777023", "<html>care</html>")

    assert cache.get_detail("1777023") == "<html>care</html>"


def test_detail_cache_miss_returns_none() -> None:
    cache = _short_ttl_cache()
    assert cache.get_detail("9999999") is None


def test_detail_and_list_namespaces_are_separate() -> None:
    """A job_id and a category_id that happen to share digits must not collide.

    Phase 2A.2 stores them in two cachetools.TTLCache instances, so this is
    a defence-in-depth check more than a behavioural risk — but if the
    implementation ever consolidates to a single dict, this test catches it.
    """
    cache = _short_ttl_cache()
    cache.set_detail("1777023", "<html>detail</html>")
    cache.set_list("1777023", "<html>list</html>")

    assert cache.get_detail("1777023") == "<html>detail</html>"
    assert cache.get_list("1777023") == "<html>list</html>"


@freeze_time("2026-06-18 00:00:00")
def test_detail_cache_expires_after_ttl() -> None:
    cache = _short_ttl_cache()
    cache.set_detail("1777023", "<html>care</html>")

    with freeze_time("2026-06-18 00:00:09"):
        assert cache.get_detail("1777023") == "<html>care</html>"

    with freeze_time("2026-06-18 00:00:11"):
        assert cache.get_detail("1777023") is None


@freeze_time("2026-06-18 00:00:00")
def test_list_cache_expires_independently_of_detail() -> None:
    cache = _short_ttl_cache()
    cache.set_detail("1777023", "<html>care</html>")
    cache.set_list("18773", "<html>list</html>")

    # 6s in: list (5s TTL) is gone, detail (10s TTL) is still there.
    with freeze_time("2026-06-18 00:00:06"):
        assert cache.get_detail("1777023") == "<html>care</html>"
        assert cache.get_list("18773") is None


def test_negative_cache_stores_status_code() -> None:
    cache = _short_ttl_cache()
    cache.set_negative("detail", "1777023", 404)
    cache.set_negative("list", "18773", 503)

    assert cache.get_negative("detail", "1777023") == 404
    assert cache.get_negative("list", "18773") == 503


def test_negative_cache_namespaces_kind() -> None:
    """detail / list negative caches must not collide on the same key."""
    cache = _short_ttl_cache()
    cache.set_negative("detail", "1", 404)
    cache.set_negative("list", "1", 503)

    assert cache.get_negative("detail", "1") == 404
    assert cache.get_negative("list", "1") == 503


@freeze_time("2026-06-18 00:00:00")
def test_negative_cache_expires_quickly() -> None:
    """Negative cache TTL is short (default 60s prod, 2s in this test) so
    Jobcan recovery is visible to the proxy within seconds, not minutes."""
    cache = _short_ttl_cache()
    cache.set_negative("detail", "1777023", 503)

    with freeze_time("2026-06-18 00:00:01"):
        assert cache.get_negative("detail", "1777023") == 503

    with freeze_time("2026-06-18 00:00:03"):
        assert cache.get_negative("detail", "1777023") is None


def test_clear_drops_all_three_caches() -> None:
    cache = _short_ttl_cache()
    cache.set_detail("a", "x")
    cache.set_list("b", "y")
    cache.set_negative("detail", "c", 500)

    cache.clear()

    assert cache.get_detail("a") is None
    assert cache.get_list("b") is None
    assert cache.get_negative("detail", "c") is None


def test_maxsize_eviction_under_lru() -> None:
    """cachetools.TTLCache evicts the LRU entry when maxsize is exceeded.

    Phase 2A.2 maxsize=1000 is far beyond realistic concurrency, but ID
    enumeration attacks could spike unique keys. This test pins the safety
    behaviour so a future implementation swap (e.g. Memorystore) keeps it.
    """
    cache = InMemoryCache(
        CacheConfig(detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=2)
    )
    cache.set_detail("a", "1")
    cache.set_detail("b", "2")
    cache.set_detail("c", "3")  # evicts 'a'

    assert cache.get_detail("a") is None
    assert cache.get_detail("b") == "2"
    assert cache.get_detail("c") == "3"


def test_default_config_uses_production_ttls() -> None:
    """Sanity check the production defaults are what Phase 2A.2 doc claims:
    detail 10 min, list 5 min, negative 60 s."""
    config = CacheConfig()
    assert config.detail_ttl == 600.0
    assert config.list_ttl == 300.0
    assert config.negative_ttl == 60.0
    assert config.maxsize == 1000
