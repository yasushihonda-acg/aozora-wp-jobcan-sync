"""`run_sync` tests — Jobcan HTTP calls mocked via respx, Firestore via the
shared `FakeFirestoreClient` (conftest.py), Slack via monkeypatch. No real
network or GCP call happens in this file."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

import sync.orchestrator as orchestrator
from sync.firestore_repo import JobCacheRepository
from sync.jobcan_client import JOBCAN_BASE_URL, JobcanClient, JobcanClientConfig
from sync.snapshot import snapshot_from_offer
from tests.conftest import FakeFirestoreClient

_NOW = datetime(2026, 8, 7, tzinfo=UTC)


def _client() -> JobcanClient:
    return JobcanClient(JobcanClientConfig(max_retries=0, retry_base_delay=0.0, crawl_delay=0.0))


def _detail_html(job_id: str) -> str:
    return f"""
    <html><body>
      <div class="job-offer-detail-title">求人 {job_id}</div>
      <div class="job-offer-description-full">本文 {job_id}</div>
      <div class="job-offer-address">拠点 {job_id}</div>
      <div class="job-offer-label">介護職 正社員</div>
      <a href="/aozora/entry/new/{job_id}">apply</a>
      <div class="job-offer-table">
        <div class="content-table-line">
          <div class="content-table-head">勤務地</div>
          <div class="td-contentTable__breakWordWrap">福岡</div>
        </div>
        <div class="content-table-line">
          <div class="content-table-head">給与</div>
          <div class="td-contentTable__breakWordWrap">¥250,000</div>
        </div>
      </div>
    </body></html>
    """


def _list_html(job_ids: list[str]) -> str:
    cards = "".join(
        f"""
        <div class="job-offer-box">
          <h2 class="job-offer-title">求人 {jid}</h2>
          <a class="job-offer-title" href="/aozora/job_offers/{jid}?hide_breadcrumb=false">
            求人 {jid}
          </a>
        </div>
        """
        for jid in job_ids
    )
    return f"<html><body>{cards}</body></html>"


def _mock_all_categories_return(job_ids: list[str]) -> None:
    """Every category_id in KNOWN_CATEGORY_IDS returns the same tiny listing
    — the orchestrator dedupes across categories, so this still yields
    exactly `job_ids` worth of detail fetches."""
    from sync.crawler import KNOWN_CATEGORY_IDS

    html = _list_html(job_ids)
    for category_id in KNOWN_CATEGORY_IDS:
        url = (
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        )
        respx.get(url).mock(return_value=httpx.Response(200, text=html))
    for job_id in job_ids:
        detail_url = (
            f"{JOBCAN_BASE_URL}/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
        )
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=_detail_html(job_id)))


@respx.mock
def test_run_sync_writes_new_jobs_as_pending_review(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "notify_slack", lambda text: None)
    _mock_all_categories_return(["1"])
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=False)

    assert result.written is True
    assert result.added == 1
    assert result.circuit_breaker_tripped is False
    snapshots = repo.get_all()
    assert snapshots["1"].sync_status == "pending_review"


@respx.mock
def test_run_sync_review_bypass_true_writes_jobs_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "notify_slack", lambda text: None)
    _mock_all_categories_return(["1"])
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert repo.get_all()["1"].sync_status == "active"
    assert result.written is True


@respx.mock
def test_run_sync_second_run_promotes_unchanged_job_bookkeeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job approved after run 1 must stay `active` (not regress to
    pending_review) when it reappears unchanged in run 2."""
    monkeypatch.setattr(orchestrator, "notify_slack", lambda text: None)
    repo = JobCacheRepository(FakeFirestoreClient())

    _mock_all_categories_return(["1"])
    with _client() as client:
        orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)
    assert repo.get_all()["1"].sync_status == "active"

    _mock_all_categories_return(["1"])
    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=False)

    assert result.unchanged == 1
    assert repo.get_all()["1"].sync_status == "active"


@respx.mock
def test_run_sync_circuit_breaker_trip_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_slack", alerts.append)

    repo = JobCacheRepository(FakeFirestoreClient())
    # Seed 10 jobs each already 1 absence away from closing (bypassing a real
    # prior run) — closed detection requires 2 *consecutive* absences, so a
    # fresh absence_count=0 seed would only reach absence_count=1 this run
    # and never trip the breaker.
    for i in range(1, 11):
        snap = snapshot_from_offer(_offer_stub(str(i)), now=_NOW, absence_count=1)
        repo.set(snap)

    _mock_all_categories_return([])  # every previously-active job vanishes this crawl too

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.circuit_breaker_tripped is True
    assert result.written is False
    # Firestore must be untouched — still the original 10 active snapshots.
    assert len(repo.get_all()) == 10
    assert all(s.sync_status == "active" for s in repo.get_all().values())
    assert len(alerts) == 1
    assert "closed" in alerts[0].lower() or "closed率" in alerts[0]


@respx.mock
def test_run_sync_notifies_slack_on_crawl_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from sync.crawler import KNOWN_CATEGORY_IDS

    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_slack", alerts.append)

    # First category 500s (recorded as the sole crawl error); every other
    # category returns one valid job each (an empty `.job-offer-box` listing
    # would itself raise JobcanStructureChangeError — that's not this test's
    # concern, so give every "healthy" category a real job to avoid it).
    first, *rest = KNOWN_CATEGORY_IDS
    respx.get(
        f"{JOBCAN_BASE_URL}/list?category_id={first}&hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))
    for category_id in rest:
        respx.get(
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        ).mock(return_value=httpx.Response(200, text=_list_html(["1"])))
    respx.get(
        f"{JOBCAN_BASE_URL}/job_offers/1?hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(200, text=_detail_html("1")))

    repo = JobCacheRepository(FakeFirestoreClient())
    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.written is True
    assert len(result.crawl.errors) == 1
    assert len(alerts) == 1


def _offer_stub(job_id: str):
    from sync.models import JobOffer

    return JobOffer(
        job_id=job_id,
        title="介護職員",
        body_html="<p>本文</p>",
        address="福岡事業所",
        label="介護職 正社員",
        location="福岡県福岡市",
        salary="¥250,000",
        apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        page_title=None,
    )
