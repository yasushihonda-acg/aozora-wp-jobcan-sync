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

    def __init__(self, reply: str = "テストの回答です。", blocked: bool = False) -> None:
        self.reply = reply
        self.blocked = blocked
        self.raises: BaseException | None = None
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, *, history: Any, message: str) -> tuple[str, bool]:
        self.calls.append({"history": history, "message": message})
        if self.raises is not None:
            raise self.raises
        return self.reply, self.blocked


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
