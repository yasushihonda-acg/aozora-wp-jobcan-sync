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

from google import genai
from google.genai import types

from .config import AppConfig
from .models import ChatMessage

_logger = logging.getLogger(__name__)

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
) -> tuple[str, bool]:
    """Call Vertex AI Gemini and return (reply_text, blocked).

    `blocked=True` means the model refused / was safety-filtered / returned
    nothing usable, and `reply_text` is `REFUSAL_MESSAGE` rather than a
    grounded answer. Two-layer scope guard: (a) the system prompt tells the
    model to decline out-of-scope questions itself, (b) this function catches
    the case where the model still returns an empty/blocked response.

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
        return REFUSAL_MESSAGE, True

    finish_reason = getattr(response.candidates[0], "finish_reason", None)
    text = response.text
    # `FinishReason` mixes `str` + `Enum` but does NOT override `__str__`, so
    # `str(finish_reason)` yields `'FinishReason.SAFETY'`, not `'SAFETY'` —
    # confirmed by direct execution against the installed SDK. Compare
    # against the enum member itself instead.
    if finish_reason == types.FinishReason.SAFETY:
        _logger.info("gemini response safety-blocked", extra={"model": cfg.model_id})
        return REFUSAL_MESSAGE, True
    if not text:
        _logger.info("gemini returned empty text", extra={"model": cfg.model_id})
        return REFUSAL_MESSAGE, True

    return text, False
