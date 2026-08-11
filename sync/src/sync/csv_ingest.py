"""CSV → `CrawlResult` ingestion pipeline (CSV-migration follow-up, 2026-08-11).

Parses ATS `job_offers` list CSV exports (`CSVファイルをダウンロード (UTF-8)`,
bulk-action value `output_file_utf8` — see `jobcan_ats.py`) into the same
`CrawlResult` shape `crawler.crawl_all` produces from HTML, so
`orchestrator.run_sync_from_crawl` needs zero changes to consume either
pipeline's output.

Deliberately has no Playwright / Firestore / CLI dependency: this module is a
pure transform from CSV rows (already downloaded to disk by `jobcan_ats.py`,
or handed in directly via `--csv-file` for offline testing) to
`JobOffer`/`JobListItem`/`CrawlResult`. That keeps it fully unit-testable
without a browser and importable from the request-serving image, which never
carries the `ats` extra.

Column → field mapping was verified against real production data during the
2026-08-11 migration session (a real `job_offers` CSV export cross-checked
field-by-field against `parse_job_list`'s output for the same job_id, real
job_id 2267337, `tests/fixtures/jobcan_responses/list_office.html`) — see the
module-level column index table and `_jobcan_text` below for the specific
transforms that reproduce the HTML path's output byte-for-byte.
"""

from __future__ import annotations

import csv
import html as html_module
import io
import logging
import re
from pathlib import Path
from typing import Final

import bleach

from ._validators import is_ascii_digit_id
from .config import SelectorConfig, default_config
from .crawler import CrawlResult
from .facility_codes import FACILITY_CODES
from .job_types import JOB_TYPE_IDS_BY_NAME
from .models import (
    JobcanStructureChangeError,
    JobcanValidationError,
    JobListItem,
    JobOffer,
)
from .parser import ENTRY_URL_PREFIX, canonical_detail_url, resolve_display_thumbnail

_logger = logging.getLogger(__name__)

PAGE_TITLE_SUFFIX = "の採用情報 | 株式会社 ACG（あおぞらケアグループ）"

# Column indices — the ONLY way any row value reaches a model. Columns 17
# (採用担当者・通知先), 19 (評価設問), 39 (社内向けメモ), 40 (エージェント向け
# メモ) — and also 23 (部署) / 28 (役職) / 29 (呼称) / 32 (想定給与) / 33-38
# (見出し・紹介文) — are deliberately absent from this list: internal-only or
# never-shown-on-the-public-page data must never be *reachable* by any
# consumer, not merely filtered out downstream (verified by
# `test_csv_ingest.py::test_internal_columns_never_reach_any_model`).
_C_JOB_ID: Final = 0
_C_FACILITY: Final = 4
_C_PREFECTURE: Final = 5
_C_ACCESS: Final = 6
_C_TITLE: Final = 8
_C_CATEGORY: Final = 11
_C_EMPLOYMENT: Final = 12
_C_CAPACITY: Final = 15
_C_BODY: Final = 16
_C_MUST: Final = 21
_C_WANT: Final = 22
_C_QUALIFICATION: Final = 24
_C_BENEFITS: Final = 25
_C_FLOW: Final = 26
_C_SALARY: Final = 27
_C_HOURS: Final = 30
_C_HOLIDAY: Final = 31  # CSV header is 「休暇・休日」— see _EXTRA_LINE_SPEC below.

# The exact 41-column header of a `job_offers` list CSV export, in order.
# Any deviation (Jobcan adds/removes/reorders a column) means the fixed
# indices above no longer point at what this module thinks they do — treated
# the same as an HTML selector going missing (`JobcanStructureChangeError`,
# CLI exit code 2).
EXPECTED_HEADER: Final[tuple[str, ...]] = (
    "求人ID",
    "限定公開求人",
    "Indeed連携",
    "Googleしごと検索連携",
    "募集拠点",
    "勤務地",
    "勤務地備考",
    "管理用求人名",
    "求人タイトル",
    "職種名(Googleしごと検索用)",
    "法人名(Indeed用)",
    "求人カテゴリ",
    "雇用形態",
    "受付開始日",
    "受付終了日",
    "定員",
    "募集要項",
    "採用担当者・通知先",
    "公開先エージェント会社",
    "評価設問",
    "エントリーフォーム",
    "必須スキル・経験",
    "歓迎スキル・経験",
    "部署",
    "必要資格",
    "待遇",
    "選考フロー",
    "給与",
    "役職",
    "呼称",
    "勤務時間",
    "休暇・休日",
    "想定給与",
    "見出し１",
    "紹介文１",
    "見出し２",
    "紹介文２",
    "見出し３",
    "紹介文３",
    "社内向けメモ",
    "エージェント向けメモ",
)

