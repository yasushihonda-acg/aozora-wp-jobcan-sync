"""Tests for the periodic (post-startup) knowledge refresh
(`app._periodic_refresh`, Stage: AIチャットPhase B連携, 2026-08-09).

A Cloud Run instance can stay warm far longer than one 6-hourly `sync`
cycle — without this, a long-lived instance would keep answering with
whatever it fetched at cold start forever. These tests use a very short
`knowledge_refresh_interval_seconds` (real `asyncio.sleep`, not mocked —
`TestClient`'s lifespan runs on its own event loop in a background thread,
so real wall-clock waiting in the test thread is the only way to observe
it) rather than time-travel the clock, mirroring the integration style
`test_startup_refresh.py` already uses for the startup fetch.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi.testclient import TestClient

from chatbot.app import create_app
from chatbot.config import AppConfig
from chatbot.gemini import GeneratedReply

# Long enough that CI jitter can't make a single real `asyncio.sleep(0.05)`
# tick land *after* the test thread's `time.sleep(0.3)` wakes up.
_SHORT_INTERVAL = 0.05
_WAIT = 0.3


def _config(**overrides: Any) -> AppConfig:
    base: dict[str, Any] = dict(
        gcp_project="test-project",
        vertex_location="global",
        model_id="gemini-3.5-flash-lite",
        allowed_origins=("https://yasushihonda-acg.github.io",),
        max_input_chars=500,
        max_history_turns=6,
        max_output_tokens=512,
        rate_limit_window_seconds=60,
        rate_limit_max_requests=20,
        jobs_detail_url="https://example.invalid/jobs_detail.json",
        knowledge_fetch_timeout_seconds=3.0,
        knowledge_refresh_interval_seconds=_SHORT_INTERVAL,
    )
    base.update(overrides)
    return AppConfig(**base)


class _FakeGenerate:
    async def __call__(self, *, history: Any, message: str) -> GeneratedReply:
        return GeneratedReply(reply="テスト回答です。")


def _recording_transport(handler: Any) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    async def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return await handler(request)

    return httpx.MockTransport(_handle), seen


_FETCHED_JOB = {
    "id": "555000",
    "title": "フェッチ求人",
    "url": "should-be-ignored",
    "category": "care",
    "employment": ["正社員"],
    "facility": "フェッチ施設",
    "city": "福岡市",
    "area": "fukuoka",
    "service_types": [],
}


async def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[_FETCHED_JOB])


def test_periodic_refresh_fetches_again_after_interval() -> None:
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)

    with TestClient(app) as client:
        assert len(seen) == 1  # the startup fetch
        time.sleep(_WAIT)
        health = client.get("/health").json()

    assert len(seen) >= 2  # at least one periodic refresh happened
    assert health["knowledge"]["source"] == "fetched"


def test_periodic_refresh_disabled_when_interval_is_zero() -> None:
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(
        config=_config(knowledge_refresh_interval_seconds=0),
        generate_fn=_FakeGenerate(),
        http_transport=transport,
    )

    with TestClient(app):
        assert len(seen) == 1  # the startup fetch still runs
        time.sleep(_WAIT)

    assert len(seen) == 1  # no periodic refresh fired


def test_periodic_refresh_task_is_cancelled_on_shutdown() -> None:
    """Regression guard: an uncancelled background task would keep firing
    after the app has shut down (e.g. between test runs sharing a process).
    "no fetch happens after context-exit" is the observable proxy for "the
    task was actually cancelled, not merely orphaned.\""""
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)

    with TestClient(app):
        pass
    count_at_shutdown = len(seen)
    time.sleep(_WAIT)

    assert len(seen) == count_at_shutdown
