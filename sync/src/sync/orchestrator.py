"""Daily full-catalogue sync orchestration (Phase B B-6).

Wires `crawler.py` -> `diff.py` -> `closed_detection.py` -> `approval.py` ->
`firestore_repo.py` into the single daily run Cloud Scheduler triggers.
Kept separate from `cli.py` so the orchestration logic is testable by
injecting a `JobcanClient` + `JobCacheRepository` directly, without having
to monkeypatch module-level functions or reach real GCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .approval import apply_review_gate, review_bypass_enabled
from .closed_detection import apply_closed_detection, find_gc_candidates
from .crawler import CrawlResult, crawl_all
from .diff import compute_diff
from .firestore_repo import JobCacheRepository
from .jobcan_client import JobcanClient
from .notifications import notify_slack


@dataclass(frozen=True)
class SyncRunResult:
    crawl: CrawlResult
    added: int
    changed: int
    unchanged: int
    removed: int
    newly_closed: int
    gc_deleted: int
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

    if closed_result.circuit_breaker_tripped:
        notify_slack(
            ":rotating_light: ジョブカン同期: closed率が閾値を超えたため同期を中止しました。 "
            f"closed_rate={closed_result.closed_rate:.0%} "
            f"newly_closed={len(closed_result.newly_closed_job_ids)} "
            f"previous_active={closed_result.previous_active_count}"
        )
        return SyncRunResult(
            crawl=crawl_result,
            added=len(diff.added),
            changed=len(diff.changed),
            unchanged=len(diff.unchanged),
            removed=len(diff.removed),
            newly_closed=len(closed_result.newly_closed_job_ids),
            gc_deleted=0,
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

    if crawl_result.errors:
        notify_slack(
            f":warning: ジョブカン同期: {len(crawl_result.errors)} 件のエラーが発生しました "
            "(Cloud Logging 参照)。"
        )

    return SyncRunResult(
        crawl=crawl_result,
        added=len(diff.added),
        changed=len(diff.changed),
        unchanged=len(diff.unchanged),
        removed=len(diff.removed),
        newly_closed=len(closed_result.newly_closed_job_ids),
        gc_deleted=len(gc_candidates),
        circuit_breaker_tripped=False,
        written=True,
    )
