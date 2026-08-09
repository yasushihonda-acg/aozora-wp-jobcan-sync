"""Tests for the request-triggered knowledge refresh
(`app._maybe_refresh_knowledge`, Stage: AIチャットPhase B連携, 2026-08-09).

An earlier version of this ran on a fixed interval from an independent
`asyncio` background task (`asyncio.sleep` in a loop). That's broken under
Cloud Run's *default* CPU allocation mode: CPU is allocated only while a
request is in flight, so a background task's timer is frozen along with
everything else whenever the instance is idle — confirmed against the
actual deployed `aozora-chatbot` revision (`gcloud run services describe`
carries no `run.googleapis.com/cpu-throttling: 'false'` annotation), and
flagged by codex review. This module replaces it with a check performed
inside `/chat` request handling, which only ever needs CPU the request
already has. Because the check is now driven by an explicit, controllable
clock read (`time.monotonic()`) rather than a real background timer, these
tests can be fully deterministic (`monkeypatch` the clock) instead of
relying on real wall-clock sleeps like the mechanism it replaced.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi.testclient import TestClient

from chatbot import app as app_module
from chatbot.app import create_app
from chatbot.config import AppConfig
from chatbot.gemini import GeneratedReply


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
        knowledge_refresh_interval_seconds=60.0,
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


def _fake_clock(monkeypatch: Any, start: float = 1_000_000.0) -> dict[str, float]:
    clock = {"now": start}
    monkeypatch.setattr(app_module.time, "monotonic", lambda: clock["now"])
    return clock


def test_chat_triggers_refresh_on_first_call_with_no_prior_lifespan(monkeypatch: Any) -> None:
    """A bare (non-lifespan) `TestClient` never runs the startup fetch, so
    `_last_refresh_attempt_at` stays at its `0.0` default — the very first
    `/chat` call must still trigger a refresh rather than staying stuck at
    FAQ-only forever."""
    _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)
    client = TestClient(app)  # deliberately bare — exercises the /chat trigger alone

    client.post("/chat", json={"message": "こんにちは"})

    assert len(seen) == 1


def test_chat_does_not_refresh_again_before_interval_elapses(monkeypatch: Any) -> None:
    clock = _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)
    client = TestClient(app)

    client.post("/chat", json={"message": "1回目"})
    clock["now"] += 30  # well within the 60s interval
    client.post("/chat", json={"message": "2回目"})

    assert len(seen) == 1


def test_chat_refreshes_again_after_interval_elapses(monkeypatch: Any) -> None:
    clock = _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)
    client = TestClient(app)

    client.post("/chat", json={"message": "1回目"})
    clock["now"] += 61  # just past the 60s interval
    client.post("/chat", json={"message": "2回目"})

    assert len(seen) == 2


def test_chat_keeps_previous_fetched_knowledge_when_later_refresh_fails(
    monkeypatch: Any,
) -> None:
    """The exact staleness-vs-availability property this whole migration
    exists for: a successful fetch followed by a LATER failed one must
    keep serving the last known-good (non-bundled) data, not revert to the
    FAQ-only bundled state (pr-test-analyzer finding, 2026-08-09 — the
    existing failure-matrix tests only proved "failure keeps bundled data"
    from a cold, never-fetched baseline, never "failure preserves a
    previously *fetched* state")."""
    clock = _fake_clock(monkeypatch)
    call_count = {"n": 0}

    async def _flaky_handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(200, json=[_FETCHED_JOB])
        raise httpx.ConnectError("connection refused", request=request)

    transport, seen = _recording_transport(_flaky_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)
    client = TestClient(app)

    client.post("/chat", json={"message": "1回目"})  # succeeds, installs 1 job
    clock["now"] += 61
    client.post("/chat", json={"message": "2回目"})  # fails, must keep the 1 job

    health = client.get("/health").json()

    assert len(seen) == 2  # both attempts happened
    assert health["knowledge"]["source"] == "fetched"
    assert health["knowledge"]["job_count"] == 1
    assert health["knowledge"]["seconds_since_last_success"] is not None


def test_chat_refresh_disabled_when_interval_is_zero(monkeypatch: Any) -> None:
    _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(
        config=_config(knowledge_refresh_interval_seconds=0),
        generate_fn=_FakeGenerate(),
        http_transport=transport,
    )
    client = TestClient(app)

    client.post("/chat", json={"message": "こんにちは"})

    assert seen == []


def test_health_endpoint_does_not_trigger_refresh(monkeypatch: Any) -> None:
    """`/health` must stay a cheap liveness check — only `/chat` (the
    surface that actually needs freshness) pays the refresh-check cost."""
    _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)
    client = TestClient(app)

    client.get("/health")

    assert seen == []


