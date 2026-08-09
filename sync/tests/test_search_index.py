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
    category_ids: list[str] | None = None,
) -> Any:
    resolved_item = _list_item(job_id, labels=labels) if list_item is _UNSET else list_item
    return snapshot_from_offer(
        _offer(job_id, address=address, label="".join(labels)),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=resolved_item,
        category_ids=category_ids if category_ids is not None else ["18773"],
    )


_YONKA = "【福岡】あおぞらケアグループ四箇（デイ・有料）"


def test_build_search_index_includes_active_jobs_with_list_item() -> None:
    snapshots = {"1": _snapshot("1", address=_YONKA, labels=["介護職", "正社員"])}

    index, warnings = build_search_index(snapshots)

    assert len(index["jobs"]) == 1
    job = index["jobs"][0]
    assert job["id"] == "1"
    assert job["category"] == "care"
    assert job["jobTypes"] == ["18773"]
    assert job["employment"] == ["正社員"]
    assert job["area"] == "fukuoka"
    assert job["facilityKey"] == "facility-四箇(デイ・有料)"
    assert warnings == []


def test_build_search_index_job_types_reflects_multiple_category_ids() -> None:
    """A posting legitimately listed under more than one category
    (`crawler.crawl_all`'s docstring: e.g. 夜勤専従 also under 介護職) must
    keep every id in `jobTypes`, not just the first — the 17-category filter
    (Stage 3 follow-up, 2026-08-09) needs the full set to match either
    chip."""
    snapshots = {
        "1": _snapshot(
            "1", address=_YONKA, labels=["介護職"], category_ids=["18773", "18988"]
        )
    }

    index, _warnings = build_search_index(snapshots)

    assert index["jobs"][0]["jobTypes"] == ["18773", "18988"]


def test_build_search_index_employment_independent_of_label_order() -> None:
    """`labels[1:]` would silently drop `正社員` here — category label
    order is observation, not contract (codex review finding, 2026-08-09)."""
    snapshots = {"1": _snapshot("1", address=_YONKA, labels=["正社員", "介護職"])}

    index, _warnings = build_search_index(snapshots)

    job = index["jobs"][0]
    assert job["category"] == "care"
    assert job["employment"] == ["正社員"]


def test_build_search_index_excludes_closed_and_missing_list_item() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職"], sync_status="closed"),
        "2": _snapshot("2", address=_YONKA, labels=["介護職"], list_item=None),
    }

    index, warnings = build_search_index(snapshots)

    assert index["jobs"] == []
    assert warnings == []


def test_build_search_index_facility_aggregates_job_count_and_categories() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職"]),
        "2": _snapshot("2", address=_YONKA, labels=["看護職"]),
    }

    index, _warnings = build_search_index(snapshots)

    facility = index["facilities"]["facility-四箇(デイ・有料)"]
    assert facility["jobCount"] == 2
    assert set(facility["categories"]) == {"care", "nurse"}
    assert facility["area"] == "fukuoka"
    assert "lat" in facility and "lng" in facility


def test_build_search_index_facility_name_is_display_name_not_raw_address() -> None:
    """`facility["name"]` renders directly into `map-search.js`'s pin popup
    and "この拠点のみ表示中" filter label — it must stay a human-readable
    facility name, not the geocoding `source_address` (code-reviewer
    finding, 2026-08-09: this used to leak a raw postal address)."""
    snapshots = {"1": _snapshot("1", address=_YONKA, labels=["介護職"])}

    index, _warnings = build_search_index(snapshots)

    facility = index["facilities"]["facility-四箇(デイ・有料)"]
    assert facility["name"] == "四箇（デイ・有料）"
    assert "福岡県" not in facility["name"]


def test_build_search_index_distinguishes_same_place_name_different_address() -> None:
    """`博多（デイ・有料）` and `博多（訪問介護/訪問看護・居宅）` are two
    different physical addresses that both reduce to "博多" before the
    parenthetical — collapsing them into one `facility-博多` key would
    silently merge their pins/job counts (code-reviewer finding,
    2026-08-09)."""
    snapshots = {
        "1": _snapshot(
            "1", address="【福岡】あおぞらケアグループ博多（デイ・有料）", labels=["介護職"]
        ),
        "2": _snapshot(
            "2",
            address="【福岡】あおぞらケアグループ博多（訪問介護/訪問看護・居宅）",
            labels=["訪問看護"],
        ),
    }

    index, _warnings = build_search_index(snapshots)

    assert len(index["facilities"]) == 2
    assert index["facilities"]["facility-博多(デイ・有料)"]["jobCount"] == 1
    assert index["facilities"]["facility-博多(訪問介護/訪問看護・居宅)"]["jobCount"] == 1


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

    index, warnings = build_search_index(snapshots)

    job = index["jobs"][0]
    assert job["area"] == "kagoshima"
    assert job["facilityKey"] not in index["facilities"]
    assert warnings == [
        "no facility_coords match (no map pin) for job_ids: ['1']"
    ]


def test_build_search_index_warns_on_unrecognised_category_label() -> None:
    """A future Jobcan label this table has never seen must be surfaced,
    not silently dropped into `category=None` with no trace (silent-
    failure-hunter finding, 2026-08-09) — indistinguishable otherwise from
    a genuine future data-drift case."""
    snapshots = {"1": _snapshot("1", address=_YONKA, labels=["架空職種", "正社員"])}

    index, warnings = build_search_index(snapshots)

    assert index["jobs"][0]["category"] is None
    assert warnings == [
        "no category_key match (no colour accent) for job_ids: ['1']"
    ]
