"""`JobSnapshot` / `snapshot_from_offer` tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pydantic
import pytest

from sync.models import JobOffer
from sync.snapshot import JobSnapshot, snapshot_from_offer


def _offer(**overrides: str) -> JobOffer:
    fields: dict[str, Any] = {
        "job_id": "1777023",
        "title": "介護職員",
        "body_html": "<p>本文</p>",
        "address": "福岡事業所",
        "label": "介護職 正社員",
        "location": "福岡県福岡市",
        "salary": "¥250,000",
        "apply_url": "https://recruit.jobcan.jp/aozora/entry/new/1777023",
        "source_url": "https://recruit.jobcan.jp/aozora/job_offers/1777023",
    }
    fields.update(overrides)
    return JobOffer(**fields)


def test_snapshot_from_offer_copies_identity_and_hash() -> None:
    offer = _offer()
    now = datetime(2026, 8, 7, 3, 0, tzinfo=UTC)

    snap = snapshot_from_offer(offer, now=now)

    assert snap.job_id == offer.job_id
    assert snap.content_hash == offer.content_hash
    assert snap.source_url == offer.source_url
    assert snap.apply_url == offer.apply_url
    assert snap.last_seen_at == now
    assert snap.source == "html_parse"


def test_snapshot_from_offer_default_status_and_absence_count() -> None:
    snap = snapshot_from_offer(_offer(), now=datetime(2026, 8, 7, tzinfo=UTC))
    assert snap.sync_status == "active"
    assert snap.absence_count == 0


def test_snapshot_from_offer_honours_explicit_status_and_absence_count() -> None:
    snap = snapshot_from_offer(
        _offer(),
        now=datetime(2026, 8, 7, tzinfo=UTC),
        sync_status="pending_review",
        absence_count=1,
    )
    assert snap.sync_status == "pending_review"
    assert snap.absence_count == 1


def test_snapshot_from_offer_normalized_subset_matches_offer_fields() -> None:
    offer = _offer(title="訪問看護師", salary="¥300,000〜")
    snap = snapshot_from_offer(offer, now=datetime(2026, 8, 7, tzinfo=UTC))

    assert snap.normalized["title"] == "訪問看護師"
    assert snap.normalized["salary"] == "¥300,000〜"
    assert snap.normalized["address"] == offer.address
    assert snap.normalized["label"] == offer.label
    assert snap.normalized["location"] == offer.location
    # body_html deliberately excluded — content_hash covers full-content diffing.
    assert "body_html" not in snap.normalized


def test_two_offers_differing_only_in_salary_produce_different_hashes() -> None:
    """Sanity check that content_hash actually reacts to field changes — this
    is what `diff.py`'s changed/unchanged split relies on."""
    offer_a = _offer(salary="¥250,000")
    offer_b = _offer(salary="¥260,000")
    snap_a = snapshot_from_offer(offer_a, now=datetime(2026, 8, 7, tzinfo=UTC))
    snap_b = snapshot_from_offer(offer_b, now=datetime(2026, 8, 7, tzinfo=UTC))
    assert snap_a.content_hash != snap_b.content_hash


def test_job_snapshot_is_frozen() -> None:
    snap = snapshot_from_offer(_offer(), now=datetime(2026, 8, 7, tzinfo=UTC))
    with pytest.raises(pydantic.ValidationError):
        snap.sync_status = "closed"  # type: ignore[misc]


def test_job_snapshot_accepts_all_sync_statuses() -> None:
    base = {
        "job_id": "1",
        "content_hash": "x" * 64,
        "source_url": "https://recruit.jobcan.jp/aozora/job_offers/1",
        "apply_url": "https://recruit.jobcan.jp/aozora/entry/new/1",
        "last_seen_at": datetime(2026, 8, 7, tzinfo=UTC),
    }
    for status in ("active", "closed", "pending_review"):
        snap = JobSnapshot(**base, sync_status=status)
        assert snap.sync_status == status
