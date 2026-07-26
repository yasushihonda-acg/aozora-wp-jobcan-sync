"""Tests that the grounding context assembled from faq.yaml + jobs_detail.json
(facility/job summary derived from the latter) actually contains what the
system prompt promises the model it will find."""

from __future__ import annotations

import json
from pathlib import Path

from chatbot.knowledge import _KNOWLEDGE_DIR, build_context, resolve_jobs


def test_context_includes_all_faq_questions() -> None:
    context = build_context()

    assert "未経験でも応募できますか？" in context
    assert "勤務地は選べますか？" in context
    assert "夜勤のない働き方はできますか？" in context
    assert "選考にはどれくらいかかりますか？" in context
    assert "見学だけでも可能ですか？" in context


def test_context_includes_job_summary_aggregates() -> None:
    context = build_context()

    assert "13 拠点" in context
    assert "34 件" in context
    assert "fukuoka" in context
    assert "kagoshima" in context


def test_context_includes_facility_names() -> None:
    context = build_context()

    assert "あおぞらケアグループ四箇" in context
    assert "本社" in context


def test_context_is_cached_across_calls() -> None:
    """`build_context` is `lru_cache`d — repeated calls must return the same
    (identical, not just equal) string object without re-reading files."""
    first = build_context()
    second = build_context()

    assert first is second


def test_context_includes_job_listing_for_job_id_selection() -> None:
    context = build_context()

    assert "応募可能な求人一覧" in context
    assert "1777023" in context
    assert "【社】介護職（博多／デイ・有料）" in context


def test_context_includes_service_types_for_job_id_disambiguation() -> None:
    """Regression test: the job listing must expose service type (デイサービス/
    訪問介護/etc.) as a distinct column, not just buried inside the free-text
    title — otherwise the model conflates different service types under the
    same `category` (e.g. デイサービス vs 訪問介護, both `care`)."""
    context = build_context()

    assert "サービス種別" in context
    # 1777023 は「あおぞらケアグループ博多（デイ・有料）」の求人
    assert "デイサービス, 有料老人ホーム" in context
    # 鹿児島北の求人は訪問介護のみで、デイサービスを含まない
    assert "訪問介護" in context


def test_jobs_detail_service_types_extracted_from_facility_name() -> None:
    detail = json.loads((_KNOWLEDGE_DIR / "jobs_detail.json").read_text(encoding="utf-8"))
    by_id = {job["id"]: job for job in detail}

    assert by_id["1777023"]["service_types"] == ["デイサービス", "有料老人ホーム"]
    assert by_id["1891471"]["service_types"] == ["特別養護老人ホーム"]
    # 本社勤務（IT/事務）はサービス種別を持たない
    assert by_id["452341"]["service_types"] == []


def test_jobs_detail_service_types_title_override_for_specialist_role() -> None:
    """`90447`（相談支援専門員）の施設「小松原（相談支援・就労・GH）」は
    グループホーム／就労支援も併設するが、この求人自体の職種は相談支援専門員
    であり GH／就労支援の直接業務ではない。施設タグをそのまま付けると
    「グループホームの求人」検索に誤って混入する（Codex review-diff 指摘）。"""
    detail = json.loads((_KNOWLEDGE_DIR / "jobs_detail.json").read_text(encoding="utf-8"))
    by_id = {job["id"]: job for job in detail}

    assert by_id["90447"]["service_types"] == ["相談支援"]


def test_jobs_detail_has_34_entries_matching_jobs_json() -> None:
    """Regression test: `jobs_detail.json` must stay in sync with
    `mockup/assets/data/jobs.json` (same ids) — see
    `scripts/build_jobs_detail.py` for how it's regenerated."""
    detail = json.loads((_KNOWLEDGE_DIR / "jobs_detail.json").read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]
    jobs_json = json.loads(
        (repo_root / "mockup" / "assets" / "data" / "jobs.json").read_text(encoding="utf-8")
    )

    assert len(detail) == 34
    assert {job["id"] for job in detail} == {job["id"] for job in jobs_json["jobs"]}
    for job in detail:
        assert job["url"] == f"jobs/{job['id']}.html"


def test_resolve_jobs_returns_known_ids_only() -> None:
    resolved = resolve_jobs(["1777023", "9999999"])

    assert [job.id for job in resolved] == ["1777023"]
    assert resolved[0].url == "jobs/1777023.html"


def test_resolve_jobs_deduplicates_and_caps_at_three() -> None:
    resolved = resolve_jobs(["1777023", "1777023", "2264134", "2264135", "2264205"])

    assert len(resolved) == 3
    assert [job.id for job in resolved] == ["1777023", "2264134", "2264135"]


def test_resolve_jobs_preserves_model_relevance_order() -> None:
    resolved = resolve_jobs(["2264135", "1777023"])

    assert [job.id for job in resolved] == ["2264135", "1777023"]


def test_resolve_jobs_empty_input_returns_empty_list() -> None:
    assert resolve_jobs([]) == []
