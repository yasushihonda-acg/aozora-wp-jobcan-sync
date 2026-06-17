"""Jobcan public-page HTML parser.

Phase 2A reflected (Codex review):
- selectors / synonyms / sanitise allowlist all come from `selectors.yaml`
  via `sync.config.SelectorConfig`. No more module-level hard-coded constants.
- synonym map (explicit) replaces fuzzy match for table-row header matching:
  `給与例` MUST NOT silently map to `給与`.
- protocol-relative apply URLs (`//host/...`) are normalised to `https://`.
- BeautifulSoup may return list-valued attrs; we coerce safely.
- DOM-order-fragile selector mixing is replaced with a single-class lookup
  per cell (the old `.content-table-head, .job-offer-table-left` style was
  prone to picking the wrong sibling during Jobcan migration windows).
"""

from __future__ import annotations

import re

import bleach
from bs4 import BeautifulSoup, Tag

from .config import RequiredTableField, SelectorConfig, default_config
from .jobcan_client import JOBCAN_BASE_URL
from .models import JobcanStructureChangeError, JobcanValidationError, JobOffer


def parse_job_detail(
    html: str,
    source_url: str,
    job_id: str | int,
    config: SelectorConfig | None = None,
) -> JobOffer:
    """Parse a Jobcan job detail page into a normalised JobOffer.

    Raises:
        JobcanStructureChangeError: required CSS selector missing.
        JobcanValidationError: selector found, but required content is empty
            (including: required `salary` / `location` row absent or unmatched).
    """
    cfg = config or default_config()
    detail = cfg.detail
    soup = BeautifulSoup(html, "lxml")

    missing: list[str] = []
    selected: dict[str, Tag] = {}

    for key in ("title", "body", "address", "label"):
        css = getattr(detail.selectors, key)
        elem = soup.select_one(css)
        if elem is None:
            missing.append(css)
        else:
            selected[key] = elem

    apply_link = soup.select_one(detail.selectors.apply_link)
    if apply_link is None or not _attr(apply_link, "href"):
        missing.append(detail.selectors.apply_link)

    table_lines = soup.select(detail.selectors.table_lines)
    if not table_lines:
        missing.append(detail.selectors.table_lines)

    if missing:
        raise JobcanStructureChangeError(missing=missing, job_id=job_id)

    # Synonym-based table-row matching: legal-content correctness > fuzzy guessing
    pairs = _extract_table_lines(
        table_lines,
        detail.selectors.table_header,
        detail.selectors.table_body,
    )
    field_values, extras = _match_required_fields(pairs, detail.required_table_fields)

    title = _text(selected["title"])
    address = _text(selected["address"])
    label = _text(selected["label"])
    body_html = _sanitize_body(selected["body"], cfg.sanitize.allowed_tags, cfg.sanitize.drop_tags)

    assert apply_link is not None  # narrowed by the missing-list check
    apply_url = _normalise_jobcan_url(_attr(apply_link, "href"))

    page_title_tag = soup.find("title")
    page_title = _text(page_title_tag) if isinstance(page_title_tag, Tag) else None

    # Required-content validation — partial display is forbidden (Codex Q6)
    location = field_values.get("location", "")
    salary = field_values.get("salary", "")
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
        loc_syns = detail.required_table_fields["location"].synonyms
        field_errors["location"] = f"no table row header matched any of: {loc_syns}"
    if not salary:
        sal_syns = detail.required_table_fields["salary"].synonyms
        field_errors["salary"] = f"no table row header matched any of: {sal_syns}"
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


def _attr(tag: Tag, name: str) -> str:
    """Get an HTML attribute as a string.

    BeautifulSoup returns `list[str]` for multi-valued attributes (e.g. `rel`,
    or when an HTML parser splits whitespace). For `href`, that should never
    happen in practice, but we coerce defensively (Codex review).
    """
    val = tag.get(name)
    if val is None:
        return ""
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val)


def _normalise_jobcan_url(href: str) -> str:
    """Coerce relative / protocol-relative URLs to absolute https://recruit.jobcan.jp/...

    Cases handled:
      - "/aozora/entry/new/123"        → "https://recruit.jobcan.jp/aozora/entry/new/123"
      - "//recruit.jobcan.jp/aozora/…" → "https://recruit.jobcan.jp/aozora/…"  (Codex)
      - "https://recruit.jobcan.jp/…"  → unchanged
    """
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("/"):
        return f"https://recruit.jobcan.jp{href}"
    return href


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(strip=True)).strip()


def _sanitize_body(tag: Tag, allowed_tags: list[str], drop_tags: list[str]) -> str:
    """Sanitise the description HTML.

    1. Decompose `<script>` / `<style>` / `<form>` / `<iframe>` etc. so even
       their inner text is removed (bleach's `strip=True` keeps inner text).
    2. Pass the remainder through bleach's allowlist with no preserved attrs.
    """
    safe = BeautifulSoup(tag.decode_contents(), "lxml")
    for bad in safe.find_all(drop_tags):
        bad.decompose()
    cleaned = bleach.clean(
        str(safe),
        tags=allowed_tags,
        attributes={},
        strip=True,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_table_lines(
    lines: list[Tag],
    header_selector: str,
    body_selector: str,
) -> list[tuple[str, str]]:
    """Extract (header, value) pairs from `.content-table-line` rows.

    Robust against Jobcan migration windows: each row is scanned for the
    *first* element matching the header selector and the *first* matching
    the body selector. If a row mixes old and new class names side by side,
    we take the first one in document order — which is the visible header.
    """
    pairs: list[tuple[str, str]] = []
    for line in lines:
        head = line.select_one(header_selector)
        body = line.select_one(body_selector)
        if head and body:
            pairs.append((_text(head), _text(body)))
            continue
        # Fallback: split by direct children (handles the rare case where Jobcan
        # ships a row with only structural divs, no head/body classes at all).
        children = [c for c in line.children if isinstance(c, Tag)]
        if len(children) >= 2:
            pairs.append((_text(children[0]), _text(children[1])))
    return pairs


def _match_required_fields(
    pairs: list[tuple[str, str]],
    required: dict[str, RequiredTableField],
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Match each row header to a required field using explicit synonyms.

    Returns:
        (field_values, extras) — field_values maps canonical field name
        ("location" / "salary") to the cell value; extras holds all rows
        that did not match any required field (preserved for display).

    Codex Q4: fuzzy match is forbidden. `給与例` does NOT match `給与`.
    """
    # Build a reverse lookup: synonym (exact string) -> field key.
    synonym_to_field: dict[str, str] = {}
    for field_key, field in required.items():
        for syn in field.synonyms:
            synonym_to_field[syn] = field_key

    field_values: dict[str, str] = {}
    extras: list[tuple[str, str]] = []
    for header, value in pairs:
        field_key = synonym_to_field.get(header)
        if field_key is not None and field_key not in field_values:
            field_values[field_key] = value
        else:
            extras.append((header, value))
    return field_values, extras


# Re-exported so callers can identify the canonical apply-URL prefix.
ENTRY_URL_PREFIX = f"{JOBCAN_BASE_URL}/entry/new/"
