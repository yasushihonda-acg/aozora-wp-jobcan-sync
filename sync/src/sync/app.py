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

Every response gets `Cache-Control: no-store` — except successful
`/assets/*` responses, which get `public, max-age=3600` instead (2026-08-08,
so the top page's CSS/JS/images don't re-download on every navigation like
the rest of this service's genuinely-dynamic pages must). `X-Robots-Tag:
noindex, nofollow` is added to everything EXCEPT the three public page kinds
(`/`, `/jobs/`, `/jobs/{ascii-digit id}`) on a 200 response (Stage 4 P0-1,
2026-08-09 — the earlier unconditional noindex meant the site could never be
found via search no matter what domain it was reachable at). Every
synchronous I/O call (Firestore reads, and — 2026-08-08 — the top page's
local file read) happens inside `run_in_threadpool`; running either directly
on the event loop would serialize every concurrent request behind it
(2026-08-07 codex second-opinion review finding, reconfirmed for the top
page 2026-08-08).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exception_handlers import http_exception_handler as _default_http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from ._validators import is_ascii_digit_id
from .cache import Cache, CacheConfig, InMemoryCache
from .detail_sections import RelatedJob, extract_region_tag
from .firestore_repo import JobCacheRepository, get_firestore_client
from .list_sections import JobListCardView, build_card_view
from .models import JobListItem, JobListPage
from .renderer import (
    render_error,
    render_job_detail,
    render_job_list,
    render_not_found,
    render_sitemap,
)
from .search_index import build_search_index
from .snapshot import JobSnapshot

# Stage 3 (求人一覧デザインパリティ): the all-jobs search page's cache key —
# distinct from any real numeric `category_id`, so `ProxyCache.get_list`/
# `set_list` (keyed only by that one string) can serve both without a
# collision. Also used as the search-index.json cache key.
_ALL_JOBS_CACHE_KEY = "__all__"

# Stage 4 P1-1 (2026-08-09): `sitemap.xml`'s cache key, same `ProxyCache.
# get_list`/`set_list` namespace as `_ALL_JOBS_CACHE_KEY` above — distinct
# string, no collision risk.
_SITEMAP_CACHE_KEY = "__sitemap__"

# Stage 2 (job-detail design parity, 2026-08-08): cap on the "関連する求人"
# sidebar — matches Phase A's `mockup/jobs/*.html` (always exactly 3).
_RELATED_JOBS_LIMIT = 3

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

# Single source of truth for Phase A's filename/query-value → category_id
# mapping (Stage 4 P0-3, 2026-08-09) — both `_TOP_PAGE_LINK_REWRITES` (in-
# page href rewriting) and the standalone legacy-URL redirect routes below
# derive from this one dict instead of each hardcoding the six ids
# separately. Values from `crawler.KNOWN_CATEGORY_IDS`.
_LEGACY_CATEGORY_IDS: dict[str, str] = {
    "care": "18773",
    "nurse": "18983",
    "visit": "18986",  # ホームヘルパー — only reachable via `jobs.html?job_type=visit`
    "care-manager": "18985",  # ケアマネジャー — via `jobs.html?job_type=care-manager` only
    "office": "58859",
    "it": "69384",
}

# `mockup/index.html` is shared with the still-live Phase A GitHub Pages
# mockup, whose job links are relative paths to sibling static files
# (`jobs-care.html`, `jobs.html?job_type=...`) that don't exist as routes on
# this service. Editing that shared file directly would break navigation on
# the GitHub Pages site *before* this service is what `recruit.aozora-cg.com`
# actually points at (Stage 5, not yet done) — so instead this service
# rewrites the known href values at serve time, leaving the shared source
# file untouched.
#
# The plain `jobs.html` link targets ("募集職種"/"求人を見る"/"すべての求人を
# 見る"/footer/mobile CTA — 7 occurrences) used to point at the largest
# single category (介護職) as an interim stand-in for the full all-jobs
# search/map/GPS experience, which Stage 1 deliberately shipped without
# (decision-maker call, 2026-08-08). Stage 3 (求人一覧デザインパリティ,
# 2026-08-09) implements that page at `/jobs/` with no `category_id` — these
# now point there instead of the 介護職 stand-in.
_TOP_PAGE_LINK_REWRITES: tuple[tuple[str, str], ...] = (
    # Logo / "採用トップ" nav / footer (3 occurrences) — self-links back to
    # the top page, which this service serves at site root, not
    # `index.html` (2026-08-08 codex review finding).
    ('href="index.html"', 'href="/"'),
    ('href="jobs.html"', 'href="/jobs/"'),
    (
        'href="jobs-care.html"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["care"]}"',
    ),
    (
        'href="jobs-nurse.html"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["nurse"]}"',
    ),
    (
        'href="jobs.html?job_type=visit"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["visit"]}"',
    ),
    (
        'href="jobs.html?job_type=care-manager"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["care-manager"]}"',
    ),
    (
        'href="jobs-office.html"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["office"]}"',
    ),
    (
        'href="jobs-it.html"',
        f'href="/jobs/?category_id={_LEGACY_CATEGORY_IDS["it"]}"',
    ),
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


# Stage 4 P0-1 (2026-08-09): the exact set of paths a search engine should be
# allowed to index. Kept as an explicit allowlist rather than a "block these"
# denylist — every new non-public route (JSON data endpoints, health checks,
# future admin surfaces) is noindex by default unless someone deliberately
# adds it here, instead of silently becoming indexable by omission.
_INDEXABLE_EXACT_PATHS = frozenset({"/", "/jobs/", "/robots.txt", "/sitemap.xml"})


def _is_indexable(path: str, status_code: int) -> bool:
    """True for the public page kinds search engines should be allowed to
    show — only ever on a genuinely successful response.

    Redirects, 404s, 5xx error pages, `/healthz`, and the JS-only
    `/jobs/search-index.json` data endpoint all stay noindex — none of them
    are a page a search result should land a candidate on. `/jobs/{id}` uses
    `is_ascii_digit_id` (the same validator the route handler itself uses,
    `app.py:369`) rather than a loose `/jobs/` prefix check, so this doesn't
    accidentally also allow-list `/jobs/search-index.json` (also `/jobs/`-
    prefixed) — that guard is exercised by
    `test_search_index_json_stays_noindex`.

    `/assets/*` deliberately stays noindex too (codex review finding,
    2026-08-09): `noindex` only keeps a URL out of search *results* — it has
    no effect on whether Googlebot fetches the resource, so marking CSS/JS/
    images indexable bought nothing for page rendering or `og:image`
    eligibility (og:image is read directly off the page's own meta tag, not
    looked up via the image's own indexing status) while needlessly exposing
    individual design assets (`sky-hero.jpg` etc.) as their own search
    results.
    """
    if status_code != 200:
        return False
    if path in _INDEXABLE_EXACT_PATHS:
        return True
    if path.startswith("/jobs/"):
        return is_ascii_digit_id(path.removeprefix("/jobs/"))
    return False


def _prefers_html_error(path: str) -> bool:
    """True when a 404 on `path` should render the branded HTML error page
    rather than staying JSON (Stage 4 P0-2, 2026-08-09).

    `.json`-suffixed paths (`/jobs/search-index.json`'s own shape, and any
    future JSON endpoint) are fetched by JS, never navigated to — a 404 HTML
    document there just turns a clean `response.json()` failure into an
    opaque `SyntaxError: Unexpected token '<'` for whoever's debugging it.
    `/assets/*` 404s are `<link>`/`<img>` resolution failures; nobody reads a
    2KB HTML document, so returning it isn't worth the render cost.
    """
    return not path.endswith(".json") and not path.startswith("/assets/")


def _apply_security_headers(response: Response, *, path: str) -> Response:
    """Stamp the response with the headers every proxy reply must carry.

    Cache-Control prevents intermediaries from holding *dynamic* (Firestore-
    backed) pages past this service's own short cache TTL; X-Robots-Tag
    keeps non-canonical/preview/error URLs out of search indexes (Stage 4
    P0-1, 2026-08-09: previously unconditional on every response, which also
    hid the pages this proxy exists to serve — see `_is_indexable`).

    `/assets/*` (the static mount, 2026-08-08 second-opinion review finding)
    gets a real `max-age` instead of `no-store` — forcing a re-download of
    every CSS/JS/image on every navigation, unlike the Phase A GitHub Pages
    mockup this replaces (which caches normally). Filenames aren't content-
    hashed, so this stays short rather than `immutable`: a stale asset would
    resolve itself within an hour instead of needing a hard refresh. Only
    applied when the response actually succeeded (`< 400`) — a 404 (e.g. a
    genuinely missing file, or a transient revision-rollout mismatch) must
    not itself get cached for an hour, and 304 Not Modified is fine to leave
    cacheable (2026-08-08 second-opinion review finding: the first version
    of this cached 404s too). `/sitemap.xml`/`/robots.txt` (Stage 4 P1-1/2)
    ride the same real-max-age branch — both only change on the ~6-hourly
    sync cadence, same as the static assets.
    """
    is_static_asset = path.startswith("/assets/")
    is_cacheable_kind = is_static_asset or path in {"/sitemap.xml", "/robots.txt"}
    is_cacheable = is_cacheable_kind and response.status_code < 400
    response.headers["Cache-Control"] = "public, max-age=3600" if is_cacheable else "no-store"
    if not _is_indexable(path, response.status_code):
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
        return _apply_security_headers(response, path=request.url.path)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        """Stage 4 P0-2 (2026-08-09): a public site must not answer a bad/
        stale link with FastAPI's default `{"detail": "not found"}` JSON —
        registered on the Starlette base class (not `fastapi.HTTPException`)
        so this also catches `StaticFiles`'s own 404s and the router's
        "no matching route" 404, both of which raise the Starlette base
        directly rather than the FastAPI subclass.

        Only 404 gets the HTML treatment, and only for a request that isn't
        itself asking for JSON/an asset (`_prefers_html_error`) — a 405 on
        `/healthz`, or a future non-404 HTTPException, falls through to
        FastAPI's own default handler unchanged.

        `render_not_found()` itself is wrapped in try/except (silent-failure-
        hunter finding, 2026-08-09) — every other render call in this module
        (`_render_detail`/`_render_list`) keeps "fetch" and "render" in
        separate try/excepts so a Jinja2 failure degrades to a *branded*
        500 with a logged, structured event instead of an unbranded, silent
        one; this handler had skipped that same pattern for its own render
        call.
        """
        if exc.status_code == 404 and _prefers_html_error(request.url.path):
            try:
                return HTMLResponse(content=render_not_found(), status_code=404)
            except Exception:
                _logger.exception(
                    "render error", extra={"kind": "not_found", "path": request.url.path}
                )
                return HTMLResponse(
                    content=_error_html(
                        title="一時的に表示できません",
                        message="一時的な問題が発生しました。",
                        fallback_url="/",
                    ),
                    status_code=500,
                )
        return await _default_http_exception_handler(request, exc)

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

    # Stage 4 P1-1 (2026-08-09). `PUBLIC_BASE_URL` unset → 503: the sitemap
    # protocol requires absolute URLs, and `request.base_url` can't safely
    # substitute (Cloud Run's uvicorn CMD doesn't widen
    # `forwarded_allow_ips`, so it would resolve to `http://` regardless of
    # the real `https://` scheme — a second, distinct place the deploy-
    # config-forgot-PUBLIC_BASE_URL failure mode already logged in
    # `create_app` above would otherwise degrade silently). A 503 here is
    # loud in Search Console instead ("couldn't fetch sitemap"). Firestore
    # failures get the same 503 — an empty/degraded sitemap would tell
    # Google every job just disappeared, which is a worse signal than "try
    # again later."
    @app.get("/sitemap.xml")
    async def get_sitemap() -> Response:
        if not PUBLIC_BASE_URL:
            _logger.error("sitemap.xml requested but PUBLIC_BASE_URL is unset")
            return Response(content="PUBLIC_BASE_URL is not configured", status_code=503)

        cached = proxy_cache.get_list(_SITEMAP_CACHE_KEY)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "sitemap"})
            return Response(content=cached, media_type="application/xml")

        try:
            snapshots, skipped = await run_in_threadpool(lambda: _resolve_repo().get_all_valid())
        except Exception:
            _logger.exception("firestore read error", extra={"kind": "sitemap"})
            return Response(content="temporarily unavailable", status_code=503)

        if skipped:
            _logger.error(
                "sitemap route: skipped malformed job_cache docs",
                extra={"skipped_job_ids": skipped},
            )

        urls = _build_sitemap_urls(snapshots, base_url=PUBLIC_BASE_URL)
        try:
            rendered = render_sitemap(urls)
        except Exception:
            # silent-failure-hunter finding (2026-08-09): fetch was already
            # protected above, but this Jinja2 render call was not — the
            # same "fetch/render split protection" every other route in this
            # module applies (`_render_detail`/`_render_list`'s callers).
            _logger.exception("render error", extra={"kind": "sitemap", "url_count": len(urls)})
            return Response(content="temporarily unavailable", status_code=503)
        proxy_cache.set_list(_SITEMAP_CACHE_KEY, rendered)
        _logger.info("cache miss → rendered", extra={"kind": "sitemap", "url_count": len(urls)})
        return Response(content=rendered, media_type="application/xml")

    # Stage 4 P1-2 (2026-08-09). Deliberately asymmetric with `/sitemap.xml`
    # above: robots.txt itself answering 5xx can make a crawler pause
    # crawling the *entire* site (it's the first thing fetched), so a
    # missing `PUBLIC_BASE_URL` degrades to "no Sitemap: line" here instead
    # of an error status — the rest of robots.txt is still valid and useful
    # without it. `/assets/` is intentionally NOT disallowed: blocking CSS/
    # JS fetches would make Google unable to render the page, which is a
    # worse outcome than crawling a few style sheets.
    @app.get("/robots.txt")
    async def get_robots_txt() -> Response:
        lines = [
            "User-agent: *",
            "Allow: /",
            "Disallow: /healthz",
            "Disallow: /jobs/search-index.json",
        ]
        if not PUBLIC_BASE_URL:
            _logger.error("robots.txt requested but PUBLIC_BASE_URL is unset — omitting Sitemap:")
        else:
            lines.append(f"Sitemap: {PUBLIC_BASE_URL}/sitemap.xml")
        return Response(content="\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")

    # Stage 4 P0-3 (2026-08-09): Phase A's static filenames, permanently
    # redirected to this service's equivalent route. The single required
    # entry is `/index.html` through `/jobs-it.html` — the whole block below
    # is a low-cost insurance policy for browser history / bookmarks / any
    # external link still shaped like the GitHub Pages mockup, not just the
    # trailing-slash job-detail case (below) that Phase A's own canonical
    # tags actually declare.
    @app.get("/index.html")
    async def redirect_legacy_index() -> Response:
        return RedirectResponse(url="/", status_code=301)

    @app.get("/jobs.html")
    async def redirect_legacy_jobs_list(job_type: str | None = None) -> Response:
        category_id = _LEGACY_CATEGORY_IDS.get(job_type) if job_type else None
        target = f"/jobs/?category_id={category_id}" if category_id else "/jobs/"
        return RedirectResponse(url=target, status_code=301)

    @app.get("/jobs-{legacy_key}.html")
    async def redirect_legacy_category_page(legacy_key: str) -> Response:
        category_id = _LEGACY_CATEGORY_IDS.get(legacy_key)
        if category_id is None:
            raise HTTPException(status_code=404, detail="not found")
        return RedirectResponse(url=f"/jobs/?category_id={category_id}", status_code=301)

    # `job-preview.html` was a Phase 0 rendering-harness sample with no
    # user-facing equivalent — 301s to the nearest useful destination (the
    # all-jobs page) rather than 404ing, since it was never reachable on
    # `recruit.aozora-cg.com` (DNS unregistered as of this writing) and so
    # has no external backlinks to preserve with a more specific target.
    @app.get("/job-preview.html")
    async def redirect_legacy_job_preview() -> Response:
        return RedirectResponse(url="/jobs/", status_code=301)

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

    # Stage 4 P0-3 (2026-08-09), highest-priority entry in this whole block:
    # Phase A's 37 sample job pages already declare
    # `<link rel="canonical" href="https://recruit.aozora-cg.com/jobs/{id}/">`
    # (trailing slash). Starlette's `redirect_slashes` default answers this
    # shape with a 307 (temporary) — the wrong signal to hand a search engine
    # for a URL it may already have indexed. This overrides that fallback
    # with an explicit 301. No `is_ascii_digit_id` check here: an invalid id
    # still redirects (301, one hop) and lets `/jobs/{job_id}` apply its own
    # validation and 404 — duplicating the check here would just be a second
    # place for that rule to drift out of sync with the real route.
    @app.get("/jobs/{job_id}/")
    async def redirect_trailing_slash_job_detail(job_id: str) -> Response:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=301)

    # Stage 3 — `map-search.js`'s filter/map/GPS dataset. Registered before
    # `/jobs/{job_id}` for the same reason as the `.html` redirect above:
    # that route is an unconstrained single-segment wildcard and would
    # otherwise swallow this path first (404-ing on `is_ascii_digit_id`)
    # since Starlette matches routes in registration order.
    #
    # Deliberately NOT under `/assets/` — that path is the `StaticFiles`
    # mount over `mockup/assets`, which still physically contains Phase A's
    # stale 37-job `assets/data/jobs.json` (verified serving 200 in
    # production, 2026-08-09); a route nested under `/assets/` would either
    # collide with or be shadowed by that mount. See `search_index.py`.
    @app.get("/jobs/search-index.json")
    async def get_job_search_index() -> Response:
        cached = proxy_cache.get_json(_ALL_JOBS_CACHE_KEY)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "search-index"})
            return JSONResponse(content=cached)

        try:
            snapshots, skipped = await run_in_threadpool(lambda: _resolve_repo().get_all_valid())
        except Exception:
            _logger.exception("firestore read error", extra={"kind": "search-index"})
            return JSONResponse(content={"facilities": {}, "jobs": []}, status_code=503)

        if skipped:
            _logger.error(
                "search-index route: skipped malformed job_cache docs",
                extra={"skipped_job_ids": skipped},
            )

        index, warnings = build_search_index(snapshots)
        for warning in warnings:
            _logger.warning("search-index build warning", extra={"detail": warning})
        proxy_cache.set_json(_ALL_JOBS_CACHE_KEY, index)
        _logger.info("cache miss → built", extra={"kind": "search-index"})
        return JSONResponse(content=index)

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

        category_id = _primary_category_id(snapshot)
        related: list[RelatedJob] = []
        if category_id is not None:
            # A failed "related jobs" lookup costs only the sidebar, not the
            # whole detail page — unlike the snapshot fetch above, this must
            # not turn into a 503 (Stage 2, job-detail design parity,
            # 2026-08-08). The Firestore read and the pure in-process
            # candidate filtering are caught separately (second-opinion
            # review finding) so a bug in `_build_related_jobs` itself
            # (e.g. a malformed `job_id` breaking its numeric sort) isn't
            # mislogged as "firestore read error" — that label must mean
            # Firestore was actually the problem.
            try:
                candidates = await run_in_threadpool(
                    lambda: _resolve_repo().get_by_category(category_id)
                )
            except Exception:
                candidates = []
                _logger.exception(
                    "firestore read error", extra={"kind": "related", "job_id": job_id}
                )
            if candidates:
                try:
                    related = _build_related_jobs(candidates, exclude_job_id=job_id)
                except Exception:
                    _logger.exception(
                        "related jobs build error", extra={"kind": "related", "job_id": job_id}
                    )

        rendered = _render_detail(snapshot, job_id=job_id, category_id=category_id, related=related)
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
        category_id: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
    ) -> Response:
        # Stage 3: `category_id` omitted → the all-jobs search page (Phase
        # A's `jobs.html` equivalent — every active posting, chip/freeword/
        # map/GPS search client-side). Present → the plain per-category card
        # grid unchanged since Stage 1 (Phase A's `jobs-{care,...}.html`
        # equivalent — no search panel).
        if category_id is not None and not is_ascii_digit_id(category_id):
            raise HTTPException(status_code=404, detail="not found")

        cache_key = category_id if category_id is not None else _ALL_JOBS_CACHE_KEY
        fallback_category_id = category_id or "18773"

        cached = proxy_cache.get_list(cache_key)
        if cached is not None:
            _logger.info("cache hit", extra={"kind": "list", "category_id": cache_key})
            return HTMLResponse(content=cached)

        try:
            snapshots, skipped = await run_in_threadpool(lambda: _resolve_repo().get_all_valid())
        except Exception:
            _logger.exception(
                "firestore read error", extra={"kind": "list", "category_id": cache_key}
            )
            return _firestore_error_response(
                JOBCAN_LIST_FALLBACK.format(category_id=fallback_category_id)
            )

        if skipped:
            _logger.error(
                "list route: skipped malformed job_cache docs",
                extra={"category_id": cache_key, "skipped_job_ids": skipped},
            )

        rendered = _render_list(snapshots, category_id=category_id)
        if rendered is None:
            fallback_url = JOBCAN_LIST_FALLBACK.format(category_id=fallback_category_id)
            return HTMLResponse(
                content=_error_html(
                    title="ページを表示できません",
                    message="一時的な問題が発生しました。元のページをご覧ください。",
                    fallback_url=fallback_url,
                ),
                status_code=500,
            )

        proxy_cache.set_list(cache_key, rendered)
        _logger.info("cache miss → rendered", extra={"kind": "list", "category_id": cache_key})
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


