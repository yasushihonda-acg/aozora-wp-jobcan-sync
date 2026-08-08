"""FastAPI proxy for the Jobcan public job pages.

Phase B B-8 — serves every request from Firestore `job_cache` (populated by
the periodic `sync-run` batch, `orchestrator.py`, every 6 hours as of
2026-08-08). **This service never fetches
Jobcan at request time** — the Phase 2A.2 live-fetch-per-request design (with
its Jobcan-error → HTTP-status mapping, allowlists, and negative cache) is
gone; every one of those concerns existed to protect an upstream fetch that no
longer happens here. A short positive-only HTML cache remains, because a
`repo.get_all()` category-listing read is cheap but not free.

# Routing surface

    GET /                             → top page (`mockup/index.html`, link-rewritten)
    GET /assets/*                     → static CSS/JS/images (`mockup/assets`)
    GET /healthz                      → 200 OK, no Firestore touch
    GET /jobs/{job_id}                → in-house HTML from `job_cache/{job_id}`
    GET /jobs/{job_id}.html           → 308 redirect to /jobs/{job_id}
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

All responses add `X-Robots-Tag: noindex, nofollow` via middleware, plus
`Cache-Control: no-store` — except successful `/assets/*` responses, which
get `public, max-age=3600` instead (2026-08-08, so the top page's CSS/JS/
images don't re-download on every navigation like the rest of this
service's genuinely-dynamic pages must). Every synchronous I/O call
(Firestore reads, and — 2026-08-08 — the top page's local file read) happens
inside `run_in_threadpool`; running either directly on the event loop would
serialize every concurrent request behind it (2026-08-07 codex second-
opinion review finding, reconfirmed for the top page 2026-08-08).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from ._validators import is_ascii_digit_id
from .cache import Cache, CacheConfig, InMemoryCache
from .firestore_repo import JobCacheRepository, get_firestore_client
from .models import JobListItem, JobListPage
from .renderer import render_error, render_job_detail, render_job_list
from .snapshot import JobSnapshot

_logger = logging.getLogger(__name__)

# Stage 1 of the Cloud Run consolidation (2026-08-08, see
# docs/handoff/GOAL.md): the top page + its CSS/JS/images used to live only
# on the Phase A GitHub Pages mockup. `PUBLIC_BASE_URL` (e.g.
# `https://recruit.aozora-cg.com`, no trailing slash) lets this service build
# canonical URLs pointing at itself instead of Jobcan; empty in local
# dev/tests, where a site-root-relative canonical is fine.
#
# `STATIC_ASSETS_DIR`/`INDEX_HTML_PATH` default to the checked-out
# `mockup/assets` / `mockup/index.html` two levels above this package — that
# resolves correctly for local dev (`sync/src/sync/app.py` → repo root) but
# NOT inside the container, where `Dockerfile` copies only `src/` (one level
# shallower) — so the Dockerfile sets both env vars explicitly to where it
# actually copied `mockup/`.
_REPO_ROOT_LOCAL_DEV = Path(__file__).resolve().parents[3]
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
STATIC_ASSETS_DIR = os.environ.get(
    "STATIC_ASSETS_DIR", str(_REPO_ROOT_LOCAL_DEV / "mockup" / "assets")
)
INDEX_HTML_PATH = os.environ.get(
    "INDEX_HTML_PATH", str(_REPO_ROOT_LOCAL_DEV / "mockup" / "index.html")
)

# `mockup/index.html` is shared with the still-live Phase A GitHub Pages
# mockup, whose job links are relative paths to sibling static files
# (`jobs-care.html`, `jobs.html?job_type=...`) that don't exist as routes on
# this service. Editing that shared file directly would break navigation on
# the GitHub Pages site *before* this service is what `recruit.aozora-cg.com`
# actually points at (Stage 5, not yet done) — so instead this service
# rewrites the known href values at serve time, leaving the shared source
# file untouched. Category ids from `crawler.KNOWN_CATEGORY_IDS`.
#
# The three plain `jobs.html` link targets ("募集職種"/"求人を見る"/"すべての
# 求人を見る"/footer/mobile CTA — 7 occurrences) point at the largest single
# category (介護職) as an interim stand-in: v1 deliberately ships without an
# all-category listing (decision-maker call, 2026-08-08 — a full
# search/map/GPS experience is Stage 3+ scope, not Stage 1).
_TOP_PAGE_LINK_REWRITES: tuple[tuple[str, str], ...] = (
    # Logo / "採用トップ" nav / footer (3 occurrences) — self-links back to
    # the top page, which this service serves at site root, not
    # `index.html` (2026-08-08 codex review finding).
    ('href="index.html"', 'href="/"'),
    ('href="jobs.html"', 'href="/jobs/?category_id=18773"'),
    ('href="jobs-care.html"', 'href="/jobs/?category_id=18773"'),
    ('href="jobs-nurse.html"', 'href="/jobs/?category_id=18983"'),
    ('href="jobs.html?job_type=visit"', 'href="/jobs/?category_id=18986"'),  # ホームヘルパー
    ('href="jobs.html?job_type=care-manager"', 'href="/jobs/?category_id=18985"'),  # ケアマネジャー
    ('href="jobs-office.html"', 'href="/jobs/?category_id=58859"'),
    ('href="jobs-it.html"', 'href="/jobs/?category_id=69384"'),
)


def _render_top_page(raw_html: str, *, base_url: str = "") -> str:
    """Apply `_TOP_PAGE_LINK_REWRITES`, logging (not raising — a missing
    target degrades to a dead link, not a broken page) any target that
    matched nothing.

    Exact-substring matching has no static guarantee the shared
    `mockup/index.html` source still contains what this table expects
    (2026-08-08 second-opinion review finding) — a future markup change
    (attribute order, quoting) could make a target silently stop matching,
    which is exactly the kind of dead-link regression this rewriting exists
    to prevent in the first place. This turns that into a loud log line
    instead of a link that quietly 404s in production with no signal.

    `base_url` (2026-08-08 codex review finding): the shared source has a
    hard-coded `https://recruit.aozora-cg.com/` canonical + `og:url` — the
    *eventual* Stage 5 domain, not wherever this is actually being served
    from during Stages 1-4. Left untouched when `base_url=""` (local dev):
    there is no better value to substitute, and the eventual-domain
    placeholder is harmless there.
    """
    for old, new in _TOP_PAGE_LINK_REWRITES:
        if old not in raw_html:
            _logger.error(
                "top page link rewrite target not found in mockup/index.html "
                "— markup may have changed, this href is now a dead link",
                extra={"expected": old},
            )
            continue
        raw_html = raw_html.replace(old, new)

    if base_url:
        raw_html = raw_html.replace(
            'href="https://recruit.aozora-cg.com/"', f'href="{base_url}/"'
        ).replace('content="https://recruit.aozora-cg.com/"', f'content="{base_url}/"')

    return raw_html


def _load_top_page() -> str | None:
    """Synchronous file read + string rewriting for `GET /` — kept as a
    plain function (not inlined in the route) so it can run inside
    `run_in_threadpool` (see module docstring) rather than blocking the
    event loop directly. Returns `None` on a missing file so the route can
    map that to its own typed 404, matching every other route's style of
    resolving I/O outside the handler and mapping the result afterward.
    """
    if not os.path.isfile(INDEX_HTML_PATH):
        _logger.error("top page file missing", extra={"path": INDEX_HTML_PATH})
        return None
    raw_html = Path(INDEX_HTML_PATH).read_text(encoding="utf-8")
    return _render_top_page(raw_html, base_url=PUBLIC_BASE_URL)


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


def _apply_security_headers(response: Response, *, is_static_asset: bool = False) -> Response:
    """Stamp the response with the headers every proxy reply must carry.

    Cache-Control prevents intermediaries from holding *dynamic* (Firestore-
    backed) pages past this service's own short cache TTL; X-Robots-Tag
    keeps non-canonical/preview URLs out of search indexes.

    `is_static_asset=True` (the `/assets/*` mount, 2026-08-08 second-opinion
    review finding) gets a real `max-age` instead — `no-store` on every CSS/
    JS/image request forced a re-download on every single navigation, unlike
    the Phase A GitHub Pages mockup this replaces (which caches normally).
    Filenames aren't content-hashed, so this stays short rather than
    `immutable`: a stale asset would resolve itself within an hour instead
    of needing a hard refresh. Only applied when the response actually
    succeeded (`< 400`) — a 404 (e.g. a genuinely missing file, or a
    transient revision-rollout mismatch) must not itself get cached for an
    hour, and 304 Not Modified is fine to leave cacheable (2026-08-08
    second-opinion review finding: the first version of this cached 404s
    too).
    """
    is_cacheable_asset = is_static_asset and response.status_code < 400
    response.headers["Cache-Control"] = "public, max-age=3600" if is_cacheable_asset else "no-store"
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
    # `K_SERVICE` is set by Cloud Run on every revision (not by local dev /
    # tests) — if it's present without `PUBLIC_BASE_URL` also being set, the
    # deploy command's `--set-env-vars` was forgotten, and canonical URLs
    # silently degrade to site-root-relative (2026-08-08 second-opinion
    # review finding: same failure *shape* as the bug Stage 1 fixed —
    # canonical pointing somewhere wrong — via a different, easy-to-forget
    # path this time).
    if os.environ.get("K_SERVICE") and not PUBLIC_BASE_URL:
        _logger.warning(
            "PUBLIC_BASE_URL is unset on a Cloud Run revision — canonical URLs "
            "will render site-root-relative instead of fully-qualified"
        )

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
        is_static_asset = request.url.path.startswith("/assets/")
        return _apply_security_headers(response, is_static_asset=is_static_asset)

    # Stage 1 of the Cloud Run consolidation: the top page's own CSS/JS/images
    # (`mockup/assets`) are served in-house so `/jobs/{id}` (a different path
    # depth) can reference them by a site-root-absolute `/assets/...` URL
    # instead of the page-relative one that used to 404 off the job routes.
    # `check_dir` left at its Starlette default (True): a missing directory
    # is a deploy-config bug, and failing loudly at construction time here
    # means the bad revision never starts serving traffic at all (Cloud Run
    # keeps routing to the last good revision) instead of *every* asset
    # request 500ing forever once traffic does reach it — `check_dir=False`
    # doesn't skip that check the way its name suggests, it only moves it to
    # per-request (Starlette re-raises the same `RuntimeError` from inside
    # `StaticFiles.__call__` on the first hit and again on every hit after,
    # since `config_checked` only latches `True` on success — 2026-08-08
    # second-opinion review finding, confirmed against Starlette's source).
    app.mount("/assets", StaticFiles(directory=STATIC_ASSETS_DIR), name="assets")

    @app.get("/", response_class=HTMLResponse)
    async def get_top_page() -> Response:
        rendered = await run_in_threadpool(_load_top_page)
        if rendered is None:
            raise HTTPException(status_code=404, detail="not found")
        return HTMLResponse(content=rendered)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "healthy"}

    # The chatbot widget (embedded in the top page — `mockup/index.html`
    # already carries its `<script>` tag, PR #97) resolves related-job card
    # links from `job.url` ("jobs/{id}.html", the Phase A static filename
    # shape) as a *page-relative* href. From `/` that resolves to
    # `/jobs/{id}.html`, which the numeric-only route below 404s on
    # (2026-08-08 codex review finding). Registered before `/jobs/{job_id}`
    # so the more specific `.html`-suffixed pattern wins the match.
    @app.get("/jobs/{job_id}.html")
    async def redirect_legacy_html_detail_url(job_id: str) -> Response:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=308)

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
        return render_job_detail(
            snapshot.offer, closed=snapshot.sync_status == "closed", base_url=PUBLIC_BASE_URL
        )
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
        return render_job_list(page, base_url=PUBLIC_BASE_URL)
    except Exception:
        _logger.exception("render error", extra={"kind": "list", "category_id": category_id})
        return None


# ASGI entrypoint for `uvicorn sync.app:app` / Docker CMD.
# `__name__ == "__main__"` is intentionally NOT used: uvicorn imports this
# module and looks up `app` directly, so the bare module-level construction
# is the right shape for Cloud Run as well (`uvicorn sync.app:app`).
app = create_app()
