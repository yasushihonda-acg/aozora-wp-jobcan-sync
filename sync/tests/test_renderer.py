"""Renderer tests — AC-1 (output content), AC-9 (no upstream script/style/form)."""

from __future__ import annotations

from sync.parser import parse_job_detail
from sync.renderer import render_job_detail

from .conftest import SAMPLE_JOB_ID, SAMPLE_SOURCE_URL


class TestRenderRealJob:
    def test_render_smoke(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        # AC-1 acceptance content
        assert html.startswith("<!DOCTYPE html>")
        assert "【社】介護職（博多／デイ・有料）" in html
        assert f"https://recruit.jobcan.jp/aozora/entry/new/{SAMPLE_JOB_ID}" in html
        assert "job-detail__title" in html
        assert "job-detail__apply-btn" in html

    def test_no_upstream_script_or_form(self, sample_html: str) -> None:
        """AC-9 — rendered output must not contain script/style/form."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert "<script" not in html
        assert "<style" not in html
        assert "<form" not in html

    def test_canonical_link_to_source(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        # canonical should point to the original Jobcan URL (Phase 0 default;
        # final canonical strategy depends on Jobcan official response).
        # Jinja2 escapes `&` to `&amp;`, so we check against the escaped form.
        assert 'rel="canonical"' in html
        escaped = SAMPLE_SOURCE_URL.replace("&", "&amp;")
        assert escaped in html
