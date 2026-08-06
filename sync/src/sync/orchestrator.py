"""Daily full-catalogue sync orchestration (Phase B B-6).

Wires `crawler.py` -> `diff.py` -> `closed_detection.py` -> `approval.py` ->
`firestore_repo.py` into the single daily run Cloud Scheduler triggers.
Kept separate from `cli.py` so the orchestration logic is testable by
injecting a `JobcanClient` + `JobCacheRepository` directly, without having
to monkeypatch module-level functions or reach real GCP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .approval import apply_review_gate, review_bypass_enabled
from .closed_detection import apply_closed_detection, find_gc_candidates
from .crawler import CrawlResult, crawl_all
from .diff import compute_diff
from .firestore_repo import JobCacheRepository
from .jobcan_client import JobcanClient
from .notifications import notify_slack

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncRunResult:
    crawl: CrawlResult
    added: int
    changed: int
    unchanged: int
    removed: int
    newly_closed: int
    gc_deleted: int
    reconciliation_mismatch: bool
    circuit_breaker_tripped: bool
    written: bool


def run_sync(
    client: JobcanClient,
    repo: JobCacheRepository,
    *,
    now: datetime,
    review_bypass: bool | None = None,
) -> SyncRunResult:
    """Run one full crawl -> diff -> closed-detection -> review-gate -> write cycle.

    `review_bypass=None` (the default) reads the `REVIEW_BYPASS` env var via
    `approval.review_bypass_enabled()`; pass an explicit bool in tests to
    avoid depending on process environment.

    On circuit-breaker trip, **nothing is written to Firestore**
    (`written=False`) — see `closed_detection.py`'s module docstring for why
    "同期中止" is interpreted as aborting the whole write, not a partial
    commit. The next day's run gets a clean previous-snapshot baseline to
    diff against, rather than one built on a possibly-erroneous mass closure.

    After a successful write, runs the 30-day closed-job GC
    (`closed_detection.find_gc_candidates`) against the snapshot set this run
    just produced and deletes any hits — this is the only place that query is
    ever acted on, so a `closed` document doesn't linger in Firestore forever
    with no removal path.

    Every warning this run collects (crawl errors, a reconciliation
    mismatch) is sent in a *single* Slack notification alongside whatever
    else the run is reporting — a circuit-breaker trip no longer silently
    swallows a separate crawl-errors warning just because it returns early
    (2026-08-07 second-opinion review finding: the two were mutually
    exclusive before, which could mislead an on-call responder into reading
    a broken crawl as "postings genuinely closed").
    """
    if review_bypass is None:
        review_bypass = review_bypass_enabled()

    crawl_result = crawl_all(client)
    previous_snapshots = repo.get_all()
    diff = compute_diff(
        crawl_result.offers,
        previous_snapshots,
        listed_job_ids=frozenset(crawl_result.listed_job_ids),
    )
    closed_result = apply_closed_detection(
        diff,
        previous_snapshots,
        now=now,
        skip_absence_bookkeeping=not crawl_result.fully_listed,
    )

    warnings: list[str] = []
    if crawl_result.errors:
        warnings.append(f"{len(crawl_result.errors)} 件のクロールエラー (Cloud Logging 参照)")

    # `expected_total`/`collected_total` reconciliation: catches a silent
    # partial crawl (e.g. a 200 with a half-rendered page) that per-request
    # error handling alone wouldn't surface — see `crawler.CrawlResult`'s
    # docstring. This was computed but never actually checked anywhere until
    # this fix (2026-08-07 second-opinion review finding).
    reconciliation_mismatch = crawl_result.expected_total != crawl_result.collected_total
    if reconciliation_mismatch:
        _logger.warning(
            "crawl reconciliation mismatch",
            extra={
                "expected_total": crawl_result.expected_total,
                "collected_total": crawl_result.collected_total,
            },
        )
        warnings.append(
            "想定件数と収集件数が不一致 "
            f"(expected={crawl_result.expected_total}, collected={crawl_result.collected_total}) "
            "— サイレントな部分クロールの可能性"
        )

    if closed_result.circuit_breaker_tripped:
        message = (
            ":rotating_light: ジョブカン同期: closed率が閾値を超えたため同期を中止しました。 "
            f"closed_rate={closed_result.closed_rate:.0%} "
            f"newly_closed={len(closed_result.newly_closed_job_ids)} "
            f"previous_open={closed_result.previous_open_count}"
        )
        if warnings:
            message += "\n追加の警告: " + " / ".join(warnings)
        notify_slack(message)
        return SyncRunResult(
            crawl=crawl_result,
            added=len(diff.added),
            changed=len(diff.changed),
            unchanged=len(diff.unchanged),
            removed=len(diff.removed),
            newly_closed=len(closed_result.newly_closed_job_ids),
            gc_deleted=0,
            reconciliation_mismatch=reconciliation_mismatch,
            circuit_breaker_tripped=True,
            written=False,
        )

    gated_snapshots = apply_review_gate(
        closed_result.next_snapshots, diff, previous_snapshots, review_bypass=review_bypass
    )
    repo.set_many(list(gated_snapshots.values()))

    gc_candidates = find_gc_candidates(gated_snapshots, now=now)
    if gc_candidates:
        repo.delete_many(gc_candidates)

    if warnings:
        notify_slack(":warning: ジョブカン同期で警告: " + " / ".join(warnings))

    return SyncRunResult(
        crawl=crawl_result,
        added=len(diff.added),
        changed=len(diff.changed),
        unchanged=len(diff.unchanged),
        removed=len(diff.removed),
        newly_closed=len(closed_result.newly_closed_job_ids),
        gc_deleted=len(gc_candidates),
        reconciliation_mismatch=reconciliation_mismatch,
        circuit_breaker_tripped=False,
        written=True,
    )
