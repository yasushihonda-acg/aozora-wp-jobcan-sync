"""Tests for the per-IP rate limiter (fixed-window, in-memory TTLCache)."""

from __future__ import annotations

from chatbot.ratelimit import RateLimiter


class _ManualClock:
    """A callable clock whose value tests advance explicitly.

    Deterministic regardless of how many times `RateLimiter`/`TTLCache`
    happen to call the timer internally per operation — unlike an
    iterator-based fake, it can't raise StopIteration from an unexpected
    extra call.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_allows_requests_within_limit() -> None:
    clock = _ManualClock()
    limiter = RateLimiter(window_seconds=60, max_requests=3, timer=clock)

    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True


def test_blocks_requests_over_limit_within_window() -> None:
    clock = _ManualClock()
    limiter = RateLimiter(window_seconds=60, max_requests=2, timer=clock)

    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False


def test_different_keys_are_tracked_independently() -> None:
    clock = _ManualClock()
    limiter = RateLimiter(window_seconds=60, max_requests=1, timer=clock)

    assert limiter.check("1.1.1.1") is True
    assert limiter.check("2.2.2.2") is True


def test_window_expiry_resets_the_counter() -> None:
    """TTLCache expires the whole per-key entry `window_seconds` after the
    first hit — advancing the manual clock past the window lets the next
    request start a fresh window."""
    clock = _ManualClock()
    limiter = RateLimiter(window_seconds=10, max_requests=1, timer=clock)

    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False

    clock.now = 20
    assert limiter.check("1.2.3.4") is True


def test_hit_list_growth_stops_once_over_limit() -> None:
    """Regression test: an abusive key hammering the limiter after already
    being rejected must not grow its per-key hit list without bound for the
    rest of the window — only `max_requests + 1` entries are ever needed to
    know the caller is over the limit."""
    clock = _ManualClock()
    limiter = RateLimiter(window_seconds=60, max_requests=2, timer=clock)

    for _ in range(100):
        limiter.check("1.2.3.4")

    assert len(limiter._hits["1.2.3.4"]) == 3  # max_requests + 1, not 100
