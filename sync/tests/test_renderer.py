"""Renderer tests — AC-1 (output content), AC-9 (no upstream script/style/form)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sync.parser import parse_job_detail
from sync.renderer import _site_relative, render_job_detail

from .conftest import SAMPLE_JOB_ID, SAMPLE_SOURCE_URL

REPO_ROOT = Path(__file__).resolve().parents[2]


def _meta_contents(html: str, attr: str, value: str) -> list[str]:
    """Every `content="..."` of the `<meta {attr}="{value}">` tags in `html`.

    Returns a list (not a single value) on purpose: the duplicate-tag
    regressions this module guards against (`theme-color` living in BOTH
    `base.html` and `job_detail.html`) are only visible as a count.
    """
    pattern = re.compile(
        rf'<meta\s+[^>]*\b{re.escape(attr)}="{re.escape(value)}"[^>]*>'
    )
    contents: list[str] = []
    for tag in pattern.findall(html):
        match = re.search(r'content="([^"]*)"', tag)
        if match:
            contents.append(match.group(1))
    return contents


def _one_meta(html: str, attr: str, value: str) -> str:
    found = _meta_contents(html, attr, value)
    assert len(found) == 1, f"expected exactly one {attr}={value} meta, got {found}"
    return found[0]


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
    """Stage 2 (job-detail design parity, 2026-08-08): `job_detail.html` was
    rewritten to Phase A's (`mockup/jobs/*.html`) BEM classes/section
    structure — see `detail_sections.py`."""

    def test_render_smoke(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        # AC-1 acceptance content
        assert html.startswith("<!DOCTYPE html>")
        assert "【社】介護職（博多／デイ・有料）" in html
        assert f"https://recruit.jobcan.jp/aozora/entry/new/{SAMPLE_JOB_ID}" in html
        assert "job-detail-hero__title" in html
        assert "job-detail-summary__cta" in html

    def test_every_section_present_for_a_fully_populated_posting(self, sample_html: str) -> None:
        """The fixture's `extra_lines` covers every known header (必須/歓迎
        スキル・経験, 待遇, 選考フロー, 休日・休暇) — every optional section
        must render, not just the always-present summary/仕事内容."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert "応募資格" in html
        assert "待遇・福利厚生" in html
        assert "選考の流れ" in html
        assert html.count('class="job-detail-section"') == 4  # 仕事内容 + 3 optional

    def test_only_known_scripts_present(self, sample_html: str) -> None:
        """AC-9's actual intent — no *upstream* (Jobcan `body_html`) script
        tag leaks through `bleach` sanitization. The template's own two
        `<script>` tags (JSON-LD + chat-widget) are legitimate Stage 2
        additions, not a violation of that intent."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert "<style" not in html
        assert "<form" not in html
        assert html.count("<script") == 2
        assert 'type="application/ld+json"' in html
        assert "chat-widget.js" in html

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
        (SEO / 被リンク維持), but must not offer a dead apply link anywhere —
        summary CTA, entry-cta section, or the fixed bottom bar."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer, closed=True)
        assert "job-detail-summary__cta" not in html
        assert "entry-cta-bar" not in html
        assert "この求人に応募する" not in html
        assert "募集は終了しました" in html

    def test_closed_false_is_the_default(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        html = render_job_detail(offer)
        assert "job-detail-summary__cta" in html
        assert "entry-cta-bar" in html
        assert "募集終了" not in html

    def test_extracted_text_is_html_escaped(self, sample_html: str) -> None:
        """`detail_sections.py`'s extraction functions return plain text —
        Jinja2 autoescape (not any manual escaping in that module) is what
        must neutralise a hostile `extra_lines` value. A qualification value
        containing an HTML tag must appear as text, not a live element."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        hostile = offer.model_copy(
            update={
                "extra_lines": [
                    *offer.extra_lines,
                    ("必要資格", "<script>alert(1)</script>資格不問"),
                ]
            }
        )
        html = render_job_detail(hostile)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_missing_optional_sections_hidden_not_empty(self) -> None:
        """AC-3: a posting whose `extra_lines`/`body_html` matches none of
        the known headers must still render 200 with those sections simply
        absent, not an empty heading."""
        from sync.models import JobOffer

        offer = JobOffer(
            job_id="999",
            title="テスト求人",
            body_html="<p>【仕事内容】見出し以降の本文のみ、他の見出しなし</p>",
            address="テスト支店",
            label="介護職正社員",
            location="テスト駅から徒歩5分",
            salary="応相談",
            apply_url="https://recruit.jobcan.jp/aozora/entry/new/999",
            source_url="https://recruit.jobcan.jp/aozora/job_offers/999",
            page_title=None,
            extra_lines=[],
        )
        html = render_job_detail(offer)
        assert html.startswith("<!DOCTYPE html>")
        assert "応募資格" not in html
        assert "待遇・福利厚生" not in html
        assert "選考の流れ" not in html
        assert "job-hashtags" not in html
        assert "aside-card" not in html
        # The always-present sections + the one section this posting does
        # have data for still render.
        assert "job-detail-summary__cta" in html
        assert "仕事内容" in html

    def test_logs_warning_when_work_description_section_is_empty(
        self, caplog: Any
    ) -> None:
        """Unlike 応募資格/待遇/選考フロー, every real Jobcan posting has a
        「【仕事内容】」 heading — an empty result is the strongest available
        signal of `body_html` format drift, and that degrade must be
        observable in production, not silent (second-opinion review
        finding)."""
        from sync.models import JobOffer

        offer = JobOffer(
            job_id="999",
            title="テスト求人",
            body_html="<p>仕事内容の見出しがない本文</p>",
            address="テスト支店",
            label="介護職正社員",
            location="テスト駅から徒歩5分",
            salary="応相談",
            apply_url="https://recruit.jobcan.jp/aozora/entry/new/999",
            source_url="https://recruit.jobcan.jp/aozora/job_offers/999",
            page_title=None,
            extra_lines=[],
        )
        with caplog.at_level(logging.WARNING, logger="sync.renderer"):
            render_job_detail(offer)

        assert any("仕事内容" in record.message for record in caplog.records)
        assert any(record.job_id == "999" for record in caplog.records)  # type: ignore[attr-defined]

    def test_no_warning_when_work_description_section_is_present(
        self, sample_html: str, caplog: Any
    ) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        with caplog.at_level(logging.WARNING, logger="sync.renderer"):
            render_job_detail(offer)

        assert caplog.records == []


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
        # No upstream (Jobcan) noise survives — only this template's own
        # chat-widget script (Stage 3, matching every other page) is
        # expected, not anything scraped from the source HTML.
        assert html.count("<script") == 1
        assert "chat-widget.js" in html
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

    def test_heading_uses_job_type_name_when_category_id_known(self) -> None:
        """Category-page filter-nav follow-up (2026-08-14): `page.category_id`
        ("18773", from `_src()`) maps to a real `JOB_TYPE_NAMES` entry."""
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page)
        assert '<h1 class="job-list__title">介護職</h1>' in html

    def test_heading_falls_back_when_category_id_unknown(self) -> None:
        """A `category_id` this table has never seen (data drift, or a
        CLI-constructed page with no matching Jobcan category) must not
        crash the template — `job_type_names.get(..., "求人一覧")` degrades
        to the generic heading instead."""
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        page = page.model_copy(update={"category_id": "99999999"})
        html = render_job_list(page)
        assert '<h1 class="job-list__title">求人一覧</h1>' in html

    def test_search_index_renders_inline_script_when_provided(self) -> None:
        """`search_index` (category-page filter-nav follow-up, 2026-08-14) is
        embedded as `<script type="application/json" id="job-search-index">`
        so `map-search.js` can read it synchronously instead of waiting on a
        `/jobs/search-index.json` round-trip — same `</` escaping convention
        `json_ld` already uses (`renderer.py`)."""
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(
            page,
            search_mode=True,
            search_index={"facilities": {}, "jobs": [{"id": "1", "jobTypes": ["18773"]}]},
        )
        assert 'id="job-search-index"' in html
        assert '"id": "1"' in html

    def test_search_index_omitted_renders_no_inline_script(self) -> None:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        page = parse_job_list(self._list_html(), self._src())
        html = render_job_list(page, search_mode=True)
        assert 'id="job-search-index"' not in html


