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


def _list_item(job_id: str) -> JobListItem:
    return JobListItem(
        job_id=job_id,
        title="介護職員",
        address="福岡事業所",
        description="excerpt",
        thumbnail_url=None,
        source_thumbnail_url=None,
        detail_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
    )


def _repo_with(*snapshots: JobSnapshot) -> JobCacheRepository:
    repo = JobCacheRepository(FakeFirestoreClient())
    if snapshots:
        repo.set_many(list(snapshots))
    return repo


def _snapshot(
    job_id: str,
    *,
    sync_status: str = "active",
    category_ids: list[str] | None = None,
    list_item: JobListItem | None = None,
) -> JobSnapshot:
    return snapshot_from_offer(
        _offer(job_id),
        now=datetime(2026, 8, 7, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=list_item if list_item is not None else _list_item(job_id),
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


# ───────────────────────────── /jobs/{job_id} ────────────────────────────


def test_get_job_detail_active_renders_200() -> None:
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "job-detail" in response.text
    assert "job-detail__apply-btn" in response.text


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
    repo = _repo_with(_snapshot("1", sync_status="closed"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert "job-detail__apply-btn" not in response.text
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


def test_get_job_detail_render_failure_returns_500(monkeypatch: Any) -> None:
    from sync import app as app_module

    def _raise(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_job_detail", _raise)
    repo = _repo_with(_snapshot("1"))
    client = _client_with(repo)

    response = client.get("/jobs/1")

    assert response.status_code == 500
    assert "一時的な問題が発生しました" in response.text


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


# ─────────────────────── lazy repo resolution (import safety) ───────────────


def test_create_app_does_not_require_repo_at_construction_time() -> None:
    """`create_app()` with no injected `repo` must not construct a real
    `firestore.Client` eagerly — that would make `import sync.app` itself
    require GCP credentials (see app.py's `_resolve_repo` docstring)."""
    app = create_app()
    assert app is not None
