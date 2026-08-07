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
    `absence_count` increments and `first_absent_at` is stamped (elapsed=0h,
    far short of the 48h threshold)."""
    previous = {"1": _snapshot("1")}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY2)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.absence_count == 1
    assert snap.first_absent_at == _DAY2
    assert snap.closed_at is None
    assert result.newly_closed_job_ids == []


def test_second_consecutive_absence_closes_the_job() -> None:
    """A job first noted absent at `first_absent_at`, still absent once 48h
    have elapsed AND it's been observed absent at least twice (the
    `absence_count` floor), closes. `_snapshot`'s seed pins `first_absent_at`
    to day 1 so that day 3 (48h later) lands exactly on the threshold."""
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=_DAY1)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.absence_count == 2
    assert snap.first_absent_at == _DAY1
    assert snap.closed_at == _DAY3
    assert result.newly_closed_job_ids == ["1"]


def test_reappearing_job_resets_absence_count_and_clears_closed_at() -> None:
    """A job with 1 prior absence that's fetched again this crawl must go
    back to a clean active/0/None/None state, not carry stale bookkeeping."""
    offer = _offer("1")
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=_DAY2)}
    diff = compute_diff([offer], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.absence_count == 0
    assert snap.first_absent_at is None
    assert snap.closed_at is None


def test_already_closed_job_is_left_untouched_on_further_absence() -> None:
    """Once closed, closed_at must not be re-stamped on later runs (it's the
    30-day GC window's anchor point)."""
    already_closed = _snapshot(
        "1", sync_status="closed", absence_count=2, first_absent_at=_DAY1, closed_at=_DAY2
    )
    previous = {"1": already_closed}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.first_absent_at == _DAY1  # unchanged
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
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 4)
    } | {str(i): _snapshot(str(i)) for i in (4, 5)}
    # jobs 1-3 already have absence_count=1 + first_absent_at=day1 (one prior
    # miss, 48h before day3); jobs 4-5 are freshly active. This crawl: none
    # of the 5 are seen again.
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
        "p1": _snapshot("p1", sync_status="pending_review", absence_count=1, first_absent_at=_DAY1),
        "p2": _snapshot("p2", sync_status="pending_review", absence_count=1, first_absent_at=_DAY1),
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
    previous = {
        "1": _snapshot("1", sync_status="pending_review", absence_count=1, first_absent_at=_DAY1)
    }
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.closed_at == _DAY3
    assert result.newly_closed_job_ids == ["1"]


def test_circuit_breaker_trips_when_every_previous_job_closes() -> None:
    """Every previously-active job vanishes this crawl -> 100% closed rate,
    the clearest possible "something is broken upstream" signal."""
    previous = {
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 11)
    }
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.closed_rate == 1.0
    assert result.circuit_breaker_tripped is True


def test_circuit_breaker_stays_quiet_when_most_jobs_survive() -> None:
    """9 jobs survive (re-fetched), 1 closes -> 10% closed rate, no trip."""
    surviving_offers = [_offer(str(i)) for i in range(1, 10)]
    previous = {str(i): _snapshot(str(i)) for i in range(1, 10)} | {
        "10": _snapshot("10", absence_count=1, first_absent_at=_DAY1)
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
    previous = {
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 11)
    }
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


def test_unfetched_job_resets_absence_bookkeeping() -> None:
    """A job listed but whose detail fetch failed (diff.unfetched) IS still
    confirmed present (only its detail page failed) — unlike a plain
    carry-forward, its `absence_count`/`first_absent_at` must reset the same
    way a fresh re-fetch would. Otherwise a run of detail-fetch failures on
    an already-once-absent job would silently keep accruing elapsed time
    toward the 48h threshold via a stale `first_absent_at` that was never
    actually re-confirmed as absent (2026-08-08 time-based closed-detection
    change; this supersedes the old "carried forward untouched" behaviour
    that the original P1 codex finding required for the crawl-count design)."""
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=_DAY1)}
    diff = DiffResult(unfetched=[previous["1"]])

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.absence_count == 0  # reset, not incremented or carried forward
    assert snap.first_absent_at is None  # reset
    assert snap.sync_status == "active"
    assert result.newly_closed_job_ids == []


def test_unfetched_job_that_is_already_closed_stays_untouched() -> None:
    """An already-`closed` job appearing in `diff.unfetched` (edge case) must
    not have its bookkeeping reset — once closed, nothing about it changes,
    same invariant as the `diff.removed` path."""
    already_closed = _snapshot(
        "1", sync_status="closed", absence_count=2, first_absent_at=_DAY1, closed_at=_DAY2
    )
    previous = {"1": already_closed}
    diff = DiffResult(unfetched=[already_closed])

    result = apply_closed_detection(diff, previous, now=_DAY3)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.absence_count == 2
    assert snap.first_absent_at == _DAY1
    assert snap.closed_at == _DAY2


def test_unfetched_does_not_count_toward_circuit_breaker() -> None:
    previous = {
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 11)
    }
    diff = DiffResult(unfetched=list(previous.values()))

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert result.newly_closed_job_ids == []
    assert result.closed_rate == 0.0
    assert result.circuit_breaker_tripped is False


