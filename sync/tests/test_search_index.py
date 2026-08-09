"""Tests for `search_index.py` (Stage 3 — `GET /jobs/search-index.json`
payload builder)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sync.models import JobListItem, JobOffer
from sync.search_index import build_search_index
from sync.snapshot import snapshot_from_offer


def _offer(job_id: str, *, address: str, label: str = "介護職正社員") -> JobOffer:
    return JobOffer(
        job_id=job_id,
        title="テスト求人",
        body_html="<p>本文</p>",
        address=address,
        label=label,
        location="福岡県福岡市",
        salary="【月額】200,000円〜",
        apply_url=f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}",
        source_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        page_title=None,
    )


def _list_item(job_id: str, *, labels: list[str]) -> JobListItem:
    return JobListItem(
        job_id=job_id,
        title="テスト求人",
        address="福岡市早良区",
        description="excerpt",
        thumbnail_url=None,
        source_thumbnail_url=None,
        detail_url=f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}",
        labels=labels,
    )


_UNSET: Any = object()


def _snapshot(
    job_id: str,
    *,
    address: str,
    labels: list[str],
    sync_status: str = "active",
    list_item: Any = _UNSET,
) -> Any:
    resolved_item = _list_item(job_id, labels=labels) if list_item is _UNSET else list_item
    return snapshot_from_offer(
        _offer(job_id, address=address, label="".join(labels)),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=resolved_item,
        category_ids=["18773"],
    )


def test_build_search_index_includes_active_jobs_with_list_item() -> None:
    address = "【福岡】あおぞらケアグループ四箇（デイ・有料）"
    snapshots = {"1": _snapshot("1", address=address, labels=["介護職", "正社員"])}

    index = build_search_index(snapshots)

    assert len(index["jobs"]) == 1
    job = index["jobs"][0]
    assert job["id"] == "1"
    assert job["category"] == "care"
    assert job["employment"] == ["正社員"]
    assert job["area"] == "fukuoka"
    assert job["facilityKey"] == "facility-四箇"


def test_build_search_index_employment_independent_of_label_order() -> None:
    """`labels[1:]` would silently drop `正社員` here — category label
    order is observation, not contract (codex review finding, 2026-08-09)."""
    address = "【福岡】あおぞらケアグループ四箇（デイ・有料）"
    snapshots = {"1": _snapshot("1", address=address, labels=["正社員", "介護職"])}

    index = build_search_index(snapshots)

    job = index["jobs"][0]
    assert job["category"] == "care"
    assert job["employment"] == ["正社員"]


_YONKA = "【福岡】あおぞらケアグループ四箇（デイ・有料）"


def test_build_search_index_excludes_closed_and_missing_list_item() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職"], sync_status="closed"),
        "2": _snapshot("2", address=_YONKA, labels=["介護職"], list_item=None),
    }

    index = build_search_index(snapshots)

    assert index["jobs"] == []


def test_build_search_index_facility_aggregates_job_count_and_categories() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職"]),
        "2": _snapshot("2", address=_YONKA, labels=["看護職"]),
    }

    index = build_search_index(snapshots)

    facility = index["facilities"]["facility-四箇"]
    assert facility["jobCount"] == 2
    assert set(facility["categories"]) == {"care", "nurse"}
    assert facility["area"] == "fukuoka"
    assert "lat" in facility and "lng" in facility


def test_build_search_index_job_without_geocoded_facility_has_no_facility_entry() -> None:
    """The roaming GH posting (`共同生活援助`) still appears in `jobs` for
    category/employment/freeword filtering, but its `facilityKey` has no
    entry in `facilities` — `map-search.js` already treats a missing
    `facilities[key]` lookup as "no pin" (`if (!f) return;`)."""
    snapshots = {
        "1": _snapshot(
            "1", address="【鹿児島】あおぞらケアグループ共同生活援助", labels=["世話人", "正社員"]
        ),
    }

    index = build_search_index(snapshots)

    job = index["jobs"][0]
    assert job["area"] == "kagoshima"
    assert job["facilityKey"] not in index["facilities"]
