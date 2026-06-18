"""Tests for the FastAPI proxy app.

These tests intentionally never touch the real Jobcan endpoint — every
JobcanClient call is intercepted at the factory boundary by passing a
stub class to `create_app(client_factory=...)`. This keeps the test
surface aligned with the Phase 2A.2 promise that "the app implementation
is verifiable without making a single outbound Jobcan request".
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sync.app import AppConfig, create_app
from sync.cache import CacheConfig, InMemoryCache
from sync.jobcan_client import JobcanClient
from sync.models import JobcanClientError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobcan_responses"


class _StubClient:
    """Drop-in JobcanClient stub that returns a canned response.

    Implements __enter__/__exit__ so it slots into the `with JobcanClient()`
    pattern in `_fetch_and_render_detail`. `fetch_count` lets tests assert
    "the second request was a cache hit, the client was not called twice".
    """

    detail_html: str = ""
    list_html: str = ""
    detail_raises: BaseException | None = None
    list_raises: BaseException | None = None
    fetch_count: int = 0

    def __init__(self, *_a: Any, **_kw: Any) -> None:
        # NO reset here: fetch_count lives at the class level and accumulates
        # across the per-request `JobcanClient()` instantiations that happen
        # inside `_do_fetch`. `_make_stub_client` zeroes the counter on the
        # generated subclass; tests assert the final accumulated value.
        return None

    def __enter__(self) -> _StubClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def fetch_job_detail(self, job_id: str | int) -> tuple[str, str]:
        type(self).fetch_count += 1
        if type(self).detail_raises is not None:
            raise type(self).detail_raises
        url = (
            f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
            "?hide_breadcrumb=true&hide_search=true"
        )
        return url, type(self).detail_html

    def fetch_job_list(self, category_id: str | int) -> tuple[str, str]:
        type(self).fetch_count += 1
        if type(self).list_raises is not None:
            raise type(self).list_raises
        url = (
            f"https://recruit.jobcan.jp/aozora/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        )
        return url, type(self).list_html


def _make_stub_client(
    *,
    detail_html: str = "",
    list_html: str = "",
    detail_raises: BaseException | None = None,
    list_raises: BaseException | None = None,
) -> type[JobcanClient]:
    """Create a fresh stub class per test so fetch_count is isolated."""

    class Stub(_StubClient):
        pass

    Stub.detail_html = detail_html
    Stub.list_html = list_html
    Stub.detail_raises = detail_raises
    Stub.list_raises = list_raises
    Stub.fetch_count = 0
    return Stub  # type: ignore[return-value]


@pytest.fixture
def sample_detail_html() -> str:
    return (FIXTURES_DIR / "job_1777023.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_list_html() -> str:
    return (FIXTURES_DIR / "list_care.html").read_text(encoding="utf-8")


def _client_with(stub: type[JobcanClient], config: AppConfig | None = None) -> TestClient:
    cache = InMemoryCache(
        CacheConfig(
            detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time
        )
    )
    config = config or AppConfig(
        fetch_enabled=True,
        job_id_allowlist=frozenset(),
        category_id_allowlist=frozenset(),
    )
    app = create_app(config=config, cache=cache, client_factory=stub)
    return TestClient(app)


# ─────────────────────────────── /healthz ───────────────────────────────


def test_healthz_returns_200() -> None:
    stub = _make_stub_client()
    client = _client_with(stub)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_healthz_has_security_headers() -> None:
    """Every response — even success — must carry the proxy headers.

    `X-Robots-Tag` keeps the Cloud Run dev URL out of search indexes; the
    middleware should not skip the healthcheck.
    """
    stub = _make_stub_client()
    client = _client_with(stub)
    response = client.get("/healthz")

    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


# ───────────────────────────── /jobs/{job_id} ────────────────────────────


def test_get_job_detail_cache_miss_fetches_and_renders(sample_detail_html: str) -> None:
    stub = _make_stub_client(detail_html=sample_detail_html)
    client = _client_with(stub)

    response = client.get("/jobs/1777023")

    assert response.status_code == 200
    # rendered job_detail.html template emits <main class="job-detail"> wrapper
    assert "job-detail" in response.text
    assert stub.fetch_count == 1


def test_get_job_detail_cache_hit_does_not_refetch(sample_detail_html: str) -> None:
    stub = _make_stub_client(detail_html=sample_detail_html)
    client = _client_with(stub)

    client.get("/jobs/1777023")
    client.get("/jobs/1777023")

    assert stub.fetch_count == 1


def test_get_job_detail_refetches_after_cache_eviction(sample_detail_html: str) -> None:
    """After the cache loses an entry (TTL expiry or manual flush), the next
    request must reach JobcanClient again.

    TTL semantics are pinned in `test_cache.py` against a direct InMemoryCache.
    Here we use `cache.clear()` to simulate TTL eviction — the freezegun +
    async threadpool + TestClient combination does not advance the clock
    inside the wrapped fetch coroutine reliably, so this test stays focused
    on "the app respects cache state" rather than "the TTL math works".
    """
    stub = _make_stub_client(detail_html=sample_detail_html)
    cache = InMemoryCache(
        CacheConfig(
            detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time
        )
    )
    app = create_app(
        config=AppConfig(
            fetch_enabled=True,
            job_id_allowlist=frozenset(),
            category_id_allowlist=frozenset(),
        ),
        cache=cache,
        client_factory=stub,
    )
    client = TestClient(app)

    client.get("/jobs/1777023")
    cache.clear()
    client.get("/jobs/1777023")

    assert stub.fetch_count == 2


def test_get_job_detail_4xx_redirects_to_jobcan() -> None:
    """4xx from Jobcan means "not here" — fall back to the canonical page so
    the user can see the source-of-truth response."""
    stub = _make_stub_client(
        detail_raises=JobcanClientError(
            "HTTP 404 from https://recruit.jobcan.jp/aozora/job_offers/9999999"
        )
    )
    client = _client_with(stub)

    response = client.get("/jobs/9999999", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert "recruit.jobcan.jp/aozora/job_offers/9999999" in location


def test_get_job_detail_5xx_returns_503_html_with_fallback_link() -> None:
    """5xx from Jobcan means upstream is broken — surface it (not hide) so
    the user knows to retry rather than think the page truly does not exist."""
    stub = _make_stub_client(
        detail_raises=JobcanClientError(
            "Transient HTTP 503 from https://recruit.jobcan.jp/aozora/job_offers/1777023"
        )
    )
    client = _client_with(stub)

    response = client.get("/jobs/1777023", follow_redirects=False)

    assert response.status_code == 503
    assert "Jobcan" in response.text
    assert "recruit.jobcan.jp/aozora/job_offers/1777023" in response.text


def test_get_job_detail_network_error_returns_503() -> None:
    """Network exhaustion (httpx failed after retries) maps to the same 503
    HTML page as 5xx, not a redirect — there is nothing the user can do at
    the canonical URL if our network can't reach Jobcan at all."""
    stub = _make_stub_client(
        detail_raises=JobcanClientError("Network error after 3 attempts: timeout")
    )
    client = _client_with(stub)

    response = client.get("/jobs/1777023", follow_redirects=False)

    assert response.status_code == 503


