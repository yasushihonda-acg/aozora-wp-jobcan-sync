"""Tests that the grounding context assembled from faq.yaml + jobs_summary.json
actually contains what the system prompt promises the model it will find."""

from __future__ import annotations

from chatbot.knowledge import build_context


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
