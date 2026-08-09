"""`run_sync` tests — Jobcan HTTP calls mocked via respx, Firestore via the
shared `FakeFirestoreClient` (conftest.py), ops notifications via monkeypatch.
No real network or GCP call happens in this file."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

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


def _list_html(job_ids: list[str], *, total_count: int | None = None) -> str:
    """`total_count` defaults to `len(job_ids)` — an accurate `.pagination-number`
    — so ordinary tests never accidentally trigger `reconciliation_mismatch`
    just because they don't care about it. Pass an explicit mismatched value
    to test the reconciliation check itself."""
    if total_count is None:
        total_count = len(job_ids)
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
    return f"""<html><body>
        <div class="pagination-number">{total_count}&nbsp;件</div>
        {cards}
    </body></html>"""


def _mock_all_categories_return(job_ids: list[str], *, total_count: int | None = None) -> None:
    """Every category_id in KNOWN_CATEGORY_IDS returns the same tiny listing
    — the orchestrator dedupes across categories, so this still yields
    exactly `job_ids` worth of detail fetches."""
    from sync.crawler import KNOWN_CATEGORY_IDS

    html = _list_html(job_ids, total_count=total_count)
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
    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
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
    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
    _mock_all_categories_return(["1"])
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert repo.get_all()["1"].sync_status == "active"
    assert result.written is True


@respx.mock
def test_run_sync_stores_list_item_and_category_ids_on_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B-8: `app.py` serves category listings straight from the Firestore
    snapshot, so `run_sync` must actually persist `list_item`/`category_ids`
    end to end (crawler -> closed_detection -> Firestore), not just compute
    them and drop them."""
    from sync.crawler import KNOWN_CATEGORY_IDS

    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
    _mock_all_categories_return(["1"])
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    snap = repo.get_all()["1"]
    assert snap.list_item is not None
    assert snap.list_item.job_id == "1"
    # every mocked category listed job_id "1" (`_mock_all_categories_return`
    # mocks the same listing HTML for every category_id), so it must be
    # associated with all of them, not just the first one seen.
    assert set(snap.category_ids) == set(KNOWN_CATEGORY_IDS)


@respx.mock
def test_run_sync_second_run_promotes_unchanged_job_bookkeeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job approved after run 1 must stay `active` (not regress to
    pending_review) when it reappears unchanged in run 2."""
    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
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
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)

    repo = JobCacheRepository(FakeFirestoreClient())
    # Seed 10 jobs each already 1 absence away from closing (bypassing a real
    # prior run) — closed detection requires BOTH 2 *consecutive* absences
    # AND 48h elapsed since `first_absent_at`, so a fresh absence_count=0
    # seed (or one with first_absent_at=_NOW) would only reach absence_count=1
    # this run with 0h elapsed and never trip the breaker.
    for i in range(1, 11):
        snap = snapshot_from_offer(_offer_stub(str(i)), now=_NOW, absence_count=1).model_copy(
            update={"first_absent_at": _NOW - timedelta(hours=48)}
        )
        repo.set(snap)

    # Every category still lists successfully (fully_listed=True) but none of
    # them mention job_ids 1-10 — a genuine absence, not a listing failure.
    # (An empty `.job-offer-box` listing would itself raise
    # JobcanStructureChangeError, which is a *different* signal this fix
    # deliberately treats as "unknown," not "closed" — see the P1 codex
    # finding this test guards against.)
    _mock_all_categories_return(["999"])

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
def test_run_sync_circuit_breaker_message_uses_unicode_emoji_not_slack_shortcodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google Chat renders no `:shortcode:` syntax — Slack's `:rotating_light:`
    would reach the ops channel as literal text. Guards against Slack notation
    creeping back into the alert path (2026-08-09 Slack -> Google Chat move)."""
    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)

    repo = JobCacheRepository(FakeFirestoreClient())
    for i in range(1, 11):
        snap = snapshot_from_offer(_offer_stub(str(i)), now=_NOW, absence_count=1).model_copy(
            update={"first_absent_at": _NOW - timedelta(hours=48)}
        )
        repo.set(snap)
    _mock_all_categories_return(["999"])

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.circuit_breaker_tripped is True
    assert len(alerts) == 1
    assert "🚨" in alerts[0]
    assert re.search(r":[a-z_]+:", alerts[0]) is None


@respx.mock
def test_run_sync_warning_message_uses_unicode_emoji_not_slack_shortcodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same guard for the non-fatal warning path — `⚠️` must carry the VS16
    (U+FE0F) so it renders in colour rather than as a monochrome glyph."""
    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)
    _mock_all_categories_return(["1"], total_count=5)
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.reconciliation_mismatch is True
    assert len(alerts) == 1
    assert "⚠️" in alerts[0]
    assert re.search(r":[a-z_]+:", alerts[0]) is None


@respx.mock
def test_run_sync_notifies_ops_on_crawl_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from sync.crawler import KNOWN_CATEGORY_IDS

    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)

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


@respx.mock
def test_run_sync_reconciliation_matches_when_counts_agree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every category reports total_count=1 and lists exactly 1 job — no
    reconciliation warning, even though the job is cross-listed in all 17
    categories and collapses to 1 via dedup (that dedup must not itself read
    as a mismatch; see `crawler.CrawlResult`'s docstring)."""
    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)
    _mock_all_categories_return(["1"], total_count=1)
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.reconciliation_mismatch is False
    assert alerts == []