def test_get_job_detail_structure_change_returns_500(broken_html: str) -> None:
    """When the parser raises JobcanStructureChangeError, the response is a
    500 HTML page — operators need to see "the parser broke" distinctly
    from "the upstream returned an error" (logs will diverge)."""
    stub = _make_stub_client(detail_html=broken_html)
    client = _client_with(stub)

    response = client.get("/jobs/1777023", follow_redirects=False)

    # broken_html lacks required selectors so parse_job_detail raises
    # JobcanStructureChangeError; app maps to 500.
    assert response.status_code == 500


def test_get_job_detail_negative_cache_returns_cached_status(
    sample_detail_html: str,
) -> None:
    """After a 4xx, the second request within the negative-cache TTL must NOT
    hit JobcanClient again — the whole point of negative caching is to absorb
    upstream pressure during outages."""
    stub = _make_stub_client(
        detail_raises=JobcanClientError(
            "HTTP 404 from https://recruit.jobcan.jp/aozora/job_offers/9999999"
        )
    )
    client = _client_with(stub)

    client.get("/jobs/9999999", follow_redirects=False)
    response = client.get("/jobs/9999999", follow_redirects=False)

    assert response.status_code == 302
    assert stub.fetch_count == 1


def test_get_job_detail_rejects_non_ascii_digits() -> None:
    """`isdigit()` accepts full-width '１２３' and Arabic-Indic digits.
    Those would 404 at Jobcan with no Japanese on the error page, so the
    proxy short-circuits with its own 404 instead (no Jobcan touch)."""
    stub = _make_stub_client()
    client = _client_with(stub)

    response = client.get("/jobs/１２３")

    assert response.status_code == 404
    assert stub.fetch_count == 0


def test_get_job_detail_allowlist_rejects_unknown_id() -> None:
    """Phase 2B-1 uses JOB_ID_ALLOWLIST to defeat ID enumeration; this test
    pins the contract that the app returns 404 (not 403) — enumeration
    probes cannot distinguish allowlist rejection from a real 404."""
    stub = _make_stub_client()
    config = AppConfig(
        fetch_enabled=True,
        job_id_allowlist=frozenset({"1777023"}),
        category_id_allowlist=frozenset(),
    )
    client = _client_with(stub, config=config)

    response = client.get("/jobs/9999999")

    assert response.status_code == 404
    assert stub.fetch_count == 0


