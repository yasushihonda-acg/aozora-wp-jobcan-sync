"""Tests for the FastAPI proxy app.

B-8: the proxy serves every request from a `JobCacheRepository` — no Jobcan
HTTP call is possible from within `app.py` anymore, so these tests build a
`JobCacheRepository` against the shared `FakeFirestoreClient` (conftest.py)
and seed it directly with `JobSnapshot`s instead of mocking any network call.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from sync.app import create_app
from sync.cache import CacheConfig, InMemoryCache
from sync.firestore_repo import JobCacheRepository
from sync.models import JobListItem, JobOffer
from sync.snapshot import JobSnapshot, snapshot_from_offer
from tests.conftest import FakeFirestoreClient


def _offer(job_id: str, **overrides: Any) -> JobOffer:
    fields: dict[str, Any] = {
        "job_id": job_id,
        "title": "介護職員",
        "body_html": "<p>本文</p>",
        "address": "福岡事業所",
        "label": "介護職 正社員",
        "location": "福岡県福岡市",
        "salary": "¥250,000",
        "apply_url": f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        "source_url": f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        "page_title": None,
    }
    fields.update(overrides)
    return JobOffer(**fields)


def _list_item(job_id: str, *, labels: list[str] | None = None) -> JobListItem:
    return JobListItem(
        job_id=job_id,
        title="介護職員",
        address="福岡事業所",
        description="excerpt",
        thumbnail_url=None,
        source_thumbnail_url=None,
        detail_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        labels=labels if labels is not None else [],
    )


def _repo_with(*snapshots: JobSnapshot) -> JobCacheRepository:
    repo = JobCacheRepository(FakeFirestoreClient())
    if snapshots:
        repo.set_many(list(snapshots))
    return repo


_UNSET: Any = object()


def _snapshot(
    job_id: str,
    *,
    sync_status: str = "active",
    category_ids: list[str] | None = None,
    list_item: JobListItem | None = _UNSET,
) -> JobSnapshot:
    """`list_item=_UNSET` (the default) defaults to a populated card;
    `list_item=None` is honoured as an explicit "no card" — a plain `None`
    default couldn't distinguish the two, which previously made it
    impossible to construct the `list_item=None` case this file needs to
    test (2026-08-07 second-opinion review finding)."""
    return snapshot_from_offer(
        _offer(job_id),
        now=datetime(2026, 8, 7, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=_list_item(job_id) if list_item is _UNSET else list_item,
        category_ids=category_ids if category_ids is not None else ["18773"],
    )


def _client_with(repo: JobCacheRepository) -> TestClient:
    cache = InMemoryCache(
        CacheConfig(detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time)
    )
    app = create_app(cache=cache, repo=repo)
    return TestClient(app)


# ─────────────────────────────── /healthz ───────────────────────────────


def test_healthz_returns_200() -> None:
    client = _client_with(_repo_with())
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_healthz_has_security_headers() -> None:
    client = _client_with(_repo_with())
    response = client.get("/healthz")

    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


# ────────────────────── / (top page) + /assets/* ──────────────────────────
# Stage 1 of the Cloud Run consolidation (2026-08-08): the top page and its
# static assets are now served in-house instead of only existing on the
# Phase A GitHub Pages mockup. These tests run against the real checked-out
# `mockup/assets`/`mockup/index.html` (the module-level default paths, same
# files local dev and CI both see) rather than a fixture — there is nothing
# meaningfully fake to substitute for "does the real top page render."


def test_top_page_returns_200_html() -> None:
    client = _client_with(_repo_with())
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.startswith("<!DOCTYPE html>")


def test_top_page_is_indexable() -> None:
    """Stage 4 P0-1: the top page is a page the public should be able to
    find via search — it must NOT carry X-Robots-Tag: noindex. Still
    no-store (dynamic content, same as before)."""
    client = _client_with(_repo_with())
    response = client.get("/")

    assert response.headers.get("Cache-Control") == "no-store"
    assert "X-Robots-Tag" not in response.headers


def test_job_list_is_indexable() -> None:
    client = _client_with(_repo_with(_snapshot("1")))
    response = client.get("/jobs/")

    assert "X-Robots-Tag" not in response.headers


def test_job_detail_is_indexable() -> None:
    client = _client_with(_repo_with(_snapshot("1")))
    response = client.get("/jobs/1")

    assert "X-Robots-Tag" not in response.headers


def test_search_index_json_stays_noindex() -> None:
    """The `/jobs/` prefix match must not swallow this sibling path — it's
    a JS-only data endpoint, never a page a search result should show."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/search-index.json")

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_chatbot_knowledge_json_stays_noindex() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/chatbot-knowledge.json")

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_404_stays_noindex() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/99999999")

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_non_ascii_digit_job_id_stays_noindex() -> None:
    """Full-width digits are rejected by `is_ascii_digit_id` and 404 —
    confirms the indexable allowlist is keyed off the real validator, not a
    loose prefix match."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/１２３")

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_top_page_rewrites_job_links_to_in_house_routes() -> None:
    """The shared mockup source file still has relative
    `jobs.html`/`jobs-care.html`/... hrefs (GitHub Pages' own routes) — this
    service must rewrite them to its own `/jobs/?category_id=...` routes
    rather than leaving dead links."""
    client = _client_with(_repo_with())
    html = client.get("/").text

    assert 'href="/jobs/?category_id=18773"' in html  # 介護職
    assert 'href="/jobs/?category_id=18983"' in html  # 看護職
    assert 'href="/jobs/?category_id=18986"' in html  # ホームヘルパー
    assert 'href="/jobs/?category_id=18985"' in html  # ケアマネジャー
    assert 'href="/jobs/?category_id=58859"' in html  # 事務職
    assert 'href="/jobs/?category_id=69384"' in html  # ITエンジニア職
    assert 'href="/"' in html  # logo / 採用トップ nav / footer self-links
    assert 'href="jobs.html"' not in html
    assert 'href="jobs-care.html"' not in html
    assert 'href="index.html"' not in html
    assert "job_type=" not in html


def test_top_page_canonical_uses_public_base_url_when_set(monkeypatch: Any) -> None:
    """2026-08-08 codex review finding: the shared source's hard-coded
    `https://recruit.aozora-cg.com/` canonical/og:url is the *eventual*
    Stage 5 domain, not wherever this is actually being served from during
    Stages 1-4 — must follow `PUBLIC_BASE_URL` like the job pages do."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://aozora-sync-flry56mxwa-an.a.run.app")
    client = _client_with(_repo_with())

    html = client.get("/").text

    assert 'href="https://aozora-sync-flry56mxwa-an.a.run.app/"' in html
    assert 'content="https://aozora-sync-flry56mxwa-an.a.run.app/"' in html
    assert "recruit.aozora-cg.com" not in html


