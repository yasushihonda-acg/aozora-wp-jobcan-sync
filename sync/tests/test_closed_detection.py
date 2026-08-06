"""`apply_closed_detection` / `find_gc_candidates` tests — pure, no Firestore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sync.closed_detection import apply_closed_detection, find_gc_candidates
from sync.diff import DiffResult, compute_diff
from sync.models import JobOffer
from sync.snapshot import JobSnapshot, snapshot_from_offer

_DAY1 = datetime(2026, 8, 5, tzinfo=UTC)
_DAY2 = datetime(2026, 8, 6, tzinfo=UTC)
_DAY3 = datetime(2026, 8, 7, tzinfo=UTC)


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


def _snapshot(job_id: str, **overrides) -> JobSnapshot:
    base = snapshot_from_offer(_offer(job_id), now=_DAY1)
    return base.model_copy(update=overrides) if overrides else base


def test_first_absence_does_not_close_the_job() -> None:
    """A job present on day 1, absent on day 2, must NOT be closed yet —
    only `absence_count` increments."""
    previous = {"1": _snapshot("1")}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY2)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.absence_count == 1
    assert snap.closed_at is None
    assert result.newly_closed_job_ids == []


def test_second_consecutive_absence_closes_the_job() -> None:
    """Day 1: present. Day 2: absent (absence_count -> 1). Day 3: absent
    again (absence_count -> 2) — NOW it closes."""
    previous = {"1": _snapshot("1", absence_count=1)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.absence_count == 2
    assert snap.closed_at == _DAY3
    assert result.newly_closed_job_ids == ["1"]


def test_reappearing_job_resets_absence_count_and_clears_closed_at() -> None:
    """A job with 1 prior absence that's fetched again this crawl must go
    back to a clean active/0/None state, not carry stale bookkeeping."""
    offer = _offer("1")
    previous = {"1": _snapshot("1", absence_count=1)}
    diff = compute_diff([offer], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.absence_count == 0
    assert snap.closed_at is None


def test_already_closed_job_is_left_untouched_on_further_absence() -> None:
    """Once closed, closed_at must not be re-stamped on later runs (it's the
    30-day GC window's anchor point)."""
    already_closed = _snapshot(
        "1", sync_status="closed", absence_count=2, closed_at=_DAY2
    )
    previous = {"1": already_closed}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.closed_at == _DAY2  # unchanged, not _DAY3
    assert result.newly_closed_job_ids == []  # not counted as newly closed again


def test_changed_and_unchanged_jobs_stay_active_with_zero_absence() -> None:
    unchanged_offer = _offer("1")
    changed_offer = _offer("2")
    previous = {
        "1": _snapshot("1"),
        "2": _snapshot("2", content_hash="stale-hash"),
    }
    diff = compute_diff([unchanged_offer, changed_offer], previous_snapshots=previous)
    assert diff.unchanged == [unchanged_offer]
    assert diff.changed == [changed_offer]

    result = apply_closed_detection(diff, previous, now=_DAY2)

    for job_id in ("1", "2"):
        snap = result.next_snapshots[job_id]
        assert snap.sync_status == "active"
        assert snap.absence_count == 0


def test_circuit_breaker_denominator_is_previous_open_count() -> None:
    """5 previously-open jobs, 3 close this run -> 60% > 30% threshold."""
    previous = {
        str(i): _snapshot(str(i), absence_count=1) for i in range(1, 4)
    } | {str(i): _snapshot(str(i)) for i in (4, 5)}
    # jobs 1-3 already have absence_count=1 (one prior miss); jobs 4-5 are
    # freshly active. This crawl: none of the 5 are seen again.
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.previous_open_count == 5
    # jobs 1-3 flip to closed (absence_count 1->2); jobs 4-5 go to absence_count=1.
    assert sorted(result.newly_closed_job_ids) == ["1", "2", "3"]
    assert result.closed_rate == 3 / 5
    assert result.circuit_breaker_tripped is True


def test_circuit_breaker_denominator_includes_pending_review() -> None:
    """A regression guard for a numerator/denominator population mismatch a
    second-opinion review caught: with an active-only denominator (the
    pre-fix behaviour), 3 active jobs + 2 of 7 pending_review jobs closing
    would read as 2/3 ≈ 67% (false trip — halts a perfectly ordinary sync
    over a couple of unapproved postings expiring). The correct denominator
    counts every previously non-closed job (3 active + 7 pending_review =
    10), giving 2/10 = 20% — no trip."""
    previous = {
        "1": _snapshot("1"),
        "2": _snapshot("2"),
        "3": _snapshot("3"),
        "p1": _snapshot("p1", sync_status="pending_review", absence_count=1),
        "p2": _snapshot("p2", sync_status="pending_review", absence_count=1),
        # p3-p7: also pending_review, but only their FIRST absence this run
        # (absence_count 0->1) — still part of the "open" population, but
        # don't close, so they only affect the denominator, not the numerator.
        **{f"p{i}": _snapshot(f"p{i}", sync_status="pending_review") for i in range(3, 8)},
    }
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.previous_open_count == 10
    assert sorted(result.newly_closed_job_ids) == ["p1", "p2"]
    assert result.closed_rate == 2 / 10
    assert result.circuit_breaker_tripped is False


def test_pending_review_job_absent_twice_auto_closes_without_reject() -> None:
    """A `pending_review` job that disappears from its listing before anyone
    approves/rejects it still closes via the normal absence path — this is
    intentional (it's genuinely gone regardless of review status), not
    something that must route through `approval.reject()`. Locked in by a
    test per second-opinion review, which found this interaction untested."""
    previous = {"1": _snapshot("1", sync_status="pending_review", absence_count=1)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.closed_at == _DAY3
    assert result.newly_closed_job_ids == ["1"]


def test_circuit_breaker_trips_when_every_previous_job_closes() -> None:
    """Every previously-active job vanishes this crawl -> 100% closed rate,
    the clearest possible "something is broken upstream" signal."""
    previous = {str(i): _snapshot(str(i), absence_count=1) for i in range(1, 11)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.closed_rate == 1.0
    assert result.circuit_breaker_tripped is True


def test_circuit_breaker_stays_quiet_when_most_jobs_survive() -> None:
    """9 jobs survive (re-fetched), 1 closes -> 10% closed rate, no trip."""
    surviving_offers = [_offer(str(i)) for i in range(1, 10)]
    previous = {str(i): _snapshot(str(i)) for i in range(1, 10)} | {
        "10": _snapshot("10", absence_count=1)
    }
    diff = compute_diff(surviving_offers, previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.previous_open_count == 10
    assert result.newly_closed_job_ids == ["10"]
    assert result.closed_rate == 0.1
    assert result.circuit_breaker_tripped is False


def test_circuit_breaker_denominator_zero_never_divides_by_zero() -> None:
    result = apply_closed_detection(DiffResult(), {}, now=_DAY1)
    assert result.previous_open_count == 0
    assert result.closed_rate == 0.0


def test_circuit_breaker_not_tripped_at_exactly_the_threshold() -> None:
    """The condition is a strict `>` — exactly 30% (3 of 10) must NOT trip."""
    previous = {str(i): _snapshot(str(i), absence_count=1) for i in range(1, 11)}
    surviving_offers = [_offer(str(i)) for i in range(4, 11)]  # 7 of 10 survive
    diff = compute_diff(surviving_offers, previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.closed_rate == 0.3
    assert result.circuit_breaker_tripped is False


def test_gc_candidate_selected_after_retention_window() -> None:
    closed_31_days_ago = _snapshot(
        "1", sync_status="closed", closed_at=_DAY1 - timedelta(days=31)
    )
    snapshots = {"1": closed_31_days_ago}

    assert find_gc_candidates(snapshots, now=_DAY1) == ["1"]


def test_gc_candidate_selected_at_exactly_the_retention_boundary() -> None:
    """The condition is `<=` — exactly 30 days must already be eligible."""
    closed_exactly_30_days_ago = _snapshot(
        "1", sync_status="closed", closed_at=_DAY1 - timedelta(days=30)
    )
    snapshots = {"1": closed_exactly_30_days_ago}

    assert find_gc_candidates(snapshots, now=_DAY1) == ["1"]


def test_gc_candidate_not_selected_within_retention_window() -> None:
    closed_10_days_ago = _snapshot(
        "1", sync_status="closed", closed_at=_DAY1 - timedelta(days=10)
    )
    snapshots = {"1": closed_10_days_ago}

    assert find_gc_candidates(snapshots, now=_DAY1) == []


def test_gc_candidate_excludes_active_jobs_regardless_of_age() -> None:
    old_but_active = _snapshot("1", last_seen_at=_DAY1 - timedelta(days=60))
    assert find_gc_candidates({"1": old_but_active}, now=_DAY1) == []


def test_gc_candidate_excludes_closed_job_with_no_closed_at() -> None:
    """Defensive: a closed snapshot with a missing closed_at (e.g. hand-edited
    Firestore data) must never be treated as GC-eligible."""
    malformed = _snapshot("1", sync_status="closed", closed_at=None)
    assert find_gc_candidates({"1": malformed}, now=_DAY1 + timedelta(days=365)) == []


def test_unfetched_job_is_carried_forward_untouched() -> None:
    """A job listed but whose detail fetch failed (diff.unfetched) must not
    have its absence_count touched, and must not close — this is the
    behaviour the P1 codex finding required."""
    previous = {"1": _snapshot("1", absence_count=1)}
    diff = DiffResult(unfetched=[previous["1"]])

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.absence_count == 1  # unchanged, not incremented
    assert snap.sync_status == "active"
    assert result.newly_closed_job_ids == []


def test_unfetched_does_not_count_toward_circuit_breaker() -> None:
    previous = {str(i): _snapshot(str(i), absence_count=1) for i in range(1, 11)}
    diff = DiffResult(unfetched=list(previous.values()))

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.newly_closed_job_ids == []
    assert result.closed_rate == 0.0
    assert result.circuit_breaker_tripped is False


def test_skip_absence_bookkeeping_treats_removed_like_unfetched() -> None:
    """When a crawl is incomplete (some category failed to list at all,
    `CrawlResult.fully_listed=False`), `diff.removed` must not advance
    absence_count or close anything — a category-level listing failure is
    just as uninformative as a per-job fetch failure."""
    previous = {str(i): _snapshot(str(i), absence_count=1) for i in range(1, 11)}
    diff = compute_diff([], previous_snapshots=previous)
    assert len(diff.removed) == 10  # sanity: without the flag these would close

    result = apply_closed_detection(
        diff, previous, now=_DAY3, skip_absence_bookkeeping=True
    )

    assert result.newly_closed_job_ids == []
    assert result.circuit_breaker_tripped is False
    for snap in result.next_snapshots.values():
        assert snap.absence_count == 1  # unchanged
        assert snap.sync_status == "active"


def test_skip_absence_bookkeeping_false_is_the_original_behaviour() -> None:
    """Sanity check that the new parameter defaults to the pre-fix behaviour
    for a genuinely complete crawl."""
    previous = {str(i): _snapshot(str(i), absence_count=1) for i in range(1, 11)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert set(result.newly_closed_job_ids) == {str(i) for i in range(1, 11)}
    assert result.circuit_breaker_tripped is True
