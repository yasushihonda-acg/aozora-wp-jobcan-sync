"""Tests for the Vertex AI call wrapper (`generate_reply`).

These use a stub `client.aio.models.generate_content` returning a real
`types.GenerateContentResponse` built by hand — no network access, no ADC
required — so the safety/finish-reason branching can be exercised precisely.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from google import genai
from google.genai import types

from chatbot.config import AppConfig
from chatbot.gemini import REFUSAL_MESSAGE, generate_reply
from chatbot.models import ChatMessage


def _config() -> AppConfig:
    return AppConfig(
        gcp_project="test-project",
        vertex_location="global",
        model_id="gemini-3.5-flash-lite",
        allowed_origins=("http://localhost:8989",),
        max_input_chars=500,
        max_history_turns=6,
        max_output_tokens=512,
        rate_limit_window_seconds=60,
        rate_limit_max_requests=20,
    )


class _StubModels:
    def __init__(self, response: types.GenerateContentResponse) -> None:
        self._response = response
        self.last_config: types.GenerateContentConfig | None = None
        self.last_contents: Any = None

    async def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.last_config = config
        self.last_contents = contents
        return self._response


class _StubAio:
    def __init__(self, models: _StubModels) -> None:
        self.models = models


class _StubClient:
    def __init__(self, response: types.GenerateContentResponse) -> None:
        self.models = _StubModels(response)
        self.aio = _StubAio(self.models)


def _as_client(stub: _StubClient) -> genai.Client:
    """`generate_reply` is typed against `genai.Client` (a concrete class, so
    pyright checks nominally, not structurally) — this stub only duck-types
    the `.aio.models.generate_content` surface it actually calls."""
    return cast(genai.Client, stub)


def _response_with_text(text: str, finish_reason: types.FinishReason | None = None) -> Any:
    candidate = types.Candidate(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        finish_reason=finish_reason,
    )
    return types.GenerateContentResponse(candidates=[candidate])


@pytest.mark.asyncio
async def test_generate_reply_returns_grounded_text() -> None:
    client = _StubClient(_response_with_text("未経験でも応募可能です。"))

    text, blocked = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert text == "未経験でも応募可能です。"
    assert blocked is False


@pytest.mark.asyncio
async def test_generate_reply_detects_safety_finish_reason() -> None:
    """Regression test: `finish_reason` is a `str`-mixin `Enum` with no
    `__str__` override, so `str(finish_reason) == "SAFETY"` (an earlier
    version of this comparison) is always False — confirmed by direct
    execution. Comparing against the enum member itself must catch this."""
    client = _StubClient(
        _response_with_text("partial filtered text", finish_reason=types.FinishReason.SAFETY)
    )

    text, blocked = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert text == REFUSAL_MESSAGE
    assert blocked is True


@pytest.mark.asyncio
async def test_generate_reply_handles_no_candidates() -> None:
    client = _StubClient(types.GenerateContentResponse(candidates=[]))

    text, blocked = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert text == REFUSAL_MESSAGE
    assert blocked is True


@pytest.mark.asyncio
async def test_generate_reply_handles_empty_text() -> None:
    client = _StubClient(_response_with_text(""))

    text, blocked = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert text == REFUSAL_MESSAGE
    assert blocked is True


@pytest.mark.asyncio
async def test_generate_reply_sets_bounded_timeout_and_retry() -> None:
    """Regression test: without an explicit `http_options`, the installed SDK
    uses an unbounded timeout (`max_allowed_time=inf`) and zero retries
    (`stop_after_attempt(1)`) — confirmed by reading `_api_client.py`."""
    client = _StubClient(_response_with_text("ok"))

    await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert client.models.last_config is not None
    http_options = client.models.last_config.http_options
    assert http_options is not None
    assert http_options.timeout is not None and http_options.timeout > 0
    assert http_options.retry_options is not None
    assert http_options.retry_options.attempts and http_options.retry_options.attempts > 1


@pytest.mark.asyncio
async def test_generate_reply_includes_history_in_contents() -> None:
    client = _StubClient(_response_with_text("ok"))
    history = [
        ChatMessage(role="user", content="前の質問"),
        ChatMessage(role="model", content="前の回答"),
    ]

    await generate_reply(
        _as_client(client),
        _config(),
        system_instruction="system",
        history=history,
        message="今の質問",
    )

    contents = client.models.last_contents
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text == "前の質問"
    assert contents[1].parts[0].text == "前の回答"
    assert contents[2].parts[0].text == "今の質問"