def test_top_page_canonical_left_as_is_without_public_base_url() -> None:
    """`base_url=""` (local dev, the module default) — no better value to
    substitute, the eventual-domain placeholder is harmless there."""
    client = _client_with(_repo_with())
    html = client.get("/").text

    assert 'href="https://recruit.aozora-cg.com/"' in html


def test_render_top_page_logs_when_rewrite_target_not_found(caplog: Any) -> None:
    """2026-08-08 second-opinion review finding: `_TOP_PAGE_LINK_REWRITES` is
    exact-substring matching with no static guarantee against
    `mockup/index.html` drifting out from under it — a target that matches
    nothing must be loud, not a silently dead link in production."""
    import logging

    from sync.app import _TOP_PAGE_LINK_REWRITES, _render_top_page

    with caplog.at_level(logging.ERROR, logger="sync.app"):
        html = _render_top_page("<html><body>no job links here</body></html>")

    assert "no job links here" in html  # unrelated content passes through unchanged
    assert any("rewrite target not found" in record.message for record in caplog.records)
    # One error per unmatched target, not one for the whole table
    assert len(caplog.records) == len(_TOP_PAGE_LINK_REWRITES)


def test_render_top_page_strips_phase_a_redirect_meta_tag() -> None:
    """The shared `mockup/index.html` source carries a GitHub-Pages-only
    self-redirect (`scripts/mockup-rebuild/add_pages_redirects.py`) so
    決裁者 bookmarks/visits of the legacy Phase A mock jump to Cloud Run.
    Serving that same tag back from Cloud Run's own `/` would loop the page
    into redirecting to itself — this must never reach the response body."""
    from sync.app import _render_top_page

    raw = (
        "<html><head><meta charset=\"utf-8\">"
        '<!-- phase-a-redirect -->'
        '<meta http-equiv="refresh" content="0;url=https://aozora-sync-flry56mxwa-an.a.run.app/">'
        "<!-- /phase-a-redirect -->"
        "<title>t</title></head><body>no job links here</body></html>"
    )

    html = _render_top_page(raw)

    assert "http-equiv=\"refresh\"" not in html
    assert "no job links here" in html  # unrelated content passes through unchanged


def test_render_top_page_meta_refresh_strip_is_silent_when_absent(caplog: Any) -> None:
    """No tag present (pre-script-run state, or already stripped) → no
    change, and no spurious log noise — only `_TOP_PAGE_LINK_REWRITES`'s own
    per-target ERROR logging should fire for this raw input."""
    import logging

    from sync.app import _TOP_PAGE_LINK_REWRITES, _render_top_page

    with caplog.at_level(logging.INFO, logger="sync.app"):
        html = _render_top_page("<html><body>no job links here</body></html>")

    assert "no job links here" in html
    assert len(caplog.records) == len(_TOP_PAGE_LINK_REWRITES)


def test_top_page_route_never_serves_phase_a_redirect_tag() -> None:
    """End-to-end guard against the actual production self-loop: `GET /`
    against the real, script-processed `mockup/index.html` must never carry
    the Phase-A-only redirect tag in its response body."""
    client = _client_with(_repo_with())

    html = client.get("/").text

    assert 'http-equiv="refresh"' not in html


def test_top_page_missing_file_returns_404(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "INDEX_HTML_PATH", "/nonexistent/index.html")
    client = _client_with(_repo_with())

    response = client.get("/")

    assert response.status_code == 404


def test_static_asset_is_served() -> None:
    client = _client_with(_repo_with())
    response = client.get("/assets/css/tokens.css")

    assert response.status_code == 200


def test_static_asset_is_cacheable_unlike_dynamic_pages() -> None:
    """2026-08-08 second-opinion review finding: `no-store` on every asset
    request forced a re-download on every navigation, unlike the Phase A
    GitHub Pages mockup this replaces."""
    client = _client_with(_repo_with())
    response = client.get("/assets/css/tokens.css")

    assert response.headers.get("Cache-Control") == "public, max-age=3600"


def test_static_asset_stays_noindex() -> None:
    """2026-08-09 codex review finding: `noindex` only keeps a URL out of
    search *results* — it doesn't block Googlebot from fetching the resource
    to render a public page, so individual CSS/JS/image files gain nothing
    from being indexable and would otherwise show up as their own search
    results."""
    client = _client_with(_repo_with())
    response = client.get("/assets/css/tokens.css")

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_static_asset_unknown_path_returns_404() -> None:
    client = _client_with(_repo_with())
    response = client.get("/assets/does-not-exist.css")

    assert response.status_code == 404


def test_static_asset_404_is_not_cached() -> None:
    """2026-08-08 second-opinion review finding: the first version of the
    static-asset cache-control fix applied `public, max-age=3600` to 404s
    too — a genuinely missing file (or a transient revision-rollout
    mismatch) would then stay "not found" in browser/CDN caches for an
    hour after the real file became available."""
    client = _client_with(_repo_with())
    response = client.get("/assets/does-not-exist.css")

    assert response.headers.get("Cache-Control") == "no-store"


# ───────────────────────────── custom 404 page (Stage 4 P0-2) ────────────