@respx.mock
def test_run_sync_warns_on_reconciliation_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every category claims total_count=5 but only lists 1 job — a silent
    partial crawl (e.g. a half-rendered listing page) that per-request error
    handling alone wouldn't catch."""
    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)
    _mock_all_categories_return(["1"], total_count=5)
    repo = JobCacheRepository(FakeFirestoreClient())

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.reconciliation_mismatch is True
    assert len(alerts) == 1
    assert "不一致" in alerts[0]


@respx.mock
def test_run_sync_circuit_breaker_message_includes_crawl_error_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A circuit-breaker trip must not silently swallow a separate
    crawl-errors warning just because it returns early — both must reach the
    same ops message, or an on-call responder reading only the closed-rate
    alert could mistake a broken crawl for genuine mass closure.

    Uses a per-job detail-fetch failure (not a category-listing failure) to
    produce a crawl error — a category-listing failure sets
    `fully_listed=False`, which (correctly, per the P1 fix) suppresses ALL
    absence-bookkeeping this run and would prevent the circuit breaker from
    tripping at all, defeating this test's premise."""
    from sync.crawler import KNOWN_CATEGORY_IDS

    alerts: list[str] = []
    monkeypatch.setattr(orchestrator, "notify_ops", alerts.append)
    repo = JobCacheRepository(FakeFirestoreClient())

    # Seed 10 jobs one absence away from closing (both the count floor and
    # the 48h duration gate must be satisfied for this run to close them).
    for i in range(1, 11):
        snap = snapshot_from_offer(_offer_stub(str(i)), now=_NOW, absence_count=1).model_copy(
            update={"first_absent_at": _NOW - timedelta(hours=48)}
        )
        repo.set(snap)

    # Every category lists successfully (fully_listed stays True) but only
    # mentions job "999" — a genuine absence for jobs 1-10. job "999"'s
    # detail fetch then 500s, producing a crawl error without touching
    # fully_listed.
    for category_id in KNOWN_CATEGORY_IDS:
        respx.get(
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        ).mock(return_value=httpx.Response(200, text=_list_html(["999"])))
    respx.get(
        f"{JOBCAN_BASE_URL}/job_offers/999?hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))

    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.circuit_breaker_tripped is True
    assert len(result.crawl.errors) == 1
    assert len(alerts) == 1  # one message, not two separate ones
    assert "closed率" in alerts[0]
    assert "クロールエラー" in alerts[0]


@respx.mock
def test_run_sync_repeated_detail_fetch_failures_never_close_a_listed_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end regression test for the P1 codex finding: a job that stays
    listed every run but whose detail fetch keeps failing (e.g. a persistent
    Jobcan-side 500 on that one posting) must NEVER close, no matter how many
    consecutive runs this happens across — closing requires evidence the
    listing itself stopped mentioning it, which never happens here."""
    from sync.crawler import KNOWN_CATEGORY_IDS

    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
    repo = JobCacheRepository(FakeFirestoreClient())

    # Run 1: job "1" is listed and fetched successfully, becomes active.
    _mock_all_categories_return(["1"])
    with _client() as client:
        orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)
    assert repo.get_all()["1"].sync_status == "active"

    # Runs 2 and 3: job "1" is still listed everywhere, but its detail page
    # 500s both times — under the pre-fix behaviour this would have counted
    # as 2 consecutive absences and closed it.
    for category_id in KNOWN_CATEGORY_IDS:
        respx.get(
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        ).mock(return_value=httpx.Response(200, text=_list_html(["1"])))
    respx.get(
        f"{JOBCAN_BASE_URL}/job_offers/1?hide_breadcrumb=true&hide_search=true"
    ).mock(return_value=httpx.Response(500))

    for _ in range(2):
        with _client() as client:
            result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)
        assert result.newly_closed == 0
        snap = repo.get_all()["1"]
        assert snap.sync_status == "active"
        assert snap.absence_count == 0


@respx.mock
def test_run_sync_deletes_gc_eligible_closed_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `closed` job past the 30-day retention window must actually be
    deleted from Firestore by the end of a successful run — the P2 codex
    finding was that `find_gc_candidates` was never wired to a deletion."""
    monkeypatch.setattr(orchestrator, "notify_ops", lambda text: None)
    repo = JobCacheRepository(FakeFirestoreClient())

    long_closed = snapshot_from_offer(_offer_stub("old"), now=_NOW - timedelta(days=40))
    long_closed = long_closed.model_copy(
        update={"sync_status": "closed", "closed_at": _NOW - timedelta(days=31)}
    )
    recently_closed = snapshot_from_offer(_offer_stub("recent"), now=_NOW - timedelta(days=5))
    recently_closed = recently_closed.model_copy(
        update={"sync_status": "closed", "closed_at": _NOW - timedelta(days=5)}
    )
    repo.set(long_closed)
    repo.set(recently_closed)

    _mock_all_categories_return(["1"])
    with _client() as client:
        result = orchestrator.run_sync(client, repo, now=_NOW, review_bypass=True)

    assert result.gc_deleted == 1
    remaining = repo.get_all()
    assert "old" not in remaining
    assert "recent" in remaining
    assert "1" in remaining


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
