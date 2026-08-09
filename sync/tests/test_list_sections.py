"""Tests for `list_sections.py` (Stage 3 — job-list card colour/chip
decorations)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sync.list_sections import (
    LABEL_TO_CATEGORY,
    build_card_view,
    build_job_type_chips,
    category_key_from_labels,
)
from sync.models import JobListItem, JobOffer
from sync.snapshot import snapshot_from_offer


def _offer(**overrides: Any) -> JobOffer:
    fields: dict[str, Any] = {
        "job_id": "1",
        "title": "テスト求人",
        "body_html": "<p>本文</p>",
        "address": "【福岡】あおぞらケアグループ四箇（デイ・有料）",
        "label": "介護職正社員",
        "location": "福岡県福岡市早良区",
        "salary": "【月額】200,000円〜",
        "apply_url": "https://recruit.jobcan.jp/aozora/entry/new/1",
        "source_url": "https://recruit.jobcan.jp/aozora/job_offers/1",
        "page_title": None,
        "extra_lines": [("休日・休暇", "年間休日110日")],
    }
    fields.update(overrides)
    return JobOffer(**fields)


def _list_item(**overrides: Any) -> JobListItem:
    fields: dict[str, Any] = {
        "job_id": "1",
        "title": "テスト求人",
        "address": "福岡市早良区",
        "description": "excerpt",
        "thumbnail_url": None,
        "source_thumbnail_url": None,
        "detail_url": "https://recruit.jobcan.jp/aozora/job_offers/1",
        "labels": ["介護職", "正社員"],
    }
    fields.update(overrides)
    return JobListItem(**fields)


def test_category_key_from_labels_matches_first_hit() -> None:
    assert category_key_from_labels(["介護職", "正社員"]) == "care"
    assert category_key_from_labels(["看護職", "パート", "アルバイト"]) == "nurse"
    assert category_key_from_labels(["事務職", "正社員"]) == "office"
    assert category_key_from_labels(["ITエンジニア職", "正社員"]) == "it"


def test_category_key_from_labels_walks_every_label_not_just_first() -> None:
    """Mirrors `parser.py::_resolve_display_thumbnail`'s corrected shape —
    Jobcan's label order is observation, not contract."""
    assert category_key_from_labels(["正社員", "介護職"]) == "care"


def test_category_key_from_labels_covers_all_17_known_job_types() -> None:
    for label in LABEL_TO_CATEGORY:
        assert category_key_from_labels([label]) is not None


def test_category_key_from_labels_none_for_unrecognised_label() -> None:
    assert category_key_from_labels(["架空職種"]) is None


def test_category_key_from_labels_none_for_empty_list() -> None:
    assert category_key_from_labels([]) is None


def test_build_card_view_derives_all_fields() -> None:
    snapshot = snapshot_from_offer(
        _offer(),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status="active",
        list_item=_list_item(),
        category_ids=["18773"],
    )

    view = build_card_view(snapshot)

    assert view is not None
    assert view.category_key == "care"
    assert view.salary_chip == "20.0 万円〜"
    assert view.holiday_chip == "110 日"
    assert view.facility_key == "facility-四箇(デイ・有料)"
    assert view.item.job_id == "1"


def test_build_card_view_none_when_list_item_absent() -> None:
    snapshot = snapshot_from_offer(
        _offer(),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status="active",
        list_item=None,
        category_ids=["18773"],
    )

    assert build_card_view(snapshot) is None


def _snapshot_for_chips(
    job_id: str,
    *,
    category_ids: list[str],
    sync_status: str = "active",
    list_item: Any = "unset",
) -> Any:
    resolved_item = (
        _list_item(job_id=job_id) if list_item == "unset" else list_item
    )
    return snapshot_from_offer(
        _offer(job_id=job_id),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=resolved_item,
        category_ids=category_ids,
    )


def test_build_job_type_chips_counts_and_sorts_descending() -> None:
    snapshots = {
        "1": _snapshot_for_chips("1", category_ids=["18773"]),
        "2": _snapshot_for_chips("2", category_ids=["18773"]),
        "3": _snapshot_for_chips("3", category_ids=["18983"]),
    }

    chips = build_job_type_chips(snapshots)

    assert [(c.category_id, c.name, c.count) for c in chips] == [
        ("18773", "介護職", 2),
        ("18983", "看護職", 1),
    ]


def test_build_job_type_chips_omits_zero_count_categories() -> None:
    """Every job type not present in `snapshots` (e.g. 新卒・既卒総合職 with
    0 active postings) must not produce a chip a visitor could press only to
    see 0 results."""
    chips = build_job_type_chips({"1": _snapshot_for_chips("1", category_ids=["18773"])})

    assert [c.category_id for c in chips] == ["18773"]


def test_build_job_type_chips_counts_multi_category_posting_for_each() -> None:
    """A posting legitimately listed under more than one category
    (`crawler.crawl_all`'s docstring, e.g. 夜勤専従 also under 介護職) counts
    toward every one of its chips."""
    snapshots = {"1": _snapshot_for_chips("1", category_ids=["18773", "18988"])}

    chips = build_job_type_chips(snapshots)

    assert {(c.category_id, c.count) for c in chips} == {("18773", 1), ("18988", 1)}


def test_build_job_type_chips_excludes_closed_and_missing_list_item() -> None:
    snapshots = {
        "1": _snapshot_for_chips("1", category_ids=["18773"], sync_status="closed"),
        "2": _snapshot_for_chips("2", category_ids=["18773"], list_item=None),
    }

    assert build_job_type_chips(snapshots) == []
