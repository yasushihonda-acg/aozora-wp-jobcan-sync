"""`compute_diff` classification tests — pure, no Firestore involved."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sync.diff import compute_diff
from sync.models import JobOffer
from sync.snapshot import snapshot_from_offer

_NOW = datetime(2026, 8, 7, tzinfo=UTC)


def _offer(job_id: str, **overrides: str) -> JobOffer:
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
    fields.update(overrides)
    return JobOffer(**fields)


def test_job_with_no_previous_snapshot_is_added() -> None:
    offer = _offer("1")
    result = compute_diff([offer], previous_snapshots={})

    assert result.added == [offer]
    assert result.changed == []
    assert result.unchanged == []
    assert result.removed == []


def test_job_with_identical_content_hash_is_unchanged() -> None:
    offer = _offer("1")
    previous = {"1": snapshot_from_offer(offer, now=_NOW)}

    result = compute_diff([offer], previous_snapshots=previous)

    assert result.unchanged == [offer]
    assert result.added == []
    assert result.changed == []


def test_job_with_different_content_hash_is_changed() -> None:
    old_offer = _offer("1", salary="¥250,000")
    new_offer = _offer("1", salary="¥280,000")
    previous = {"1": snapshot_from_offer(old_offer, now=_NOW)}

    result = compute_diff([new_offer], previous_snapshots=previous)

    assert result.changed == [new_offer]
    assert result.added == []
    assert result.unchanged == []


def test_previous_job_absent_from_current_crawl_is_removed() -> None:
    old_offer = _offer("1")
    previous = {"1": snapshot_from_offer(old_offer, now=_NOW)}

    result = compute_diff([], previous_snapshots=previous)

    assert len(result.removed) == 1
    assert result.removed[0].job_id == "1"
    assert result.added == []
    assert result.changed == []
    assert result.unchanged == []


def test_mixed_batch_classifies_each_job_independently() -> None:
    """4 jobs, one of each outcome, in a single call."""
    added_offer = _offer("added")
    unchanged_offer = _offer("unchanged")
    changed_old = _offer("changed", salary="¥250,000")
    changed_new = _offer("changed", salary="¥260,000")
    removed_offer = _offer("removed")

    previous = {
        "unchanged": snapshot_from_offer(unchanged_offer, now=_NOW),
        "changed": snapshot_from_offer(changed_old, now=_NOW),
        "removed": snapshot_from_offer(removed_offer, now=_NOW),
    }
    current = [added_offer, unchanged_offer, changed_new]

    result = compute_diff(current, previous_snapshots=previous)

    assert result.added == [added_offer]
    assert result.unchanged == [unchanged_offer]
    assert result.changed == [changed_new]
    assert [s.job_id for s in result.removed] == ["removed"]


def test_empty_current_and_empty_previous_is_a_no_op() -> None:
    result = compute_diff([], previous_snapshots={})
    assert result.added == result.changed == result.unchanged == result.removed == []
