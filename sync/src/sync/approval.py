"""Approval workflow (Phase B B-4): `pending_review` gate + `review_bypass` flag.

Implements CLAUDE.md's existing operational plan ("初期1ヶ月は半自動運用...採用担当
承認 → 反映") as a feature flag rather than a one-time migration —
`review_bypass=False` is the semi-automatic phase (every new/changed posting
waits in `pending_review` until a human approves it via the Slack
notification link, plan item 13; no dedicated approval UI, a minimal Cloud
Run endpoint just flips the status when the link is hit). Flipping
`review_bypass=True` (env var `REVIEW_BYPASS`, wired in B-6) switches to the
fully-automatic phase with no code change or data migration — the same shape
as `aozora-sns-auto`'s `compute_finalize_target_status` / `REVIEW_BYPASS`.

Deliberately a separate pass from `closed_detection.py`: "did this job
survive the crawl" and "does this surviving job need human approval" are two
independent questions over the same diff. `apply_review_gate` takes
`apply_closed_detection`'s output and overrides `sync_status` only for the
jobs this pass cares about, instead of duplicating the added/changed/
unchanged iteration.
"""

from __future__ import annotations

import os
from datetime import datetime

from .diff import DiffResult
from .snapshot import JobSnapshot, SyncStatus


def review_bypass_enabled() -> bool:
    """Read the `REVIEW_BYPASS` env var (Cloud Run `--set-env-vars`, B-6)."""
    return os.environ.get("REVIEW_BYPASS", "false").lower() == "true"


def compute_target_sync_status(
    *,
    is_new_or_changed: bool,
    previous_status: SyncStatus | None,
    review_bypass: bool = False,
) -> SyncStatus:
    """Decide the `sync_status` a surviving (non-absent) job should have next.

    Rules, in order:

    - `review_bypass=True` → always `"active"` — the fully-automatic phase
      skips the review gate entirely, regardless of anything else.
    - New content (`is_new_or_changed=True`), OR a job_id reactivating after
      having been `"closed"` → `"pending_review"`. A job_id that reappears
      with byte-identical content after being closed is still a meaningful
      state change (closed → live again) that a human should confirm, not
      something to silently reactivate just because the diff happened to
      call it "unchanged".
    - Otherwise (unchanged content, was not closed) → carry `previous_status`
      forward unchanged. Falls back to `"active"` if `previous_status` is
      `None` (defensive only — an unchanged job always has a previous
      snapshot by construction of `diff.compute_diff`).
    """
    if review_bypass:
        return "active"
    reactivating_from_closed = previous_status == "closed"
    if is_new_or_changed or reactivating_from_closed:
        return "pending_review"
    return previous_status or "active"


def apply_review_gate(
    next_snapshots: dict[str, JobSnapshot],
    diff: DiffResult,
    previous_snapshots: dict[str, JobSnapshot],
    *,
    review_bypass: bool = False,
) -> dict[str, JobSnapshot]:
    """Override `sync_status` on `apply_closed_detection`'s output where a
    job needs (re-)approval. Returns a new dict; does not mutate the input.
    """
    gated = dict(next_snapshots)

    for offer in (*diff.added, *diff.changed):
        previous = previous_snapshots.get(offer.job_id)
        target_status = compute_target_sync_status(
            is_new_or_changed=True,
            previous_status=previous.sync_status if previous else None,
            review_bypass=review_bypass,
        )
        gated[offer.job_id] = gated[offer.job_id].model_copy(
            update={"sync_status": target_status}
        )

    for offer in diff.unchanged:
        previous = previous_snapshots[offer.job_id]
        target_status = compute_target_sync_status(
            is_new_or_changed=False,
            previous_status=previous.sync_status,
            review_bypass=review_bypass,
        )
        gated[offer.job_id] = gated[offer.job_id].model_copy(
            update={"sync_status": target_status}
        )

    return gated


def approve(snapshot: JobSnapshot) -> JobSnapshot:
    """Human approval action (Slack link click): `pending_review` -> `active`."""
    if snapshot.sync_status != "pending_review":
        raise ValueError(
            f"cannot approve job_id={snapshot.job_id}: sync_status is "
            f"{snapshot.sync_status!r}, not 'pending_review' "
            "(stale Slack link, or already actioned)"
        )
    return snapshot.model_copy(update={"sync_status": "active"})


def reject(snapshot: JobSnapshot, *, now: datetime) -> JobSnapshot:
    """Human rejection action: `pending_review` -> `closed`.

    Stamps `closed_at=now` — a rejected posting starts the same 30-day GC
    clock as a naturally-closed one (`closed_detection.find_gc_candidates`),
    rather than lingering in Firestore with no removal path.
    """
    if snapshot.sync_status != "pending_review":
        raise ValueError(
            f"cannot reject job_id={snapshot.job_id}: sync_status is "
            f"{snapshot.sync_status!r}, not 'pending_review' "
            "(stale Slack link, or already actioned)"
        )
    return snapshot.model_copy(update={"sync_status": "closed", "closed_at": now})
