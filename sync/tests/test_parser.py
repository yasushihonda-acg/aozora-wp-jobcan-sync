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
        thumbnail_url http(s) validator and abort the whole page. The parser
        must downgrade this to thumbnail_url=None instead."""
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
        assert page.items[0].thumbnail_url is None


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
