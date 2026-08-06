"""CLI tests for `render` and `list` subcommands.

Phase 2A.1b — exercises `python -m sync list --category-id <cid> --fixture <path>`
plus exit-code paths (input validation, structure change, render).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

import sync.cli as cli_module
from sync.cli import app
from sync.crawler import KNOWN_CATEGORY_IDS
from sync.jobcan_client import JOBCAN_BASE_URL
from tests.conftest import FakeFirestoreClient

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
        assert "job-detail__title" in result.stdout


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


def _mock_every_category_returns(job_ids: list[str]) -> None:
    cards = "".join(
        f'<div class="job-offer-box"><h2 class="job-offer-title">求人 {jid}</h2>'
        f'<a class="job-offer-title" href="/aozora/job_offers/{jid}">求人 {jid}</a></div>'
        for jid in job_ids
    )
    html = f"<html><body>{cards}</body></html>"
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
            repo.set(snapshot_from_offer(offer, now=datetime.now(UTC), absence_count=1))

        # Every category lists successfully (fully_listed=True) but mentions
        # only job_id "999" — a genuine absence for jobs 1-10, not a listing
        # failure. An empty `.job-offer-box` listing would itself raise
        # JobcanStructureChangeError, a different signal this fix treats as
        # "unknown," not "closed".
        _mock_every_category_returns(["999"])

        result = runner.invoke(app, ["sync-run"])

        assert result.exit_code == 5, result.output
        assert len(fake_client.store) == 10  # untouched
