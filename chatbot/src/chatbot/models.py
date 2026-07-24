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
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    # True when the model refused / was safety-filtered and `reply` is the
    # canned fallback message rather than a grounded answer.
    blocked: bool = False
