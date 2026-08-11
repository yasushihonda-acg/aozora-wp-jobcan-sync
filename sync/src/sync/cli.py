"""Phase 0 CLI: `python -m sync render <job_id>`. Phase B adds `sync-run`.
CSV-migration follow-up (2026-08-11) adds `sync-run-csv` / `csv-diff`.

Exit codes:
    0 — success (HTML rendered to stdout or --out file / sync completed)
    1 — Jobcan client error (network / HTTP failure)
    2 — JobcanStructureChangeError (selectors missing / CSV header mismatch)
    3 — JobcanValidationError (selectors found but required fields empty)
    4 — Render/template error
    5 — sync-run / sync-run-csv: closed-rate circuit breaker tripped, nothing written
    6 — ATS自動化の安全ガードが作動 (破壊的操作の可能性、実行せず中止) — jobcan_ats.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer

from ._validators import is_ascii_digit_id
from .csv_ingest import crawl_from_csv
from .firestore_repo import JobCacheRepository, get_firestore_client
from .jobcan_client import JobcanClient
from .models import JobcanClientError, JobcanStructureChangeError, JobcanValidationError
from .orchestrator import run_sync, run_sync_from_crawl
from .parser import parse_job_detail, parse_job_list
from .renderer import render_job_detail, render_job_list
from .snapshot import JobSnapshot

app = typer.Typer(
    add_completion=False,
    help="Aozora Phase B (Phase 0) — Jobcan proxy + in-house template renderer.",
    no_args_is_help=True,
)

_JOB_ID_ARG = typer.Argument(..., help="Jobcan job_offer ID (digits only)")
_OUT_OPT = typer.Option(None, "--out", "-o", help="Write HTML to this path (default: stdout)")
_FIXTURE_OPT = typer.Option(
    None,
    "--fixture",
    "-f",
    help="Read HTML from a local fixture file instead of fetching from Jobcan",
)


@app.command()
def render(
    job_id: str = _JOB_ID_ARG,
    out: Path | None = _OUT_OPT,
    fixture: Path | None = _FIXTURE_OPT,
) -> None:
    """Fetch and render a single job offer."""
    if not is_ascii_digit_id(job_id):
        typer.echo(f"job_id must be ASCII digits, got: {job_id!r}", err=True)
        raise typer.Exit(code=1)

    try:
        if fixture is not None:
            html = fixture.read_text(encoding="utf-8")
            source_url = (
                f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
                "?hide_breadcrumb=true&hide_search=true"
            )
        else:
            with JobcanClient() as client:
                source_url, html = client.fetch_job_detail(job_id)
    except JobcanClientError as exc:
        typer.echo(f"client error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        offer = parse_job_detail(html, source_url, job_id=job_id)
    except JobcanStructureChangeError as exc:
        typer.echo(f"structure-change: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except JobcanValidationError as exc:
        typer.echo(f"validation: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    try:
        rendered = render_job_detail(offer)
    except Exception as exc:
        typer.echo(f"render error: {exc}", err=True)
        raise typer.Exit(code=4) from exc

    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        byte_len = len(rendered.encode("utf-8"))
        typer.echo(f"wrote {out} ({byte_len} bytes)", err=True)
    else:
        sys.stdout.write(rendered)


_CATEGORY_OPT = typer.Option(
    ...,
    "--category-id",
    "-c",
    help="Jobcan category_id (digits only, e.g. 18773 for 介護)",
)


@app.command("list")
def list_(
    category_id: str = _CATEGORY_OPT,
    out: Path | None = _OUT_OPT,
    fixture: Path | None = _FIXTURE_OPT,
) -> None:
    """Fetch and render a Jobcan category listing page."""
    if not is_ascii_digit_id(category_id):
        typer.echo(f"category_id must be ASCII digits, got: {category_id!r}", err=True)
        raise typer.Exit(code=1)

    try:
        if fixture is not None:
            html = fixture.read_text(encoding="utf-8")
            source_url = (
                f"https://recruit.jobcan.jp/aozora/list"
                f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
            )
        else:
            with JobcanClient() as client:
                source_url, html = client.fetch_job_list(category_id)
    except JobcanClientError as exc:
        typer.echo(f"client error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        page = parse_job_list(html, source_url)
    except JobcanStructureChangeError as exc:
        typer.echo(f"structure-change: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        rendered = render_job_list(page)
    except Exception as exc:
        typer.echo(f"render error: {exc}", err=True)
        raise typer.Exit(code=4) from exc

    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        # `len(rendered)` counts characters; UTF-8 Japanese is 3 bytes/char,
        # so report the encoded byte length to match the on-disk file size.
        byte_len = len(rendered.encode("utf-8"))
        typer.echo(f"wrote {out} ({byte_len} bytes, {len(page.items)} jobs)", err=True)
    else:
        sys.stdout.write(rendered)


@app.command("sync-run")
def sync_run() -> None:
    """Full-catalogue sync (B-6): crawl -> diff -> closed-detection ->
    review-gate -> Firestore write. Entry point for the Cloud Run Job that
    Cloud Scheduler triggers every 6 hours (2026-08-08: moved from once a
    day); see `infra/README.md` §8."""
    now = datetime.now(tz=UTC)
    repo = JobCacheRepository(get_firestore_client())
    with JobcanClient() as client:
        result = run_sync(client, repo, now=now)

    typer.echo(
        f"added={result.added} changed={result.changed} unchanged={result.unchanged} "
        f"removed={result.removed} newly_closed={result.newly_closed} "
        f"gc_deleted={result.gc_deleted} "
        f"crawl_errors={len(result.crawl.errors)} written={result.written}"
    )
    if result.circuit_breaker_tripped:
        raise typer.Exit(code=5)


_OUT_DIR_OPT = typer.Option(..., "--out-dir", help="Directory to save downloaded CSVs into")
_HEADED_OPT = typer.Option(
    False, "--headed", help="Run the browser visibly instead of headless (for manual debugging)"
)


@app.command("ats-download")
def ats_download(out_dir: Path = _OUT_DIR_OPT, headed: bool = _HEADED_OPT) -> None:
    """Logs into ats.jobcan.jp and downloads the 公開状況=公開-filtered
    `job_offers` CSVs into `out_dir`, one file per page — download only, no
    Firestore write (CSV-migration follow-up, 2026-08-11). The offline
    counterpart to `sync-run-csv`'s browser-driven input: run this once,
    inspect the files, then feed them to `sync-run-csv --csv-file` or
    `csv-diff --csv-file` separately.

    Requires the `ats` extra (`uv sync --extra ats && uv run playwright
    install chromium`) — imported here, not at module level, so every other
    command works without it installed."""
    from .jobcan_ats import JobcanAtsClient, JobcanAtsConfig

    config = JobcanAtsConfig(headless=not headed)
    with JobcanAtsClient(config) as client:
        result = client.download_published_csvs(out_dir)

    typer.echo(
        f"downloaded={len(result.paths)} pages expected_total={result.expected_total} "
        f"unfiltered_total={result.unfiltered_total} "
        f"fully_downloaded={result.fully_downloaded} errors={len(result.errors)}"
    )
    for path in result.paths:
        typer.echo(f"  {path}")
    if not result.fully_downloaded:
        raise typer.Exit(code=1)


class _DryRunRepository(JobCacheRepository):
    """`set_many`/`delete_many` are no-ops — `get_all()` still reads the real
    store so `sync-run-csv --dry-run` reports an accurate diff against
    current production data without writing anything (CSV-migration
    follow-up, 2026-08-11)."""

    def set_many(self, snapshots: list[JobSnapshot]) -> None:
        pass

    def delete_many(self, job_ids: list[str]) -> None:
        pass


_CSV_FILE_OPT = typer.Option(
    ...,
    "--csv-file",
    help="Path to a downloaded job_offers CSV (repeatable for multiple pages)",
)
_DRY_RUN_OPT = typer.Option(
    False, "--dry-run", help="Diff against Firestore but write nothing"
)
_EXPECTED_TOTAL_OPT = typer.Option(
    None,
    "--expected-total",
    help=(
        "Total count from the ATS list screen's own 「NNN件中」 text "
        "(feeds the reconciliation check). Falls back to the collected row "
        "count when omitted — fine for local testing, but that makes "
        "reconciliation vacuous; a production run should always pass this."
    ),
)


@app.command("sync-run-csv")
def sync_run_csv(
    csv_file: list[Path] = _CSV_FILE_OPT,
    dry_run: bool = _DRY_RUN_OPT,
    expected_total: int | None = _EXPECTED_TOTAL_OPT,
) -> None:
    """CSV-path full-catalogue sync (CSV-migration follow-up, 2026-08-11):
    parse already-downloaded `job_offers` CSVs -> diff -> closed-detection ->
    review-gate -> Firestore write. Playwright-free — the CSVs must already
    be on disk (see `ats-download`, which does the browser-driven part
    separately). `--dry-run` diffs against real Firestore data without
    writing, for a safe dry run before the first production cutover."""
    now = datetime.now(tz=UTC)
    try:
        crawl_result = crawl_from_csv(csv_file, expected_total=expected_total)
    except JobcanStructureChangeError as exc:
        typer.echo(f"structure-change: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    firestore_client = get_firestore_client()
    repo: JobCacheRepository = (
        _DryRunRepository(firestore_client) if dry_run else JobCacheRepository(firestore_client)
    )

    result = run_sync_from_crawl(crawl_result, repo, now=now, source="csv")

    typer.echo(
        f"added={result.added} changed={result.changed} unchanged={result.unchanged} "
        f"removed={result.removed} newly_closed={result.newly_closed} "
        f"gc_deleted={result.gc_deleted} "
        f"crawl_errors={len(result.crawl.errors)} written={result.written}"
    )
    if result.circuit_breaker_tripped:
        raise typer.Exit(code=5)


@app.command("sync-run-csv-live")
def sync_run_csv_live() -> None:
    """The actual Cloud Run Job entry point (`sync/Dockerfile.job`'s CMD):
    ats-download's browser-driven CSV export followed immediately by the
    same diff -> closed-detection -> review-gate -> Firestore write
    `sync-run-csv` performs, in one process (CSV-migration follow-up,
    2026-08-11). A Cloud Run Job execution is a single container run with no
    durable disk between steps, so `ats-download` and `sync-run-csv` cannot
    be two separate scheduled steps — this command is what actually runs
    unattended every 6 hours; both split commands stay for manual/offline use
    (`ats-download` to inspect files by hand, `sync-run-csv --csv-file` /
    `csv-diff` to replay a previously-downloaded set).

    `AtsDownloadResult.fully_downloaded=False` (a page failed after retries)
    is combined into `CrawlResult.fully_listed` before the write — this is
    what makes `orchestrator.run_sync_from_crawl`'s `skip_absence_bookkeeping`
    correctly suppress absence-counting on a partial download, exactly as it
    already does for a partial HTML crawl."""
    import tempfile
    from pathlib import Path as _Path

    from .jobcan_ats import JobcanAtsClient

    now = datetime.now(tz=UTC)
    with tempfile.TemporaryDirectory(prefix="aozora-ats-") as tmp_dir:
        with JobcanAtsClient() as client:
            ats_result = client.download_published_csvs(_Path(tmp_dir))

        try:
            crawl_result = crawl_from_csv(
                ats_result.paths, expected_total=ats_result.expected_total
            )
        except JobcanStructureChangeError as exc:
            typer.echo(f"structure-change: {exc}", err=True)
            raise typer.Exit(code=2) from exc

    crawl_result.fully_listed = crawl_result.fully_listed and ats_result.fully_downloaded
    crawl_result.errors.extend(ats_result.errors)

    repo = JobCacheRepository(get_firestore_client())
    result = run_sync_from_crawl(crawl_result, repo, now=now, source="csv")

    typer.echo(
        f"added={result.added} changed={result.changed} unchanged={result.unchanged} "
        f"removed={result.removed} newly_closed={result.newly_closed} "
        f"gc_deleted={result.gc_deleted} "
        f"ats_errors={len(ats_result.errors)} crawl_errors={len(result.crawl.errors)} "
        f"written={result.written}"
    )
    if result.circuit_breaker_tripped:
        raise typer.Exit(code=5)


_DIFF_FIELDS: tuple[str, ...] = (
    "address",
    "label",
    "location",
    "title",
    "apply_url",
    "source_url",
    "page_title",
    "salary",
    "body_html",
)


@app.command("csv-diff")
def csv_diff(csv_file: list[Path] = _CSV_FILE_OPT) -> None:
    """Read-only comparison between CSV-derived postings and the current
    `job_cache` `active` snapshots (CSV-migration follow-up, 2026-08-11) —
    the cutover gate: run this and review its output BEFORE the first
    `sync-run-csv` write to production. Writes nothing."""
    try:
        crawl_result = crawl_from_csv(csv_file)
    except JobcanStructureChangeError as exc:
        typer.echo(f"structure-change: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    repo = JobCacheRepository(get_firestore_client())
    previous = repo.get_all()

    csv_job_ids = {offer.job_id for offer in crawl_result.offers}
    active_job_ids = {jid for jid, snap in previous.items() if snap.sync_status == "active"}
    common = csv_job_ids & active_job_ids

    typer.echo(
        f"job_id: csv={len(csv_job_ids)} firestore_active={len(active_job_ids)} "
        f"common={len(common)} only_in_csv={len(csv_job_ids - active_job_ids)} "
        f"only_in_firestore={len(active_job_ids - csv_job_ids)}"
    )

    offers_by_id = {offer.job_id: offer for offer in crawl_result.offers}
    for field in _DIFF_FIELDS:
        mismatches = sorted(
            jid
            for jid in common
            if getattr(offers_by_id[jid], field) != getattr(previous[jid].offer, field)
        )
        sample = ", ".join(mismatches[:3])
        typer.echo(
            f"{field}: {len(mismatches)} mismatches" + (f" (e.g. {sample})" if mismatches else "")
        )

    extra_lines_mismatches = sorted(
        jid
        for jid in common
        if set(offers_by_id[jid].extra_lines) != set(previous[jid].offer.extra_lines)
    )
    sample = ", ".join(extra_lines_mismatches[:3])
    typer.echo(
        f"extra_lines: {len(extra_lines_mismatches)} mismatches"
        + (f" (e.g. {sample})" if extra_lines_mismatches else "")
    )

    category_ids_mismatches = sorted(
        jid
        for jid in common
        if sorted(crawl_result.category_ids.get(jid, [])) != sorted(previous[jid].category_ids)
    )
    sample = ", ".join(category_ids_mismatches[:3])
    typer.echo(
        f"category_ids: {len(category_ids_mismatches)} mismatches"
        + (f" (e.g. {sample})" if category_ids_mismatches else "")
    )

    if crawl_result.errors:
        typer.echo(f"csv row errors: {len(crawl_result.errors)} (see stderr log above)")


@app.command()
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version as _v

    try:
        typer.echo(_v("aozora-sync"))
    except Exception:
        typer.echo("0.1.0 (unreleased)")


if __name__ == "__main__":
    app()
