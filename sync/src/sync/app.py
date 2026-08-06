"""FastAPI proxy for the Jobcan public job pages.

Phase B B-8 — serves every request from Firestore `job_cache` (populated by
the daily `sync-run` batch, `orchestrator.py`). **This service never fetches
Jobcan at request time** — the Phase 2A.2 live-fetch-per-request design (with
its Jobcan-error → HTTP-status mapping, allowlists, and negative cache) is
gone; every one of those concerns existed to protect an upstream fetch that no
longer happens here. A short positive-only HTML cache remains, because a
`repo.get_all()` category-listing read is cheap but not free.

# Routing surface

    GET /healthz                      → 200 OK, no Firestore touch
    GET /jobs/{job_id}                → in-house HTML from `job_cache/{job_id}`
    GET /jobs/?category_id=...        → in-house listing, filtered from `job_cache`

# Status → response mapping

| `JobSnapshot.sync_status` | Response                                    |
|----------------------------|----------------------------------------------|
| (no document / unknown id) | 404                                          |
| `pending_review`            | 404 (never actually reached in practice —    |
|                             | `REVIEW_BYPASS=true` is always on, B-8; kept |
|                             | as a defensive default if that ever flips)   |
| `active`                    | 200, normal render                          |
| `closed`                    | 200, apply CTA replaced with a closed banner |
|                             | (page stays up for SEO / 被リンク維持)         |
| Firestore read failure      | 503, HTML page with a Jobcan fallback link   |
| render failure (Jinja2 etc.)| 500, HTML page with a Jobcan fallback link   |

All responses add `Cache-Control: no-store` and `X-Robots-Tag: noindex,
nofollow` via middleware. Every Firestore read happens inside
`run_in_threadpool` — the SDK is synchronous, and running it directly on the
event loop would serialize every concurrent request behind it (2026-08-07
codex second-opinion review finding).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from ._validators import is_ascii_digit_id
from .cache import Cache, CacheConfig, InMemoryCache
from .firestore_repo import JobCacheRepository, get_firestore_client
from .models import JobListItem, JobListPage
from .renderer import render_error, render_job_detail, render_job_list
from .snapshot import JobSnapshot

_logger = logging.getLogger(__name__)

JOBCAN_DETAIL_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
    "?hide_breadcrumb=true&hide_search=true"
)
JOBCAN_LIST_FALLBACK = (
    "https://recruit.jobcan.jp/aozora/list"
    "?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
)


def _error_html(title: str, message: str, fallback_url: str) -> str:
    return render_error(title=title, message=message, fallback_url=fallback_url)


def _apply_security_headers(response: Response) -> Response:
    """Stamp the response with the headers every proxy reply must carry.

    Cache-Control prevents intermediaries from holding pages past this
    service's own short cache TTL; X-Robots-Tag keeps non-canonical/preview
    URLs out of search indexes.
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _rewrite_detail_url(item: JobListItem, job_id: str) -> JobListItem:
    """Point a stored listing card at this service's own detail route.

    `JobListItem.detail_url` is persisted as the absolute Jobcan URL (the
    crawler's parse output is never rewritten before storage, so a future
    consumer of the raw snapshot always sees what Jobcan actually served).
    The proxy rewrites it only at render time, so card clicks stay in-house
    instead of bouncing back to Jobcan.
    """
    return item.model_copy(update={"detail_url": f"/jobs/{job_id}"})


def create_app(
    *,
    cache: Cache | None = None,
    repo: JobCacheRepository | None = None,
) -> FastAPI:
    """Construct the FastAPI app.

    Dependency-injection-friendly: tests pass a fake `repo` (e.g. backed by
    `tests.conftest.FakeFirestoreClient`) and a fresh `InMemoryCache`.
    Production leaves `repo=None` — resolved lazily (see `_resolve_repo`)
    rather than built here, so `app = create_app()` at import time never
    touches `google.auth.default()`. `get_firestore_client()` is only ever
    called elsewhere (`cli.py`) inside a function body, never at module
    scope; constructing a real `firestore.Client` eagerly here would make
    `import sync.app` itself require GCP credentials — breaking test
    collection and any tooling that imports this module without ADC set up.
    """
    proxy_cache: Cache = cache or InMemoryCache(CacheConfig())
    _injected_repo = repo
    _lazy_repo: JobCacheRepository | None = None

    def _resolve_repo() -> JobCacheRepository:
        nonlocal _lazy_repo
        if _injected_repo is not None:
            return _injected_repo
        if _lazy_repo is None:
            _lazy_repo = JobCacheRepository(get_firestore_client())
        return _lazy_repo

    app = FastAPI(
        title="Aozora Jobcan Proxy",
        description="Phase B B-8 — Firestore-backed in-house job page proxy",
        version="0.3.0",
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        return _apply_security_headers(response)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def get_job_detail(job_id: str) -> Response:
        if not is_ascii_digit_id(job_id):
            raise HTTPException(status_code=404, detail="not found")

        cached = proxy_cache.get_detail(job_id)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "detail", "job_id": job_id})
            return HTMLResponse(content=cached)

        try:
            snapshot = await run_in_threadpool(lambda: _resolve_repo().get(job_id))
        except Exception:
            _logger.exception("firestore read error", extra={"kind": "detail", "job_id": job_id})
            return _firestore_error_response(JOBCAN_DETAIL_FALLBACK.format(job_id=job_id))

        if snapshot is None or snapshot.sync_status == "pending_review":
            raise HTTPException(status_code=404, detail="not found")

        rendered = _render_detail(snapshot, job_id=job_id)
        if rendered is None:
            fallback_url = JOBCAN_DETAIL_FALLBACK.format(job_id=job_id)
            return HTMLResponse(
                content=_error_html(
                    title="ページを表示できません",
                    message="一時的な問題が発生しました。元のページをご覧ください。",
                    fallback_url=fallback_url,
                ),
                status_code=500,
            )

        proxy_cache.set_detail(job_id, rendered)
        _logger.info("cache miss → rendered", extra={"kind": "detail", "job_id": job_id})
        return HTMLResponse(content=rendered)

    @app.get("/jobs/", response_class=HTMLResponse)
    async def get_job_list(
        category_id: Annotated[str, Query(..., min_length=1, max_length=16)],
    ) -> Response:
        if not is_ascii_digit_id(category_id):
            raise HTTPException(status_code=404, detail="not found")

        cached = proxy_cache.get_list(category_id)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "list", "category_id": category_id})
            return HTMLResponse(content=cached)

        try:
            snapshots, skipped = await run_in_threadpool(lambda: _resolve_repo().get_all_valid())
        except Exception:
            _logger.exception(
                "firestore read error", extra={"kind": "list", "category_id": category_id}
            )
            return _firestore_error_response(JOBCAN_LIST_FALLBACK.format(category_id=category_id))

        if skipped:
            _logger.error(
                "list route: skipped malformed job_cache docs",
                extra={"category_id": category_id, "skipped_job_ids": skipped},
            )

        rendered = _render_list(snapshots, category_id=category_id)
        if rendered is None:
            fallback_url = JOBCAN_LIST_FALLBACK.format(category_id=category_id)
            return HTMLResponse(
                content=_error_html(
                    title="ページを表示できません",
                    message="一時的な問題が発生しました。元のページをご覧ください。",
                    fallback_url=fallback_url,
                ),
                status_code=500,
            )

        proxy_cache.set_list(category_id, rendered)
        _logger.info("cache miss → rendered", extra={"kind": "list", "category_id": category_id})
        return HTMLResponse(content=rendered)

    return app


