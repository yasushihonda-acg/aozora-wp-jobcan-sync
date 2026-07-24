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
from chatbot.gemini import REFUSAL_MESSAGE, TRUNCATED_MESSAGE, generate_reply
from chatbot.models import ChatMessage, GeminiReply


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


def _response_with_text(
    text: str,
    finish_reason: types.FinishReason | None = None,
    parsed: GeminiReply | None = None,
) -> Any:
    candidate = types.Candidate(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        finish_reason=finish_reason,
    )
    return types.GenerateContentResponse(candidates=[candidate], parsed=parsed)


@pytest.mark.asyncio
async def test_generate_reply_returns_grounded_text() -> None:
    parsed = GeminiReply(reply="未経験でも応募可能です。", suggestions=[], job_ids=[])
    client = _StubClient(_response_with_text("ignored raw text", parsed=parsed))

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == "未経験でも応募可能です。"
    assert result.blocked is False
    assert result.suggestions == []
    assert result.job_ids == []


@pytest.mark.asyncio
async def test_generate_reply_returns_suggestions_and_job_ids() -> None:
    parsed = GeminiReply(
        reply="日勤のみの求人もございます。",
        suggestions=["未経験でも応募できますか？", "選考期間はどれくらいですか？"],
        job_ids=["2264205"],
    )
    client = _StubClient(_response_with_text("ignored raw text", parsed=parsed))

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.suggestions == ["未経験でも応募できますか？", "選考期間はどれくらいですか？"]
    assert result.job_ids == ["2264205"]
    assert result.blocked is False


@pytest.mark.asyncio
async def test_generate_reply_requests_structured_json_output() -> None:
    """Regression test: without `response_mime_type`/`response_schema` the
    model returns free-form text and `response.parsed` is never populated by
    the SDK, so every reply would fall into the parse-failure branch."""
    parsed = GeminiReply(reply="ok", suggestions=[], job_ids=[])
    client = _StubClient(_response_with_text("ok", parsed=parsed))

    await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert client.models.last_config is not None
    assert client.models.last_config.response_mime_type == "application/json"
    assert client.models.last_config.response_schema is GeminiReply


@pytest.mark.asyncio
async def test_generate_reply_detects_safety_finish_reason() -> None:
    """Regression test: `finish_reason` is a `str`-mixin `Enum` with no
    `__str__` override, so `str(finish_reason) == "SAFETY"` (an earlier
    version of this comparison) is always False — confirmed by direct
    execution. Comparing against the enum member itself must catch this."""
    client = _StubClient(
        _response_with_text("partial filtered text", finish_reason=types.FinishReason.SAFETY)
    )

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == REFUSAL_MESSAGE
    assert result.blocked is True
    assert result.suggestions == []
    assert result.job_ids == []


@pytest.mark.asyncio
async def test_generate_reply_detects_max_tokens_truncation() -> None:
    """Regression test: a MAX_TOKENS finish means the JSON was cut off
    mid-generation (so `response.parsed` is None) — without an explicit
    check this would fall through to the generic parse-failure branch and
    show REFUSAL_MESSAGE instead of a truncation-specific message."""
    client = _StubClient(
        _response_with_text(
            '{"reply": "夜勤のない働き方もご用意しております。デイサービス、訪問介護、事',
            finish_reason=types.FinishReason.MAX_TOKENS,
        )
    )

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == TRUNCATED_MESSAGE
    assert result.blocked is True


@pytest.mark.asyncio
async def test_generate_reply_handles_no_candidates() -> None:
    client = _StubClient(types.GenerateContentResponse(candidates=[]))

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == REFUSAL_MESSAGE
    assert result.blocked is True


@pytest.mark.asyncio
async def test_generate_reply_handles_empty_reply_text() -> None:
    parsed = GeminiReply(reply="", suggestions=[], job_ids=[])
    client = _StubClient(_response_with_text("", parsed=parsed))

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == REFUSAL_MESSAGE
    assert result.blocked is True


@pytest.mark.asyncio
async def test_generate_reply_handles_unparseable_structured_output() -> None:
    """`response.parsed` stays None (never raises) when the SDK can't parse
    the model's JSON against `GeminiReply` — confirmed via context7
    `/googleapis/python-genai` `_from_response` (2026-07-24)."""
    client = _StubClient(_response_with_text("not valid json", parsed=None))

    result = await generate_reply(
        _as_client(client), _config(), system_instruction="system", history=[], message="質問"
    )

    assert result.reply == REFUSAL_MESSAGE
    assert result.blocked is True


@pytest.mark.asyncio
async def test_generate_reply_sets_bounded_timeout_and_retry() -> None:
    """Regression test: without an explicit `http_options`, the installed SDK
    uses an unbounded timeout (`max_allowed_time=inf`) and zero retries
    (`stop_after_attempt(1)`) — confirmed by reading `_api_client.py`."""
    parsed = GeminiReply(reply="ok", suggestions=[], job_ids=[])
    client = _StubClient(_response_with_text("ok", parsed=parsed))

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
    parsed = GeminiReply(reply="ok", suggestions=[], job_ids=[])
    client = _StubClient(_response_with_text("ok", parsed=parsed))
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
