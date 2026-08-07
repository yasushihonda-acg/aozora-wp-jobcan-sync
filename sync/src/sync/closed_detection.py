"""Closed-job detection + circuit breaker + GC candidate selection (Phase B B-3).

Three separate, pure, I/O-free concerns living in one module because they
share the same input shape (`DiffResult` + previous `job_cache` snapshots)
and are always exercised together by the sync run:

1. **Closed detection** — "不在" (absent from its category listing) for at
   least 48 hours (`CLOSE_AFTER_ABSENCE_DURATION`) since it was FIRST observed
   absent (`JobSnapshot.first_absent_at`) flips a job to `closed`. This is a
   time-based threshold, not a crawl-count one (2026-08-08: the sync run
   moved from once-daily to every 6 hours, so "2 consecutive crawls" would
   have shrunk the tolerance window from ~48h to ~12h). A single absence does
   not close it: a Jobcan-side pagination hiccup or a transient 5xx on one
   category page must not permanently hide a still-open posting. Detail-page
   404 is a different error class entirely (`JobcanClientError`, recorded by
   `crawler.py` per job) — that's a fetch failure, not "the listing doesn't
   mention this job_id anymore." `absence_count` (still tracked alongside
   `first_absent_at`) enforces the same "never on a single observation" floor
   as an explicit invariant, even though in practice `first_absent_at` only
   ever gets set on a genuine absence, so reaching the 48h threshold already
   implies at least two absent observations.
2. **Circuit breaker** — if the newly-closed count this run exceeds 30% of
   the *previous* snapshot's non-closed count, something is more likely
   broken on Jobcan's or our side (HTML structure change, wrong category_id,
   a network partial failure) than 30%+ of postings genuinely closing within
   48 hours. The denominator is "previous non-closed count" —
   `active` + `pending_review` — not `active` alone: the numerator
   (`newly_closed`) can close a `pending_review` job just as readily as an
   `active` one (see below), so restricting the denominator to `active` only
   would let `closed_rate` exceed 100% and silently under-trip whenever a
   run's absences skew toward not-yet-approved postings. Pinning down what
   `sync-strategy.md` §5 left ambiguous (2026-08-07 codex second-opinion
   review caught the original active-only denominator as a numerator/
   denominator population mismatch).
3. **GC candidate selection** — a `closed` job past the 30-day retention
   window is a candidate for actual removal. Kept as a query, not a mutation:
   the caller (a future Cloud Run Job, B-6) decides when/whether to delete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .diff import DiffResult
from .models import JobListItem
from .snapshot import JobSnapshot, snapshot_from_offer

# 1 回の不在では closed 化しない — 2 回連続不在で確定(下記 CLOSE_AFTER_ABSENCE_DURATION
# との AND 条件。時間閾値だけなら理屈上は冗長だが、「単一観測では絶対に閉じない」という
# 元設計の保証を emergent な性質ではなく明示的な不変条件として残すため維持)。
CLOSE_AFTER_CONSECUTIVE_ABSENCES = 2

# 一覧から最初に不在を観測してから (`first_absent_at`) この時間が経過して初めて
# closed 確定 (2026-08-08: クロール間隔が日次→6時間ごとになったのに合わせて
# 実行回数ベースから時間ベースへ変更。日次時代の「2回連続不在」は実質48時間の
# 猶予だったため、その意味論をそのまま保持する)。
CLOSE_AFTER_ABSENCE_DURATION = timedelta(hours=48)

# 分母は「前回スナップショットの非closed件数(active + pending_review)」
# (sync-strategy.md §5 の未定義点を確定。active限定だと分子と population が
# 食い違い rate が 1.0 を超えうる、というレビュー指摘を反映して active 限定から拡張)。
CLOSED_RATE_CIRCUIT_BREAKER_THRESHOLD = 0.30

# closed_at から 30 日後に GC 対象 (CLAUDE.md「同期復旧設計」の既存運用ルール)。
GC_RETENTION_DAYS = 30


@dataclass(frozen=True)
class ClosedDetectionResult:
    next_snapshots: dict[str, JobSnapshot] = field(default_factory=dict)
    newly_closed_job_ids: list[str] = field(default_factory=list)
    previous_open_count: int = 0
    """Previous snapshot count with `sync_status != "closed"` — the
    denominator for `closed_rate`. Named "open" (not "active") because it
    deliberately includes `pending_review` alongside `active`; see the
    module docstring's circuit-breaker section for why."""
    closed_rate: float = 0.0
    circuit_breaker_tripped: bool = False


