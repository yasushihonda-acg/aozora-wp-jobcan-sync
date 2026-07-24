"""Tests for the FastAPI chatbot app.

These tests never touch Vertex AI — every Gemini call is intercepted at the
`create_app(generate_fn=...)` boundary, mirroring the `client_factory` DI
pattern in `sync/tests/test_app.py`.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chatbot.app import create_app
from chatbot.config import AppConfig
from chatbot.gemini import GeneratedReply
from chatbot.ratelimit import RateLimiter


def _config(**overrides: Any) -> AppConfig:
    base: dict[str, Any] = dict(
        gcp_project="test-project",
        vertex_location="global",
        model_id="gemini-3.5-flash-lite",
        allowed_origins=("https://yasushihonda-acg.github.io", "http://localhost:8989"),
        max_input_chars=500,
        max_history_turns=6,
        max_output_tokens=512,
        rate_limit_window_seconds=60,
        rate_limit_max_requests=20,
    )
    base.update(overrides)
    return AppConfig(**base)


class _FakeGenerate:
    """Records every call so tests can assert on history trimming etc."""

    def __init__(
        self,
        reply: str = "テストの回答です。",
        blocked: bool = False,
        suggestions: list[str] | None = None,
        job_ids: list[str] | None = None,
    ) -> None:
        self.reply = reply
        self.blocked = blocked
        self.suggestions = suggestions or []
        self.job_ids = job_ids or []
        self.raises: BaseException | None = None
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, *, history: Any, message: str) -> GeneratedReply:
        self.calls.append({"history": history, "message": message})
        if self.raises is not None:
            raise self.raises
        return GeneratedReply(
            reply=self.reply,
            blocked=self.blocked,
            suggestions=self.suggestions,
            job_ids=self.job_ids,
        )


def _client_with(
    generate_fn: _FakeGenerate,
    *,
    config: AppConfig | None = None,
    rate_limiter: RateLimiter | None = None,
) -> TestClient:
    app = create_app(
        config=config or _config(),
        generate_fn=generate_fn,
        rate_limiter=rate_limiter,
    )
    return TestClient(app)


# ─────────────────────────────── /health ───────────────────────────────


def test_health_returns_200() -> None:
    client = _client_with(_FakeGenerate())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_has_security_headers() -> None:
    client = _client_with(_FakeGenerate())
    response = client.get("/health")

    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


# ─────────────────────────────── POST /chat ───────────────────────────────


def test_chat_returns_reply() -> None:
    fake = _FakeGenerate(reply="未経験でもOJTと外部研修でサポートします。")
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "未経験でも応募できますか？"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "未経験でもOJTと外部研修でサポートします。"
    assert body["blocked"] is False
    assert fake.calls[0]["message"] == "未経験でも応募できますか？"


def test_chat_blocked_reply_is_passed_through() -> None:
    fake = _FakeGenerate(reply="お答えできません。", blocked=True)
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "給与を交渉できますか？"})

    assert response.status_code == 200
    assert response.json()["blocked"] is True


def test_chat_response_includes_suggestions() -> None:
    fake = _FakeGenerate(suggestions=["未経験でも応募できますか？", "選考期間は？"])
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "夜勤なしで働けますか？"})

    assert response.json()["suggestions"] == ["未経験でも応募できますか？", "選考期間は？"]


def test_chat_response_resolves_known_job_id() -> None:
    """`1777023` is a real id from `knowledge/jobs_detail.json` (博多 care job)."""
    fake = _FakeGenerate(job_ids=["1777023"])
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "博多で働ける求人はありますか？"})

    jobs = response.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] == "1777023"
    assert jobs[0]["url"] == "jobs/1777023.html"


def test_chat_response_drops_hallucinated_job_id() -> None:
    """A model-suggested id that isn't in the known job list must never
    reach the client — this is the whitelist guard in `knowledge.resolve_jobs`."""
    fake = _FakeGenerate(job_ids=["9999999"])
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "求人を教えてください"})

    assert response.json()["jobs"] == []


def test_chat_rejects_empty_message() -> None:
    client = _client_with(_FakeGenerate())

    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_chat_rejects_message_over_configured_limit() -> None:
    fake = _FakeGenerate()
    client = _client_with(fake, config=_config(max_input_chars=10))

    response = client.post("/chat", json={"message": "a" * 11})

    assert response.status_code == 422
    assert fake.calls == []


def test_chat_within_configured_limit_is_accepted() -> None:
    fake = _FakeGenerate()
    client = _client_with(fake, config=_config(max_input_chars=10))

    response = client.post("/chat", json={"message": "a" * 10})

    assert response.status_code == 200


def test_chat_trims_history_to_max_turns() -> None:
    fake = _FakeGenerate()
    client = _client_with(fake, config=_config(max_history_turns=2))

    history = [
        {"role": "user", "content": "1問目"},
        {"role": "model", "content": "1回答目"},
        {"role": "user", "content": "2問目"},
        {"role": "model", "content": "2回答目"},
    ]
    client.post("/chat", json={"message": "3問目", "history": history})

    sent_history = fake.calls[0]["history"]
    assert len(sent_history) == 2
    assert sent_history[-1].content == "2回答目"


def test_chat_trims_oversized_history_entry_server_side() -> None:
    """The client is expected to cap history, but the server must not trust
    that — a malicious/broken caller could send an oversized entry."""
    fake = _FakeGenerate()
    client = _client_with(fake, config=_config(max_input_chars=5, max_history_turns=6))

    history = [{"role": "user", "content": "x" * 50}]
    client.post("/chat", json={"message": "abcde", "history": history})

    sent_history = fake.calls[0]["history"]
    assert len(sent_history[0].content) == 5


def test_chat_max_history_turns_zero_sends_empty_history() -> None:
    """Regression test: `history[-0:]` is `history[0:]` (Python has no
    negative zero) and used to return the FULL list instead of an empty one
    when `max_history_turns=0` — a documented, supported env override."""
    fake = _FakeGenerate()
    client = _client_with(fake, config=_config(max_history_turns=0))

    history = [{"role": "user", "content": "1問目"}, {"role": "model", "content": "1回答目"}]
    client.post("/chat", json={"message": "2問目", "history": history})

    assert fake.calls[0]["history"] == []


def test_chat_rejects_history_over_50_entries() -> None:
    """Regression test: without a list-level `max_length`, Pydantic would
    fully parse an arbitrarily large history array before `_trim_history`
    ever discards most of it."""
    fake = _FakeGenerate()
    client = _client_with(fake)

    history = [{"role": "user", "content": "x"} for _ in range(51)]
    response = client.post("/chat", json={"message": "テスト", "history": history})

    assert response.status_code == 422
    assert fake.calls == []


def test_chat_vertex_failure_returns_503() -> None:
    fake = _FakeGenerate()
    fake.raises = RuntimeError("simulated Vertex AI failure")
    client = _client_with(fake)

    response = client.post("/chat", json={"message": "夜勤なしで働けますか？"})

    assert response.status_code == 503
    assert "しばらくしてから" in response.json()["detail"]


def test_chat_rate_limit_exceeded_returns_429() -> None:
    limiter = RateLimiter(window_seconds=60, max_requests=1, timer=time.time)
    fake = _FakeGenerate()
    client = _client_with(fake, rate_limiter=limiter)

    first = client.post("/chat", json={"message": "1回目"})
    second = client.post("/chat", json={"message": "2回目"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_rate_limit_key_uses_last_xff_entry_not_first() -> None:
    """Regression test: GFE appends its own observed peer IP as the LAST
    entry in X-Forwarded-For; anything before it is caller-supplied and
    spoofable. Using the first entry (as an earlier version did) lets a
    caller send a fresh fake value on every request to dodge the limiter
    entirely — each of the two calls below claims a different spoofed FIRST
    hop but the same real (last) hop, so they must share one rate-limit key."""
    limiter = RateLimiter(window_seconds=60, max_requests=1, timer=time.time)
    fake = _FakeGenerate()
    client = _client_with(fake, rate_limiter=limiter)

    first = client.post(
        "/chat",
        json={"message": "1回目"},
        headers={"x-forwarded-for": "203.0.113.1, 198.51.100.9"},
    )
    second = client.post(
        "/chat",
        json={"message": "2回目"},
        headers={"x-forwarded-for": "203.0.113.99, 198.51.100.9"},
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_chat_cors_preflight_allows_configured_origin() -> None:
    client = _client_with(
        _FakeGenerate(),
        config=_config(allowed_origins=("https://yasushihonda-acg.github.io",)),
    )

    response = client.options(
        "/chat",
        headers={
            "Origin": "https://yasushihonda-acg.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://yasushihonda-acg.github.io"
    )


def test_chat_cors_rejects_unlisted_origin() -> None:
    client = _client_with(
        _FakeGenerate(),
        config=_config(allowed_origins=("https://yasushihonda-acg.github.io",)),
    )

    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    # FastAPI's CORSMiddleware omits the ACAO header for disallowed origins
    # rather than rejecting the request outright (browser then blocks JS
    # from reading the response) — the absence of the header IS the guard.
    assert "access-control-allow-origin" not in response.headers


# ───────────────────────── env-driven AppConfig construction ─────────────────────


def test_app_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "GCP_PROJECT",
        "VERTEX_LOCATION",
        "MODEL_ID",
        "ALLOWED_ORIGINS",
        "MAX_INPUT_CHARS",
        "MAX_HISTORY_TURNS",
    ):
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.vertex_location == "global"
    assert config.model_id == "gemini-3.5-flash-lite"
    assert config.max_input_chars == 500
    assert "https://yasushihonda-acg.github.io" in config.allowed_origins


def test_app_config_from_env_parses_allowed_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example.com, https://b.example.com")

    config = AppConfig.from_env()

    assert config.allowed_origins == ("https://a.example.com", "https://b.example.com")
