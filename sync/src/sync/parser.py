"""Jobcan public-page HTML parser.

Codex review reflected:
- sanitize body HTML with `bleach` (allowlist-only — strip script/style/form)
- explicit required-field validation; partial display is forbidden
- distinguish JobcanStructureChangeError (selector missing) from
  JobcanValidationError (selector found but content empty)
"""

from __future__ import annotations

import re

import bleach
from bs4 import BeautifulSoup, Tag

from .jobcan_client import JOBCAN_BASE_URL
from .models import JobcanStructureChangeError, JobcanValidationError, JobOffer

# Bleach allowlist — preserve only semantic structure for job descriptions.
# Codex review (Q6): "外部HTMLを自社ドメインで配信する以上、
# XSS・意図しないリンク・画像・script混入の責任は自社側に寄ります。"
ALLOWED_TAGS = ["p", "br", "ul", "ol", "li", "strong", "em", "b", "i", "h2", "h3", "h4"]
ALLOWED_ATTRIBUTES: dict[str, list[str]] = {}  # No attributes preserved.

# Selectors confirmed via Phase 0 verification (see docs/specs/jobcan-html-structure.md)
SELECTORS = {
    "title": ".job-offer-detail-title",
    "body": ".job-offer-description-full",
    "address": ".job-offer-address",
    "label": ".job-offer-label",
    "apply_link": 'a[href^="/aozora/entry/new/"]',
    "table_lines": ".content-table-line",
}

# Required content-table-line headers — order matters because Jobcan uses
# repeated div headers with no class differentiation between rows.
TABLE_HEADER_TO_FIELD = {
    "勤務地": "location",
    "給与": "salary",
}


def parse_job_detail(html: str, source_url: str, job_id: str | int) -> JobOffer:
    """Parse a Jobcan job detail page into a normalised JobOffer.

    Raises:
        JobcanStructureChangeError: if any required CSS selector is missing.
        JobcanValidationError: if required fields are present but empty.
    """
    soup = BeautifulSoup(html, "lxml")

    missing: list[str] = []
    selected: dict[str, Tag] = {}

    for key in ("title", "body", "address", "label"):
        elem = soup.select_one(SELECTORS[key])
        if elem is None:
            missing.append(SELECTORS[key])
        else:
            selected[key] = elem

    apply_link = soup.select_one(SELECTORS["apply_link"])
    if apply_link is None or not apply_link.get("href"):
        missing.append(SELECTORS["apply_link"])

    table_lines = soup.select(SELECTORS["table_lines"])
    if not table_lines:
        missing.append(SELECTORS["table_lines"])

    if missing:
        raise JobcanStructureChangeError(missing=missing, job_id=job_id)

    # Extract table lines into (header, value) pairs.
    extracted_lines = _extract_table_lines(table_lines)

    location = ""
    salary = ""
    extras: list[tuple[str, str]] = []
    for header, value in extracted_lines:
        if header == "勤務地":
            location = value
        elif header == "給与":
            salary = value
        else:
            extras.append((header, value))

    title = _text(selected["title"])
    address = _text(selected["address"])
    label = _text(selected["label"])
    body_html = _sanitize_body(selected["body"])

    # apply_link is guaranteed non-None here (early-return above).
    assert apply_link is not None
    apply_href = str(apply_link["href"])
    apply_url = (
        apply_href if apply_href.startswith("http") else f"https://recruit.jobcan.jp{apply_href}"
    )

    page_title_tag = soup.find("title")
    page_title = _text(page_title_tag) if isinstance(page_title_tag, Tag) else None

    # Required-field validation (Codex Q6 — partial display forbidden).
    field_errors: dict[str, str] = {}
    if not title:
        field_errors["title"] = "empty after extraction"
    if not body_html:
        field_errors["body_html"] = "empty after sanitization"
    if not address:
        field_errors["address"] = "empty after extraction"
    if not label:
        field_errors["label"] = "empty after extraction"
    if not location:
        field_errors["location"] = "missing 勤務地 row in content-table"
    if not salary:
        field_errors["salary"] = "missing 給与 row in content-table"
    if field_errors:
        raise JobcanValidationError(field_errors=field_errors, job_id=job_id)

    return JobOffer(
        job_id=str(job_id),
        title=title,
        body_html=body_html,
        address=address,
        label=label,
        location=location,
        salary=salary,
        apply_url=apply_url,
        source_url=source_url,
        page_title=page_title,
        extra_lines=extras,
    )


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(strip=True)).strip()


def _sanitize_body(tag: Tag) -> str:
    """Sanitise the description HTML.

    Strategy:
      1. Decompose `<script>`, `<style>`, `<form>` and friends first so even
         their text content is dropped (bleach's strip=True removes the
         tag wrapper but preserves the inner text — not what we want for
         script bodies).
      2. Then pass the remaining markup to bleach with the allowlist.
    """
    # Work on a copy so the caller's tree is untouched.
    safe = BeautifulSoup(tag.decode_contents(), "lxml")
    for bad in safe.find_all(["script", "style", "form", "iframe", "object", "embed"]):
        bad.decompose()
    cleaned = bleach.clean(
        str(safe),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_table_lines(lines: list[Tag]) -> list[tuple[str, str]]:
    """Extract (header, value) pairs from `.content-table-line` rows.

    Each row in Jobcan's structure has two cell-like sub-divs in this order:
    header (e.g. "勤務地") and value. We extract via the document order to
    avoid depending on volatile classnames.
    """
    pairs: list[tuple[str, str]] = []
    for line in lines:
        head = line.select_one(".content-table-head, .job-offer-table-left")
        body = line.select_one(".td-contentTable__breakWordWrap, .job-offer-table-right")
        if head and body:
            pairs.append((_text(head), _text(body)))
            continue
        # Fallback: split by direct children
        children = [c for c in line.children if isinstance(c, Tag)]
        if len(children) >= 2:
            pairs.append((_text(children[0]), _text(children[1])))
    return pairs


# Re-exported so callers can identify the canonical apply-URL prefix.
ENTRY_URL_PREFIX = f"{JOBCAN_BASE_URL}/entry/new/"