def apply_closed_detection(
    diff: DiffResult,
    previous_snapshots: dict[str, JobSnapshot],
    *,
    now: datetime,
    skip_absence_bookkeeping: bool = False,
    list_items: dict[str, JobListItem] | None = None,
    category_ids: dict[str, list[str]] | None = None,
) -> ClosedDetectionResult:
    """Fold this crawl's diff into the next `job_cache` snapshot set.

    Every job seen this crawl (added/changed/unchanged) becomes `active` with
    `absence_count`/`first_absent_at` reset (0 / `None`). `diff.unfetched`
    (listed but detail fetch failed) also has its bookkeeping reset — being
    listed IS evidence the posting is still there, even though its detail
    page failed to fetch this run, so it must not be treated as "still
    absent" (unlike a plain carry-forward, which would let a run of detail-
    fetch failures accumulate elapsed time toward the 48h threshold via a
    stale `first_absent_at` it never actually re-confirmed). Every job
    genuinely absent this crawl (`diff.removed`) gets its `absence_count`
    incremented and `first_absent_at` stamped on the FIRST absence only; once
    both `absence_count >= 2` and 48h have elapsed since `first_absent_at`,
    it flips to `closed` and stamps `closed_at`. A job already `closed` from
    an earlier run is left fully untouched (unfetched or removed) —
    `absence_count`/`first_absent_at` stop mattering once closed, and
    re-stamping `closed_at` on every subsequent run would break the 30-day GC
    window's start point.

    `skip_absence_bookkeeping=True` (pass when `CrawlResult.fully_listed` is
    False) holds every entry in `diff.removed` exactly as-is instead — a
    third treatment, distinct from both the reset above and the normal
    absence path below: if any category failed to list completely this run,
    a "genuine" absence and a "we simply never got to check" gap are
    indistinguishable, so nothing should be counted toward closure (no
    advance) but also nothing should be assumed confirmed-present (no reset)
    until a run with a complete picture settles it either way.

    `list_items`/`category_ids` (B-8: `CrawlResult.list_items`/`category_ids`)
    are threaded through to every freshly-built snapshot so `app.py` can serve
    category listings straight from Firestore. Omitting them (the default)
    leaves `JobSnapshot.list_item`/`category_ids` at their empty defaults —
    fine for tests that only care about closed-detection, not serving.

    `skip_absence_bookkeeping=True` also changes how `category_ids` is
    assembled for `changed`/`unchanged` offers: instead of replacing them with
    only this run's (possibly incomplete) categories, it unions with the
    *previous* snapshot's `category_ids`. Otherwise a job cross-listed under
    categories A and B, on a run where B's listing fails outright, would be
    rebuilt with `category_ids=["A"]` — silently dropping its card from
    `/jobs/?category_id=B` until the next healthy run, even though nothing
    about its B-listing actually changed (2026-08-07 codex + second-opinion
    review finding). Same principle as the absence-bookkeeping skip itself:
    when this run's picture is incomplete, don't act on what it doesn't show.
    """
    list_items = list_items or {}
    category_ids = category_ids or {}
    next_snapshots: dict[str, JobSnapshot] = {}

    for offer in (*diff.added, *diff.changed, *diff.unchanged):
        this_run_category_ids = category_ids.get(offer.job_id)
        if skip_absence_bookkeeping:
            previous = previous_snapshots.get(offer.job_id)
            if previous is not None and previous.category_ids:
                merged = list(previous.category_ids)
                for category_id in this_run_category_ids or []:
                    if category_id not in merged:
                        merged.append(category_id)
                this_run_category_ids = merged
        next_snapshots[offer.job_id] = snapshot_from_offer(
            offer,
            now=now,
            list_item=list_items.get(offer.job_id),
            category_ids=this_run_category_ids,
        )

    for previous in diff.unfetched:
        if previous.sync_status == "closed":
            next_snapshots[previous.job_id] = previous
        else:
            # Still listed this run (only its detail fetch failed) — that's
            # confirmation it's present, not absent. Reset the same way a
            # fresh re-fetch would, or a stale `first_absent_at` from a prior
            # genuine absence would keep accruing elapsed time toward the
            # 48h threshold without ever being re-confirmed as absent.
            next_snapshots[previous.job_id] = previous.model_copy(
                update={"absence_count": 0, "first_absent_at": None}
            )

    if skip_absence_bookkeeping:
        for previous in diff.removed:
            next_snapshots[previous.job_id] = previous
        removed_candidates: list[JobSnapshot] = []
    else:
        removed_candidates = diff.removed

    newly_closed: list[str] = []
    for previous in removed_candidates:
        if previous.sync_status == "closed":
            next_snapshots[previous.job_id] = previous
            continue

        absence_count = previous.absence_count + 1
        first_absent_at = previous.first_absent_at or now
        if (
            absence_count >= CLOSE_AFTER_CONSECUTIVE_ABSENCES
            and now - first_absent_at >= CLOSE_AFTER_ABSENCE_DURATION
        ):
            next_snapshots[previous.job_id] = previous.model_copy(
                update={
                    "sync_status": "closed",
                    "absence_count": absence_count,
                    "first_absent_at": first_absent_at,
                    "closed_at": now,
                }
            )
            newly_closed.append(previous.job_id)
        else:
            next_snapshots[previous.job_id] = previous.model_copy(
                update={"absence_count": absence_count, "first_absent_at": first_absent_at}
            )

    previous_open_count = sum(
        1 for snapshot in previous_snapshots.values() if snapshot.sync_status != "closed"
    )
    closed_rate = len(newly_closed) / previous_open_count if previous_open_count > 0 else 0.0

    return ClosedDetectionResult(
        next_snapshots=next_snapshots,
        newly_closed_job_ids=newly_closed,
        previous_open_count=previous_open_count,
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
    (B-6's periodic Cloud Run Job). `closed_at is None` (shouldn't happen for a
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
