"""Pydantic request/response models for POST /chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One turn of prior conversation, as echoed back by the client."""

    role: Literal["user", "model"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """POST /chat request body.

    `message`/`history[].content` carry a generous Pydantic ceiling (4000
    chars) purely as a request-size sanity guard against malformed/abusive
    payloads. The actual configurable business limit
    (`AppConfig.max_input_chars`, default 500) is enforced in the route
    handler instead of here, because it must be tunable via env without
    redeploying this schema (see chatbot/README.md).
    """

    message: str = Field(..., min_length=1, max_length=4000)
    # `max_length` on the list itself matters, not just per-item: without it,
    # Pydantic fully parses/instantiates however many ChatMessage entries a
    # caller sends (each individually valid) before `_trim_history` ever
    # discards most of them — a client could submit tens of thousands of
    # entries and pay only the per-item validation cost, not a request-size
    # cap. 50 is a generous ceiling above any realistic `max_history_turns`
    # config (default 6).
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)


class JobCard(BaseModel):
    """A single recommended job, resolved server-side from a Gemini-suggested
    id against the known job list (`knowledge.resolve_jobs`) — never built
    directly from model output, so a hallucinated id/title can't reach the
    client."""

    id: str
    title: str
    url: str
    category: str
    employment: list[str]
    facility: str
    city: str


class GeminiReply(BaseModel):
    """Structured output schema passed to Gemini as `response_schema`.

    `job_ids` are raw candidate ids as chosen by the model — still
    unvalidated at this layer. The caller (`app.py`) must resolve them
    through `knowledge.resolve_jobs` before they reach `ChatResponse.jobs`.
    """

    reply: str
    suggestions: list[str] = Field(default_factory=list, max_length=3)
    job_ids: list[str] = Field(default_factory=list, max_length=3)


class ChatResponse(BaseModel):
    reply: str
    # True when the model refused / was safety-filtered and `reply` is the
    # canned fallback message rather than a grounded answer.
    blocked: bool = False
    # Follow-up question chips the client can offer the user (e.g. "続けて
    # 聞ける質問"). Empty when the model had nothing to suggest.
    suggestions: list[str] = Field(default_factory=list)
    # Recommended jobs, already validated against the known job list.
    jobs: list[JobCard] = Field(default_factory=list)