def _build_sitemap_urls(snapshots: dict[str, JobSnapshot], *, base_url: str) -> list[str]:
    """Pure function (no Firestore/Jinja2) building the absolute URL list
    for `sitemap.xml` (Stage 4 P1-1, 2026-08-09) — split out from the route
    handler so this specific decision (which pages count as "worth
    crawling") is unit-testable without a TestClient.

    `active` jobs only: `closed` postings stay up (SEO / 被リンク維持,
    `render_job_detail`'s own docstring) but aren't linked from anywhere in
    the live site once removed from listings — putting them in the sitemap
    would be the *only* place advertising them, which contradicts the
    internal link structure instead of just tolerating an orphaned page.
    Category URLs come from `_LEGACY_CATEGORY_IDS`'s 6 distinct ids (the
    ones actually linked from the top page), not the full 17-category
    `crawler.KNOWN_CATEGORY_IDS` — a sitemap enumerates the information
    architecture, not every query string that happens to work.
    """
    urls = [f"{base_url}/", f"{base_url}/jobs/"]
    urls += [
        f"{base_url}/jobs/?category_id={category_id}"
        for category_id in dict.fromkeys(_LEGACY_CATEGORY_IDS.values())
    ]
    urls += [
        f"{base_url}/jobs/{job_id}"
        for job_id, snapshot in snapshots.items()
        if snapshot.sync_status == "active"
    ]
    return urls


