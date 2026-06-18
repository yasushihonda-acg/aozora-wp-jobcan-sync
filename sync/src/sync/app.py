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
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from .cache import Cache, CacheConfig, InMemoryCache
from .jobcan_client import JobcanClient
from .models import (
    JobcanClientError,
    JobcanStructureChangeError,
    JobcanValidationError,
)
from .parser import parse_job_detail, parse_job_list
from .renderer import render_job_detail, render_job_list

_logger = logging.getLogger(__name__)

JOBCAN_DETAIL_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
    "?hide_breadcrumb=true&hide_search=true"
)
JOBCAN_LIST_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/list"
    "?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
)

# Returned for any error class that should not redirect (5xx / parse failures).
# Kept ASCII-clean for HTTP header consistency; body is the only Japanese-bearing
# response surface and renders without a template to avoid extending the failure
# blast radius into Jinja2.
_ERROR_HTML_TEMPLATE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"ja\">\n"
    "<head><meta charset=\"utf-8\"><title>{title}</title>"
    "<meta name=\"robots\" content=\"noindex, nofollow\"></head>\n"
    "<body>\n"
    "<h1>{title}</h1>\n"
    "<p>{message}</p>\n"
    '<p><a href="{fallback_url}">Jobcan の元ページを開く</a></p>\n'
    "</body></html>\n"
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


def _is_valid_id(value: str) -> bool:
    """Reject non-ASCII digits early (e.g. full-width Jobcan rejects with 404).

    Mirrors the CLI guard (`cli.py`) so callers see the same input contract
    whether they hit the proxy or run the CLI directly.
    """
    return value.isascii() and value.isdigit()


def _allowed(value: str, allowlist: frozenset[str]) -> bool:
    """Empty allowlist = unrestricted (Phase 2A.2 default).

    Phase 2B-1 sets non-empty allowlists to defeat ID-enumeration attacks
    (Codex Q5/Q8). The "empty = all" convention keeps tests and local CLI
    use cheap.
    """
    return not allowlist or value in allowlist


def _error_html(title: str, message: str, fallback_url: str) -> str:
    return _ERROR_HTML_TEMPLATE.format(title=title, message=message, fallback_url=fallback_url)


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

    app = FastAPI(
        title="Aozora Jobcan Proxy",
        description="Phase 2A.2 — Cloud-Run-ready Jobcan public-page proxy",
        version="0.2.0",
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
        if not _is_valid_id(job_id):
            # 404 (not 400) so enumeration probes cannot distinguish
            # "format invalid" from "id not in allowlist" — same response.
            raise HTTPException(status_code=404, detail="not found")

        if not _allowed(job_id, app_config.job_id_allowlist):
            _logger.info("allowlist reject", extra={"kind": "detail", "job_id": job_id})
            raise HTTPException(status_code=404, detail="not found")

        fallback_url = JOBCAN_DETAIL_FALLBACK.format(job_id=job_id)

        cached = proxy_cache.get_detail(job_id)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "detail", "job_id": job_id})
            return HTMLResponse(content=cached)

        neg_status = proxy_cache.get_negative("detail", job_id)
        if neg_status is not None:
            return _render_negative(neg_status, fallback_url, kind="detail", key=job_id)

        if not app_config.fetch_enabled:
            _logger.info(
                "fetch disabled, returning maintenance page",
                extra={"kind": "detail", "job_id": job_id},
            )
            return HTMLResponse(
                content=_error_html(
                    title="メンテナンス中",
                    message="求人情報は現在準備中です。Jobcan の元ページを直接ご覧ください。",
                    fallback_url=fallback_url,
                ),
                status_code=503,
            )

        html = await _fetch_and_render_detail(
            client_factory=client_factory,
            job_id=job_id,
            fallback_url=fallback_url,
            cache=proxy_cache,
        )
        return html

    @app.get("/jobs/", response_class=HTMLResponse)
    async def get_job_list(
        category_id: Annotated[str, Query(..., min_length=1, max_length=16)],
    ) -> Response:
        if not _is_valid_id(category_id):
            raise HTTPException(status_code=404, detail="not found")

        if not _allowed(category_id, app_config.category_id_allowlist):
            _logger.info(
                "allowlist reject", extra={"kind": "list", "category_id": category_id}
            )
            raise HTTPException(status_code=404, detail="not found")

        fallback_url = JOBCAN_LIST_FALLBACK.format(category_id=category_id)

        cached = proxy_cache.get_list(category_id)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "list", "category_id": category_id})
            return HTMLResponse(content=cached)

        neg_status = proxy_cache.get_negative("list", category_id)
        if neg_status is not None:
            return _render_negative(neg_status, fallback_url, kind="list", key=category_id)

        if not app_config.fetch_enabled:
            _logger.info(
                "fetch disabled, returning maintenance page",
                extra={"kind": "list", "category_id": category_id},
            )
            return HTMLResponse(
                content=_error_html(
                    title="メンテナンス中",
                    message="求人一覧は現在準備中です。Jobcan の元ページを直接ご覧ください。",
                    fallback_url=fallback_url,
                ),
                status_code=503,
            )

        html = await _fetch_and_render_list(
            client_factory=client_factory,
            category_id=category_id,
            fallback_url=fallback_url,
            cache=proxy_cache,
        )
        return html

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
    client_factory: type[JobcanClient],
    job_id: str,
    fallback_url: str,
    cache: Cache,
) -> Response:
    """Fetch + parse + render one job detail page, with full exception mapping."""

    def _do_fetch() -> tuple[str, str]:
        # JobcanClient is sync (httpx.Client). Wrapping the network + parse
        # in a single threadpool call keeps the FastAPI event loop free under
        # concurrency (Codex Q4) without rewriting the existing CLI path.
        with client_factory() as client:
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

    cache.set_detail(job_id, rendered)
    _logger.info("cache miss → fetched", extra={"kind": "detail", "job_id": job_id})
    return HTMLResponse(content=rendered)


async def _fetch_and_render_list(
    *,
    client_factory: type[JobcanClient],
    category_id: str,
    fallback_url: str,
    cache: Cache,
) -> Response:
    def _do_fetch() -> tuple[str, str]:
        with client_factory() as client:
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

    cache.set_list(category_id, rendered)
    _logger.info(
        "cache miss → fetched", extra={"kind": "list", "category_id": category_id}
    )
    return HTMLResponse(content=rendered)


# HTTP statuses that JobcanClient surfaces as "HTTP {N} from {url}" messages.
# These split JobcanClientError instances into 4xx (redirect-able) vs 5xx /
# network (HTML maintenance page) without exposing the underlying httpx
# exception types to the route layer.
_HTTP_PREFIX = "HTTP "


def _classify_client_error(exc: JobcanClientError) -> int:
    """Return the HTTP status code embedded in the error, or 500 if untaggable.

    Naive string scrape because JobcanClient's error message format already
    encodes the status — see `_get_with_retry` in jobcan_client.py. Tying
    the format to a constant is more brittle than this since the client
    has multiple message paths (network exhausted, transient, permanent).
    """
    message = str(exc)
    if message.startswith(_HTTP_PREFIX):
        # Format: "HTTP 404 from ..."
        try:
            return int(message.split(" ", 2)[1])
        except (IndexError, ValueError):
            return 500
    if "Transient HTTP" in message:
        try:
            # Format: "Transient HTTP 503 from ..."
            return int(message.split("Transient HTTP", 1)[1].strip().split(" ", 1)[0])
        except (IndexError, ValueError):
            return 500
    if "Network error" in message:
        return 503
    return 500


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