# extra_lines key mapping: (emitted key, source column). Emitted keys MUST
# match the literal strings `detail_sections.py` matches on (e.g.
# `extract_holiday_chip`/`extract_holiday_paragraph` both key on exactly
# "休日・休暇"). The CSV's own column header for this field is reversed
# ("休暇・休日") — this table is where that reversal is corrected; the CSV
# header text itself must never be used as an extra_lines key.
_EXTRA_LINE_SPEC: Final[tuple[tuple[str, int], ...]] = (
    ("必須スキル・経験", _C_MUST),
    ("歓迎スキル・経験", _C_WANT),
    ("必要資格", _C_QUALIFICATION),
    ("勤務時間", _C_HOURS),
    ("休日・休暇", _C_HOLIDAY),
    ("待遇", _C_BENEFITS),
    ("選考フロー", _C_FLOW),
)


def _jobcan_text(s: str) -> str:
    """Reproduces `parser._text`'s output for CSV-embedded multi-line values.

    HTML path: BeautifulSoup's `get_text(strip=True)` strips each text node
    individually and concatenates with no separator, then `parser._text`
    collapses any remaining internal whitespace runs to a single space. CSV
    cells hold the same content as raw newline-separated text (each line was
    one `<br>`-delimited text node in the source HTML) — splitting on `\\n`
    and stripping each line reproduces the identical per-node stripping, and
    the final `re.sub` collapse matches `_text`'s last step.

    Verified against real production data: applying this to CSV column 16
    (募集要項) for job_id 2267337 produces a string byte-for-byte equal to
    `parse_job_list(list_office.html).items[...].description` for the same
    posting (2026-08-11).
    """
    joined = "".join(ln.strip() for ln in s.replace("\r\n", "\n").split("\n"))
    return re.sub(r"\s+", " ", joined).strip()