def test_skip_absence_bookkeeping_holds_removed_entries_fully_untouched() -> None:
    """When a crawl is incomplete (some category failed to list at all,
    `CrawlResult.fully_listed=False`), `diff.removed` must not advance
    `absence_count`/`first_absent_at` or close anything — a category-level
    listing failure is just as uninformative as a per-job fetch failure.
    Unlike `diff.unfetched` (which IS confirmation of presence and resets
    bookkeeping), an incomplete crawl's `removed` entries are simply held —
    neither reset nor advanced — since presence was never actually
    confirmed either."""
    previous = {
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 11)
    }
    diff = compute_diff([], previous_snapshots=previous)
    assert len(diff.removed) == 10  # sanity: without the flag these would close

    result = apply_closed_detection(
        diff, previous, now=_DAY3, skip_absence_bookkeeping=True
    )

    assert result.newly_closed_job_ids == []
    assert result.circuit_breaker_tripped is False
    for snap in result.next_snapshots.values():
        assert snap.absence_count == 1  # unchanged
        assert snap.first_absent_at == _DAY1  # held, not reset and not advanced
        assert snap.sync_status == "active"


def test_skip_absence_bookkeeping_false_is_the_original_behaviour() -> None:
    """Sanity check that the new parameter defaults to the pre-fix behaviour
    for a genuinely complete crawl."""
    previous = {
        str(i): _snapshot(str(i), absence_count=1, first_absent_at=_DAY1) for i in range(1, 11)
    }
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)

    assert set(result.newly_closed_job_ids) == {str(i) for i in range(1, 11)}
    assert result.circuit_breaker_tripped is True


def test_list_items_and_category_ids_are_threaded_onto_fresh_snapshots() -> None:
    """B-8: a newly-added job's listing-card row and category association
    (from `CrawlResult.list_items`/`category_ids`) must land on the snapshot
    `apply_closed_detection` builds, not just on the `JobOffer` — `app.py`
    reads them off the snapshot, not the offer, when serving listings."""
    from sync.models import JobListItem

    offer = _offer("1")
    item = JobListItem(
        job_id="1",
        title="介護職員",
        address="福岡事業所",
        description="excerpt",
        thumbnail_url=None,
        source_thumbnail_url=None,
        detail_url="https://recruit.jobcan.jp/aozora/job_offers/1",
    )
    diff = compute_diff([offer], previous_snapshots={})

    result = apply_closed_detection(
        diff,
        {},
        now=_DAY1,
        list_items={"1": item},
        category_ids={"1": ["18773", "18988"]},
    )

    assert result.next_snapshots["1"].list_item == item
    assert result.next_snapshots["1"].category_ids == ["18773", "18988"]


def test_list_items_and_category_ids_default_to_empty_when_omitted() -> None:
    """Existing callers that only care about closed-detection (not serving)
    must not be forced to pass these — omitting them stays safe."""
    offer = _offer("1")
    diff = compute_diff([offer], previous_snapshots={})

    result = apply_closed_detection(diff, {}, now=_DAY1)

    assert result.next_snapshots["1"].list_item is None
    assert result.next_snapshots["1"].category_ids == []


def test_skip_absence_bookkeeping_unions_category_ids_with_previous() -> None:
    """2026-08-07 codex + second-opinion review finding: a job cross-listed
    under categories A and B, on a run where B's listing fails outright
    (`fully_listed=False` -> `skip_absence_bookkeeping=True`), must not lose
    its B membership just because this run's `category_ids` map only saw A —
    that would silently drop its card from `/jobs/?category_id=B` until the
    next healthy run, even though nothing about the B-listing itself changed."""
    previous = {"1": _snapshot("1", category_ids=["A", "B"])}
    offer = _offer("1")
    diff = compute_diff([offer], previous_snapshots=previous)

    result = apply_closed_detection(
        diff,
        previous,
        now=_DAY2,
        skip_absence_bookkeeping=True,
        category_ids={"1": ["A"]},  # this run only saw category A
    )

    assert set(result.next_snapshots["1"].category_ids) == {"A", "B"}


def test_skip_absence_bookkeeping_false_replaces_category_ids_normally() -> None:
    """On a genuinely complete run, a job that really left category B must
    actually leave it — the union behaviour above must NOT apply here, or a
    job could never be removed from a category again."""
    previous = {"1": _snapshot("1", category_ids=["A", "B"])}
    offer = _offer("1")
    diff = compute_diff([offer], previous_snapshots=previous)

    result = apply_closed_detection(
        diff,
        previous,
        now=_DAY2,
        skip_absence_bookkeeping=False,
        category_ids={"1": ["A"]},
    )

    assert result.next_snapshots["1"].category_ids == ["A"]