def test_unknown_job_id_returns_branded_html_404() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/9999999")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "見つかりません" in response.text
    assert 'href="/jobs/"' in response.text
    assert 'href="/"' in response.text


def test_unmatched_route_returns_branded_html_404() -> None:
    client = _client_with(_repo_with())
    response = client.get("/nothing-at-all")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")


def test_invalid_job_id_returns_branded_html_404() -> None:
    """`is_ascii_digit_id` rejects non-numeric ids before Firestore is even
    queried — still routes through the same branded 404, not a bare
    validation-error JSON."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/abc")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")


def test_static_asset_404_stays_json_not_html() -> None:
    """`_prefers_html_error`: a missing CSS/JS/image file is a `<link>`/
    `<img>` resolution failure nobody reads a 2KB HTML document for."""
    client = _client_with(_repo_with())
    response = client.get("/assets/does-not-exist.css")

    assert response.status_code == 404
    assert not response.headers["content-type"].startswith("text/html")


def test_json_endpoint_404_stays_json() -> None:
    """A `.json`-suffixed 404 must stay parseable as JSON — the branded HTML
    error page would turn a clean `response.json()` failure into an opaque
    `SyntaxError` for whoever's debugging the fetch."""
    client = _client_with(_repo_with())
    response = client.get("/whatever.json")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_healthz_disallowed_method_stays_default_json_handler() -> None:
    """Regression: registering the 404 handler on the StarletteHTTPException
    base class must not swallow non-404 statuses (405 here) — those still
    fall through to FastAPI's own default handler."""
    client = _client_with(_repo_with())
    response = client.post("/healthz")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/json")


def test_missing_top_page_returns_branded_html_404(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "INDEX_HTML_PATH", "/nonexistent/index.html")
    client = _client_with(_repo_with())

    response = client.get("/")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "見つかりません" in response.text


