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