def _primary_category_id(snapshot: JobSnapshot) -> str | None:
    """The category the "related jobs" sidebar (and every back/breadcrumb
    link) is built from — `None` for a `category_ids`-less snapshot (never
    produced by a real `crawl_all()` run, but not schema-impossible).
    `render_job_detail` treats `category_id=None` as "link back to `/`
    instead of a category listing" (Stage 2, job-detail design parity,
    2026-08-08)."""
    return snapshot.category_ids[0] if snapshot.category_ids else None


def _build_related_jobs(
    candidates: list[JobSnapshot], *, exclude_job_id: str
) -> list[RelatedJob]:
    """Turns same-category snapshots (`firestore_repo.get_by_category`'s
    result) into the `.aside-card__list` sidebar entries — pure, no
    Firestore access, so this is unit-testable without a client/event loop.
    The Firestore call itself stays inline in the route handler, matching
    every other read in this module (`_render_list`/`_render_detail` are
    likewise pure; `_resolve_repo()` is a `create_app()`-local closure, not
    reachable from a module-level function).
    """
    # Deterministic ordering (see `_render_list`'s identical newest-first
    # rationale) — job_id has no fixed digit width, so numeric, not
    # lexicographic, sort.
    filtered = [c for c in candidates if c.job_id != exclude_job_id]
    filtered.sort(key=lambda c: int(c.job_id), reverse=True)
    return [
        RelatedJob(
            job_id=c.job_id,
            title=c.offer.title,
            detail_url=f"/jobs/{c.job_id}",
            region_tag=extract_region_tag(c.offer.address),
        )
        for c in filtered[:_RELATED_JOBS_LIMIT]
    ]


