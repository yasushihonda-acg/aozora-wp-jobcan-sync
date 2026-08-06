"""Closed-job detection + circuit breaker + GC candidate selection (Phase B B-3).

Three separate, pure, I/O-free concerns living in one module because they
share the same input shape (`DiffResult` + previous `job_cache` snapshots)
and are always exercised together by the sync run:

1. **Closed detection** — "不在" (absent from its category listing) for 2
   consecutive crawls flips a job to `closed`. A single absence does not
   close it: a Jobcan-side pagination hiccup or a transient 5xx on one
   category page must not permanently hide a still-open posting. Detail-page
   404 is a different error class entirely (`JobcanClientError`, recorded by
   `crawler.py` per job) — that's a fetch failure, not "the listing doesn't
   mention this job_id anymore."
2. **Circuit breaker** — if the newly-closed count this run exceeds 30% of
   the *previous* snapshot's active count, something is more likely broken
   on Jobcan's or our side (HTML structure change, wrong category_id, a
   network partial failure) than 30%+ of postings genuinely closing between
   two daily crawls. The denominator is explicitly "previous active count",
   not "current total" — pinning down what `sync-strategy.md` §5 left
   ambiguous.
3. **GC candidate selection** — a `closed` job past the 30-day retention
   window is a candidate for actual removal. Kept as a query, not a mutation:
   the caller (a future Cloud Run Job, B-6) decides when/whether to delete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .diff import DiffResult
from .snapshot import JobSnapshot, snapshot_from_offer

# 1 回の不在では closed 化しない — 2 回連続不在で確定。
CLOSE_AFTER_CONSECUTIVE_ABSENCES = 2

# 分母は「前回スナップショットの active 件数」(sync-strategy.md §5 の未定義点を確定)。
CLOSED_RATE_CIRCUIT_BREAKER_THRESHOLD = 0.30

# closed_at から 30 日後に GC 対象 (CLAUDE.md「同期復旧設計」の既存運用ルール)。
GC_RETENTION_DAYS = 30


@dataclass(frozen=True)
class ClosedDetectionResult:
    next_snapshots: dict[str, JobSnapshot] = field(default_factory=dict)
    newly_closed_job_ids: list[str] = field(default_factory=list)
    previous_active_count: int = 0
    closed_rate: float = 0.0
    circuit_breaker_tripped: bool = False


def apply_closed_detection(
    diff: DiffResult,
    previous_snapshots: dict[str, JobSnapshot],
    *,
    now: datetime,
) -> ClosedDetectionResult:
    """Fold this crawl's diff into the next `job_cache` snapshot set.

    Every job seen this crawl (added/changed/unchanged) becomes `active` with
    `absence_count` reset to 0. Every job absent this crawl (`diff.removed`)
    gets its `absence_count` incremented; the 2nd consecutive absence flips
    it to `closed` and stamps `closed_at`. A job already `closed` from an
    earlier run is left untouched — `absence_count` stops mattering once
    closed, and re-stamping `closed_at` on every subsequent run would break
    the 30-day GC window's start point.
    """
    next_snapshots: dict[str, JobSnapshot] = {}

    for offer in (*diff.added, *diff.changed, *diff.unchanged):
        next_snapshots[offer.job_id] = snapshot_from_offer(offer, now=now)

    newly_closed: list[str] = []
    for previous in diff.removed:
        if previous.sync_status == "closed":
            next_snapshots[previous.job_id] = previous
            continue

        absence_count = previous.absence_count + 1
        if absence_count >= CLOSE_AFTER_CONSECUTIVE_ABSENCES:
            next_snapshots[previous.job_id] = previous.model_copy(
                update={"sync_status": "closed", "absence_count": absence_count, "closed_at": now}
            )
            newly_closed.append(previous.job_id)
        else:
            next_snapshots[previous.job_id] = previous.model_copy(
                update={"absence_count": absence_count}
            )

    previous_active_count = sum(
        1 for snapshot in previous_snapshots.values() if snapshot.sync_status == "active"
    )
    closed_rate = (
        len(newly_closed) / previous_active_count if previous_active_count > 0 else 0.0
    )

    return ClosedDetectionResult(
        next_snapshots=next_snapshots,
        newly_closed_job_ids=newly_closed,
        previous_active_count=previous_active_count,
        closed_rate=closed_rate,
        circuit_breaker_tripped=closed_rate > CLOSED_RATE_CIRCUIT_BREAKER_THRESHOLD,
    )


def find_gc_candidates(
    snapshots: dict[str, JobSnapshot],
    *,
    now: datetime,
    retention_days: int = GC_RETENTION_DAYS,
) -> list[str]:
    """job_ids that are `closed` and past the retention window.

    A query only — actual Firestore deletion is the caller's responsibility
    (B-6's daily Cloud Run Job). `closed_at is None` (shouldn't happen for a
    `closed` snapshot produced by `apply_closed_detection`, but Firestore
    data can always be hand-edited or come from an older schema) is treated
    as "not yet eligible" rather than raising — a defensively-missing
    timestamp must never cause premature deletion.
    """
    cutoff = now - timedelta(days=retention_days)
    return [
        job_id
        for job_id, snapshot in snapshots.items()
        if snapshot.sync_status == "closed"
        and snapshot.closed_at is not None
        and snapshot.closed_at <= cutoff
    ]
