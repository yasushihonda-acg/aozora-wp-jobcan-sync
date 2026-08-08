"""Renderer tests — AC-1 (output content), AC-9 (no upstream script/style/form)."""

from __future__ import annotations

from sync.parser import parse_job_detail
from sync.renderer import _site_relative, render_job_detail

from .conftest import SAMPLE_JOB_ID, SAMPLE_SOURCE_URL


class TestSiteRelative:
    """`site_relative` Jinja filter — see its docstring for why this exists
    (Stage 1 of the Cloud Run consolidation, 2026-08-08: a `/jobs/...` page
    resolving a page-relative `assets/img/...` thumbnail 404s)."""

    def test_prefixes_page_relative_path(self) -> None:
        assert _site_relative("assets/img/illust-job-care.png") == "/assets/img/illust-job-care.png"

    def test_leaves_absolute_url_unchanged(self) -> None:
        url = "https://storage.googleapis.com/ats-public-files/foo.jpg"
        assert _site_relative(url) == url

    def test_leaves_already_site_root_relative_unchanged(self) -> None:
        assert _site_relative("/assets/img/x.png") == "/assets/img/x.png"

    def test_none_becomes_empty_string(self) -> None:
        assert _site_relative(None) == ""


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

    def test_canonical_link_to_own_site(self, sample_html: str) -> None:
        """Stage 1 of the Cloud Run consolidation (2026-08-08): canonical
        points at this service's own URL, not the upstream Jobcan one — the
        old behaviour undermined the "keep closed listings up for SEO"
        design intent (rel=canonical pointing elsewhere tells crawlers the
        in-house page is a duplicate, not the authoritative copy)."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer, base_url="https://recruit.aozora-cg.com")
        assert 'rel="canonical"' in html
        assert f'href="https://recruit.aozora-cg.com/jobs/{SAMPLE_JOB_ID}"' in html

    def test_canonical_is_site_root_relative_without_base_url(self, sample_html: str) -> None:
        """`base_url=""` (the default — local dev/tests) still renders a
        path, just not a fully-qualified one."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert f'href="/jobs/{SAMPLE_JOB_ID}"' in html

    def test_closed_true_hides_apply_cta_and_shows_banner(self, sample_html: str) -> None:
        """B-8: a `sync_status="closed"` snapshot still gets a detail page
        (SEO / 被リンク維持), but must not offer a dead apply link."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer, closed=True)
        assert "job-detail__apply-btn" not in html
        assert "募集は終了しました" in html

    def test_closed_false_is_the_default(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert "job-detail__apply-btn" in html
        assert "募集終了" not in html


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

    def test_thumbnail_src_is_site_root_relative(self) -> None:
        """Stage 1 of the Cloud Run consolidation (2026-08-08): thumbnail
        `src` must not be the raw stored `assets/img/...` value — see
        `_site_relative`'s docstring."""
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert 'src="/assets/img/illust-job-care.png"' in html
        assert 'src="assets/img/illust-job-care.png"' not in html

    def test_main_class_is_job_list(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert '<main class="job-list">' in html

    def test_canonical_points_to_own_site(self) -> None:
        """Stage 1 of the Cloud Run consolidation (2026-08-08): see
        TestRenderRealJob.test_canonical_link_to_own_site for why."""
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page, base_url="https://recruit.aozora-cg.com")
        assert 'rel="canonical"' in html
        assert (
            f'href="https://recruit.aozora-cg.com/jobs/?category_id={page.category_id}"' in html
        )

    def test_canonical_is_site_root_relative_without_base_url(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert f'href="/jobs/?category_id={page.category_id}"' in html