def test_404_render_failure_degrades_to_branded_500(monkeypatch: Any) -> None:
    """silent-failure-hunter finding (2026-08-09): `render_not_found()` was
    called directly inside the exception handler with no try/except —
    unlike every other render call in this module, a Jinja2 failure there
    fell all the way through to an unbranded, unlogged 500 with no
    Cache-Control/X-Robots-Tag at all (the security-headers middleware never
    got a chance to run on the raw ASGI error response)."""
    from sync import app as app_module

    def _raise(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_not_found", _raise)
    client = _client_with(_repo_with())

    response = client.get("/jobs/9999999")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    assert "一時的な問題が発生しました" in response.text
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


# ───────────────────────────── /jobs/{job_id} ────────────────────────────


def test_get_job_detail_active_renders_200() -> None:
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "job-detail-hero" in response.text
    assert "job-detail-summary__cta" in response.text
    assert "entry-cta-bar" in response.text


def test_get_job_detail_unknown_id_returns_404() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/9999999")
    assert response.status_code == 404


def test_get_job_detail_pending_review_returns_404() -> None:
    """`REVIEW_BYPASS=true` is always on (B-8 決定), so this never happens in
    practice — kept as a defensive default in case that flips back."""
    repo = _repo_with(_snapshot("1", sync_status="pending_review"))
    client = _client_with(repo)

    response = client.get("/jobs/1")
    assert response.status_code == 404


def test_get_job_detail_closed_renders_200_without_apply_cta() -> None:
    """No apply CTA anywhere — summary button, entry-cta section, header
    button, or the fixed bottom bar (Stage 2, job-detail design parity)."""
    repo = _repo_with(_snapshot("1", sync_status="closed"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "job-detail-summary__cta" not in response.text
    assert "entry-cta-bar" not in response.text
    assert "この求人に応募する" not in response.text
    assert 'class="site-header__cta"' not in response.text
    assert "募集は終了しました" in response.text


def test_get_job_detail_cache_hit_does_not_re_read_firestore() -> None:
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    client.get("/jobs/1")
    # Deleting the snapshot from Firestore after the first request simulates
    # "the underlying data is gone now" — a cache hit must still serve the
    # previous render without re-reading the repo.
    repo.delete_many(["1"])

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "job-detail" in response.text


def test_get_job_detail_rejects_non_ascii_digits() -> None:
    """`isdigit()` accepts full-width '１２３' and Arabic-Indic digits; the
    proxy short-circuits with its own 404 instead of a Firestore read."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/１２３")
    assert response.status_code == 404


def test_get_job_detail_html_suffix_redirects_to_canonical_route() -> None:
    """The chatbot widget's related-job links resolve to `/jobs/{id}.html`
    (page-relative `job.url` from `/`) — this must redirect, not 308
    (2026-08-08 codex review finding). Unchanged by Stage 4 P0-3 — this is
    the widget's own in-app navigation, not a search-engine-facing URL, so
    308 (method-preserving) stays correct where the new 301s below are
    search-engine-facing permanent moves."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/1777023.html", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/jobs/1777023"


# ─────────────── Stage 4 P0-3: legacy Phase A URL → new URL redirects ─────


def test_trailing_slash_job_detail_redirects_301_not_307() -> None:
    """Phase A's 37 sample job pages already declare
    `<link rel="canonical" href="https://recruit.aozora-cg.com/jobs/{id}/">`
    (trailing slash) — Starlette's `redirect_slashes` default answers this
    shape with a 307 (temporary), which is the wrong signal for a URL a
    search engine already has indexed under the old domain. This route
    overrides that fallback with an explicit 301."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/104625/", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["location"] == "/jobs/104625"


def test_trailing_slash_invalid_job_id_redirects_then_404s() -> None:
    """Boundary: the trailing-slash redirect itself doesn't validate the id
    — it hands off to `/jobs/{job_id}` unchanged, which then applies its own
    `is_ascii_digit_id` check. Confirms there's no double-404 or bypass."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/abc/", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["location"] == "/jobs/abc"

    followed = client.get(response.headers["location"])
    assert followed.status_code == 404


def test_legacy_static_filenames_redirect_301(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")
    client = _client_with(_repo_with())

    cases = {
        "/index.html": "/",
        "/jobs.html": "/jobs/",
        "/jobs-care.html": "/jobs/?category_id=18773",
        "/jobs-nurse.html": "/jobs/?category_id=18983",
        "/jobs-office.html": "/jobs/?category_id=58859",
        "/jobs-it.html": "/jobs/?category_id=69384",
    }
    for old_path, expected_location in cases.items():
        response = client.get(old_path, follow_redirects=False)
        assert response.status_code == 301, old_path
        assert response.headers["location"] == expected_location, old_path


def test_legacy_jobs_html_job_type_query_maps_to_category_id() -> None:
    client = _client_with(_repo_with())

    visit = client.get("/jobs.html?job_type=visit", follow_redirects=False)
    assert visit.headers["location"] == "/jobs/?category_id=18986"

    care_manager = client.get("/jobs.html?job_type=care-manager", follow_redirects=False)
    assert care_manager.headers["location"] == "/jobs/?category_id=18985"


def test_legacy_jobs_html_unknown_job_type_drops_query() -> None:
    """Anything other than the two known `job_type` values must not leak a
    literal `category_id=None` (or the raw unknown value) into the redirect
    target — falls back to the unfiltered all-jobs page."""
    client = _client_with(_repo_with())
    response = client.get("/jobs.html?job_type=unknown", follow_redirects=False)

    assert response.headers["location"] == "/jobs/"


def test_legacy_redirects_carry_noindex() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/104625/", follow_redirects=False)

    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_html_suffix_redirect_still_308_after_legacy_redirects_added() -> None:
    """Regression: adding the new `/jobs/{id}/` route must not shadow the
    existing `/jobs/{id}.html` → 308 route registered right before it."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/1777023.html", follow_redirects=False)

    assert response.status_code == 308


def test_search_index_json_route_unshadowed_by_legacy_redirects() -> None:
    """Regression: `/jobs/search-index.json` must still resolve to its own
    route, not get swallowed by the new `/jobs/{job_id}/` wildcard."""
    client = _client_with(_repo_with())
    response = client.get("/jobs/search-index.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_legacy_category_ids_are_all_known_categories() -> None:
    """A typo'd id here wouldn't 404 today — it would silently render an
    empty listing page, since `/jobs/?category_id=` filters rather than
    validates. Pin every `_LEGACY_CATEGORY_IDS` value against the crawler's
    own known-category list instead."""
    from sync import app as app_module
    from sync.crawler import KNOWN_CATEGORY_IDS

    assert set(app_module._LEGACY_CATEGORY_IDS.values()) <= set(KNOWN_CATEGORY_IDS)


def test_legacy_category_ids_match_github_pages_redirect_script() -> None:
    """pr-test-analyzer finding (2026-08-09): `scripts/mockup-rebuild/
    add_pages_redirects.py` deliberately *duplicates* (doesn't import)
    `_LEGACY_CATEGORY_IDS` — that script stays a plain-stdlib tool
    independent of `sync`'s FastAPI dependency chain. Duplication without a
    pin is a silent-drift risk: if a category id ever changes on the
    `app.py` side, the GitHub-Pages-only static redirects that script
    already stamped into 44 files would keep pointing at the stale id with
    no test, log, or runtime signal (GitHub Pages is static hosting — there
    is nothing to alert)."""
    import sys
    from pathlib import Path

    from sync.app import _LEGACY_CATEGORY_IDS

    script_dir = Path(__file__).resolve().parents[2] / "scripts" / "mockup-rebuild"
    sys.path.insert(0, str(script_dir))
    try:
        import add_pages_redirects  # pyright: ignore[reportMissingImports]
    finally:
        sys.path.remove(str(script_dir))

    combined = {**add_pages_redirects._CATEGORY_IDS, **add_pages_redirects._JOB_TYPE_CATEGORY_IDS}
    assert combined == _LEGACY_CATEGORY_IDS


def test_unknown_legacy_category_page_404s() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs-unknown.html", follow_redirects=False)

    assert response.status_code == 404


def test_get_job_detail_render_failure_returns_500(monkeypatch: Any) -> None:
    from sync import app as app_module

    def _raise(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_job_detail", _raise)
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 500
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"
    assert "一時的な問題が発生しました" in response.text


def test_get_job_detail_firestore_read_failure_returns_503(monkeypatch: Any) -> None:
    """A repo.get() failure (Firestore outage, malformed doc) must be caught
    and logged, not propagate as an unhandled exception (2026-08-07
    second-opinion review finding — this path previously had no try/except
    at all, unlike the list route)."""
    repo = _repo_with(_snapshot("1"))

    def _raise(_job_id: str) -> None:
        raise RuntimeError("simulated Firestore outage")

    monkeypatch.setattr(repo, "get", _raise)
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 503
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"
    assert "データの取得に問題が発生している可能性があります" in response.text


# ───────────────────── /jobs/{job_id} — related jobs sidebar ──────────────
# Stage 2 (job-detail design parity, 2026-08-08).


def test_get_job_detail_related_shows_same_category_excludes_self() -> None:
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        _snapshot("2", category_ids=["18773"]),
        _snapshot("3", category_ids=["58859"]),  # different category
    )
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    aside = response.text.split('class="aside-card__list"')[1]
    assert 'href="/jobs/2"' in aside
    assert 'href="/jobs/1"' not in aside  # self excluded
    assert 'href="/jobs/3"' not in aside  # different category excluded


def test_get_job_detail_related_capped_at_three() -> None:
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        *(_snapshot(str(n), category_ids=["18773"]) for n in range(2, 7)),  # 5 more
    )
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert response.text.count("aside-card__list") == 1
    # 5 candidates (2..6) minus the cap — exactly 3 survive.
    shown = sum(f'/jobs/{n}"' in response.text for n in range(2, 7))
    assert shown == 3


def test_get_job_detail_no_category_ids_hides_sidebar() -> None:
    repo = _repo_with(_snapshot("1", category_ids=[]))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "aside-card" not in response.text
    # No category_ids also means the back/breadcrumb links fall back to "/"
    # rather than a `?category_id=None` dead link.
    assert "category_id=None" not in response.text


def test_get_job_detail_related_lookup_failure_still_renders_200(monkeypatch: Any) -> None:
    """A `get_by_category` failure must cost only the sidebar, not the whole
    detail page — unlike the primary snapshot fetch, which 503s."""
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))

    def _raise(_category_id: str) -> None:
        raise RuntimeError("simulated Firestore outage")

    monkeypatch.setattr(repo, "get_by_category", _raise)
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "aside-card" not in response.text
    assert "job-detail-summary__cta" in response.text  # rest of the page is intact


# ──────────────────────────── /jobs/?category_id= ─────────────────────────


def test_get_job_list_returns_matching_active_jobs() -> None:
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        _snapshot("2", category_ids=["18988"]),
    )
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert "job-list" in response.text
    assert response.text.count("job-list-card__link") == 1


def test_get_job_list_excludes_closed_jobs() -> None:
    repo = _repo_with(_snapshot("1", sync_status="closed", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 0


def test_get_job_list_includes_job_in_multiple_categories() -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773", "18988"]))
    client = _client_with(repo)

    for category_id in ("18773", "18988"):
        response = client.get(f"/jobs/?category_id={category_id}")
        assert response.text.count("job-list-card__link") == 1


def test_get_job_list_card_links_to_in_house_detail_route() -> None:
    """Persisted `JobListItem.detail_url` stays the Jobcan absolute URL, but
    the rendered card must point at this service's own `/jobs/{id}` route —
    see `_rewrite_detail_url`'s docstring in app.py."""
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert 'href="/jobs/1"' in response.text
    # the page's own canonical link legitimately still points at Jobcan
    # (source-of-truth listing) — only the card's own click target changes.
    assert 'class="job-list-card__link" href="https://recruit.jobcan.jp' not in response.text


def test_get_job_list_empty_category_returns_200_with_no_cards() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 0


def test_get_job_list_rejects_non_ascii_digits() -> None:
    client = _client_with(_repo_with())
    response = client.get("/jobs/?category_id=１８")
    assert response.status_code == 404


def test_get_job_list_render_failure_returns_500(monkeypatch: Any) -> None:
    from sync import app as app_module

    def _raise(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_job_list", _raise)
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 500
    assert "一時的な問題が発生しました" in response.text


def test_get_job_list_excludes_pending_review_jobs() -> None:
    """Low practical urgency (`REVIEW_BYPASS=true` always on per B-8), but
    the schema/filter still supports the state and should stay verified."""
    repo = _repo_with(_snapshot("1", sync_status="pending_review", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 0


def test_get_job_list_skips_snapshot_with_no_list_item() -> None:
    """`list_item=None` should be defensive-only (every real `crawl_all()`
    job_id has one), but if it's ever missing the card must be silently
    skipped rather than blow up `_rewrite_detail_url` and 500 the whole
    category (2026-08-07 second-opinion review finding — previously untested)."""
    repo = _repo_with(_snapshot("1", category_ids=["18773"], list_item=None))
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 0


def test_get_job_list_closed_and_multi_category_combo() -> None:
    """The one state-flag combination not covered elsewhere: a `closed` job
    that's also cross-listed under two categories must vanish from both,
    not just one."""
    repo = _repo_with(_snapshot("1", sync_status="closed", category_ids=["18773", "18988"]))
    client = _client_with(repo)

    for category_id in ("18773", "18988"):
        response = client.get(f"/jobs/?category_id={category_id}")
        assert response.text.count("job-list-card__link") == 0


def test_get_job_list_firestore_read_failure_returns_503(monkeypatch: Any) -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))

    def _raise() -> None:
        raise RuntimeError("simulated Firestore outage")

    monkeypatch.setattr(repo, "get_all_valid", _raise)
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 503
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"
    assert "データの取得に問題が発生している可能性があります" in response.text


def test_get_job_list_cache_hit_does_not_re_read_firestore() -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    client = _client_with(repo)

    client.get("/jobs/?category_id=18773")
    repo.delete_many(["1"])

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 1


def test_get_job_list_malformed_doc_does_not_take_down_other_jobs() -> None:
    """A malformed document elsewhere in `job_cache` must not prevent a
    healthy job's own category listing from rendering — this is the whole
    point of using `get_all_valid()` instead of `get_all()` in the list
    route (2026-08-07 second-opinion review finding)."""
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    fake_client: FakeFirestoreClient = repo._client  # type: ignore[assignment]
    fake_client.store["bad"] = {"job_id": "bad"}  # missing every other field
    client = _client_with(repo)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 1


# ───────────────────── /jobs/ all-jobs search mode (Stage 3) ─────────────────


def test_get_job_list_no_category_id_returns_all_active_jobs() -> None:
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        _snapshot("2", category_ids=["18988"]),
        _snapshot("3", sync_status="closed", category_ids=["18773"]),
    )
    client = _client_with(repo)

    response = client.get("/jobs/")

    assert response.status_code == 200
    assert response.text.count("job-list-card__link") == 2


def test_get_job_list_no_category_id_renders_search_panel_and_map() -> None:
    client = _client_with(_repo_with(_snapshot("1", category_ids=["18773"])))

    response = client.get("/jobs/")

    assert 'id="job-search-panel"' in response.text
    assert 'id="job-map-wrap"' in response.text
    assert 'data-jobs-endpoint="/jobs/search-index.json"' in response.text


def test_get_job_list_with_category_id_has_no_search_panel() -> None:
    client = _client_with(_repo_with(_snapshot("1", category_ids=["18773"])))

    response = client.get("/jobs/?category_id=18773")

    assert 'id="job-search-panel"' not in response.text


def test_get_job_list_search_panel_renders_job_type_chips_with_counts() -> None:
    """Job-type-filter-granularity follow-up (2026-08-09): the 職種 chip row
    must reflect the Jobcan-original 17-category granularity, each labelled
    with its live posting count, not the old 4-bucket colour system."""
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        _snapshot("2", category_ids=["18773"]),
        _snapshot("3", category_ids=["18983"]),
    )
    client = _client_with(repo)

    response = client.get("/jobs/")

    assert response.text.count('data-filter-group="jobType"') == 1
    assert (
        '<button type="button" class="job-search-panel__chip" '
        'data-value="18773" aria-pressed="false">介護職'
        '<span class="job-search-panel__chip-count">2</span></button>'
    ) in response.text
    assert (
        '<button type="button" class="job-search-panel__chip" '
        'data-value="18983" aria-pressed="false">看護職'
        '<span class="job-search-panel__chip-count">1</span></button>'
    ) in response.text


def test_get_job_list_search_panel_omits_zero_count_job_type_chips() -> None:
    client = _client_with(_repo_with(_snapshot("1", category_ids=["18773"])))

    response = client.get("/jobs/")

    assert 'data-value="73697"' not in response.text  # 新卒・既卒総合職, 0 postings


def test_get_job_list_card_has_category_colour_modifier() -> None:
    item = _list_item("1", labels=["介護職", "正社員"])
    repo = _repo_with(_snapshot("1", category_ids=["18773"], list_item=item))
    client = _client_with(repo)

    response = client.get("/jobs/")

    assert "job-list-card--care" in response.text
    assert 'class="job-card__meta-grid"' in response.text


def test_get_job_list_all_jobs_cache_key_distinct_from_category_cache() -> None:
    """`/jobs/` (all jobs) and `/jobs/?category_id=18773` must not share a
    cache entry — different content behind the same `ProxyCache.get_list`
    store (`_ALL_JOBS_CACHE_KEY` vs the real category_id)."""
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"]),
        _snapshot("2", category_ids=["18988"]),
    )
    client = _client_with(repo)

    all_jobs = client.get("/jobs/")
    one_category = client.get("/jobs/?category_id=18773")

    assert all_jobs.text.count("job-list-card__link") == 2
    assert one_category.text.count("job-list-card__link") == 1


# ───────────────────── /jobs/search-index.json (Stage 3) ─────────────────────


def test_get_job_search_index_returns_json_for_active_jobs() -> None:
    repo = _repo_with(
        _snapshot(
            "1",
            category_ids=["18773"],
            list_item=_list_item("1", labels=["介護職", "正社員"]),
        )
    )
    client = _client_with(repo)

    response = client.get("/jobs/search-index.json")

    assert response.status_code == 200
    body = response.json()
    assert body["jobs"] == [
        {
            "id": "1",
            "facilityKey": "facility-福岡事業所",
            "category": "care",
            "jobTypes": ["18773"],
            "employment": ["正社員"],
            "area": None,
        }
    ]


def test_get_job_search_index_excludes_closed_jobs() -> None:
    repo = _repo_with(_snapshot("1", sync_status="closed", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/search-index.json")

    assert response.json()["jobs"] == []


def test_get_job_search_index_cache_hit_does_not_re_read_firestore() -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    client = _client_with(repo)
    client.get("/jobs/search-index.json")

    fake_client: FakeFirestoreClient = repo._client  # type: ignore[assignment]
    fake_client.store.clear()

    response = client.get("/jobs/search-index.json")
    assert len(response.json()["jobs"]) == 1


def test_get_job_search_index_firestore_read_failure_returns_503(monkeypatch: Any) -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))

    def _boom(self: Any) -> Any:
        raise RuntimeError("firestore down")

    monkeypatch.setattr(JobCacheRepository, "get_all_valid", _boom)
    client = _client_with(repo)

    response = client.get("/jobs/search-index.json")

    assert response.status_code == 503
    assert response.json() == {"facilities": {}, "jobs": []}


def test_get_job_search_index_not_shadowed_by_numeric_job_id_route() -> None:
    """`/jobs/{job_id}` is an unconstrained wildcard registered after this
    route specifically so `/jobs/search-index.json` doesn't 404 through the
    numeric-id validator first (see the route's registration-order comment
    in app.py)."""
    client = _client_with(_repo_with())

    response = client.get("/jobs/search-index.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


# ──────────────── /jobs/chatbot-knowledge.json (AIチャット連携) ────────────────


def test_get_chatbot_knowledge_returns_json_array_for_active_jobs() -> None:
    repo = _repo_with(
        _snapshot(
            "1",
            category_ids=["18773"],
            list_item=_list_item("1", labels=["介護職", "正社員"]),
        )
    )
    client = _client_with(repo)

    response = client.get("/jobs/chatbot-knowledge.json")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body == [
        {
            "id": "1",
            "title": "介護職員",
            "category": "care",
            "employment": ["正社員"],
            "area": "unknown",
            "facility": "福岡事業所",
            "city": "",
            "service_types": [],
            "url": "jobs/1",
        }
    ]


def test_get_chatbot_knowledge_excludes_closed_jobs() -> None:
    repo = _repo_with(_snapshot("1", sync_status="closed", category_ids=["18773"]))
    client = _client_with(repo)

    response = client.get("/jobs/chatbot-knowledge.json")

    assert response.json() == []


def test_get_chatbot_knowledge_cache_hit_does_not_re_read_firestore() -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))
    client = _client_with(repo)
    client.get("/jobs/chatbot-knowledge.json")

    fake_client: FakeFirestoreClient = repo._client  # type: ignore[assignment]
    fake_client.store.clear()

    response = client.get("/jobs/chatbot-knowledge.json")
    assert len(response.json()) == 1


def test_get_chatbot_knowledge_firestore_read_failure_returns_503(monkeypatch: Any) -> None:
    repo = _repo_with(_snapshot("1", category_ids=["18773"]))

    def _boom(self: Any) -> Any:
        raise RuntimeError("firestore down")

    monkeypatch.setattr(JobCacheRepository, "get_all_valid", _boom)
    client = _client_with(repo)

    response = client.get("/jobs/chatbot-knowledge.json")

    assert response.status_code == 503
    assert response.json() == []


def test_get_chatbot_knowledge_not_shadowed_by_numeric_job_id_route() -> None:
    client = _client_with(_repo_with())

    response = client.get("/jobs/chatbot-knowledge.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_get_chatbot_knowledge_cache_is_independent_of_search_index_cache() -> None:
    """Both endpoints may share the `__all__` cache key string but must not
    share a cache store — `search-index.json` returns a dict, this route
    returns a list, and a stale/wrong-shaped hit from the other endpoint's
    store would corrupt this one (`cache.py`'s `_json` vs `_json_list`)."""
    repo = _repo_with(
        _snapshot("1", category_ids=["18773"], list_item=_list_item("1", labels=["介護職"]))
    )
    client = _client_with(repo)

    client.get("/jobs/search-index.json")
    knowledge_response = client.get("/jobs/chatbot-knowledge.json")

    assert isinstance(knowledge_response.json(), list)
    assert len(knowledge_response.json()) == 1


# ─────────────────────── lazy repo resolution (import safety) ───────────────


def test_create_app_does_not_require_repo_at_construction_time() -> None:
    """`create_app()` with no injected `repo` must not construct a real
    `firestore.Client` eagerly — that would make `import sync.app` itself
    require GCP credentials (see app.py's `_resolve_repo` docstring)."""
    app = create_app()
    assert app is not None


def test_create_app_warns_when_public_base_url_unset_on_cloud_run(
    monkeypatch: Any, caplog: Any
) -> None:
    """2026-08-08 second-opinion review finding: forgetting `--set-env-vars
    PUBLIC_BASE_URL=...` on a real Cloud Run deploy silently degrades every
    canonical URL — this must be loud, not silent."""
    import logging

    from sync import app as app_module

    monkeypatch.setenv("K_SERVICE", "aozora-sync")
    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")

    with caplog.at_level(logging.WARNING, logger="sync.app"):
        create_app()

    assert any("PUBLIC_BASE_URL is unset" in record.message for record in caplog.records)


def test_create_app_does_not_warn_when_public_base_url_is_set(
    monkeypatch: Any, caplog: Any
) -> None:
    import logging

    from sync import app as app_module

    monkeypatch.setenv("K_SERVICE", "aozora-sync")
    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")

    with caplog.at_level(logging.WARNING, logger="sync.app"):
        create_app()

    assert not any("PUBLIC_BASE_URL is unset" in record.message for record in caplog.records)


def test_create_app_does_not_warn_outside_cloud_run(monkeypatch: Any, caplog: Any) -> None:
    """Local dev / tests never set `K_SERVICE` — no warning noise there."""
    import logging

    from sync import app as app_module

    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")

    with caplog.at_level(logging.WARNING, logger="sync.app"):
        create_app()

    assert not any("PUBLIC_BASE_URL is unset" in record.message for record in caplog.records)


def test_resolve_repo_builds_the_client_at_most_once(monkeypatch: Any) -> None:
    """Pins the actual behaviour `_resolve_repo`'s lazy singleton exists for
    (2026-08-07 second-opinion review finding: this was previously asserted
    only by "doesn't crash," which would still pass even if the client were
    rebuilt on every request). `/healthz` must never trigger it; the first
    `/jobs/...` request must build it exactly once; a second request must
    reuse it."""
    from sync import app as app_module

    build_count = 0

    def _fake_get_firestore_client() -> object:
        nonlocal build_count
        build_count += 1
        return FakeFirestoreClient()

    monkeypatch.setattr(app_module, "get_firestore_client", _fake_get_firestore_client)
    app = app_module.create_app()
    client = TestClient(app)

    client.get("/healthz")
    assert build_count == 0

    client.get("/jobs/1")  # 404 (empty repo) — still exercises _resolve_repo
    assert build_count == 1

    client.get("/jobs/1")
    assert build_count == 1


# ───────────────── OGP / Twitter Card (Stage 4-E, 2026-08-09) ─────────────────


def test_job_detail_route_serves_ogp_tags() -> None:
    """End-to-end wiring check: `base.html`'s `social_meta` block must reach
    the real `/jobs/{id}` response, not just `render_job_detail` in
    isolation (Phase B had no `og:*` at all before Stage 4-E)."""
    client = _client_with(_repo_with(_snapshot("1")))
    html = client.get("/jobs/1").text

    assert html.count('property="og:title"') == 1
    assert html.count('<meta property="og:type" content="article">') == 1
    assert html.count('property="og:url"') == 1
    assert html.count('property="og:image"') == 1
    assert html.count('<meta name="twitter:card" content="summary_large_image">') == 1


def test_job_list_route_serves_ogp_tags() -> None:
    client = _client_with(_repo_with(_snapshot("1")))
    html = client.get("/jobs/?category_id=18773").text

    assert html.count('<meta property="og:type" content="website">') == 1
    assert html.count('name="description"') == 1
    assert html.count('property="og:image"') == 1


def test_job_detail_route_ogp_urls_are_absolute_when_public_base_url_set(
    monkeypatch: Any,
) -> None:
    """pr-test-analyzer finding (2026-08-09): `render_job_detail(base_url=...)`
    is unit-tested for absolute og:url/og:image in `test_renderer.py`, but
    nothing previously confirmed `app.py` actually threads `PUBLIC_BASE_URL`
    through to that call on the real route — a wiring regression there
    (e.g. a future refactor dropping the `base_url=` kwarg at the call site)
    would go undetected by route-level tests that never set the env var."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with(_snapshot("1")))

    html = client.get("/jobs/1").text

    assert 'property="og:url" content="https://recruit.aozora-cg.com/jobs/1"' in html
    assert (
        'property="og:image" content="https://recruit.aozora-cg.com/assets/img/sky-hero.jpg"'
        in html
    )


def test_job_list_route_ogp_urls_are_absolute_when_public_base_url_set(
    monkeypatch: Any,
) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with(_snapshot("1")))

    html = client.get("/jobs/?category_id=18773").text

    assert (
        'property="og:image" content="https://recruit.aozora-cg.com/assets/img/sky-hero.jpg"'
        in html
    )


# ─────────────── sitemap.xml / robots.txt (Stage 4 P1-1/P1-2) ────────────

import xml.etree.ElementTree as ET  # noqa: E402

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _sitemap_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.text for el in root.iter(f"{_SITEMAP_NS}loc") if el.text is not None]


def test_sitemap_lists_top_list_categories_and_active_jobs_only(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    repo = _repo_with(_snapshot("1"), _snapshot("2", sync_status="closed"))
    client = _client_with(repo)

    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    locs = _sitemap_locs(response.text)
    assert "https://recruit.aozora-cg.com/" in locs
    assert "https://recruit.aozora-cg.com/jobs/" in locs
    assert "https://recruit.aozora-cg.com/jobs/1" in locs
    assert "https://recruit.aozora-cg.com/jobs/2" not in locs  # closed — excluded
    # top(1) + list(1) + 17 categories + 1 active job
    assert len(locs) == 20


def test_sitemap_urls_all_absolute(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with(_snapshot("1")))
    response = client.get("/sitemap.xml")

    for loc in _sitemap_locs(response.text):
        assert loc.startswith("https://")


def test_sitemap_empty_repo_still_lists_top_list_and_categories(monkeypatch: Any) -> None:
    """Boundary: zero jobs must still produce a well-formed sitemap with the
    19 static entries (top + list + 17 categories), not an empty/invalid
    doc."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with())
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert len(_sitemap_locs(response.text)) == 19  # top(1) + list(1) + 17 categories


def test_sitemap_returns_503_without_public_base_url(monkeypatch: Any) -> None:
    """A relative-URL sitemap is spec-invalid — refuse rather than emit one
    (mirrors the K_SERVICE-without-PUBLIC_BASE_URL warning `create_app`
    already logs for canonical URLs)."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")
    client = _client_with(_repo_with())

    response = client.get("/sitemap.xml")
    assert response.status_code == 503


def test_sitemap_returns_503_on_firestore_error(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")

    def _raise() -> Any:
        raise RuntimeError("simulated Firestore outage")

    client = _client_with(_repo_with())
    monkeypatch.setattr(
        app_module.JobCacheRepository, "get_all_valid", lambda self: _raise()
    )

    response = client.get("/sitemap.xml")
    assert response.status_code == 503
    assert "<urlset" not in response.text
    assert response.headers.get("Cache-Control") == "no-store"


def test_sitemap_render_failure_returns_503(monkeypatch: Any) -> None:
    """silent-failure-hunter finding (2026-08-09): the Firestore read was
    already protected by try/except, but the subsequent `render_sitemap()`
    Jinja2 call was not — same "fetch protected, render not" gap as the
    404 handler's own finding."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")

    def _raise(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_sitemap", _raise)
    client = _client_with(_repo_with(_snapshot("1")))

    response = client.get("/sitemap.xml")

    assert response.status_code == 503
    assert "<urlset" not in response.text


def test_sitemap_503_is_not_cached(monkeypatch: Any) -> None:
    """Regression: a transient 503 must not poison the cache — the next
    request (once the underlying problem clears) has to try again rather
    than replay the failure for the rest of the TTL."""
    from sync import app as app_module

    client = _client_with(_repo_with())

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")
    first = client.get("/sitemap.xml")
    assert first.status_code == 503

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    second = client.get("/sitemap.xml")
    assert second.status_code == 200


def test_sitemap_cache_hit_skips_firestore(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    build_count = 0
    original = app_module.JobCacheRepository.get_all_valid

    def _counting(self: Any) -> Any:
        nonlocal build_count
        build_count += 1
        return original(self)

    monkeypatch.setattr(app_module.JobCacheRepository, "get_all_valid", _counting)

    client.get("/sitemap.xml")
    assert build_count == 1
    client.get("/sitemap.xml")
    assert build_count == 1  # second hit served from cache


def test_sitemap_has_no_robots_tag_and_is_cacheable(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with())
    response = client.get("/sitemap.xml")

    assert "X-Robots-Tag" not in response.headers
    assert response.headers.get("Cache-Control") == "public, max-age=3600"


def test_robots_txt_references_sitemap_and_allows_assets(monkeypatch: Any) -> None:
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://recruit.aozora-cg.com")
    client = _client_with(_repo_with())

    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    body = response.text
    assert "Sitemap: https://recruit.aozora-cg.com/sitemap.xml" in body
    assert "Disallow: /healthz" in body
    assert "Disallow: /jobs/search-index.json" in body
    assert "Disallow: /jobs/chatbot-knowledge.json" in body
    assert "Disallow: /assets/" not in body  # must not block CSS/JS rendering


def test_robots_txt_degrades_gracefully_without_public_base_url(monkeypatch: Any) -> None:
    """Asymmetric with sitemap.xml on purpose: robots.txt itself returning
    5xx can make a crawler pause crawling the whole site, so a missing
    PUBLIC_BASE_URL degrades to "no Sitemap: line" rather than an error
    status."""
    from sync import app as app_module

    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "")
    client = _client_with(_repo_with())

    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "Sitemap:" not in response.text


def test_robots_txt_has_no_robots_tag() -> None:
    client = _client_with(_repo_with())
    response = client.get("/robots.txt")

    assert "X-Robots-Tag" not in response.headers


def test_robots_txt_is_cacheable() -> None:
    """pr-test-analyzer finding (2026-08-09): `_apply_security_headers`'s
    docstring says `/robots.txt` rides the same real-max-age branch as
    `/sitemap.xml` and the static assets, but no test previously asserted
    that for robots.txt specifically."""
    client = _client_with(_repo_with())
    response = client.get("/robots.txt")

    assert response.headers.get("Cache-Control") == "public, max-age=3600"
