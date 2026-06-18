"""FastAPI proxy for the Jobcan public job pages.

Phase 2A.2 — Cloud-Run-ready service that fronts the existing CLI parsing
and rendering pipeline with HTTP endpoints, a TTL cache, structured logs,
and a "fixture mode" kill switch for Phase 2B-0 deployment.

# Routing surface

    GET /healthz                      → 200 OK, no Jobcan touch
    GET /jobs/{job_id}                → in-house HTML, fetched + cached
    GET /jobs/?category_id=...        → in-house listing HTML

# Operational envs (read once at app construction)

| env var                  | default | effect                                    |
|--------------------------|---------|-------------------------------------------|
| JOBCAN_FETCH_ENABLED     | true    | when false, return 503 instead of fetch   |
|                          |         | (Phase 2B-0 deploys with false)           |
| JOB_ID_ALLOWLIST         | ""      | comma-separated job_ids; empty = any      |
| CATEGORY_ID_ALLOWLIST    | ""      | comma-separated category_ids; empty = any |

# Exception → HTTP status mapping (Codex Q6)

The mapping intentionally varies the response body per failure class so
upstream incidents stay distinguishable in logs and UX. All responses
add `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`.

| Exception                       | Status | Body                                       |
|---------------------------------|--------|--------------------------------------------|
| `JobcanClientError` (4xx)       | 302    | Redirect to Jobcan canonical URL           |
| `JobcanClientError` (5xx / net) | 503    | HTML page with manual fallback link        |
| `JobcanStructureChangeError`    | 500    | HTML page with manual fallback link        |
| `JobcanValidationError`         | 500    | HTML page with manual fallback link        |
| Allowlist reject                | 404    | Plain 404 (do not confirm id existence)    |
| Fetch disabled                  | 503    | HTML page noting maintenance               |

Negative cache: 4xx and 5xx responses are stored in a short-TTL cache so
a flapping Jobcan endpoint does not amplify into per-request fetches.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.concurrency import run_in_threadpool

from ._validators import is_ascii_digit_id
from .cache import Cache, CacheConfig, InMemoryCache
from .jobcan_client import JobcanClient
from .models import (
    JobcanClientError,
    JobcanStructureChangeError,
    JobcanValidationError,
)
from .parser import parse_job_detail, parse_job_list
from .renderer import render_error, render_job_detail, render_job_list

_logger = logging.getLogger(__name__)

JOBCAN_DETAIL_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
    "?hide_breadcrumb=true&hide_search=true"
)
JOBCAN_LIST_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/list"
    "?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
)

def _parse_csv_env(value: str) -> frozenset[str]:
    """Parse a comma-separated env var into a frozenset of trimmed entries.

    Empty string yields the empty set, which the route layer interprets as
    "no allowlist enforced". This separates the "explicitly empty" case
    from "unset" cleanly at the type level.
    """
    if not value:
        return frozenset()
    return frozenset(entry.strip() for entry in value.split(",") if entry.strip())


@dataclass(frozen=True)
class AppConfig:
    """Application configuration resolved at app construction.

    Pulled into a frozen dataclass so the route layer can rely on stable
    settings for the request lifetime; env mutation mid-request does not
    affect in-flight handlers.
    """

    fetch_enabled: bool
    job_id_allowlist: frozenset[str]
    category_id_allowlist: frozenset[str]

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            fetch_enabled=os.environ.get("JOBCAN_FETCH_ENABLED", "true").lower() != "false",
            job_id_allowlist=_parse_csv_env(os.environ.get("JOB_ID_ALLOWLIST", "")),
            category_id_allowlist=_parse_csv_env(os.environ.get("CATEGORY_ID_ALLOWLIST", "")),
        )


def _allowed(value: str, allowlist: frozenset[str]) -> bool:
    """Empty allowlist = unrestricted (Phase 2A.2 default).

    Phase 2B-1 sets non-empty allowlists to defeat ID-enumeration attacks
    (Codex Q5/Q8). The "empty = all" convention keeps tests and local CLI
    use cheap.
    """
    return not allowlist or value in allowlist


def _error_html(title: str, message: str, fallback_url: str) -> str:
    # Phase 2A.3 cleanup (code-review #5): delegate to the Jinja2-backed
    # `render_error` in renderer.py so autoescape covers user-controlled
    # message bodies (e.g. selector lists in JobcanStructureChangeError).
    return render_error(title=title, message=message, fallback_url=fallback_url)


def _pre_fetch_check(
    *,
    kind: str,
    resource_id: str,
    log_key: str,
    fallback_url: str,
    allowlist: frozenset[str],
    fetch_enabled: bool,
    cache: Cache,
    maintenance_message: str,
) -> Response | None:
    """Validate, allowlist-filter, and cache-lookup before any Jobcan fetch.

    Phase 2A.3 cleanup (code-review #3): the detail and list endpoints used
    to duplicate this six-step gate (id check → allowlist → cache hit →
    negative cache → fetch disabled → proceed) almost verbatim. Centralising
    here means new pre-fetch behaviour (e.g. per-IP rate-limit, request id)
    drops into one place. Returns:

    - `HTMLResponse` / `RedirectResponse` when the request can short-circuit
      (cache hit, negative cache hit, fetch-disabled maintenance)
    - `None` when the caller should proceed to fetch

    Also raises `HTTPException(404)` for invalid ids / allowlist rejects so
    enumeration probes can't distinguish either case from a real 404.
    """
    if not is_ascii_digit_id(resource_id):
        raise HTTPException(status_code=404, detail="not found")

    if not _allowed(resource_id, allowlist):
        _logger.info("allowlist reject", extra={"kind": kind, log_key: resource_id})
        raise HTTPException(status_code=404, detail="not found")

    cached = cache.get(kind, resource_id)
    if cached is not None:
        _logger.info("cache hit", extra={"kind": kind, log_key: resource_id})
        return HTMLResponse(content=cached)

    neg_status = cache.get_negative(kind, resource_id)
    if neg_status is not None:
        return _render_negative(neg_status, fallback_url, kind=kind, key=resource_id)

    if not fetch_enabled:
        _logger.info(
            "fetch disabled, returning maintenance page",
            extra={"kind": kind, log_key: resource_id},
        )
        return HTMLResponse(
            content=_error_html(
                title="メンテナンス中",
                message=maintenance_message,
                fallback_url=fallback_url,
            ),
            status_code=503,
        )

    return None


def _apply_security_headers(response: Response) -> Response:
    """Stamp the response with the headers every proxy reply must carry.

    Cache-Control prevents intermediaries from holding error pages or stale
    redirects past the cache TTL; X-Robots-Tag keeps the dev URL out of
    search indexes during Phase 2B-0/2B-1 (Codex Q8).
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def create_app(
    *,
    config: AppConfig | None = None,
    cache: Cache | None = None,
    client_factory: type[JobcanClient] = JobcanClient,
) -> FastAPI:
    """Construct the FastAPI app.

    Dependency-injection-friendly: tests pass a mocked client_factory and
    a fresh InMemoryCache. Production constructs everything from env vars.
    """
    app_config = config or AppConfig.from_env()
    proxy_cache: Cache = cache or InMemoryCache(CacheConfig())

    # Phase 2A.3 cleanup (code-review #6): single long-lived JobcanClient so
    # the underlying httpx.Client keeps its connection pool, TLS session, and
    # DNS cache across requests. Previously the proxy constructed one per
    # request inside `_do_fetch`, paying TLS handshake cost on every fetch
    # under Cloud Run concurrency. Closed via the lifespan shutdown phase so
    # tests that build multiple apps in one process don't leak sockets.
    proxy_client = client_factory()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            proxy_client.close()

    app = FastAPI(
        title="Aozora Jobcan Proxy",
        description="Phase 2A.2 — Cloud-Run-ready Jobcan public-page proxy",
        version="0.2.0",
        lifespan=_lifespan,
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Every response — success, error, redirect — gets the proxy security
        # headers. Centralising here avoids forgetting on a new endpoint.
        response = await call_next(request)
        return _apply_security_headers(response)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def get_job_detail(job_id: str) -> Response:
        fallback_url = JOBCAN_DETAIL_FALLBACK.format(job_id=job_id)
        early = _pre_fetch_check(
            kind="detail",
            resource_id=job_id,
            log_key="job_id",
            fallback_url=fallback_url,
            allowlist=app_config.job_id_allowlist,
            fetch_enabled=app_config.fetch_enabled,
            cache=proxy_cache,
            maintenance_message=(
                "求人情報は現在準備中です。Jobcan の元ページを直接ご覧ください。"
            ),
        )
        if early is not None:
            return early
        return await _fetch_and_render_detail(
            client=proxy_client,
            job_id=job_id,
            fallback_url=fallback_url,
            cache=proxy_cache,
        )

    @app.get("/jobs/", response_class=HTMLResponse)
    async def get_job_list(
        category_id: Annotated[str, Query(..., min_length=1, max_length=16)],
    ) -> Response:
        fallback_url = JOBCAN_LIST_FALLBACK.format(category_id=category_id)
        early = _pre_fetch_check(
            kind="list",
            resource_id=category_id,
            log_key="category_id",
            fallback_url=fallback_url,
            allowlist=app_config.category_id_allowlist,
            fetch_enabled=app_config.fetch_enabled,
            cache=proxy_cache,
            maintenance_message=(
                "求人一覧は現在準備中です。Jobcan の元ページを直接ご覧ください。"
            ),
        )
        if early is not None:
            return early
        return await _fetch_and_render_list(
            client=proxy_client,
            category_id=category_id,
            fallback_url=fallback_url,
            cache=proxy_cache,
        )

    return app


def _render_negative(
    status_code: int, fallback_url: str, *, kind: str, key: str
) -> Response:
    """Render a cached negative-status response.

    4xx returns the redirect (the upstream told us "not here", let the user
    confirm at the source). 5xx / network failures return a 503 HTML page —
    the redirect hides the outage, the HTML surfaces it with a manual link.
    """
    _logger.info(
        "negative cache hit",
        extra={"kind": kind, "key": key, "negative_status": status_code},
    )
    if 400 <= status_code < 500:
        # 4xx negative cache: redirect to Jobcan canonical (cached 302).
        # Cache-Control: no-store is added by middleware so browsers don't
        # promote the redirect across cache windows after Jobcan recovers.
        return RedirectResponse(url=fallback_url, status_code=302)
    return HTMLResponse(
        content=_error_html(
            title="一時的に表示できません",
            message=(
                "Jobcan 側に問題が発生している可能性があります。"
                "少し時間をおいてから再度お試しください。"
            ),
            fallback_url=fallback_url,
        ),
        status_code=503,
    )


async def _fetch_and_render_detail(
    *,
    client: JobcanClient,
    job_id: str,
    fallback_url: str,
    cache: Cache,
) -> Response:
    """Fetch + parse + render one job detail page, with full exception mapping."""

    def _do_fetch() -> tuple[str, str]:
        # JobcanClient is sync (httpx.Client). Wrapping the network call in a
        # threadpool keeps the FastAPI event loop free under concurrency
        # (Codex Q4). The client is long-lived (Phase 2A.3 #6), so its
        # connection pool / TLS session is reused across requests.
        return client.fetch_job_detail(job_id)

    try:
        source_url, html = await run_in_threadpool(_do_fetch)
    except JobcanClientError as exc:
        return _handle_client_error(
            exc, fallback_url, cache=cache, kind="detail", key=job_id
        )

    try:
        offer = parse_job_detail(html, source_url, job_id=job_id)
        rendered = render_job_detail(offer)
    except JobcanStructureChangeError as exc:
        _logger.error(
            "structure change",
            extra={"kind": "detail", "job_id": job_id, "missing": exc.missing},
        )
        cache.set_negative("detail", job_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="Jobcan のページ構造が変わった可能性があります。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except JobcanValidationError as exc:
        _logger.error(
            "validation failed",
            extra={"kind": "detail", "job_id": job_id, "field_errors": exc.field_errors},
        )
        cache.set_negative("detail", job_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="求人情報の取得に失敗しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except PydanticValidationError as exc:
        # parse_job_detail's domain checks raise JobcanValidationError for empty
        # fields, but the Pydantic validators on JobOffer (apply_url / source_url
        # http(s) prefix) still fire for malformed values that slipped past the
        # domain checks — e.g. a malicious Jobcan HTML returning `javascript:...`
        # as the apply link. Without this catch the proxy returns FastAPI's
        # default 500 and skips negative caching, amplifying load on Jobcan.
        _logger.error(
            "pydantic validation failed",
            extra={"kind": "detail", "job_id": job_id, "errors": exc.errors()},
        )
        cache.set_negative("detail", job_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="求人情報の検証に失敗しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except Exception:
        # Last-resort catch for render-time failures (Jinja2 TemplateError,
        # AttributeError on malformed JobOffer fields, etc.). The CLI path
        # (cli.py L131) already does this; mirroring here keeps the proxy
        # from leaking stack traces and ensures the negative cache absorbs
        # the failure so connection floods do not amplify the incident.
        _logger.exception(
            "render or unexpected error",
            extra={"kind": "detail", "job_id": job_id},
        )
        cache.set_negative("detail", job_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="一時的な問題が発生しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )

    cache.set_detail(job_id, rendered)
    _logger.info("cache miss → fetched", extra={"kind": "detail", "job_id": job_id})
    return HTMLResponse(content=rendered)


async def _fetch_and_render_list(
    *,
    client: JobcanClient,
    category_id: str,
    fallback_url: str,
    cache: Cache,
) -> Response:
    def _do_fetch() -> tuple[str, str]:
        return client.fetch_job_list(category_id)

    try:
        source_url, html = await run_in_threadpool(_do_fetch)
    except JobcanClientError as exc:
        return _handle_client_error(
            exc, fallback_url, cache=cache, kind="list", key=category_id
        )

    try:
        page = parse_job_list(html, source_url)
        rendered = render_job_list(page)
    except JobcanStructureChangeError as exc:
        _logger.error(
            "structure change",
            extra={"kind": "list", "category_id": category_id, "missing": exc.missing},
        )
        cache.set_negative("list", category_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="Jobcan のページ構造が変わった可能性があります。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except JobcanValidationError as exc:
        # parse_job_list does not currently raise this, but the symmetry with
        # the detail path matters: when Phase 2B adds list-level field validation
        # (e.g. requiring non-empty `address` on each card), this handler must
        # already exist. Asymmetry was a finding in Phase 2A.2 code review.
        _logger.error(
            "validation failed",
            extra={
                "kind": "list",
                "category_id": category_id,
                "field_errors": exc.field_errors,
            },
        )
        cache.set_negative("list", category_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="求人情報の取得に失敗しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except PydanticValidationError as exc:
        _logger.error(
            "pydantic validation failed",
            extra={
                "kind": "list",
                "category_id": category_id,
                "errors": exc.errors(),
            },
        )
        cache.set_negative("list", category_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="求人情報の検証に失敗しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )
    except Exception:
        _logger.exception(
            "render or unexpected error",
            extra={"kind": "list", "category_id": category_id},
        )
        cache.set_negative("list", category_id, 500)
        return HTMLResponse(
            content=_error_html(
                title="ページを表示できません",
                message="一時的な問題が発生しました。元のページをご覧ください。",
                fallback_url=fallback_url,
            ),
            status_code=500,
        )

    cache.set_list(category_id, rendered)
    _logger.info(
        "cache miss → fetched", extra={"kind": "list", "category_id": category_id}
    )
    return HTMLResponse(content=rendered)


def _classify_client_error(exc: JobcanClientError) -> int:
    """Translate a JobcanClientError into the HTTP status the proxy returns.

    Phase 2A.3 cleanup (code-review #7): JobcanClientError now carries
    `status_code` as a typed attribute set by jobcan_client.py at raise time.
    The earlier `_classify_client_error` parsed it back out of the message
    string; this version dispatches on the attribute directly so the proxy
    breaks loudly (mypy / runtime) if jobcan_client.py ever forgets to set
    a code, instead of silently degrading to 500.

    Network failures (status_code=None) map to 503 because the canonical
    Jobcan URL is just as unreachable for the user — a redirect would push
    them onto the same network they can't reach.
    """
    if exc.status_code is None:
        return 503
    return exc.status_code


def _handle_client_error(
    exc: JobcanClientError,
    fallback_url: str,
    *,
    cache: Cache,
    kind: str,
    key: str,
) -> Response:
    status = _classify_client_error(exc)
    cache.set_negative(kind, key, status)
    if 400 <= status < 500:
        _logger.info(
            "jobcan 4xx → redirect to canonical",
            extra={"kind": kind, "key": key, "upstream_status": status},
        )
        return RedirectResponse(url=fallback_url, status_code=302)
    _logger.warning(
        "jobcan 5xx / network → maintenance page",
        extra={"kind": kind, "key": key, "upstream_status": status},
    )
    return HTMLResponse(
        content=_error_html(
            title="一時的に表示できません",
            message=(
                "Jobcan 側に問題が発生している可能性があります。"
                "少し時間をおいてから再度お試しください。"
            ),
            fallback_url=fallback_url,
        ),
        status_code=503,
    )


# ASGI entrypoint for `uvicorn sync.app:app` / Docker CMD.
# `__name__ == "__main__"` is intentionally NOT used: uvicorn imports this
# module and looks up `app` directly, so the bare module-level construction
# is the right shape for Cloud Run as well (`uvicorn sync.app:app`).
app = create_app()
