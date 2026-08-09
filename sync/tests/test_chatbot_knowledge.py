"""Tests for `chatbot_knowledge.py` (`GET /jobs/chatbot-knowledge.json`
payload builder — the source `chatbot/`'s knowledge base fetches instead of
the stale, hand-maintained Phase A `jobs_detail.json`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sync.chatbot_knowledge import build_chatbot_knowledge
from sync.models import JobListItem, JobOffer
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


def _list_item(job_id: str, *, title: str, labels: list[str]) -> JobListItem:
    return JobListItem(
        job_id=job_id,
        title=title,
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
    title: str = "テスト求人",
    sync_status: str = "active",
    list_item: Any = _UNSET,
) -> Any:
    resolved_item = (
        _list_item(job_id, title=title, labels=labels) if list_item is _UNSET else list_item
    )
    return snapshot_from_offer(
        _offer(job_id, address=address, label="".join(labels)),
        now=datetime(2026, 8, 9, tzinfo=UTC),
        sync_status=sync_status,  # type: ignore[arg-type]
        list_item=resolved_item,
        category_ids=["18773"],
    )


_YONKA = "【福岡】あおぞらケアグループ四箇（デイ・有料）"
_KOMATSUBARA = "【鹿児島】あおぞらケアグループ小松原（相談支援・就労・GH）"


def test_build_chatbot_knowledge_returns_nine_field_shape() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職", "正社員"], title="介護職員募集"),
    }

    records, warnings = build_chatbot_knowledge(snapshots)

    assert len(records) == 1
    record = records[0]
    assert set(record.keys()) == {
        "id",
        "title",
        "category",
        "employment",
        "area",
        "facility",
        "city",
        "service_types",
        "url",
    }
    assert record["id"] == "1"
    assert record["title"] == "介護職員募集"
    assert record["category"] == "care"
    assert record["employment"] == ["正社員"]
    assert record["area"] == "fukuoka"
    assert record["facility"] == "四箇（デイ・有料）"
    assert record["city"] == "福岡市早良区"
    assert record["service_types"] == ["デイサービス", "有料老人ホーム"]
    assert record["url"] == "jobs/1"
    assert warnings == []


def test_build_chatbot_knowledge_excludes_closed_and_missing_list_item() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["介護職"], sync_status="closed"),
        "2": _snapshot("2", address=_YONKA, labels=["介護職"], list_item=None),
    }

    records, warnings = build_chatbot_knowledge(snapshots)

    assert records == []
    assert warnings == []


def test_build_chatbot_knowledge_missing_coords_degrades_to_empty_city_with_warning() -> None:
    """The roaming GH posting (`共同生活援助`) has no `FACILITY_COORDS` entry
    — unlike `search_index.py` (which simply omits it from `facilities`),
    this must still appear in the chatbot's job list (removing a real,
    applyable job from the recommendation pool is exactly the bug this
    module exists to fix), just with `city=""` and a warning so the gap is
    observable rather than silently accepted."""
    snapshots = {
        "1": _snapshot(
            "1",
            address="【鹿児島】あおぞらケアグループ共同生活援助",
            labels=["世話人", "正社員"],
            title="グループホーム世話人",
        ),
    }

    records, warnings = build_chatbot_knowledge(snapshots)

    assert len(records) == 1
    assert records[0]["city"] == ""
    assert records[0]["service_types"] == []
    assert warnings == ["no facility_coords match (no city) for job_ids: ['1']"]


def test_build_chatbot_knowledge_title_override_narrows_service_types() -> None:
    """A job titled `相談支援専門員` at a multi-service facility (小松原:
    相談支援・就労・GH) is specifically a 相談支援 role — tagging it with the
    facility's full service-type list would let Gemini recommend it for a
    GH/就労支援 query where it doesn't actually belong (ported from
    `chatbot/scripts/build_jobs_detail.py::_TITLE_SERVICE_TYPE_OVERRIDE`,
    originally a Codex review-diff finding on job 90447)."""
    snapshots = {
        "1": _snapshot(
            "1", address=_KOMATSUBARA, labels=["相談員", "正社員"], title="相談支援専門員募集"
        ),
    }

    records, _warnings = build_chatbot_knowledge(snapshots)

    assert records[0]["service_types"] == ["相談支援"]


def test_build_chatbot_knowledge_employment_independent_of_label_order() -> None:
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["正社員", "介護職"]),
    }

    records, _warnings = build_chatbot_knowledge(snapshots)

    assert records[0]["employment"] == ["正社員"]


def test_build_chatbot_knowledge_normalizes_null_category_to_string_with_warning() -> None:
    """`category_key_from_labels()` returns `None` for an unrecognized
    Jobcan label — chatbot's `parse_jobs_detail()` requires `category: str`
    and validates the WHOLE payload as one list, so a single `null` here
    would fail the entire knowledge refresh for every other active posting
    too (codex review finding, 2026-08-09). Must degrade to a fallback
    string, not `None`, and surface the miss via `warnings` the same way
    `search_index.py::build_search_index` already does for its own
    category miss."""
    snapshots = {
        "1": _snapshot("1", address=_YONKA, labels=["架空職種", "正社員"]),
    }

    records, warnings = build_chatbot_knowledge(snapshots)

    assert records[0]["category"] == "unknown"
    assert warnings == ["no category_key match for job_ids: ['1']"]


def test_build_chatbot_knowledge_normalizes_null_area_to_string_with_warning() -> None:
    """Same rationale as the category case above, for `area_from_address()`
    returning `None` (address with neither a `【福岡】`/`【鹿児島】` region
    marker nor a `FACILITY_COORDS` match)."""
    snapshots = {
        "1": _snapshot("1", address="架空拠点", labels=["介護職", "正社員"]),
    }

    records, warnings = build_chatbot_knowledge(snapshots)

    assert records[0]["area"] == "unknown"
    assert warnings == [
        "no facility_coords match (no city) for job_ids: ['1']",
        "no area match for job_ids: ['1']",
    ]


def test_build_chatbot_knowledge_url_has_no_html_suffix() -> None:
    """Cloud Run's canonical detail route is `/jobs/{id}` — `jobs/{id}.html`
    is a 308-redirecting legacy alias, not the value new records should
    carry (unlike Phase A's `jobs_detail.json`, which predates that route)."""
    snapshots = {"42": _snapshot("42", address=_YONKA, labels=["介護職"])}

    records, _warnings = build_chatbot_knowledge(snapshots)

    assert records[0]["url"] == "jobs/42"