def _firestore_error_response(fallback_url: str) -> Response:
    """503 page for a Firestore read failure — distinct from a render
    failure (500) so an operator scanning logs can tell "Firestore is down"
    apart from "this one job's/category's data is malformed"
    (2026-08-07 second-opinion review finding: the detail route previously
    let this propagate as an unhandled, unlogged exception)."""
    return HTMLResponse(
        content=_error_html(
            title="一時的に表示できません",
            message=(
                "データの取得に問題が発生している可能性があります。"
                "少し時間をおいてから再度お試しください。"
            ),
            fallback_url=fallback_url,
        ),
        status_code=503,
    )


def _render_detail(snapshot: JobSnapshot, *, job_id: str) -> str | None:
    """Render one snapshot's detail page. `None` signals a render failure.

    Render-time failures (Jinja2 `TemplateError`, an unexpected attribute
    error) should be rare — `snapshot.offer` is already a validated
    `JobOffer` — but the CLI (`cli.py render`) and the old fetch-per-request
    proxy both guarded this call, so this keeps the same defensive posture
    instead of leaking a stack trace to the client.
    """
    try:
        return render_job_detail(snapshot.offer, closed=snapshot.sync_status == "closed")
    except Exception:
        _logger.exception("render error", extra={"kind": "detail", "job_id": job_id})
        return None


def _render_list(snapshots: dict[str, JobSnapshot], *, category_id: str) -> str | None:
    """Build and render the listing page for one category from already-read
    snapshots, or `None` on a render failure.

    Deliberately pure (no Firestore access) — the caller reads the
    collection separately (`get_all_valid()`, off the event loop) so a
    Firestore-read failure and a template-render failure log and respond
    differently (503 vs 500) instead of being conflated under one bare
    `except Exception` (2026-08-07 second-opinion review finding).

    Filtering in Python rather than a Firestore query: a composite query
    (`category_ids array_contains X and sync_status == active`) would need a
    manually-provisioned composite index in a project that deliberately has
    no Terraform/IaC (`.claude/memory/feedback_overengineering_recovery_2026-06-18.md`),
    and the catalogue is small enough that reading the whole collection
    through the list cache (`CacheConfig.list_ttl`) stays cheap. Revisit this
    if the catalogue grows into the thousands — the real posting count has
    not yet been confirmed by an actual production `sync-run` (B-8 was
    implemented and reviewed before any Cloud Run Job ever executed;
    `infra/README.md` §8.1b's dry-run is where that gets measured for real).
    """
    try:
        cards = [
            _rewrite_detail_url(snapshot.list_item, snapshot.job_id)
            for snapshot in snapshots.values()
            if category_id in snapshot.category_ids
            and snapshot.sync_status == "active"
            and snapshot.list_item is not None
        ]
        # Numeric, not lexicographic (str sort would put "10000000" before
        # "9999999") — job_id has no fixed digit width. Descending as a
        # deterministic newest-first proxy: Firestore has no listing-order
        # info to replicate Jobcan's own display order, and job_ids increase
        # monotonically (review-code-b8 second-opinion finding).
        cards.sort(key=lambda item: int(item.job_id), reverse=True)
        page = JobListPage(
            source_url=JOBCAN_LIST_FALLBACK.format(category_id=category_id),
            category_id=category_id,
            items=cards,
            total_count=len(cards),
            last_page=1,
            next_url=None,
        )
        return render_job_list(page)
    except Exception:
        _logger.exception("render error", extra={"kind": "list", "category_id": category_id})
        return None


# ASGI entrypoint for `uvicorn sync.app:app` / Docker CMD.
# `__name__ == "__main__"` is intentionally NOT used: uvicorn imports this
# module and looks up `app` directly, so the bare module-level construction
# is the right shape for Cloud Run as well (`uvicorn sync.app:app`).
app = create_app()