def _body_html_from_csv(raw: str, cfg: SelectorConfig) -> str:
    """Builds `JobOffer.body_html` from CSV column 16 (募集要項) alone.

    The structured columns (待遇/選考フロー/勤務時間/... ) go to `extra_lines`
    instead, never here — `detail_sections.build_detail_view` already derives
    individual page sections from `extra_lines`; folding those columns into
    `body_html` too would render every section twice.

    `html.escape` runs BEFORE assembly (so a posting body containing a literal
    `<` or `&` cannot become markup), then `bleach.clean` with the same
    allowlist `selectors.yaml`'s `sanitize.allowed_tags` defines for the HTML
    path runs as defence in depth — one allowlist, two ingestion paths.
    """
    lines = [ln.strip() for ln in raw.replace("\r\n", "\n").split("\n")]
    inner = "<br>".join(html_module.escape(ln, quote=False) for ln in lines)
    cleaned = bleach.clean(
        f"<p> {inner} </p>",
        tags=cfg.sanitize.allowed_tags,
        attributes={},
        strip=True,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _extra_lines_from_row(
    row: list[str], facility_name: str, facility_street: str
) -> list[tuple[str, str]]:
    """Builds `JobOffer.extra_lines` from one CSV row.

    「募集拠点」 is emitted first (matching the HTML detail table's row order)
    with `facility_name + facility_street` concatenated with no separator —
    the same shape `detail_sections.simplify_address` already parses out of
    the HTML path's 募集拠点 table cell (verified against
    `job_1777023.html`'s 募集拠点 row, which renders the facility-name link
    text immediately followed by the address `<p>`, no separator between
    them).
    """
    lines: list[tuple[str, str]] = [("募集拠点", facility_name + facility_street)]
    for key, col in _EXTRA_LINE_SPEC:
        value = _jobcan_text(row[col])
        if value:
            lines.append((key, value))
    capacity = row[_C_CAPACITY].strip()
    if capacity:
        lines.append(("定員", f"{capacity} 名"))  # HTML renders "3 名" with a space.
    return lines


class _RowError(Exception):
    """Internal: one row failed to convert. Caller turns this into a
    `CrawlResult.errors` entry and skips the row — mirrors
    `crawler._fetch_one_detail`'s per-job_id failure handling."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def _offer_and_item_from_row(
    row: list[str], cfg: SelectorConfig
) -> tuple[JobOffer, JobListItem, list[str]]:
    """Converts one CSV data row into `(JobOffer, JobListItem, category_ids)`.

    Raises `_RowError` for a row-level problem (unknown facility code, unknown
    category name, empty required field) — the caller catches this and routes
    it to `CrawlResult.errors`, matching how a single bad job_id degrades in
    the HTML path instead of aborting the whole ingest.
    """
    job_id = row[_C_JOB_ID].strip()
    if not is_ascii_digit_id(job_id):
        raise _RowError("求人ID", f"not ascii digits: {job_id!r}")

    facility_code = row[_C_FACILITY].strip()
    facility = FACILITY_CODES.get(facility_code)
    if facility is None:
        raise _RowError("募集拠点", f"unknown facility code {facility_code!r}")
    facility_name, _postal, facility_street = facility

    category = row[_C_CATEGORY].strip()
    category_id = JOB_TYPE_IDS_BY_NAME.get(category)
    category_ids = [category_id] if category_id is not None else []
    if category_id is None:
        _logger.warning(
            "csv_ingest: unrecognised 求人カテゴリ, category_ids left empty",
            extra={"job_id": job_id, "category": category},
        )

    employments = [e.strip() for e in row[_C_EMPLOYMENT].split(";") if e.strip()]
    title = _jobcan_text(row[_C_TITLE])
    location = _jobcan_text(row[_C_PREFECTURE]) + _jobcan_text(row[_C_ACCESS])
    salary = _jobcan_text(row[_C_SALARY])
    label = category + "".join(employments)
    body_html = _body_html_from_csv(row[_C_BODY], cfg)

    field_errors: dict[str, str] = {}
    for field_name, value in (
        ("title", title),
        ("body_html", body_html),
        ("address", facility_name),
        ("label", label),
        ("location", location),
        ("salary", salary),
    ):
        if not value:
            field_errors[field_name] = "empty in CSV row"
    if field_errors:
        raise JobcanValidationError(field_errors=field_errors, job_id=job_id)

    page_title = f"{title}({facility_name}){PAGE_TITLE_SUFFIX}"

    offer = JobOffer(
        job_id=job_id,
        title=title,
        body_html=body_html,
        address=facility_name,
        label=label,
        location=location,
        salary=salary,
        apply_url=f"{ENTRY_URL_PREFIX}{job_id}",
        source_url=canonical_detail_url(job_id),
        page_title=page_title,
        extra_lines=_extra_lines_from_row(row, facility_name, facility_street),
    )

    labels = [category, *employments]
    list_item = JobListItem(
        job_id=job_id,
        title=title,
        address=facility_name,
        description=_jobcan_text(row[_C_BODY]),
        detail_url=canonical_detail_url(job_id),
        labels=labels,
        # The Jobcan CDN thumbnail URL is derivable but not literally present
        # in the CSV. `source_thumbnail_url`'s own docstring says it preserves
        # the ORIGINAL Jobcan-supplied URL unchanged — guessing one here would
        # violate that contract. `thumbnail_categories.enabled=True` in
        # `selectors.yaml` means the in-house override always wins anyway, so
        # nothing renders from this field either way.
        thumbnail_url=resolve_display_thumbnail(
            job_id=job_id,
            labels=labels,
            source_thumbnail_url=None,
            thumb_cfg=cfg.list.thumbnail_categories,
        ),
        source_thumbnail_url=None,
    )

    return offer, list_item, category_ids


def _read_csv_text(path: Path) -> str:
    """Decodes one downloaded CSV file, preferring UTF-8 (the ingestion
    pipeline always requests `output_file_utf8`) with a defensive cp932
    fallback for a file downloaded by the Shift-JIS option."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _logger.error("csv_ingest: not UTF-8, falling back to cp932", extra={"path": str(path)})
        return raw.decode("cp932", errors="replace")


def crawl_from_csv(
    paths: list[Path],
    *,
    expected_total: int | None = None,
    config: SelectorConfig | None = None,
) -> CrawlResult:
    """Builds a `CrawlResult` from one or more downloaded `job_offers` CSVs.

    Multiple `paths` are for the paginated-download case (`jobcan_ats.py`
    downloads one CSV per page of the 公開状況=公開 filtered list) — rows are
    concatenated across files before de-dup, first-seen job_id wins (mirrors
    `crawler.crawl_all`'s cross-category de-dup).

    `expected_total`, when given, should come from the ATS list screen's own
    「NNN件中」 count text (`jobcan_ats.AtsDownloadResult.expected_total`), NOT
    from `len(rows)` — `CrawlResult.expected_total` feeds
    `orchestrator.run_sync_from_crawl`'s reconciliation check, which only
    catches a silent partial download if the expectation is independent of
    what was actually collected. When omitted (the `--csv-file` offline path),
    it falls back to the collected row count and reconciliation is vacuous —
    logged at WARNING so an offline run is never mistaken for a
    production-grade completeness check.

    Raises `JobcanStructureChangeError` if any file's header does not match
    `EXPECTED_HEADER` exactly — the CSV-path equivalent of an HTML selector
    going missing (same exit code as the HTML path, CLI exit code 2).
    """
    cfg = config or default_config()
    result = CrawlResult()
    seen_job_ids: set[str] = set()
    total_rows = 0

    for path in paths:
        text = _read_csv_text(path)
        rows = list(csv.reader(io.StringIO(text, newline="")))
        if not rows:
            raise JobcanStructureChangeError(missing=[f"CSV file is empty: {path}"])
        header = tuple(rows[0])
        if header != EXPECTED_HEADER:
            raise JobcanStructureChangeError(
                missing=[
                    f"CSV header mismatch in {path}: got {len(header)} cols; "
                    f"unexpected={set(header) - set(EXPECTED_HEADER)}; "
                    f"missing={set(EXPECTED_HEADER) - set(header)}"
                ]
            )

        for row in rows[1:]:
            total_rows += 1
            row_job_id = row[_C_JOB_ID].strip() if row else ""
            # Recorded BEFORE conversion is attempted, independent of whether
            # the row's other columns are valid: the CSV row's mere presence
            # is what "listed" means for this pipeline (the CSV *is* the
            # listing, unlike the HTML path where a listing row and its
            # detail-page fetch are two separate requests). A row that fails
            # validation (unknown facility code, blank salary, ...) is still
            # a posting Jobcan is showing — recording it here is what makes
            # `compute_diff` treat it as "unfetched" instead of "removed", so
            # a transient CSV data problem can never make a still-published
            # posting drift toward the 48h auto-close threshold (codex
            # review finding, 2026-08-11: the previous version only added to
            # `listed_job_ids` after a successful conversion).
            if is_ascii_digit_id(row_job_id):
                result.listed_job_ids.add(row_job_id)
            try:
                offer, list_item, category_ids = _offer_and_item_from_row(row, cfg)
            except (_RowError, JobcanValidationError) as exc:
                result.errors.append(
                    {"job_id": row_job_id, "error": f"{type(exc).__name__}: {exc}"}
                )
                _logger.error("csv_ingest: row failed, skipping", extra={"error": str(exc)})
                continue

            result.listed_job_ids.add(offer.job_id)
            result.list_items.setdefault(offer.job_id, list_item)
            existing_category_ids = result.category_ids.setdefault(offer.job_id, [])
            for category_id in category_ids:
                if category_id not in existing_category_ids:
                    existing_category_ids.append(category_id)

            if offer.job_id in seen_job_ids:
                continue
            seen_job_ids.add(offer.job_id)
            result.offers.append(offer)

    result.collected_total = total_rows
    if expected_total is not None:
        result.expected_total = expected_total
    else:
        _logger.warning(
            "csv_ingest: no expected_total given, falling back to collected row count "
            "(offline/--csv-file run — reconciliation check is vacuous)"
        )
        result.expected_total = total_rows

    return result
