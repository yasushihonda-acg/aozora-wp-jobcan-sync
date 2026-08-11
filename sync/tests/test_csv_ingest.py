"""Tests for `csv_ingest.py` — the CSV → `CrawlResult` ingestion pipeline
(CSV-migration follow-up, 2026-08-11).

`job_offer_list_page1.csv`'s single row is not hand-typed: it was generated
from `tests/fixtures/jobcan_responses/job_1777023.html`'s own table cells
(`<br>` → `\\r\\n`, matching what a real Jobcan CSV export does to the same
rich-text field — verified against real production data during the
2026-08-11 migration session, see `csv_ingest.py`'s module docstring). This
lets `test_csv_row_reproduces_html_parsed_offer` assert byte-for-byte
equality against `parser.parse_job_detail`'s output for the exact same
posting, rather than a hand-maintained approximation that could drift from
what the two pipelines actually produce.
"""

from __future__ import annotations

import json

from sync.csv_ingest import EXPECTED_HEADER, crawl_from_csv
from sync.models import JobcanStructureChangeError
from sync.parser import parse_job_detail

from .conftest import CSV_FIXTURES_DIR, FIXTURES_DIR, SAMPLE_JOB_ID, SAMPLE_SOURCE_URL

_INTERNAL_SENTINELS = (
    "SENTINEL-STAFF-17",
    "SENTINEL-EVAL-19",
    "SENTINEL-MEMO-39",
    "SENTINEL-AGENT-40",
)

_PARITY_FIELDS = (
    "job_id",
    "title",
    "address",
    "label",
    "location",
    "salary",
    "apply_url",
    "source_url",
    "page_title",
    "body_html",
)


def test_csv_row_reproduces_html_parsed_offer() -> None:
    """The single strongest correctness check in this module: both ingestion
    pipelines must agree, field-for-field, on the exact same real posting."""
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
    assert result.errors == []
    csv_offer = next(o for o in result.offers if o.job_id == SAMPLE_JOB_ID)

    html = (FIXTURES_DIR / f"job_{SAMPLE_JOB_ID}.html").read_text(encoding="utf-8")
    html_offer = parse_job_detail(html, SAMPLE_SOURCE_URL, job_id=SAMPLE_JOB_ID)

    for field in _PARITY_FIELDS:
        assert getattr(csv_offer, field) == getattr(html_offer, field), field
    assert set(csv_offer.extra_lines) == set(html_offer.extra_lines)


def test_csv_row_produces_matching_list_item() -> None:
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
    item = result.list_items[SAMPLE_JOB_ID]
    assert item.title == "【社】介護職（博多／デイ・有料）"
    assert item.address == "【福岡】あおぞらケアグループ博多（デイ・有料）"
    assert item.labels == ["介護職", "正社員"]
    assert item.detail_url == SAMPLE_SOURCE_URL
    # No guessed Jobcan CDN URL — see `csv_ingest._offer_and_item_from_row`.
    assert item.source_thumbnail_url is None


def test_csv_row_resolves_category_id_from_job_type_name() -> None:
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
    assert result.category_ids[SAMPLE_JOB_ID] == ["18773"]  # 介護職


def test_internal_columns_never_reach_any_model() -> None:
    """The four internal-only CSV columns (採用担当者・通知先/評価設問/
    社内向けメモ/エージェント向けメモ) must be structurally unreachable —
    the fixture puts a literal sentinel in each, this asserts none of them
    appear anywhere in the produced models."""
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
    blob = json.dumps(
        [o.model_dump() for o in result.offers]
        + [i.model_dump() for i in result.list_items.values()],
        ensure_ascii=False,
    )
    for sentinel in _INTERNAL_SENTINELS:
        assert sentinel not in blob


def test_multiple_files_dedup_first_seen_wins() -> None:
    """`job_offer_list_page2.csv` contains a fresh job (9999901) plus a
    duplicate of page1's 1777023 with deliberately different content — the
    duplicate must be silently ignored, keeping page1's version."""
    result = crawl_from_csv(
        [
            CSV_FIXTURES_DIR / "job_offer_list_page1.csv",
            CSV_FIXTURES_DIR / "job_offer_list_page2.csv",
        ]
    )
    assert result.errors == []
    job_ids = {o.job_id for o in result.offers}
    assert job_ids == {SAMPLE_JOB_ID, "9999901"}

    kept = next(o for o in result.offers if o.job_id == SAMPLE_JOB_ID)
    assert kept.title == "【社】介護職（博多／デイ・有料）"
    assert "DUPLICATE" not in kept.title

    # collected_total counts every row read, duplicates included — it feeds
    # `CrawlResult.collected_total`, a raw "how many rows did we read" count,
    # distinct from the de-duplicated `offers` list.
    assert result.collected_total == 3


def test_bad_rows_are_skipped_not_fatal() -> None:
    """Row-level problems (unknown facility, empty required field, malformed
    job_id) must land in `errors` and be skipped — one bad row must never
    abort the whole file, mirroring `crawler._fetch_one_detail`'s per-job_id
    failure handling. An unrecognised 求人カテゴリ is NOT a row failure (it
    degrades to `category_ids=[]` with a warning, per `job_types.py`'s
    manual-curation trade-off), so only 3 of the 4 rows in this fixture
    become errors."""
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_bad_rows.csv"])
    error_job_ids = {e["job_id"] for e in result.errors}
    assert error_job_ids == {"9999902", "9999904", "abc123"}

    offer_job_ids = {o.job_id for o in result.offers}
    assert "9999903" in offer_job_ids  # unknown category: degraded, not skipped
    assert result.category_ids["9999903"] == []


def test_bad_header_raises_structure_change_error() -> None:
    import pytest

    with pytest.raises(JobcanStructureChangeError):
        crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_bad_header.csv"])


def test_expected_header_matches_fixture_header() -> None:
    """Guards `EXPECTED_HEADER` itself against silent drift from the real
    41-column shape the fixtures were built against."""
    import csv

    with (CSV_FIXTURES_DIR / "job_offer_list_page1.csv").open(
        encoding="utf-8-sig", newline=""
    ) as f:
        header = tuple(next(csv.reader(f)))
    assert header == EXPECTED_HEADER
    assert len(EXPECTED_HEADER) == 41


def test_expected_total_defaults_to_collected_row_count_when_omitted() -> None:
    result = crawl_from_csv([CSV_FIXTURES_DIR / "job_offer_list_page1.csv"])
    assert result.expected_total == result.collected_total == 1


def test_expected_total_uses_given_value_when_provided() -> None:
    result = crawl_from_csv(
        [CSV_FIXTURES_DIR / "job_offer_list_page1.csv"], expected_total=382
    )
    assert result.expected_total == 382
    assert result.collected_total == 1
