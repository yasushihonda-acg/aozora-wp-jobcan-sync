"""Vertex AI Gemini call: client construction + async generate + safety guards.

SDK note: `genai.Client(vertexai=True, project=..., location=...)` is the
documented initializer for Vertex AI-backed generative models (confirmed via
context7 `/googleapis/python-genai` README, 2026-07-24). A separate
`enterprise=True` variant surfaced in some docs targets the distinct "Gemini
Enterprise Agent Platform" chat-SaaS product line, not plain
`generateContent` calls — do not conflate the two (see
`~/.claude/memory/reference_vertex_ai_to_gemini_enterprise_2026.md`).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from .config import AppConfig
from .models import ChatMessage, GeminiReply

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedReply:
    """Result of one `generate_reply` call.

    `job_ids` are still raw, unvalidated candidate ids from the model — the
    caller (`app.py`) must resolve them through `knowledge.resolve_jobs`
    before they reach a client. Keeping that resolution out of this module
    means `gemini.py` has no dependency on `knowledge.py`.
    """

    reply: str
    suggestions: list[str] = field(default_factory=list)
    job_ids: list[str] = field(default_factory=list)
    blocked: bool = False

# Kept loose (BLOCK_ONLY_HIGH) because everyday care-industry vocabulary
# (夜勤/介護/身体介助 etc.) can otherwise trip default safety thresholds and
# return an empty response for entirely benign FAQ questions.
#
# The official README examples pass plain strings (e.g. category=
# 'HARM_CATEGORY_HATE_SPEECH') and rely on pydantic to coerce them — that
# works at runtime but fails pyright's static check against the declared
# `HarmCategory` enum type, so we use the enum members directly instead.
_SAFETY_CATEGORIES = (
    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
)

REFUSAL_MESSAGE = (
    "申し訳ございません、その内容についてはこちらでお答えできません。"
    "求人詳細ページまたは応募フォームからお問い合わせください。"
)

TRUNCATED_MESSAGE = (
    "回答が長くなり途中で区切れてしまいました。恐れ入りますが、"
    "もう少し具体的に絞ってご質問いただけますでしょうか。"
)


def build_client(cfg: AppConfig) -> genai.Client:
    """Construct the Vertex AI client. ADC-based (Cloud Run SA / local user
    login) — no API key involved."""
    return genai.Client(vertexai=True, project=cfg.gcp_project, location=cfg.vertex_location)


def _to_contents(history: Sequence[ChatMessage], message: str) -> list[types.Content]:
    contents = [
        types.Content(role=turn.role, parts=[types.Part.from_text(text=turn.content)])
        for turn in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
    return contents


async def generate_reply(
    client: genai.Client,
    cfg: AppConfig,
    *,
    system_instruction: str,
    history: Sequence[ChatMessage],
    message: str,
) -> GeneratedReply:
    """Call Vertex AI Gemini and return a `GeneratedReply`.

    `blocked=True` means the model refused / was safety-filtered / returned
    nothing usable (including malformed structured output), and `reply` is
    one of the canned fallback messages rather than a grounded answer.
    Two-layer scope guard: (a) the system prompt tells the model to decline
    out-of-scope questions itself, (b) this function catches the case where
    the model still returns an empty/blocked/unparseable response.

    Raises on transport/API failure (404 model retired, timeout, quota) —
    the caller (app.py `/chat` handler) maps that to HTTP 503.
    """
    contents = _to_contents(history, message)
    response = await client.aio.models.generate_content(
        model=cfg.model_id,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=cfg.max_output_tokens,
            temperature=0.2,
            # Structured JSON output (reply/suggestions/job_ids) — confirmed
            # compatible with system_instruction/safety_settings/http_options
            # via context7 `/googleapis/python-genai` (2026-07-24). Gemini's
            # constrained decoding also enforces GeminiReply's field
            # constraints (e.g. max 3 items), reducing reliance on the
            # prompt instruction alone.
            response_mime_type="application/json",
            response_schema=GeminiReply,
            safety_settings=[
                types.SafetySetting(
                    category=category,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                )
                for category in _SAFETY_CATEGORIES
            ],
            # No http_options means an unbounded request (the SDK sets
            # max_allowed_time=inf when timeout is None) and zero retries
            # (retry_options=None means stop_after_attempt(1)) — confirmed by
            # reading google.genai._api_client. 20s keeps this under Cloud
            # Run's 30s --timeout; 3 attempts uses the SDK's built-in
            # exponential-backoff retry on 429/500/502/503/504/timeout.
            http_options=types.HttpOptions(
                timeout=20_000,
                retry_options=types.HttpRetryOptions(attempts=3),
            ),
        ),
    )

    if not response.candidates:
        _logger.info("gemini returned no candidates", extra={"model": cfg.model_id})
        return GeneratedReply(reply=REFUSAL_MESSAGE, blocked=True)

    finish_reason = getattr(response.candidates[0], "finish_reason", None)
    # `FinishReason` mixes `str` + `Enum` but does NOT override `__str__`, so
    # `str(finish_reason)` yields `'FinishReason.SAFETY'`, not `'SAFETY'` —
    # confirmed by direct execution against the installed SDK. Compare
    # against the enum member itself instead.
    if finish_reason == types.FinishReason.SAFETY:
        _logger.info("gemini response safety-blocked", extra={"model": cfg.model_id})
        return GeneratedReply(reply=REFUSAL_MESSAGE, blocked=True)
    if finish_reason == types.FinishReason.MAX_TOKENS:
        # A MAX_TOKENS finish means the JSON was cut off mid-generation and
        # `response.parsed` will be None (invalid JSON) — without this
        # explicit branch that would fall into the generic "failed to parse"
        # case below and show REFUSAL_MESSAGE instead of a truncation-specific
        # message. `max_output_tokens` (768) and the system prompt's "数百字
        # 以内" instruction make this rare in practice, but not impossible if
        # the model ignores the length hint.
        _logger.info(
            "gemini response truncated at max_output_tokens", extra={"model": cfg.model_id}
        )
        return GeneratedReply(reply=TRUNCATED_MESSAGE, blocked=True)

    parsed = response.parsed
    # The SDK sets `.parsed` to None (never raises) on invalid JSON or a
    # pydantic validation failure — e.g. the model naming more than 3
    # suggestions/job_ids despite the schema's `max_length` constraint on
    # constrained decoding not being perfectly honored. Confirmed via
    # context7 `/googleapis/python-genai` (`_from_response`, 2026-07-24).
    if not isinstance(parsed, GeminiReply):
        _logger.info(
            "gemini structured output failed to parse",
            extra={"model": cfg.model_id, "finish_reason": str(finish_reason)},
        )
        return GeneratedReply(reply=REFUSAL_MESSAGE, blocked=True)
    if not parsed.reply:
        _logger.info("gemini returned empty reply text", extra={"model": cfg.model_id})
        return GeneratedReply(reply=REFUSAL_MESSAGE, blocked=True)

    return GeneratedReply(
        reply=parsed.reply,
        suggestions=parsed.suggestions,
        job_ids=parsed.job_ids,
        blocked=False,
    )
