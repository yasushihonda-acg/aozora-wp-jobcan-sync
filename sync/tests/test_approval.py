"""Approval workflow tests: `compute_target_sync_status` / `apply_review_gate`
/ `approve` / `reject` — pure, no Firestore, no env vars mutated globally."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from sync.approval import (
    apply_review_gate,
    approve,
    compute_target_sync_status,
    reject,
    review_bypass_enabled,
)
from sync.closed_detection import apply_closed_detection
from sync.diff import compute_diff
from sync.models import JobOffer
from sync.snapshot import JobSnapshot, snapshot_from_offer

_NOW = datetime(2026, 8, 7, tzinfo=UTC)


def _offer(job_id: str) -> JobOffer:
    fields: dict[str, Any] = {
        "job_id": job_id,
        "title": "介護職員",
        "body_html": "<p>本文</p>",
        "address": "福岡事業所",
        "label": "介護職 正社員",
        "location": "福岡県福岡市",
        "salary": "¥250,000",
        "apply_url": f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        "source_url": f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
    }
    return JobOffer(**fields)


def _snapshot(job_id: str, **overrides: Any) -> JobSnapshot:
    base = snapshot_from_offer(_offer(job_id), now=_NOW)
    return base.model_copy(update=overrides) if overrides else base


# ---------------------------------------------------------------------------
# compute_target_sync_status
# ---------------------------------------------------------------------------


def test_review_bypass_always_wins_regardless_of_other_inputs() -> None:
    assert (
        compute_target_sync_status(
            is_new_or_changed=True, previous_status="closed", review_bypass=True
        )
        == "active"
    )


def test_review_bypass_true_reactivating_from_closed_skips_review() -> None:
    """The specific combination second-opinion review flagged as untested:
    `is_new_or_changed=False` (byte-identical content) + `previous_status=
    "closed"` + `review_bypass=True`. Without bypass this exact input
    requires `pending_review` (see
    `test_unchanged_job_reactivating_from_closed_requires_review` below) —
    bypass mode deliberately overrides that safety net too, since "fully
    automatic" means no posting gets human review, not "every posting except
    ones that were previously rejected." See `compute_target_sync_status`'s
    docstring for the full rationale."""
    assert (
        compute_target_sync_status(
            is_new_or_changed=False, previous_status="closed", review_bypass=True
        )
        == "active"
    )


def test_new_job_without_bypass_goes_to_pending_review() -> None:
    assert (
        compute_target_sync_status(is_new_or_changed=True, previous_status=None)
        == "pending_review"
    )


def test_changed_job_without_bypass_goes_to_pending_review() -> None:
    assert (
        compute_target_sync_status(is_new_or_changed=True, previous_status="active")
        == "pending_review"
    )


def test_unchanged_job_carries_previous_status_forward() -> None:
    assert (
        compute_target_sync_status(is_new_or_changed=False, previous_status="active")
        == "active"
    )
    assert (
        compute_target_sync_status(is_new_or_changed=False, previous_status="pending_review")
        == "pending_review"
    )


def test_unchanged_job_reactivating_from_closed_requires_review() -> None:
    """Byte-identical content on a job_id that was closed must still require
    re-approval — a closed->live transition is meaningful regardless of
    whether the posting text happens to be unchanged."""
    assert (
        compute_target_sync_status(is_new_or_changed=False, previous_status="closed")
        == "pending_review"
    )


def test_unchanged_job_with_missing_previous_status_defaults_active() -> None:
    """Defensive-only branch: `is_new_or_changed=False` implies a previous
    snapshot always exists in practice, but must not raise if absent."""
    assert compute_target_sync_status(is_new_or_changed=False, previous_status=None) == "active"


# ---------------------------------------------------------------------------
# apply_review_gate — composed with closed_detection.apply_closed_detection
# ---------------------------------------------------------------------------


def test_added_job_is_gated_to_pending_review() -> None:
    offer = _offer("1")
    diff = compute_diff([offer], previous_snapshots={})
    next_snapshots = apply_closed_detection(diff, {}, now=_NOW).next_snapshots

    gated = apply_review_gate(next_snapshots, diff, {}, review_bypass=False)

    assert gated["1"].sync_status == "pending_review"


def test_changed_job_is_gated_to_pending_review() -> None:
    # A stale content_hash in the previous snapshot is enough to force a
    # "changed" classification, regardless of the current offer's own content.
    new_offer = _offer("1")
    previous = {"1": _snapshot("1", content_hash="stale")}
    diff = compute_diff([new_offer], previous_snapshots=previous)
    assert diff.changed == [new_offer]
    next_snapshots = apply_closed_detection(diff, previous, now=_NOW).next_snapshots

    gated = apply_review_gate(next_snapshots, diff, previous, review_bypass=False)

    assert gated["1"].sync_status == "pending_review"


def test_unchanged_job_stays_active_when_previously_active() -> None:
    offer = _offer("1")
    previous = {"1": _snapshot("1")}
    diff = compute_diff([offer], previous_snapshots=previous)
    next_snapshots = apply_closed_detection(diff, previous, now=_NOW).next_snapshots

    gated = apply_review_gate(next_snapshots, diff, previous, review_bypass=False)

    assert gated["1"].sync_status == "active"


def test_unchanged_job_stays_pending_review_when_not_yet_approved() -> None:
    """A job still awaiting approval must NOT silently flip to active just
    because it reappeared with unchanged content in the next crawl."""
    offer = _offer("1")
    previous = {"1": _snapshot("1", sync_status="pending_review")}
    diff = compute_diff([offer], previous_snapshots=previous)
    next_snapshots = apply_closed_detection(diff, previous, now=_NOW).next_snapshots

    gated = apply_review_gate(next_snapshots, diff, previous, review_bypass=False)

    assert gated["1"].sync_status == "pending_review"


def test_review_bypass_true_forces_every_surviving_job_active() -> None:
    added_offer = _offer("added")
    unchanged_offer = _offer("unchanged")
    previous = {"unchanged": _snapshot("unchanged")}
    diff = compute_diff([added_offer, unchanged_offer], previous_snapshots=previous)
    next_snapshots = apply_closed_detection(diff, previous, now=_NOW).next_snapshots

    gated = apply_review_gate(next_snapshots, diff, previous, review_bypass=True)

    assert gated["added"].sync_status == "active"
    assert gated["unchanged"].sync_status == "active"


def test_apply_review_gate_does_not_touch_removed_jobs() -> None:
    """Removed/closed bookkeeping is closed_detection.py's job — the review
    gate must leave those entries exactly as apply_closed_detection produced."""
    previous = {"1": _snapshot("1")}
    diff = compute_diff([], previous_snapshots=previous)
    closed_result = apply_closed_detection(diff, previous, now=_NOW)

    gated = apply_review_gate(closed_result.next_snapshots, diff, previous, review_bypass=False)

    assert gated["1"] == closed_result.next_snapshots["1"]


def test_apply_review_gate_does_not_mutate_input_dict() -> None:
    offer = _offer("1")
    diff = compute_diff([offer], previous_snapshots={})
    next_snapshots = apply_closed_detection(diff, {}, now=_NOW).next_snapshots
    original = dict(next_snapshots)

    apply_review_gate(next_snapshots, diff, {}, review_bypass=False)

    assert next_snapshots == original


# ---------------------------------------------------------------------------
# approve / reject
# ---------------------------------------------------------------------------


def test_approve_flips_pending_review_to_active() -> None:
    snapshot = _snapshot("1", sync_status="pending_review")
    result = approve(snapshot)
    assert result.sync_status == "active"


def test_approve_raises_on_non_pending_review_status() -> None:
    snapshot = _snapshot("1", sync_status="active")
    with pytest.raises(ValueError, match="pending_review"):
        approve(snapshot)


def test_reject_flips_pending_review_to_closed_and_stamps_closed_at() -> None:
    snapshot = _snapshot("1", sync_status="pending_review")
    result = reject(snapshot, now=_NOW)
    assert result.sync_status == "closed"
    assert result.closed_at == _NOW


def test_reject_raises_on_non_pending_review_status() -> None:
    snapshot = _snapshot("1", sync_status="closed")
    with pytest.raises(ValueError, match="pending_review"):
        reject(snapshot, now=_NOW)


# ---------------------------------------------------------------------------
# review_bypass_enabled (env var)
# ---------------------------------------------------------------------------


def test_review_bypass_enabled_defaults_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REVIEW_BYPASS", raising=False)
    assert review_bypass_enabled() is False


def test_review_bypass_enabled_true_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEW_BYPASS", "true")
    assert review_bypass_enabled() is True


def test_review_bypass_enabled_false_for_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEW_BYPASS", "yes")
    assert review_bypass_enabled() is False
