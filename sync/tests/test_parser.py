"""Parser tests.

Covers Acceptance Criteria:
- AC-2: parser pytest all PASS, key fields populated
- AC-3: StructureChangeError on missing selectors
- AC-7: ValidationError on empty required fields (selector found, content empty)
- AC-8: apply_url is exactly the Jobcan canonical entry URL
- AC-9: sanitised body strips <script>, <style>, <form>
"""

from __future__ import annotations

import pytest

from sync.models import JobcanStructureChangeError, JobcanValidationError, JobOffer
from sync.parser import parse_job_detail

from .conftest import SAMPLE_JOB_ID, SAMPLE_SOURCE_URL


class TestParseRealFixture:
    """AC-2 — real Jobcan HTML extraction."""

    def test_title(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        assert offer.title == "【社】介護職（博多／デイ・有料）"

    def test_apply_url_exact_match(self, sample_html: str) -> None:
        """AC-8 — apply_url must be the canonical Jobcan entry URL."""
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        assert offer.apply_url == f"https://recruit.jobcan.jp/aozora/entry/new/{SAMPLE_JOB_ID}"

    # (Required-field population is covered by `test_parse_real_fixture_variations`
    # below, which exercises the same fixture plus 4 others. Removed to avoid
    # duplicated assertions — keep the fixture-specific title/apply_url exact-match
    # tests above and the extras test below.)

    def test_extra_table_lines_extracted(self, sample_html: str) -> None:
        offer = parse_job_detail(sample_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        # The fixture has at least one non-mapped row (募集拠点, 必須スキル, etc.)
        assert len(offer.extra_lines) >= 1
        headers = {h for h, _ in offer.extra_lines}
        # 募集拠点 is a common Jobcan row label.
        assert "募集拠点" in headers or any("スキル" in h for h in headers)


# AC-3 of Phase 2A: parser must succeed across job-category variations.
# Each tuple is (job_id, label_keyword). label_keyword is checked as a
# substring — fixtures are real Jobcan pages and may rename labels.
MULTI_FIXTURE_JOBS = [
    ("1777023", "介護職"),     # 介護職正社員 (full-time, Hakata day care)
    ("1668696", "相談員"),     # 相談員短時間正社員 (short-time, Nagayoshi)
    ("1690435", "ITエンジニア"),  # ITエンジニア職正社員 (in-house SE assistant)
    ("2215694", "事務"),       # 事務職正社員 (Kagoshima new branch)
    ("2199420", "介護職"),     # 介護職正社員 (Tamura new branch)
]


@pytest.mark.parametrize("job_id, label_keyword", MULTI_FIXTURE_JOBS)
def test_parse_real_fixture_variations(job_id: str, label_keyword: str) -> None:
    """AC-3 (Phase 2A): parser handles 5 real Jobcan fixtures spanning multiple
    job categories without raising. All required fields populated.
    """
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "jobcan_responses" / f"job_{job_id}.html"
    html = fixture.read_text(encoding="utf-8")
    source_url = (
        f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
        "?hide_breadcrumb=true&hide_search=true"
    )

    offer = parse_job_detail(html, source_url, job_id)

    assert offer.job_id == job_id
    assert offer.title  # not empty
    assert offer.label  # not empty
    assert label_keyword in offer.label
    assert offer.address  # not empty
    assert offer.location  # not empty
    assert offer.salary  # not empty
    assert offer.body_html  # not empty
    assert offer.apply_url == f"https://recruit.jobcan.jp/aozora/entry/new/{job_id}"


class TestUrlNormalisation:
    """AC-1 Phase 2A: protocol-relative / relative apply URLs are normalised."""

    @pytest.mark.parametrize(
        "href, expected",
        [
            ("/aozora/entry/new/123", "https://recruit.jobcan.jp/aozora/entry/new/123"),
            ("//recruit.jobcan.jp/aozora/entry/new/456", "https://recruit.jobcan.jp/aozora/entry/new/456"),
            ("https://recruit.jobcan.jp/aozora/entry/new/789", "https://recruit.jobcan.jp/aozora/entry/new/789"),
        ],
    )
    def test_normalise(self, href: str, expected: str) -> None:
        from sync.parser import _normalise_jobcan_url

        assert _normalise_jobcan_url(href) == expected


def _build_table_html(salary_header: str, salary_value: str = "¥250,000") -> str:
    """Build a minimal job-detail HTML fragment with a configurable salary header.

    Used by TestSynonymMapping and TestDuplicateCanonicalRow to vary just the
    table rows under test, without restating the entire BeautifulSoup-parseable
    scaffold each time.
    """
    return f"""
    <html><body>
      <div class="job-offer-detail-title">タイトル</div>
      <div class="job-offer-description-full">本文</div>
      <div class="job-offer-address">拠点</div>
      <div class="job-offer-label">介護職 正社員</div>
      <a href="/aozora/entry/new/123">apply</a>
      <div class="job-offer-table">
        <div class="content-table-line">
          <div class="content-table-head">勤務地</div>
          <div class="td-contentTable__breakWordWrap">福岡</div>
        </div>
        <div class="content-table-line">
          <div class="content-table-head">{salary_header}</div>
          <div class="td-contentTable__breakWordWrap">{salary_value}</div>
        </div>
      </div>
    </body></html>
    """


class TestSynonymMapping:
    """AC-1 Phase 2A: header rename (e.g. `給与` → `給与（月給）`) is handled by
    the synonyms list in selectors.yaml, NOT by fuzzy match."""

    def test_givo_alias_maps_to_salary(self) -> None:
        """The synonym `給与（月給）` should map to salary, not raise ValidationError."""
        offer = parse_job_detail(_build_table_html("給与（月給）"), SAMPLE_SOURCE_URL, "123")
        assert offer.salary == "¥250,000"

    def test_givo_rei_does_not_map_to_salary(self) -> None:
        """`給与例` (gross-pay example) is NOT a synonym of `給与`; fuzzy match
        would be dangerous (legal-content mismatch).

        With the canonical row label absent, the parser must raise
        ValidationError, not silently use `給与例` as the salary.
        """
        with pytest.raises(JobcanValidationError) as exc_info:
            parse_job_detail(
                _build_table_html("給与例", "¥300,000 (sample)"),
                SAMPLE_SOURCE_URL,
                "123",
            )
        assert "salary" in exc_info.value.field_errors


class TestDomOrderRobustness:
    """AC-1 Phase 2A: Jobcan migration windows may ship rows with new class
    names (`.job-offer-table-left` / `.job-offer-table-right`), old class
    names (`.content-table-head` / `.td-contentTable__breakWordWrap`), or
    both side-by-side. The parser must handle each layout without misordering
    header/value pairs."""

    @staticmethod
    def _wrap(table_rows: str) -> str:
        return f"""
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full">本文</div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            {table_rows}
          </div>
        </body></html>
        """

    def test_new_class_only_resolves(self) -> None:
        """A row that uses only the new (`job-offer-table-left/right`) classes
        must parse — the comma-selector in selectors.yaml covers both
        old and new naming."""
        rows = """
            <div class="content-table-line">
              <div class="job-offer-table-left">勤務地</div>
              <div class="job-offer-table-right">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="job-offer-table-left">給与</div>
              <div class="job-offer-table-right">¥250,000</div>
            </div>
        """
        offer = parse_job_detail(self._wrap(rows), SAMPLE_SOURCE_URL, "123")
        assert offer.location == "福岡"
        assert offer.salary == "¥250,000"

    def test_old_class_only_resolves(self) -> None:
        """A row that uses only the old (`content-table-head` /
        `td-contentTable__breakWordWrap`) classes must parse — same comma
        selector covers it."""
        rows = """
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
        """
        offer = parse_job_detail(self._wrap(rows), SAMPLE_SOURCE_URL, "123")
        assert offer.location == "福岡"
        assert offer.salary == "¥250,000"

    def test_mixed_classes_document_order_wins(self) -> None:
        """A migration-window row may carry both old and new header classes
        in the same `.content-table-line`. The first one in document order is
        the visible header on the live page, so the parser must pick it. The
        test fixes the value as the second cell to confirm the pairing isn't
        scrambled by class lookup order."""
        # Old-class header first, new-class body second — selectors.yaml maps
        # `.content-table-head, .job-offer-table-left` for header and
        # `.td-contentTable__breakWordWrap, .job-offer-table-right` for body,
        # so the parser must pair them across the two naming systems within
        # one row.
        rows = """
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="job-offer-table-right">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="job-offer-table-left">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
        """
        offer = parse_job_detail(self._wrap(rows), SAMPLE_SOURCE_URL, "123")
        assert offer.location == "福岡"
        assert offer.salary == "¥250,000"


class TestDuplicateCanonicalRow:
    """Phase 2A.1a code-review #1: a Jobcan posting that emits TWO rows with
    canonical (or synonym) `給与` headers — the second value must NOT leak into
    `extra_lines` where the renderer would show it as a separately-labelled
    `給与` row alongside the canonical one. Documented first-wins policy."""

    def test_duplicate_canonical_row_dropped_silently(self) -> None:
        html = """
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full">本文</div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥350,000 (with bonus)</div>
            </div>
          </div>
        </body></html>
        """
        offer = parse_job_detail(html, SAMPLE_SOURCE_URL, "123")
        # First-wins: first 給与 row populates the canonical field.
        assert offer.salary == "¥250,000"
        # Second 給与 row must NOT appear in extras (would label-duplicate the
        # canonical row at render time).
        extras_headers = [h for h, _ in offer.extra_lines]
        assert "給与" not in extras_headers


class TestStructureChangeDetection:
    """AC-3 — when required selectors are missing, raise StructureChangeError."""

    def test_missing_required_selectors_raises(self, broken_html: str) -> None:
        with pytest.raises(JobcanStructureChangeError) as exc_info:
            parse_job_detail(broken_html, SAMPLE_SOURCE_URL, SAMPLE_JOB_ID)
        # Several selectors should be reported missing.
        assert exc_info.value.missing
        assert ".job-offer-detail-title" in exc_info.value.missing


class TestValidationOnEmptyContent:
    """AC-7 — selectors exist but content is empty → ValidationError, not partial render."""

    def test_empty_body_raises_validation_error(self) -> None:
        """All selectors exist, but description body is blank → must raise."""
        html = """
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full"></div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
          </div>
        </body></html>
        """
        with pytest.raises(JobcanValidationError) as exc_info:
            parse_job_detail(html, SAMPLE_SOURCE_URL, "123")
        assert "body_html" in exc_info.value.field_errors

    def test_missing_required_table_row_raises_validation_error(self) -> None:
        """Selectors exist, but 給与 row is missing → location/salary become empty."""
        html = """
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full">本文</div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
          </div>
        </body></html>
        """
        with pytest.raises(JobcanValidationError) as exc_info:
            parse_job_detail(html, SAMPLE_SOURCE_URL, "123")
        assert "salary" in exc_info.value.field_errors


class TestSanitization:
    """AC-9 — bleach allowlist strips script/style/form/event attributes."""

    def test_script_stripped_from_body(self) -> None:
        html = """
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full">
            <p>説明本文</p>
            <script>alert('xss')</script>
            <style>body { display: none }</style>
            <form action="evil.com"><input/></form>
          </div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
          </div>
        </body></html>
        """
        offer: JobOffer = parse_job_detail(html, SAMPLE_SOURCE_URL, "123")
        assert "<script" not in offer.body_html
        assert "<style" not in offer.body_html
        assert "<form" not in offer.body_html
        assert "<input" not in offer.body_html
        assert "alert" not in offer.body_html  # script contents also stripped
        assert "説明本文" in offer.body_html  # legit content preserved

    def test_class_and_event_attrs_stripped(self) -> None:
        html = """
        <html><body>
          <div class="job-offer-detail-title">タイトル</div>
          <div class="job-offer-description-full">
            <p class="evil" onclick="hack()">クリック</p>
          </div>
          <div class="job-offer-address">拠点</div>
          <div class="job-offer-label">介護職 正社員</div>
          <a href="/aozora/entry/new/123">apply</a>
          <div class="job-offer-table">
            <div class="content-table-line">
              <div class="content-table-head">勤務地</div>
              <div class="td-contentTable__breakWordWrap">福岡</div>
            </div>
            <div class="content-table-line">
              <div class="content-table-head">給与</div>
              <div class="td-contentTable__breakWordWrap">¥250,000</div>
            </div>
          </div>
        </body></html>
        """
        offer = parse_job_detail(html, SAMPLE_SOURCE_URL, "123")
        assert "class=" not in offer.body_html
        assert "onclick" not in offer.body_html
        assert "hack" not in offer.body_html
        assert "クリック" in offer.body_html  # text preserved


# ============================================================
# Phase 2A.1b — parse_job_list (category listing page)
# ============================================================
from sync.parser import parse_job_list  # noqa: E402

LIST_FIXTURES = [
    ("list_care", 10, "介護"),
    ("list_nurse", 10, "相談員"),
    ("list_it", 4, "ITエンジニア"),
    ("list_office", 10, "事務"),
]


def _list_fixture_html(name: str) -> str:
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "jobcan_responses" / f"{name}.html"
    return fixture.read_text(encoding="utf-8")


def _list_source_url(category_id: str = "18773") -> str:
    return (
        f"https://recruit.jobcan.jp/aozora/list"
        f"?category_id={category_id}&hide_breadcrumb=true&hide_search=true"
    )


class TestParseJobListReal:
    """AC-1 Phase 2A.1b: parse_job_list works across all 4 category fixtures."""

    @pytest.mark.parametrize("name, expected_count, label_keyword", LIST_FIXTURES)
    def test_item_count_and_labels(
        self, name: str, expected_count: int, label_keyword: str
    ) -> None:
        page = parse_job_list(_list_fixture_html(name), _list_source_url())
        assert len(page.items) == expected_count
        # Every category fixture has at least one card whose labels contain the
        # category keyword (Jobcan label layout: [職種, 雇用形態]).
        all_labels = [lbl for item in page.items for lbl in item.labels]
        assert any(label_keyword in lbl for lbl in all_labels), (
            f"{name}: no card label contains {label_keyword!r}; got: {all_labels[:5]}"
        )

    def test_required_fields_populated(self) -> None:
        page = parse_job_list(_list_fixture_html("list_care"), _list_source_url())
        for item in page.items:
            assert item.job_id.isdigit()
            assert item.title
            assert item.address
            assert item.detail_url.startswith("https://recruit.jobcan.jp/aozora/job_offers/")

    def test_detail_url_is_canonical(self) -> None:
        """detail_url must drop Jobcan's listing query and force the proxy's
        own `hide_breadcrumb=true&hide_search=true` shape."""
        page = parse_job_list(_list_fixture_html("list_care"), _list_source_url())
        item = page.items[0]
        assert item.detail_url == (
            f"https://recruit.jobcan.jp/aozora/job_offers/{item.job_id}"
            "?hide_breadcrumb=true&hide_search=true"
        )

    def test_category_id_extracted_from_source_url(self) -> None:
        page = parse_job_list(_list_fixture_html("list_care"), _list_source_url("18773"))
        assert page.category_id == "18773"

    def test_source_url_preserved(self) -> None:
        src = _list_source_url("18773")
        page = parse_job_list(_list_fixture_html("list_care"), src)
        assert page.source_url == src

    def test_thumbnail_present_for_real_fixtures(self) -> None:
        """All 4 real fixtures contain at least one card with a thumbnail."""
        for name, _, _ in LIST_FIXTURES:
            page = parse_job_list(_list_fixture_html(name), _list_source_url())
            with_thumbs = [i for i in page.items if i.thumbnail_url]
            assert with_thumbs, f"{name}: zero cards with thumbnails"


class TestParseJobListErrors:
    """Boundary and error-case coverage."""

    def test_empty_html_raises_structure_change(self) -> None:
        """No `.job-offer-box` at all → StructureChangeError (alerts operator)."""
        with pytest.raises(JobcanStructureChangeError) as exc_info:
            parse_job_list("<html><body></body></html>", _list_source_url())
        assert exc_info.value.missing == [".job-offer-box"]

    def test_box_without_title_or_url_is_skipped_silently(self) -> None:
        """One malformed card alongside valid cards → just drop the bad one.

        Jobcan sometimes inserts promo cards that lack the standard markup;
        aborting the whole page on the first odd card would block the proxy.
        """
        html = """
        <html><body>
          <div class="job-offer-box">
            <h2 class="job-offer-title">タイトル</h2>
            <p class="job-offer-address">拠点</p>
            <ul class="job-offer-label"><li>介護職</li><li>正社員</li></ul>
            <div class="job-offer-description">説明</div>
            <a href="/aozora/job_offers/999?hide_breadcrumb=false">link</a>
          </div>
          <div class="job-offer-box">
            <p>this card has no title and no link — should be silently dropped</p>
          </div>
        </body></html>
        """
        page = parse_job_list(html, _list_source_url())
        assert len(page.items) == 1
        assert page.items[0].job_id == "999"

    def test_only_malformed_cards_raises_structure_change(self) -> None:
        """If every card is malformed, treat as a structure change."""
        html = """
        <html><body>
          <div class="job-offer-box"><p>no title, no link</p></div>
          <div class="job-offer-box"><p>also broken</p></div>
        </body></html>
        """
        with pytest.raises(JobcanStructureChangeError):
            parse_job_list(html, _list_source_url())

    def test_non_numeric_job_id_in_href_is_skipped(self) -> None:
        """`/aozora/job_offers/abc` cannot yield a numeric job_id → drop card.

        Defends against Jobcan ever introducing slug-style URLs without us
        noticing — Pydantic JobListItem requires a digit string.
        """
        html = """
        <html><body>
          <div class="job-offer-box">
            <h2 class="job-offer-title">タイトル</h2>
            <a href="/aozora/job_offers/abc?ref=promo">link</a>
            <p class="job-offer-address">拠点</p>
            <div class="job-offer-description">説明</div>
          </div>
        </body></html>
        """
        with pytest.raises(JobcanStructureChangeError):
            parse_job_list(html, _list_source_url())


class TestParseJobListPartialCardData:
    """Cards may legitimately lack address / description / labels / thumbnail
    when Jobcan omits them. parse_job_list keeps the card (Phase 2A.1b: the
    template renders fine without the missing piece)."""

    def test_card_without_address_is_kept_with_empty_string(self) -> None:
        html = """
        <html><body>
          <div class="job-offer-box">
            <h2 class="job-offer-title">タイトル</h2>
            <ul class="job-offer-label"><li>介護職</li></ul>
            <div class="job-offer-description">説明</div>
            <a href="/aozora/job_offers/777?ref=promo">link</a>
          </div>
        </body></html>
        """
        page = parse_job_list(html, _list_source_url())
        assert len(page.items) == 1
        assert page.items[0].address == ""
        assert page.items[0].title == "タイトル"

    def test_relative_thumbnail_src_is_dropped_not_raised(self) -> None:
        """A path-relative `<img src="./thumb.jpg">` would fail Pydantic's
        source_thumbnail_url http(s) validator and abort the whole page. The
        parser must downgrade the source to None instead so one weird card
        does not break the whole listing.

        Phase 2A.1c note: `thumbnail_url` (display) may still hold an in-house
        override path; the guarantee here is about the AUDIT-TRAIL field
        `source_thumbnail_url`, which is the one that the validator protects.
        """
        html = """
        <html><body>
          <div class="job-offer-box">
            <img class="job-offer-main-image-thumbnail" src="./thumb.jpg" alt="x">
            <h2 class="job-offer-title">タイトル</h2>
            <ul class="job-offer-label"><li>介護職</li></ul>
            <p class="job-offer-address">拠点</p>
            <div class="job-offer-description">説明</div>
            <a href="/aozora/job_offers/888?ref=promo">link</a>
          </div>
        </body></html>
        """
        page = parse_job_list(html, _list_source_url())
        assert len(page.items) == 1
        item = page.items[0]
        # source side: relative URL was dropped to None (validator-protected)
        assert item.source_thumbnail_url is None
        # display side: Phase 2A.1c override still fires on labels, independent
        # of source presence. `介護職` → care image. Code-review #6 finding:
        # this contract must be asserted, not implicit.
        assert item.thumbnail_url == "assets/img/illust-job-care.png"


class TestParseJobListCategoryEdgeCases:
    """category_id extraction edge cases (URL without the param, etc.)."""

    def test_source_url_without_category_id_yields_none(self) -> None:
        html = _list_fixture_html("list_care")
        page = parse_job_list(html, "https://recruit.jobcan.jp/aozora/list")
        assert page.category_id is None

    def test_multi_value_category_id_takes_first(self) -> None:
        """URL with duplicated `category_id=` (unlikely but possible) — take the first."""
        html = _list_fixture_html("list_care")
        src = "https://recruit.jobcan.jp/aozora/list?category_id=18773&category_id=99999"
        page = parse_job_list(html, src)
        assert page.category_id == "18773"


# ============================================================
# Phase 2A.1c — thumbnail_categories override
# ============================================================
import logging  # noqa: E402

from sync.config import (  # noqa: E402
    ListConfig,
    SelectorConfig,
    ThumbnailCategoriesConfig,
    ThumbnailCategoryEntry,
    default_config,
)


def _make_thumb_cfg(
    *,
    enabled: bool = True,
    categories: dict[str, ThumbnailCategoryEntry] | None = None,
    default_image: str = "assets/img/illust-job-default.png",
) -> ThumbnailCategoriesConfig:
    """Test helper — build a thumbnail_categories config with minimal categories."""
    if categories is None:
        categories = {
            "care": ThumbnailCategoryEntry(
                synonyms=["介護職"], image="assets/img/illust-job-care.png"
            ),
            "nurse": ThumbnailCategoryEntry(
                synonyms=["看護師", "相談員"], image="assets/img/illust-job-nurse.png"
            ),
        }
    return ThumbnailCategoriesConfig(
        enabled=enabled,
        categories=categories,
        default_image=default_image,
    )


def _with_thumb_cfg(thumb_cfg: ThumbnailCategoriesConfig) -> SelectorConfig:
    """Clone the production SelectorConfig but swap in our test thumb_cfg."""
    base = default_config()
    return SelectorConfig(
        version=base.version,
        detail=base.detail,
        list=ListConfig(
            selectors=base.list.selectors,
            thumbnail_categories=thumb_cfg,
        ),
        sanitize=base.sanitize,
    )


def _single_card_html(
    *,
    job_id: str = "111",
    labels: list[str] | None = None,
    thumbnail_src: str | None = None,
) -> str:
    if labels is None:
        labels = ["介護職", "正社員"]
    label_html = "".join(f"<li>{lbl}</li>" for lbl in labels)
    thumb_html = (
        f'<img class="job-offer-main-image-thumbnail" src="{thumbnail_src}" alt="x">'
        if thumbnail_src is not None
        else ""
    )
    return f"""
    <html><body>
      <div class="job-offer-box">
        {thumb_html}
        <h2 class="job-offer-title">タイトル</h2>
        <ul class="job-offer-label">{label_html}</ul>
        <p class="job-offer-address">拠点</p>
        <div class="job-offer-description">説明</div>
        <a href="/aozora/job_offers/{job_id}?ref=promo">link</a>
      </div>
    </body></html>
    """


class TestThumbnailOverrideEnabledMatching:
    """`thumbnail_url` is rewritten to the in-house image when labels match."""

    def test_care_synonym_match(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["介護職", "正社員"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-care.png"

    def test_nurse_first_synonym_match(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["看護師", "正社員"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-nurse.png"

    def test_nurse_second_synonym_match(self) -> None:
        """`相談員` and `看護師` both belong to the `nurse` category."""
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["相談員", "正社員"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-nurse.png"

    def test_label_order_reversed_still_matches(self) -> None:
        """Codex Q2: must not depend on `labels[0]`. The category label can
        appear anywhere in the list."""
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            # employment-form first, job-type second — opposite of fixture order
            _single_card_html(labels=["正社員", "介護職"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-care.png"

    def test_first_matching_label_wins(self) -> None:
        """If a card carries TWO category labels (`介護職` and `看護師`), the
        one that appears first in document order wins. Synonym dict iteration
        is irrelevant — we walk labels."""
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["看護師", "介護職"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-nurse.png"


class TestThumbnailOverrideDefaultFallback:
    """Unknown / missing labels fall through to `default_image` with a warning."""

    def test_unknown_label_falls_to_default(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["ケアマネージャー", "正社員"]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-default.png"

    def test_empty_labels_falls_to_default(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=[]),
            _list_source_url(),
            cfg,
        )
        assert page.items[0].thumbnail_url == "assets/img/illust-job-default.png"

    def test_unknown_label_emits_structured_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Codex Q2: default-fallback must NOT be silent. The warning carries
        job_id + labels + known_synonyms so the operator can add the missing
        synonym to selectors.yaml."""
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        with caplog.at_level(logging.WARNING, logger="sync.parser"):
            parse_job_list(
                _single_card_html(job_id="999", labels=["ケアマネージャー"]),
                _list_source_url(),
                cfg,
            )
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        record = warnings[0]
        assert record.job_id == "999"  # type: ignore[attr-defined]
        assert record.labels == ["ケアマネージャー"]  # type: ignore[attr-defined]
        assert record.default_image == "assets/img/illust-job-default.png"  # type: ignore[attr-defined]
        assert "介護職" in record.known_synonyms  # type: ignore[attr-defined]

    def test_known_label_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        with caplog.at_level(logging.WARNING, logger="sync.parser"):
            parse_job_list(
                _single_card_html(labels=["介護職"]),
                _list_source_url(),
                cfg,
            )
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings == []


class TestThumbnailOverrideFeatureFlag:
    """`enabled: false` — the override is bypassed and Jobcan URLs survive."""

    def test_disabled_preserves_jobcan_source(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg(enabled=False))
        jobcan_url = (
            "https://storage.googleapis.com/ats-public-files.ats.jobcan.jp"
            "/job_offer/main_image_file/111/_.jpg"
        )
        page = parse_job_list(
            _single_card_html(labels=["介護職"], thumbnail_src=jobcan_url),
            _list_source_url(),
            cfg,
        )
        item = page.items[0]
        assert item.thumbnail_url == jobcan_url
        assert item.source_thumbnail_url == jobcan_url

    def test_disabled_with_no_source_yields_none(self) -> None:
        """When Jobcan provides no thumbnail and the override is disabled,
        the field is None — the template renders the card without an image."""
        cfg = _with_thumb_cfg(_make_thumb_cfg(enabled=False))
        page = parse_job_list(
            _single_card_html(labels=["介護職"], thumbnail_src=None),
            _list_source_url(),
            cfg,
        )
        item = page.items[0]
        assert item.thumbnail_url is None
        assert item.source_thumbnail_url is None


class TestThumbnailCategoriesConfigValidation:
    """Phase 2A.1c code-review #3: synonym collision is rejected at config-load."""

    def test_synonym_shared_by_two_categories_raises(self) -> None:
        """Two categories listing the same synonym (operator typo) must fail
        Pydantic validation, NOT silently last-writer-wins at runtime."""
        with pytest.raises(Exception) as exc_info:
            ThumbnailCategoriesConfig(
                enabled=True,
                categories={
                    "care": ThumbnailCategoryEntry(
                        synonyms=["介護職", "相談員"], image="care.png"
                    ),
                    "nurse": ThumbnailCategoryEntry(
                        synonyms=["相談員"], image="nurse.png"
                    ),
                },
                default_image="default.png",
            )
        assert "相談員" in str(exc_info.value)
        assert "care" in str(exc_info.value)
        assert "nurse" in str(exc_info.value)

    def test_duplicate_synonym_within_same_category_raises(self) -> None:
        """evaluator finding: intra-category synonym duplication signals an
        operator typo (copy-paste while editing selectors.yaml). Even though
        it would be harmless at runtime (dict overwrite with the same image),
        we reject it at load so the operator notices the dead line."""
        with pytest.raises(Exception) as exc_info:
            ThumbnailCategoriesConfig(
                enabled=True,
                categories={
                    "care": ThumbnailCategoryEntry(
                        synonyms=["介護職", "介護職"],  # duplicate
                        image="care.png",
                    ),
                },
                default_image="default.png",
            )
        assert "介護職" in str(exc_info.value)
        assert "twice" in str(exc_info.value)

    def test_synonym_to_image_built_at_load(self) -> None:
        """Phase 2A.1c code-review #4: the reverse map is populated by the
        model_validator, ready for the parser to use without rebuilding."""
        cfg = ThumbnailCategoriesConfig(
            enabled=True,
            categories={
                "care": ThumbnailCategoryEntry(synonyms=["介護職"], image="care.png"),
                "nurse": ThumbnailCategoryEntry(
                    synonyms=["看護師", "相談員"], image="nurse.png"
                ),
            },
            default_image="default.png",
        )
        assert cfg.synonym_to_image == {
            "介護職": "care.png",
            "看護師": "nurse.png",
            "相談員": "nurse.png",
        }


class TestSourceThumbnailPreservation:
    """`source_thumbnail_url` is the audit trail of what Jobcan actually returned."""

    def test_source_preserved_when_override_active(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        jobcan_url = (
            "https://storage.googleapis.com/ats-public-files.ats.jobcan.jp"
            "/job_offer/main_image_file/111/_.jpg"
        )
        page = parse_job_list(
            _single_card_html(labels=["介護職"], thumbnail_src=jobcan_url),
            _list_source_url(),
            cfg,
        )
        item = page.items[0]
        # display rewritten, source preserved
        assert item.thumbnail_url == "assets/img/illust-job-care.png"
        assert item.source_thumbnail_url == jobcan_url

    def test_source_is_none_when_jobcan_omits_thumbnail(self) -> None:
        cfg = _with_thumb_cfg(_make_thumb_cfg())
        page = parse_job_list(
            _single_card_html(labels=["介護職"], thumbnail_src=None),
            _list_source_url(),
            cfg,
        )
        item = page.items[0]
        assert item.source_thumbnail_url is None
        # Override still fires even without a source thumbnail
        assert item.thumbnail_url == "assets/img/illust-job-care.png"