async def test_chat_resolves_jobs_against_the_snapshot_used_for_generation(
    monkeypatch: Any,
) -> None:
    """Regression (codex review finding, 2026-08-09): a refresh completing
    while a `/chat` request is still awaiting Gemini must not silently drop
    an id the model legitimately saw and recommended from the knowledge it
    was actually shown. Uses a real concurrent second request (via
    `httpx.AsyncClient` over `ASGITransport`, not `TestClient`, so both
    requests genuinely interleave on the same event loop) whose own
    refresh-check installs different knowledge while the first request is
    suspended mid-generation."""
    clock = _fake_clock(monkeypatch)

    first_job = {**_FETCHED_JOB, "id": "111"}
    second_job = {**_FETCHED_JOB, "id": "222"}  # does NOT include "111"
    fetch_count = {"n": 0}

    async def _handler(request: httpx.Request) -> httpx.Response:
        fetch_count["n"] += 1
        return httpx.Response(200, json=[first_job] if fetch_count["n"] == 1 else [second_job])

    transport, _seen = _recording_transport(_handler)

    refresh_started = asyncio.Event()
    refresh_may_continue = asyncio.Event()

    class _StatefulGenerate:
        """Call 1 (priming) and call 3 (the concurrent refresh-triggering
        request) return immediately; call 2 (the request under test)
        pauses so a real second request can interleave before it resolves
        its recommendation."""

        def __init__(self) -> None:
            self.call_count = 0

        async def __call__(self, *, history: Any, message: str) -> GeneratedReply:
            self.call_count += 1
            if self.call_count == 2:
                refresh_started.set()
                await refresh_may_continue.wait()
                return GeneratedReply(reply="ご案内します。", job_ids=["111"])
            return GeneratedReply(reply="通常の案内")

    app = create_app(
        config=_config(), generate_fn=_StatefulGenerate(), http_transport=transport
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Priming call: installs first_job (id=111), interval not yet due
        # for the next call since the clock hasn't moved.
        await client.post("/chat", json={"message": "1回目"})

        async def _request_under_test() -> httpx.Response:
            return await client.post("/chat", json={"message": "求人ありますか"})

        task_a = asyncio.create_task(_request_under_test())
        await refresh_started.wait()

        # A concurrent request arrives after the interval has elapsed —
        # its own refresh check installs second_job (id=222) while task_a
        # is still suspended above.
        clock["now"] += 61
        await client.post("/chat", json={"message": "別のリクエスト"})

        refresh_may_continue.set()
        response_a = await task_a

    assert fetch_count["n"] == 2  # priming fetch + the concurrent request's fetch
    assert response_a.json()["jobs"][0]["id"] == "111"


def test_install_failure_is_caught_and_previous_knowledge_kept(monkeypatch: Any) -> None:
    """Regression (silent-failure-hunter finding, 2026-08-09): `_install`
    used to sit OUTSIDE `_refresh_knowledge`'s try/except — if it ever
    raised, the exception would escape uncaught (a crash loop at startup,
    or an ungraceful 500 from `/chat`). `create_app()` itself calls
    `build_system_instruction` once already (for the initial FAQ-only
    prompt) before this monkeypatch is applied, so patching unconditionally
    only affects the LATER refresh-triggered call inside `_install` — and
    asserts the app keeps serving the previous (bundled, FAQ-only)
    knowledge rather than crashing or leaving `/health` in an inconsistent
    state."""
    _fake_clock(monkeypatch)
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)

    def _flaky_build(context: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "build_system_instruction", _flaky_build)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "こんにちは"})
    health = client.get("/health").json()

    assert len(seen) == 1  # the fetch itself succeeded — only _install failed
    assert response.status_code == 200  # no ungraceful 500 reached the client
    assert health["knowledge"]["source"] == "bundled"
    assert health["knowledge"]["job_count"] == 0
    assert health["knowledge"]["seconds_since_last_success"] is None