def test_get_job_detail_fetch_disabled_returns_503_maintenance(
    sample_detail_html: str,
) -> None:
    """`JOBCAN_FETCH_ENABLED=false` is the Phase 2B-0 deployment mode: the
    Cloud Run instance is up but does NOT reach out to Jobcan. Requests get
    a 503 maintenance page; no outbound Jobcan traffic."""
    stub = _make_stub_client(detail_html=sample_detail_html)
    config = AppConfig(
        fetch_enabled=False,
        job_id_allowlist=frozenset(),
        category_id_allowlist=frozenset(),
    )
    client = _client_with(stub, config=config)

    response = client.get("/jobs/1777023")

    assert response.status_code == 503
    assert stub.fetch_count == 0


# ──────────────────────────── /jobs/?category_id= ─────────────────────────


def test_get_job_list_cache_miss_fetches_and_renders(sample_list_html: str) -> None:
    stub = _make_stub_client(list_html=sample_list_html)
    client = _client_with(stub)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 200
    assert "job-list" in response.text
    assert stub.fetch_count == 1


def test_get_job_list_cache_hit_does_not_refetch(sample_list_html: str) -> None:
    stub = _make_stub_client(list_html=sample_list_html)
    client = _client_with(stub)

    client.get("/jobs/?category_id=18773")
    client.get("/jobs/?category_id=18773")

    assert stub.fetch_count == 1


def test_get_job_list_4xx_redirects_to_jobcan() -> None:
    stub = _make_stub_client(
        list_raises=JobcanClientError(
            "HTTP 404 from https://recruit.jobcan.jp/aozora/list?category_id=99999"
        )
    )
    client = _client_with(stub)

    response = client.get("/jobs/?category_id=99999", follow_redirects=False)

    assert response.status_code == 302
    assert "recruit.jobcan.jp/aozora/list" in response.headers["location"]


def test_get_job_list_fetch_disabled_returns_503() -> None:
    stub = _make_stub_client(list_html="ignored")
    config = AppConfig(
        fetch_enabled=False,
        job_id_allowlist=frozenset(),
        category_id_allowlist=frozenset(),
    )
    client = _client_with(stub, config=config)

    response = client.get("/jobs/?category_id=18773")

    assert response.status_code == 503
    assert stub.fetch_count == 0


def test_get_job_list_structure_change_returns_500() -> None:
    """A list page that has no `.job-offer-box` raises
    JobcanStructureChangeError — must map to 500."""
    stub = _make_stub_client(list_html="<html><body>empty</body></html>")
    client = _client_with(stub)

    response = client.get("/jobs/?category_id=18773", follow_redirects=False)

    # Empty list page surfaces structure change at parse time.
    assert response.status_code == 500


def test_get_job_list_rejects_non_ascii_digits() -> None:
    stub = _make_stub_client()
    client = _client_with(stub)

    response = client.get("/jobs/?category_id=１８")

    assert response.status_code == 404
    assert stub.fetch_count == 0


# ───────────────────── env-driven AppConfig construction ─────────────────────


def test_app_config_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOBCAN_FETCH_ENABLED", raising=False)
    monkeypatch.delenv("JOB_ID_ALLOWLIST", raising=False)
    monkeypatch.delenv("CATEGORY_ID_ALLOWLIST", raising=False)

    config = AppConfig.from_env()

    assert config.fetch_enabled is True
    assert config.job_id_allowlist == frozenset()
    assert config.category_id_allowlist == frozenset()


def test_app_config_from_env_disables_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """`JOBCAN_FETCH_ENABLED=false` is the kill switch for Phase 2B-0."""
    monkeypatch.setenv("JOBCAN_FETCH_ENABLED", "false")

    config = AppConfig.from_env()

    assert config.fetch_enabled is False


def test_app_config_from_env_parses_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOB_ID_ALLOWLIST", "1777023, 1668696 ,1690435")
    monkeypatch.setenv("CATEGORY_ID_ALLOWLIST", "18773")

    config = AppConfig.from_env()

    assert config.job_id_allowlist == frozenset({"1777023", "1668696", "1690435"})
    assert config.category_id_allowlist == frozenset({"18773"})


# ─────────────────────── exception classification helpers ───────────────────


def test_classify_client_error_4xx() -> None:
    from sync.app import _classify_client_error

    assert (
        _classify_client_error(
            JobcanClientError("HTTP 404 from https://recruit.jobcan.jp/x")
        )
        == 404
    )