class TestSocialMeta:
    """Stage 4-E (2026-08-09): `base.html` had no `og:*`/`twitter:*` tags at
    all, so Phase B was a regression from Phase A's own
    `mockup/index.html` (og:title/description/type/url + theme-color) —
    shared links rendered as a bare URL with no card. The tags now live in
    `base.html`'s `social_meta` block and reuse the existing
    `page_title`/`canonical_url` blocks via Jinja2's `self.<block>()`, so
    every child template gets a correct og:title/og:url for free."""

    @staticmethod
    def _detail_html(**kwargs: Any) -> str:
        path = (
            Path(__file__).parent
            / "fixtures"
            / "jobcan_responses"
            / f"job_{SAMPLE_JOB_ID}.html"
        )
        offer = parse_job_detail(
            path.read_text(encoding="utf-8"), SAMPLE_SOURCE_URL, SAMPLE_JOB_ID
        )
        return render_job_detail(offer, **kwargs)

    @staticmethod
    def _list_html(**kwargs: Any) -> str:
        from sync.parser import parse_job_list
        from sync.renderer import render_job_list

        path = (
            Path(__file__).parent / "fixtures" / "jobcan_responses" / "list_care.html"
        )
        page = parse_job_list(
            path.read_text(encoding="utf-8"),
            "https://recruit.jobcan.jp/aozora/list?category_id=18773",
        )
        return render_job_list(page, **kwargs)

    def test_detail_has_every_core_og_tag_exactly_once(self) -> None:
        html = self._detail_html(base_url="https://recruit.aozora-cg.com")
        assert _one_meta(html, "property", "og:type") == "article"
        assert _one_meta(html, "property", "og:site_name")
        assert _one_meta(html, "property", "og:locale") == "ja_JP"
        assert _one_meta(html, "property", "og:title")
        assert _one_meta(html, "property", "og:description")
        assert (
            _one_meta(html, "property", "og:url")
            == f"https://recruit.aozora-cg.com/jobs/{SAMPLE_JOB_ID}"
        )
        assert (
            _one_meta(html, "property", "og:image")
            == "https://recruit.aozora-cg.com/assets/img/sky-hero.jpg"
        )
        assert _one_meta(html, "name", "twitter:card") == "summary_large_image"

    def test_list_has_website_og_type_and_meta_description(self) -> None:
        """The direct regression check: Phase A's `mockup/index.html` has
        both, Phase B's listing page had neither."""
        html = self._list_html()
        assert _one_meta(html, "property", "og:type") == "website"
        description = _one_meta(html, "name", "description")
        assert description  # not an empty attribute

    def test_og_title_matches_title_tag(self) -> None:
        """Wiring check for `{{ self.page_title() }}` — a stale hard-coded
        og:title would silently drift from the real page title."""
        for html in (self._detail_html(), self._list_html()):
            title = re.search(r"<title>(.*?)</title>", html, re.S)
            assert title is not None
            assert _one_meta(html, "property", "og:title") == title.group(1).strip()

    def test_og_url_matches_canonical_link(self) -> None:
        """Wiring check for `{{ self.canonical_url() }}`."""
        for html in (
            self._detail_html(base_url="https://recruit.aozora-cg.com"),
            self._list_html(base_url="https://recruit.aozora-cg.com"),
        ):
            canonical = re.search(r'<link rel="canonical" href="([^"]*)">', html)
            assert canonical is not None
            assert _one_meta(html, "property", "og:url") == canonical.group(1)

    def test_og_description_falls_back_to_site_description_when_lead_empty(self) -> None:
        """A posting whose `body_html` starts straight at 「【仕事内容】」 has
        no lead paragraph (`detail_sections.extract_lead_paragraph`) — the
        share card must not degrade to `content=""`."""
        from sync.models import JobOffer
        from sync.renderer import SITE_DESCRIPTION

        offer = JobOffer(
            job_id="999",
            title="テスト求人",
            body_html="<p>【仕事内容】介護業務全般</p>",
            address="テスト支店",
            label="介護職正社員",
            location="テスト駅から徒歩5分",
            salary="応相談",
            apply_url="https://recruit.jobcan.jp/aozora/entry/new/999",
            source_url="https://recruit.jobcan.jp/aozora/job_offers/999",
            page_title=None,
            extra_lines=[],
        )
        html = render_job_detail(offer)
        assert _one_meta(html, "property", "og:description") == SITE_DESCRIPTION

    def test_theme_color_is_not_duplicated_on_detail_page(self) -> None:
        """`job_detail.html` used to carry its own `theme-color`/`description`
        metas; both moved into `base.html` and the originals were removed."""
        assert _meta_contents(self._detail_html(), "name", "theme-color") == ["#0a52b8"]
        assert len(_meta_contents(self._detail_html(), "name", "description")) == 1

    def test_og_image_file_exists_in_repo(self) -> None:
        """`OG_IMAGE_PATH` is served from this app's own `/assets` mount
        (`app.py` StaticFiles → `mockup/assets`), so a typo here is a broken
        share card that no template test would catch."""
        from sync.renderer import OG_IMAGE_PATH

        assert OG_IMAGE_PATH.startswith("/assets/")
        assert (REPO_ROOT / "mockup" / OG_IMAGE_PATH.lstrip("/")).is_file()