# --- 2026-08-08: time-based closed-detection (48h threshold) ---
#
# The sync run moved from once-daily to every 6 hours. "2 consecutive
# crawls" used to mean ~24h of tolerance against a transient Jobcan hiccup;
# at 6h cadence it would shrink to ~6-12h, which is too easily tripped by an
# ordinary multi-hour outage. `first_absent_at` + `CLOSE_AFTER_ABSENCE_DURATION`
# (48h) decouples the tolerance window from crawl cadence.


def test_absent_for_47_hours_does_not_close() -> None:
    """One hour short of the 48h threshold must not close yet."""
    first_absent_at = _DAY1
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=first_absent_at)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(
        diff, previous, now=first_absent_at + timedelta(hours=47)
    )

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.first_absent_at == first_absent_at
    assert result.newly_closed_job_ids == []


def test_absent_for_exactly_48_hours_closes() -> None:
    """The condition is `>=` (consistent with `find_gc_candidates`'s `<=`
    cutoff at the other end of a snapshot's lifecycle) — exactly 48h elapsed
    must already close, not require crossing past it."""
    first_absent_at = _DAY1
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=first_absent_at)}
    diff = compute_diff([], previous_snapshots=previous)
    now = first_absent_at + timedelta(hours=48)

    result = apply_closed_detection(diff, previous, now=now)

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "closed"
    assert snap.closed_at == now
    assert result.newly_closed_job_ids == ["1"]


def test_absent_for_49_hours_closes() -> None:
    """Past the threshold must close too, not just exactly at it."""
    first_absent_at = _DAY1
    previous = {"1": _snapshot("1", absence_count=1, first_absent_at=first_absent_at)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(
        diff, previous, now=first_absent_at + timedelta(hours=49)
    )

    assert result.next_snapshots["1"].sync_status == "closed"
    assert result.newly_closed_job_ids == ["1"]


def test_single_absence_does_not_close_even_after_48_hours() -> None:
    """The `absence_count >= 2` floor is independent of elapsed time — a
    genuinely single observation must never close regardless of how much
    time has passed (defensive; in the normal control flow `first_absent_at`
    is only ever set alongside an absence, so reaching this path in
    production requires two runs, but this test hand-seeds the edge case to
    pin the floor down explicitly rather than leaving it an emergent
    property of when `first_absent_at` happens to get set)."""
    previous = {"1": _snapshot("1", absence_count=0, first_absent_at=_DAY1)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(
        diff, previous, now=_DAY1 + timedelta(hours=48)
    )

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.absence_count == 1  # 0 -> 1 this run
    assert result.newly_closed_job_ids == []


def test_high_absence_count_with_recent_first_absence_does_not_close() -> None:
    """The duration gate is independent of `absence_count` — even many
    recorded absences must not close before 48h has elapsed since the
    FIRST one (defends the AND condition, not just the floor)."""
    previous = {"1": _snapshot("1", absence_count=5, first_absent_at=_DAY3)}
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(diff, previous, now=_DAY3)  # 0h elapsed

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert result.newly_closed_job_ids == []


def test_pre_migration_doc_without_first_absent_at_is_not_closed_immediately() -> None:
    """A production `job_cache` document written before `first_absent_at`
    existed (the 2026-08-07 initial sync: `absence_count=0`,
    `first_absent_at` unset) must not be closed just because 48h have
    passed since some unrelated past event — the first absence observed
    this run stamps `first_absent_at=now`, so elapsed=0 regardless of how
    stale the document already was."""
    previous = {"1": _snapshot("1")}  # absence_count=0, first_absent_at=None (defaults)
    diff = compute_diff([], previous_snapshots=previous)

    result = apply_closed_detection(
        diff, previous, now=_DAY1 + timedelta(hours=48)
    )

    snap = result.next_snapshots["1"]
    assert snap.sync_status == "active"
    assert snap.first_absent_at == _DAY1 + timedelta(hours=48)
    assert result.newly_closed_job_ids == []


def test_six_hourly_cadence_closes_at_the_8th_check_not_sooner() -> None:
    """Simulates the new 6h Cloud Scheduler cadence against a job whose
    absence was first noted at `first_absent_at`: checks 1-7 (6h apart, up
    to 42h elapsed) must stay active; check 8 (48h elapsed) closes it. This
    is the concrete scenario the 48h threshold exists to handle now that
    "2 consecutive crawls" no longer means "2 days" at the new cadence."""
    first_absent_at = _DAY1
    snapshots = {"1": _snapshot("1", absence_count=1, first_absent_at=first_absent_at)}

    for check in range(1, 8):  # checks 1-7: +6h .. +42h
        now = first_absent_at + timedelta(hours=6 * check)
        diff = compute_diff([], previous_snapshots=snapshots)
        result = apply_closed_detection(diff, snapshots, now=now)
        assert result.newly_closed_job_ids == [], f"must not close at check {check}"
        snapshots = result.next_snapshots

    assert snapshots["1"].sync_status == "active"

    now_8th_check = first_absent_at + timedelta(hours=48)
    diff = compute_diff([], previous_snapshots=snapshots)
    result = apply_closed_detection(diff, snapshots, now=now_8th_check)

    assert result.newly_closed_job_ids == ["1"]
    assert result.next_snapshots["1"].sync_status == "closed"