def test_classify_client_error_5xx_transient() -> None:
    from sync.app import _classify_client_error

    assert (
        _classify_client_error(
            JobcanClientError("Transient HTTP 503 from https://recruit.jobcan.jp/x")
        )
        == 503
    )


def test_classify_client_error_network_returns_503() -> None:
    from sync.app import _classify_client_error

    assert (
        _classify_client_error(JobcanClientError("Network error after 3 attempts: timeout"))
        == 503
    )


def test_classify_client_error_unknown_returns_500() -> None:
    from sync.app import _classify_client_error

    assert _classify_client_error(JobcanClientError("something else")) == 500


# ───────────────────────── structure change short-circuit ────────────────────


def test_pydantic_validation_error_returns_500_and_caches_negative(
    sample_detail_html: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 2A.2 code-review #1: parse_job_detail can return a JobOffer whose
    Pydantic validators raise (e.g. apply_url that the parser's domain check
    accepted but `_must_be_http_url` rejects, like `javascript:...`).

    Without an explicit `except PydanticValidationError`, the proxy returns
    FastAPI's default 500 and skips negative caching → connection floods
    re-fetch on every retry.
    """
    from sync import app as app_module

    def _raise_pydantic(*_args: Any, **_kwargs: Any) -> None:
        # Construct a real Pydantic ValidationError by instantiating a model
        # with a value the validator rejects — simpler than building one by
        # hand and exercises the exact failure shape app.py sees in prod.
        from sync.models import JobOffer

        JobOffer(
            job_id="1777023",
            title="t",
            body_html="<p>x</p>",
            address="a",
            label="l",
            location="loc",
            salary="s",
            apply_url="javascript:alert(1)",  # not http(s) → ValidationError
            source_url="https://recruit.jobcan.jp/aozora/job_offers/1777023",
        )

    # app.py imports `parse_job_detail` at module load time, so patching the
    # `sync.parser` module has no effect — the app holds its own bound name.
    # Replace the binding in `sync.app` instead.
    monkeypatch.setattr(app_module, "parse_job_detail", _raise_pydantic)

    stub = _make_stub_client(detail_html=sample_detail_html)
    cache = InMemoryCache(
        CacheConfig(
            detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time
        )
    )
    app = create_app(
        config=AppConfig(
            fetch_enabled=True,
            job_id_allowlist=frozenset(),
            category_id_allowlist=frozenset(),
        ),
        cache=cache,
        client_factory=stub,
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/jobs/1777023", follow_redirects=False)

    assert response.status_code == 500
    assert "求人情報の検証に失敗しました" in response.text
    # Second request hits the negative cache; no re-fetch even though the
    # stub returns valid HTML — the failure path must absorb retries.
    client.get("/jobs/1777023", follow_redirects=False)
    assert stub.fetch_count == 1


def test_render_exception_returns_500_and_caches_negative(
    sample_detail_html: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 2A.2 code-review #2: cli.py wraps render in `except Exception`
    so Jinja2 TemplateError / AttributeError on malformed offer fields surface
    as a controlled exit. The proxy must do the same so a template bug does
    not leak stack traces and force every retry to re-fetch Jobcan."""
    from sync import app as app_module

    def _raise_jinja(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("simulated Jinja2 TemplateError")

    monkeypatch.setattr(app_module, "render_job_detail", _raise_jinja)

    stub = _make_stub_client(detail_html=sample_detail_html)
    cache = InMemoryCache(
        CacheConfig(
            detail_ttl=10.0, list_ttl=5.0, negative_ttl=2.0, maxsize=8, timer=time.time
        )
    )
    app = create_app(
        config=AppConfig(
            fetch_enabled=True,
            job_id_allowlist=frozenset(),
            category_id_allowlist=frozenset(),
        ),
        cache=cache,
        client_factory=stub,
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/jobs/1777023", follow_redirects=False)

    assert response.status_code == 500
    assert "一時的な問題が発生しました" in response.text
    client.get("/jobs/1777023", follow_redirects=False)
    assert stub.fetch_count == 1


def test_structure_change_sets_negative_cache(broken_html: str) -> None:
    """After a JobcanStructureChangeError, the second request inside the
    negative-cache TTL should NOT re-attempt the fetch — operators should
    have time to push a selector fix without amplifying load on Jobcan."""
    stub = _make_stub_client(detail_html=broken_html)
    client = _client_with(stub)

    client.get("/jobs/1777023", follow_redirects=False)
    client.get("/jobs/1777023", follow_redirects=False)

    # Second request hits the negative cache (500 → maintenance page), no refetch.
    assert stub.fetch_count == 1