def _render_detail(
    snapshot: JobSnapshot,
    *,
    job_id: str,
    category_id: str | None = None,
    related: list[RelatedJob] | None = None,
) -> str | None:
    """Render one snapshot's detail page. `None` signals a render failure.

    Render-time failures (Jinja2 `TemplateError`, an unexpected attribute
    error) should be rare — `snapshot.offer` is already a validated
    `JobOffer` — but the CLI (`cli.py render`) and the old fetch-per-request
    proxy both guarded this call, so this keeps the same defensive posture
    instead of leaking a stack trace to the client.
    """
    try:
        return render_job_detail(
            snapshot.offer,
            closed=snapshot.sync_status == "closed",
            base_url=PUBLIC_BASE_URL,
            category_id=category_id,
            thumbnail_url=snapshot.list_item.thumbnail_url if snapshot.list_item else None,
            related=related,
        )
    except Exception:
        _logger.exception("render error", extra={"kind": "detail", "job_id": job_id})
        return None


def _render_list(snapshots: dict[str, JobSnapshot], *, category_id: str | None) -> str | None:
    """Build and render the listing page from already-read snapshots, or
    `None` on a render failure. `category_id=None` (Stage 3) builds the
    all-jobs search page instead of one category's card grid.

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
        card_views: list[JobListCardView] = []
        for snapshot in snapshots.values():
            if snapshot.sync_status != "active":
                continue
            if category_id is not None and category_id not in snapshot.category_ids:
                continue
            view = build_card_view(snapshot)
            if view is None:
                continue
            rewritten_item = _rewrite_detail_url(view.item, view.item.job_id)
            card_views.append(view.model_copy(update={"item": rewritten_item}))

        # Numeric, not lexicographic (str sort would put "10000000" before
        # "9999999") — job_id has no fixed digit width. Descending as a
        # deterministic newest-first proxy: Firestore has no listing-order
        # info to replicate Jobcan's own display order, and job_ids increase
        # monotonically (review-code-b8 second-opinion finding).
        card_views.sort(key=lambda v: int(v.item.job_id), reverse=True)
        fallback_category_id = category_id or "18773"
        page = JobListPage(
            source_url=JOBCAN_LIST_FALLBACK.format(category_id=fallback_category_id),
            category_id=category_id,
            items=[v.item for v in card_views],
            total_count=len(card_views),
            last_page=1,
            next_url=None,
        )
        search_mode = category_id is None
        return render_job_list(
            page,
            base_url=PUBLIC_BASE_URL,
            cards=card_views,
            search_mode=search_mode,
            search_index_url="/jobs/search-index.json" if search_mode else None,
        )
    except Exception:
        _logger.exception("render error", extra={"kind": "list", "category_id": category_id})
        return None


# ASGI entrypoint for `uvicorn sync.app:app` / Docker CMD.
# `__name__ == "__main__"` is intentionally NOT used: uvicorn imports this
# module and looks up `app` directly, so the bare module-level construction
# is the right shape for Cloud Run as well (`uvicorn sync.app:app`).
app = create_app()
