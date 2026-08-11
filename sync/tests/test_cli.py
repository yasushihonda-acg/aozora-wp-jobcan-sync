"""CLI tests for `render` and `list` subcommands.

Phase 2A.1b — exercises `python -m sync list --category-id <cid> --fixture <path>`
plus exit-code paths (input validation, structure change, render).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

import sync.cli as cli_module
from sync.cli import app
from sync.crawler import KNOWN_CATEGORY_IDS
from sync.jobcan_client import JOBCAN_BASE_URL
from tests.conftest import CSV_FIXTURES_DIR, FakeFirestoreClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobcan_responses"
runner = CliRunner()


class TestListSubcommand:
    def test_renders_listing_to_stdout(self) -> None:
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(FIXTURES_DIR / "list_care.html"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "<!DOCTYPE html>" in result.stdout
        assert "求人一覧" in result.stdout
        assert "job-list-card" in result.stdout

    def test_writes_to_out_file(self, tmp_path: Path) -> None:
        out = tmp_path / "list.html"
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(FIXTURES_DIR / "list_office.html"),
                "--out",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.is_file()
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")
        # The stderr summary mentions the byte count and item count
        assert "wrote" in result.output
        assert "10 jobs" in result.output

    @pytest.mark.parametrize("bad", ["18773a", "abc", "1８7７3"])  # full-width digits
    def test_rejects_non_ascii_digits(self, bad: str) -> None:
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                bad,
                "--fixture",
                str(FIXTURES_DIR / "list_care.html"),
            ],
        )
        assert result.exit_code == 1
        assert "category_id must be ASCII digits" in result.output

    def test_structure_change_exit_code(self, tmp_path: Path) -> None:
        """An HTML file with zero `.job-offer-box` exits with code 2."""
        broken = tmp_path / "empty.html"
        broken.write_text("<html><body><p>no cards here</p></body></html>")
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(broken),
            ],
        )
        assert result.exit_code == 2
        assert "structure-change" in result.output


class TestRenderSubcommandStillWorks:
    """Regression guard: adding `list` must not break the existing `render` flow."""

    def test_render_fixture(self) -> None:
        result = runner.invoke(
            app,
            [
                "render",
                "1777023",
                "--fixture",
                str(FIXTURES_DIR / "job_1777023.html"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "<!DOCTYPE html>" in result.stdout
        assert "job-detail-hero__title" in result.stdout


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


def _mock_every_category_returns(job_ids: list[str], *, total_count: int | None = None) -> None:
    """`total_count` defaults to `len(job_ids)` — an accurate `.pagination-number`
    — so these CLI-level tests never accidentally trip `reconciliation_mismatch`
    (see the identical rationale in `test_orchestrator.py`'s `_list_html`)."""
    if total_count is None:
        total_count = len(job_ids)
    cards = "".join(
        f'<div class="job-offer-box"><h2 class="job-offer-title">求人 {jid}</h2>'
        f'<a class="job-offer-title" href="/aozora/job_offers/{jid}">求人 {jid}</a></div>'
        for jid in job_ids
    )
    pagination = f'<div class="pagination-number">{total_count}&nbsp;件</div>'
    html = f"<html><body>{pagination}{cards}</body></html>"
    for category_id in KNOWN_CATEGORY_IDS:
        respx.get(
            f"{JOBCAN_BASE_URL}/list"
            f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
        ).mock(return_value=httpx.Response(200, text=html))
    for job_id in job_ids:
        respx.get(
            f"{JOBCAN_BASE_URL}/job_offers/{job_id}?hide_breadcrumb=true&hide_search=true"
        ).mock(return_value=httpx.Response(200, text=_detail_html(job_id)))


class TestSyncRunSubcommand:
    """`sync-run` (B-6): CLI wiring only — `run_sync` itself is covered in
    depth by `test_orchestrator.py`. `get_firestore_client` is monkeypatched
    to a fake so this never touches real GCP."""

    @respx.mock
    def test_sync_run_success_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # `sync-run` builds a JobcanClient with the real default crawl_delay
        # (3s, deliberately polite toward Jobcan) — across 17 categories that
        # would make this test take ~50s+ for no reason. Skip the actual wait.
        monkeypatch.setattr("sync.jobcan_client.time.sleep", lambda seconds: None)
        monkeypatch.setattr(cli_module, "get_firestore_client", FakeFirestoreClient)
        monkeypatch.setenv("REVIEW_BYPASS", "true")
        _mock_every_category_returns(["1"])

        result = runner.invoke(app, ["sync-run"])

        assert result.exit_code == 0, result.output
        assert "added=1" in result.output
        assert "written=True" in result.output

    @respx.mock
    def test_sync_run_circuit_breaker_exits_five(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from sync.firestore_repo import JobCacheRepository
        from sync.snapshot import snapshot_from_offer

        monkeypatch.setattr("sync.jobcan_client.time.sleep", lambda seconds: None)
        fake_client = FakeFirestoreClient()
        monkeypatch.setattr(cli_module, "get_firestore_client", lambda: fake_client)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        from sync.models import JobOffer

        # first_absent_at is pinned 48h+ before the CLI's own datetime.now(UTC)
        # call inside run_sync — both the 2-absence floor and the 48h
        # duration gate must be satisfied for this run to trip the breaker.
        seed_now = datetime.now(UTC)
        first_absent_at = seed_now - timedelta(hours=48)
        repo = JobCacheRepository(fake_client)
        for i in range(1, 11):
            offer = JobOffer(
                job_id=str(i),
                title="介護職員",
                body_html="<p>本文</p>",
                address="福岡事業所",
                label="介護職 正社員",
                location="福岡県福岡市",
                salary="¥250,000",
                apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{i}",
                source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{i}",
                page_title=None,
            )
            snap = snapshot_from_offer(offer, now=seed_now, absence_count=1).model_copy(
                update={"first_absent_at": first_absent_at}
            )
            repo.set(snap)

        # Every category lists successfully (fully_listed=True) but mentions
        # only job_id "999" — a genuine absence for jobs 1-10, not a listing
        # failure. An empty `.job-offer-box` listing would itself raise
        # JobcanStructureChangeError, a different signal this fix treats as
        # "unknown," not "closed".
        _mock_every_category_returns(["999"])

        result = runner.invoke(app, ["sync-run"])

        assert result.exit_code == 5, result.output
        assert len(fake_client.store) == 10  # untouched


class TestSyncRunCsvSubcommand:
    """`sync-run-csv` (CSV-migration follow-up, 2026-08-11): Playwright-free
    CLI wiring only — `run_sync_from_crawl` itself is covered in depth by
    `test_orchestrator.py`, `crawl_from_csv` by `test_csv_ingest.py`."""

    _PAGE1 = str(CSV_FIXTURES_DIR / "job_offer_list_page1.csv")
    _BAD_HEADER = str(CSV_FIXTURES_DIR / "job_offer_list_bad_header.csv")

    def test_success_writes_and_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli_module, "get_firestore_client", FakeFirestoreClient)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        result = runner.invoke(app, ["sync-run-csv", "--csv-file", self._PAGE1])

        assert result.exit_code == 0, result.output
        assert "added=1" in result.output
        assert "written=True" in result.output

    def test_dry_run_writes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_client = FakeFirestoreClient()
        monkeypatch.setattr(cli_module, "get_firestore_client", lambda: fake_client)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        result = runner.invoke(
            app, ["sync-run-csv", "--csv-file", self._PAGE1, "--dry-run"]
        )

        assert result.exit_code == 0, result.output
        assert "added=1" in result.output
        assert "written=True" in result.output  # SyncRunResult itself still reports success
        assert fake_client.store == {}  # but nothing was actually persisted

    def test_bad_header_exits_two(self) -> None:
        result = runner.invoke(app, ["sync-run-csv", "--csv-file", self._BAD_HEADER])

        assert result.exit_code == 2, result.output
        assert "structure-change" in result.output

    def test_expected_total_feeds_reconciliation_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sync.orchestrator as orchestrator_module

        monkeypatch.setattr(orchestrator_module, "notify_ops", lambda text: None)
        monkeypatch.setattr(cli_module, "get_firestore_client", FakeFirestoreClient)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        result = runner.invoke(
            app,
            [
                "sync-run-csv",
                "--csv-file",
                self._PAGE1,
                "--expected-total",
                "382",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "added=1" in result.output


class _FakeAtsClient:
    """Stand-in for `jobcan_ats.JobcanAtsClient` — `sync-run-csv-live`
    imports the real class function-locally (see `cli.py`), so tests
    monkeypatch it at its origin (`sync.jobcan_ats.JobcanAtsClient`), not on
    `cli_module`. Copies a fixture CSV into the dest dir to stand in for a
    real browser-driven download; proves the CLI's temp-dir/fully_listed
    wiring, not the browser automation itself (that's
    `test_jobcan_ats_safety.py` + the Step 6 live verification)."""

    def __init__(self, config: object = None) -> None:
        self._fully_downloaded = True
        self._errors: list[dict[str, str]] = []

    def __enter__(self) -> _FakeAtsClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def download_published_csvs(self, dest_dir: Path):
        import shutil

        from sync.jobcan_ats import AtsDownloadResult

        dest = dest_dir / "page_1.csv"
        shutil.copy(CSV_FIXTURES_DIR / "job_offer_list_page1.csv", dest)
        return AtsDownloadResult(
            paths=[dest],
            expected_total=1,
            unfiltered_total=1,
            fully_downloaded=self._fully_downloaded,
            errors=self._errors,
        )


class TestSyncRunCsvLiveSubcommand:
    """`sync-run-csv-live` (CSV-migration follow-up, 2026-08-11): the actual
    Cloud Run Job entry point. Combines a faked `JobcanAtsClient` download
    with a real `crawl_from_csv` + `run_sync_from_crawl` against
    `FakeFirestoreClient` — proves the CLI wiring end to end without a
    browser."""

    def test_success_writes_and_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sync.jobcan_ats as jobcan_ats_module

        monkeypatch.setattr(jobcan_ats_module, "JobcanAtsClient", _FakeAtsClient)
        monkeypatch.setattr(cli_module, "get_firestore_client", FakeFirestoreClient)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        result = runner.invoke(app, ["sync-run-csv-live"])

        assert result.exit_code == 0, result.output
        assert "added=1" in result.output
        assert "written=True" in result.output
        assert "ats_errors=0" in result.output

    def test_partial_download_suppresses_absence_bookkeeping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A page that failed after retries (`fully_downloaded=False`) must
        be threaded into `CrawlResult.fully_listed` — this is what makes
        `run_sync_from_crawl` skip absence-bookkeeping on a partial download,
        the same protection the HTML path already has."""

        class _PartialFakeAtsClient(_FakeAtsClient):
            def __init__(self, config: object = None) -> None:
                super().__init__(config)
                self._fully_downloaded = False
                self._errors = [{"page": "2", "error": "JobcanAtsError: timeout"}]

        import sync.jobcan_ats as jobcan_ats_module

        monkeypatch.setattr(jobcan_ats_module, "JobcanAtsClient", _PartialFakeAtsClient)
        monkeypatch.setattr(cli_module, "get_firestore_client", FakeFirestoreClient)
        monkeypatch.setenv("REVIEW_BYPASS", "true")

        result = runner.invoke(app, ["sync-run-csv-live"])

        assert result.exit_code == 0, result.output
        assert "ats_errors=1" in result.output


class TestCsvDiffSubcommand:
    """`csv-diff` (CSV-migration follow-up, 2026-08-11): read-only, never
    calls `set_many`/`delete_many` — only `repo.get_all()`."""

    _PAGE1 = str(CSV_FIXTURES_DIR / "job_offer_list_page1.csv")
    _BAD_HEADER = str(CSV_FIXTURES_DIR / "job_offer_list_bad_header.csv")

    def test_reports_zero_mismatches_against_matching_firestore_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from sync.csv_ingest import crawl_from_csv
        from sync.firestore_repo import JobCacheRepository
        from sync.snapshot import snapshot_from_offer

        fake_client = FakeFirestoreClient()
        monkeypatch.setattr(cli_module, "get_firestore_client", lambda: fake_client)

        # Seed Firestore with the exact same offer the CSV fixture produces —
        # a real cutover-readiness scenario, not merely "diff runs without
        # crashing."
        crawl_result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
        offer = crawl_result.offers[0]
        repo = JobCacheRepository(fake_client)
        snap = snapshot_from_offer(
            offer,
            now=datetime.now(UTC),
            list_item=crawl_result.list_items[offer.job_id],
            category_ids=crawl_result.category_ids[offer.job_id],
        )
        repo.set(snap)

        result = runner.invoke(app, ["csv-diff", "--csv-file", self._PAGE1])

        assert result.exit_code == 0, result.output
        assert "common=1" in result.output
        assert "only_in_csv=0" in result.output
        assert "only_in_firestore=0" in result.output
        for field in (
            "address",
            "label",
            "location",
            "title",
            "apply_url",
            "source_url",
            "page_title",
            "salary",
            "body_html",
            "extra_lines",
            "category_ids",
        ):
            assert f"{field}: 0 mismatches" in result.output

    def test_writes_nothing_to_firestore(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_client = FakeFirestoreClient()
        monkeypatch.setattr(cli_module, "get_firestore_client", lambda: fake_client)

        result = runner.invoke(app, ["csv-diff", "--csv-file", self._PAGE1])

        assert result.exit_code == 0, result.output
        assert fake_client.store == {}

    def test_bad_header_exits_two(self) -> None:
        result = runner.invoke(app, ["csv-diff", "--csv-file", self._BAD_HEADER])

        assert result.exit_code == 2, result.output
        assert "structure-change" in result.output
