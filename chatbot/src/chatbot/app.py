"""FastAPI app for the recruitment FAQ chatbot.

# Routing surface

    GET  /health   → 200 OK, no Vertex AI touch
    POST /chat     → FAQ-grounded Gemini reply

`/healthz` is intentionally NOT used: `infra/README.md §7.1` records that
Cloud Run/GFE intercepts that exact path and returns a bare 404 before the
app ever sees the request (observed on the `sync` service). `/health`
sidesteps the known issue.

# DI

`create_app(*, config=None, generate_fn=None, rate_limiter=None,
http_transport=None)` lets tests swap in a fake Gemini call so the suite
never touches Vertex AI — mirrors the `client_factory` DI in
`sync/src/sync/app.py`. `http_transport` does the same for the startup
knowledge refresh (`httpx.MockTransport` instead of GitHub Pages).

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
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from . import knowledge
from .config import AppConfig
from .gemini import GeneratedReply, build_client, generate_reply
from .models import ChatMessage, ChatRequest, ChatResponse
from .prompts import build_system_instruction
from .ratelimit import RateLimiter

_logger = logging.getLogger(__name__)

GenerateFn = Callable[..., Awaitable[GeneratedReply]]


def _apply_security_headers(response: Response) -> Response:
    """Mirrors `sync/src/sync/app.py`'s `_apply_security_headers` — keep the
    two in sync if the header policy ever changes (e.g. adding CSP, or
    dropping X-Robots-Tag once the recruitment site is meant to be indexed).
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting.

    Cloud Run terminates TLS at the Google Front End, so `request.client.host`
    is the GFE, not the browser. `X-Forwarded-For` is a chain where each hop
    appends the IP of whoever it received the connection from — anything a
    direct caller supplies ends up at the FRONT of the list, and GFE appends
    its own observed peer at the END. Using the first entry (as an earlier
    version of this function did) is fully attacker-controlled and lets a
    caller defeat the rate limiter by sending a fresh value on every request;
    the last entry is what GFE itself appended. Still spoofable if this
    service is ever placed behind another proxy that doesn't strip
    client-supplied headers — this is a coarse brake, not an auth boundary
    (see ratelimit.py docstring).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _trim_history(history: list[ChatMessage], cfg: AppConfig) -> list[ChatMessage]:
    """Cap history length and per-turn length server-side.

    The client also caps what it sends, but a malicious/broken caller could
    submit arbitrary history — the server must not trust that cap (cost
    control, see plan §5.9).
    """
    # `history[-0:]` is `history[0:]` (Python has no negative zero), which
    # returns the WHOLE list instead of an empty one — `max_history_turns=0`
    # is a documented, supported env override, so this can't be assumed away.
    trimmed = history[-cfg.max_history_turns :] if cfg.max_history_turns > 0 else []
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
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Construct the FastAPI app.

    Dependency-injection-friendly: tests pass a fake `generate_fn` and a
    fresh `RateLimiter`; production builds everything from env vars.
    `http_transport` lets tests replace the knowledge-refresh HTTP client
    with `httpx.MockTransport` instead of touching GitHub Pages
    (`knowledge.fetch_knowledge`'s `transport` parameter).

    No network I/O happens here: `create_app()` runs at every test module's
    import time (this module's own `app = create_app()` below), so the
    knowledge refresh is deferred to `_lifespan` startup instead — which
    Starlette's `TestClient` only runs when used as a context manager (see
    `tests/test_startup_refresh.py`), so the existing test suite stays
    offline.
    """
    app_config = config or AppConfig.from_env()
    limiter = rate_limiter or RateLimiter(
        window_seconds=app_config.rate_limit_window_seconds,
        max_requests=app_config.rate_limit_max_requests,
    )
    knowledge_base = knowledge.bundled_knowledge()
    system_instruction = build_system_instruction(knowledge_base.context)

    def _install(new_base: knowledge.KnowledgeBase) -> None:
        """The only writer of the two names above.

        Updating both in one place guarantees the system prompt and the job
        whitelist always describe the same job set — never a context
        listing an id the whitelist doesn't know, or vice versa. Safe to
        write as two separate statements because this only runs during
        lifespan startup, before uvicorn binds its listen socket: no
        request can ever observe the moment between the two assignments.
        """
        nonlocal knowledge_base, system_instruction
        knowledge_base = new_base
        system_instruction = build_system_instruction(new_base.context)

    async def _refresh_knowledge() -> None:
        """Startup-only knowledge refresh from GitHub Pages.

        Every failure path keeps the image-bundled data and lets the app
        start — this is not politeness, it's required: uvicorn calls
        `sys.exit(STARTUP_FAILURE)` if a lifespan startup handler raises
        (uvicorn/server.py), so one escaped exception here would turn a
        transient GitHub Pages blip into a Cloud Run crash loop. Catches
        `Exception`, not `BaseException` — `asyncio.CancelledError` (e.g.
        Cloud Run shutting the instance down mid-startup) must still
        propagate.
        """
        if not app_config.jobs_detail_url:
            _logger.info("knowledge refresh disabled (JOBS_DETAIL_URL is empty)")
            return
        try:
            refreshed = await knowledge.fetch_knowledge(
                app_config.jobs_detail_url,
                timeout_seconds=app_config.knowledge_fetch_timeout_seconds,
                transport=http_transport,
            )
        except Exception:
            _logger.warning(
                "knowledge refresh failed; serving image-bundled data",
                exc_info=True,
                extra={"url": app_config.jobs_detail_url},
            )
            return
        _install(refreshed)
        _logger.info(
            "knowledge refreshed from %s (%d jobs)",
            app_config.jobs_detail_url,
            len(refreshed.jobs_by_id),
        )

    # Holds the lazily-built real client (empty when `generate_fn` was
    # injected, i.e. every test) so `_lifespan` below can close it on
    # shutdown without caring which branch was taken — mirrors
    # `sync/src/sync/app.py`'s `proxy_client.close()` lifespan cleanup.
    _client_holder: list[genai.Client] = []

    # Single declaration point for `_generate` (pyright reportRedeclaration
    # otherwise flags the two branches as conflicting types — an explicit
    # `GenerateFn` annotation vs. an inferred concrete coroutine function).
    _generate: GenerateFn
    if generate_fn is not None:
        _generate = generate_fn
    else:

        async def _real_generate(
            *, history: Sequence[ChatMessage], message: str
        ) -> GeneratedReply:
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

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await _refresh_knowledge()
        try:
            yield
        finally:
            if _client_holder:
                _client_holder[0].close()

    app = FastAPI(
        title="Aozora Recruit FAQ Chatbot",
        description="Vertex AI Gemini-backed FAQ assistant for the recruitment mockup",
        version="0.1.0",
        lifespan=_lifespan,
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
    async def health() -> dict[str, object]:
        return {
            "status": "healthy",
            "knowledge": {
                "source": knowledge_base.source,
                "job_count": len(knowledge_base.jobs_by_id),
            },
        }

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
            generated = await _generate(history=trimmed_history, message=payload.message)
        except Exception:
            # Vertex failure (404 model retired, timeout, quota, network) —
            # never leak the upstream exception to the client; log it here
            # so Cloud Run logs retain the detail for debugging.
            _logger.exception("chat generation failed", extra={"model": app_config.model_id})
            raise HTTPException(
                status_code=503,
                detail="現在チャットボットをご利用いただけません。しばらくしてから再度お試しください。",
            ) from None

        # `resolve_jobs` is the whitelist check — a hallucinated/stale id
        # from the model is silently dropped here rather than reaching the
        # client (see knowledge.py docstring).
        jobs = knowledge_base.resolve_jobs(generated.job_ids)
        return ChatResponse(
            reply=generated.reply,
            blocked=generated.blocked,
            suggestions=generated.suggestions,
            jobs=jobs,
        )

    return app


# ASGI entrypoint for `uvicorn chatbot.app:app` / Docker CMD.
app = create_app()
