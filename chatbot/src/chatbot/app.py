"""FastAPI app for the recruitment FAQ chatbot.

# Routing surface

    GET  /health   → 200 OK, no Vertex AI touch
    POST /chat     → FAQ-grounded Gemini reply

`/healthz` is intentionally NOT used: `infra/README.md §7.1` records that
Cloud Run/GFE intercepts that exact path and returns a bare 404 before the
app ever sees the request (observed on the `sync` service). `/health`
sidesteps the known issue.

# DI

`create_app(*, config=None, generate_fn=None, rate_limiter=None)` lets tests
swap in a fake Gemini call so the suite never touches Vertex AI — mirrors the
`client_factory` DI in `sync/src/sync/app.py`.

# Lazy Vertex client

The real `genai.Client` is built lazily, on the first `/chat` call that
actually needs it — not at `create_app()`/module-import time. Two reasons:
constructing it eagerly would make `import chatbot.app` (which every test
file does) attempt Vertex AI credential resolution even when a test injects
`generate_fn` and never uses the client; and on Cloud Run this defers the
cost to the first real request instead of extending cold start further than
necessary.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from .config import AppConfig
from .gemini import build_client, generate_reply
from .knowledge import build_context
from .models import ChatMessage, ChatRequest, ChatResponse
from .prompts import build_system_instruction
from .ratelimit import RateLimiter

_logger = logging.getLogger(__name__)

GenerateFn = Callable[..., Awaitable[tuple[str, bool]]]


def _apply_security_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting.

    Cloud Run terminates TLS at the Google Front End, so `request.client.host`
    is the GFE, not the browser — `X-Forwarded-For`'s first hop is the
    signal to use instead (same precedent as the Maps API key referrer setup
    docs). Spoofable by a direct caller; this is a coarse brake, not an auth
    boundary (see ratelimit.py docstring).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _trim_history(history: list[ChatMessage], cfg: AppConfig) -> list[ChatMessage]:
    """Cap history length and per-turn length server-side.

    The client also caps what it sends, but a malicious/broken caller could
    submit arbitrary history — the server must not trust that cap (cost
    control, see plan §5.9).
    """
    trimmed = history[-cfg.max_history_turns :]
    return [
        turn
        if len(turn.content) <= cfg.max_input_chars
        else ChatMessage(role=turn.role, content=turn.content[: cfg.max_input_chars])
        for turn in trimmed
    ]


def create_app(
    *,
    config: AppConfig | None = None,
    generate_fn: GenerateFn | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    """Construct the FastAPI app.

    Dependency-injection-friendly: tests pass a fake `generate_fn` and a
    fresh `RateLimiter`; production builds everything from env vars.
    """
    app_config = config or AppConfig.from_env()
    limiter = rate_limiter or RateLimiter(
        window_seconds=app_config.rate_limit_window_seconds,
        max_requests=app_config.rate_limit_max_requests,
    )
    system_instruction = build_system_instruction(build_context())

    # Single declaration point for `_generate` (pyright reportRedeclaration
    # otherwise flags the two branches as conflicting types — an explicit
    # `GenerateFn` annotation vs. an inferred concrete coroutine function).
    _generate: GenerateFn
    if generate_fn is not None:
        _generate = generate_fn
    else:
        _client_holder: list[genai.Client] = []

        async def _real_generate(
            *, history: Sequence[ChatMessage], message: str
        ) -> tuple[str, bool]:
            if not _client_holder:
                _client_holder.append(build_client(app_config))
            return await generate_reply(
                _client_holder[0],
                app_config,
                system_instruction=system_instruction,
                history=history,
                message=message,
            )

        _generate = _real_generate

    app = FastAPI(
        title="Aozora Recruit FAQ Chatbot",
        description="Vertex AI Gemini-backed FAQ assistant for the recruitment mockup",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_config.allowed_origins),
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        return _apply_security_headers(response)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        if len(payload.message) > app_config.max_input_chars:
            raise HTTPException(
                status_code=422,
                detail=f"message must be {app_config.max_input_chars} characters or fewer",
            )

        client_ip = _client_ip(request)
        if not limiter.check(client_ip):
            raise HTTPException(
                status_code=429,
                detail="レート制限を超えました。しばらくしてから再度お試しください。",
                headers={"Retry-After": str(app_config.rate_limit_window_seconds)},
            )

        trimmed_history = _trim_history(payload.history, app_config)

        try:
            reply, blocked = await _generate(history=trimmed_history, message=payload.message)
        except Exception:
            # Vertex failure (404 model retired, timeout, quota, network) —
            # never leak the upstream exception to the client; log it here
            # so Cloud Run logs retain the detail for debugging.
            _logger.exception("chat generation failed", extra={"model": app_config.model_id})
            raise HTTPException(
                status_code=503,
                detail="現在チャットボットをご利用いただけません。しばらくしてから再度お試しください。",
            ) from None

        return ChatResponse(reply=reply, blocked=blocked)

    return app


# ASGI entrypoint for `uvicorn chatbot.app:app` / Docker CMD.
app = create_app()
