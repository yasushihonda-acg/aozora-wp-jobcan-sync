"""Tests for the startup knowledge refresh (`app._refresh_knowledge`).

Every fetch call is intercepted via `create_app(http_transport=...)` with
`httpx.MockTransport` — no test here ever touches GitHub Pages. Starlette's
`TestClient` only runs lifespan startup when used as a context manager
(empirically verified — a bare `TestClient(app)` never fetches), so tests
that need the refresh to run use `with TestClient(app) as client: ...`, and
the one regression guard below deliberately does NOT.

`_refresh_knowledge` catches every exception (see its docstring — an escaped
exception during lifespan startup crashes the whole process), which means a
handler that raises `AssertionError` to signal "fetch happened" would be
silently swallowed and produce a false-positive pass. Every "fetch not
attempted" assertion here instead checks the recorded request list is empty.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

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
    )
    base.update(overrides)
    return AppConfig(**base)


class _FakeGenerate:
    def __init__(self, job_ids: list[str] | None = None) -> None:
        self.job_ids = job_ids or []

    async def __call__(self, *, history: Any, message: str) -> GeneratedReply:
        return GeneratedReply(reply="テスト回答です。", job_ids=self.job_ids)


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


async def _network_error_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


async def _timeout_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


async def _not_found_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, text="<html>not found</html>")


async def _html_body_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>oops</html>")


async def _schema_violation_handler(request: httpx.Request) -> httpx.Response:
    # Missing `area`/`service_types` — a `JobCard`-only check would admit
    # this; `_StrictJobDetail` must not (see test_knowledge.py).
    return httpx.Response(200, json=[{"id": "1", "title": "x", "url": "u", "category": "c",
                                       "employment": ["正社員"], "facility": "f", "city": "c"}])


async def _empty_payload_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


async def _non_list_payload_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"jobs": []})


def test_lifespan_fetch_replaces_jobs_end_to_end() -> None:
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(
        config=_config(),
        generate_fn=_FakeGenerate(job_ids=["555000"]),
        http_transport=transport,
    )

    with TestClient(app) as client:
        health = client.get("/health").json()
        chat = client.post("/chat", json={"message": "求人ありますか"}).json()

    assert len(seen) == 1
    assert health["knowledge"] == {"source": "fetched", "job_count": 1}
    assert [job["id"] for job in chat["jobs"]] == ["555000"]


def test_lifespan_fetch_requests_configured_url() -> None:
    transport, seen = _recording_transport(_ok_handler)
    config = _config(jobs_detail_url="https://example.invalid/custom-path.json")
    app = create_app(config=config, generate_fn=_FakeGenerate(), http_transport=transport)

    with TestClient(app):
        pass

    assert str(seen[0].url) == "https://example.invalid/custom-path.json"


def test_fetched_url_is_recomputed_from_id_not_trusted() -> None:
    """`jobs_detail.json`'s `url` field is rendered directly into `<a href>`
    by `chat-widget.js` — a fetched payload must never get to supply it."""
    transport, _ = _recording_transport(_ok_handler)
    app = create_app(
        config=_config(),
        generate_fn=_FakeGenerate(job_ids=["555000"]),
        http_transport=transport,
    )

    with TestClient(app) as client:
        chat = client.post("/chat", json={"message": "求人ありますか"}).json()

    assert chat["jobs"][0]["url"] == "jobs/555000.html"


@pytest.mark.parametrize(
    "handler",
    [
        _network_error_handler,
        _timeout_handler,
        _not_found_handler,
        _html_body_handler,
        _schema_violation_handler,
        _empty_payload_handler,
        _non_list_payload_handler,
    ],
    ids=[
        "network_error",
        "timeout",
        "http_404",
        "html_body",
        "schema_violation_missing_area",
        "empty_payload",
        "non_list_payload",
    ],
)
def test_fetch_failure_keeps_bundled_data_and_app_stays_up(
    handler: Any, caplog: pytest.LogCaptureFixture
) -> None:
    transport, seen = _recording_transport(handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)

    with caplog.at_level(logging.WARNING, logger="chatbot.app"), TestClient(app) as client:
        health = client.get("/health").json()
        chat = client.post("/chat", json={"message": "こんにちは"})

    assert len(seen) == 1  # fetch was attempted, not skipped
    assert health["knowledge"] == {"source": "bundled", "job_count": 37}
    assert chat.status_code == 200
    assert any("knowledge refresh failed" in record.message for record in caplog.records)


def test_empty_jobs_detail_url_disables_fetch() -> None:
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(
        config=_config(jobs_detail_url=""),
        generate_fn=_FakeGenerate(),
        http_transport=transport,
    )

    with TestClient(app) as client:
        health = client.get("/health").json()

    assert seen == []
    assert health["knowledge"] == {"source": "bundled", "job_count": 37}


def test_no_fetch_without_lifespan_context_manager() -> None:
    """Regression guard: a bare (non-`with`) `TestClient` never runs
    lifespan startup, so `seen` staying empty is what proves the fetch is
    still gated behind `_lifespan` rather than e.g. `create_app` itself. If
    a future refactor moved the fetch to run eagerly, this test would catch
    it by `seen` becoming non-empty."""
    transport, seen = _recording_transport(_ok_handler)
    app = create_app(config=_config(), generate_fn=_FakeGenerate(), http_transport=transport)

    client = TestClient(app)  # deliberately not a context manager
    client.get("/health")

    assert seen == []
