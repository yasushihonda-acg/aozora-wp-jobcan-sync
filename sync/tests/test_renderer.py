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


class TestRenderJobList:
    """Phase 2A.1b — render_job_list smoke tests."""

    @staticmethod
    def _list_html() -> str:
        from pathlib import Path

        path = (
            Path(__file__).parent / "fixtures" / "jobcan_responses" / "list_care.html"
        )
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _src() -> str:
        return (
            "https://recruit.jobcan.jp/aozora/list"
            "?category_id=18773&hide_breadcrumb=true&hide_search=true"
        )

    def test_render_smoke(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert html.startswith("<!DOCTYPE html>")
        # Page heading text
        assert "求人一覧" in html
        # All 10 items rendered as cards
        assert html.count("job-list-card__link") == len(page.items)
        # Detail URLs are present in the rendered HTML
        for item in page.items:
            assert item.job_id in html
        # No upstream noise survives
        assert "<script" not in html
        assert "<style" not in html
        assert "<form" not in html

    def test_uses_list_css_link(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        # Tokens are shared, but the list-specific CSS overrides the detail one
        assert "tokens.css" in html
        assert "sync-job-list.css" in html
        assert "sync-job-detail.css" not in html

    def test_main_class_is_job_list(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert '<main class="job-list">' in html

    def test_canonical_points_to_source_url(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert 'rel="canonical"' in html
        # Jinja2 escapes `&` to `&amp;`
        assert self._src().replace("&", "&amp;") in html
