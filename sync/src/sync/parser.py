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

import hashlib
import logging
import re
from collections.abc import Sequence
from urllib.parse import parse_qs, urlsplit

import bleach
from bs4 import BeautifulSoup, Tag

from .config import (
    ListSelectors,
    RequiredTableField,
    SelectorConfig,
    ThumbnailCategoriesConfig,
    default_config,
)
from .jobcan_client import JOBCAN_BASE_URL
from .models import (
    JobcanStructureChangeError,
    JobcanValidationError,
    JobListItem,
    JobListPage,
    JobOffer,
)

# Phase 2A.1c: emits a structured warning when a card's labels do not match
# any thumbnail-category synonym and the parser falls back to default_image.
# Operators can spot a new Jobcan job-type (e.g. "ケアマネージャー") this way.
_logger = logging.getLogger(__name__)

# Pattern that pulls the numeric job_id out of any Jobcan job-detail URL,
# whether relative (`/aozora/job_offers/123?...`) or absolute.
_JOB_ID_RE = re.compile(r"/aozora/job_offers/(\d+)")


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
        if field_key is None:
            # Unknown header — preserved for display in `extra_lines`.
            extras.append((header, value))
            continue
        if field_key in field_values:
            # Duplicate canonical row (e.g. two `給与` rows in a multi-position
            # posting). First-wins: silently drop the duplicate so the renderer
            # doesn't show a second labelled row alongside the canonical one.
            # Phase 2A.2 will add structured logging here for operator visibility.
            continue
        field_values[field_key] = value
    return field_values, extras


# Re-exported so callers can identify the canonical apply-URL prefix.
ENTRY_URL_PREFIX = f"{JOBCAN_BASE_URL}/entry/new/"


def parse_job_list(
    html: str,
    source_url: str,
    config: SelectorConfig | None = None,
) -> JobListPage:
    """Parse a Jobcan category listing page into a JobListPage.

    Each `.job-offer-box` becomes one `JobListItem`. A card is **silently
    dropped** (no exception) when any of these is true — Jobcan occasionally
    renders promo cards inside the grid that lack the standard markup, and
    aborting the whole page on a single odd card would block the proxy:

    - title selector absent or empty text
    - detail-URL selector absent or empty href
    - href that does not contain `/aozora/job_offers/<digits>`

    `address` / `description` / `labels` / `thumbnail_url` may be empty when
    Jobcan omits them; the card still renders without the missing piece
    (the template handles the empty case).

    Raises:
        JobcanStructureChangeError: zero job cards found, or **every** card
            was dropped by the rules above. Either case means Jobcan changed
            the listing markup and a human needs to look.
    """
    cfg = config or default_config()
    selectors = cfg.list.selectors
    thumb_cfg = cfg.list.thumbnail_categories
    soup = BeautifulSoup(html, "lxml")

    boxes = soup.select(selectors.job_card)
    if not boxes:
        raise JobcanStructureChangeError(missing=[selectors.job_card], job_id=None)

    items: list[JobListItem] = []
    for box in boxes:
        item = _parse_list_card(box, selectors, thumb_cfg)
        if item is not None:
            items.append(item)

    if not items:
        # Every card was malformed — treat as a structure change so the
        # operator is alerted instead of silently shipping an empty page.
        raise JobcanStructureChangeError(
            missing=[selectors.title, selectors.address, selectors.job_url],
            job_id=None,
        )

    category_id = _extract_category_id(source_url)
    total_count, last_page, next_url = _parse_pagination(soup, selectors, category_id)
    return JobListPage(
        source_url=source_url,
        category_id=category_id,
        items=items,
        total_count=total_count,
        last_page=last_page,
        next_url=next_url,
    )


# Pulls the leading integer out of either pagination-count format Jobcan
# renders: "53 件中　1-10 件を表示" (paginated) or "4 件" (single page, no
# `.pagination-list` at all). Both start with the total count, so one pattern
# covers both — see `selectors.yaml` comment for the real fixture text.
_PAGINATION_TOTAL_RE = re.compile(r"(\d+)")

# Pulls the page number out of a `/aozora/list/all/all/{page}?...` URL.
# Page 1 has no path segment (`/aozora/list/all/all?...`), so a link *without*
# a trailing digit segment is page 1 — not matched here, callers default to 1.
_PAGE_NUMBER_RE = re.compile(r"/list/all/all/(\d+)(?:\?|$)")


def _parse_pagination(
    soup: BeautifulSoup,
    selectors: ListSelectors,
    category_id: str | None,
) -> tuple[int | None, int, str | None]:
    """Extract (total_count, last_page, next_url) from a listing page.

    Deliberately lenient: pagination is never required by
    `JobcanStructureChangeError` (a category with 10 or fewer jobs renders no
    `.pagination-list` at all — real fixture: list_it.html, 4 jobs, "4 件"
    with no page links). Every branch below degrades to "single page" rather
    than raising, so a Jobcan tweak to the pagination markup alone never
    blocks the list from rendering — it just stops multi-page crawling
    (caught separately by the crawler's total-count reconciliation).
    """
    total_tag = soup.select_one(selectors.pagination_total)
    total_count: int | None = None
    if total_tag is not None:
        match = _PAGINATION_TOTAL_RE.search(_text(total_tag))
        if match:
            total_count = int(match.group(1))

    last_link = soup.select_one(selectors.pagination_last_link)
    if last_link is None:
        # No `rel="last"` link — either a single-page category, or (defensive
        # fallback) Jobcan renders a `rel="next"` chain without a last link.
        next_link = soup.select_one('a[rel="next"]')
        if next_link is None:
            return total_count, 1, None
        next_href = _attr(next_link, "href")
        return total_count, 1, _normalise_jobcan_url(next_href) if next_href else None

    last_href = _attr(last_link, "href")
    page_match = _PAGE_NUMBER_RE.search(last_href)
    last_page = int(page_match.group(1)) if page_match else 1

    next_link = soup.select_one('a[rel="next"]')
    next_href = _attr(next_link, "href") if next_link is not None else ""
    next_url = _normalise_jobcan_url(next_href) if next_href else None

    return total_count, last_page, next_url


def _parse_list_card(
    box: Tag,
    selectors: ListSelectors,
    thumb_cfg: ThumbnailCategoriesConfig,
) -> JobListItem | None:
    """Extract a single JobListItem from a `.job-offer-box`.

    Returns None when the card lacks any of: title text, detail-page link,
    or a numeric job_id parseable from the link. None means "skip this card";
    the caller decides what to do (currently: drop silently).
    """
    title_tag = box.select_one(selectors.title)
    url_tag = box.select_one(selectors.job_url)
    if title_tag is None or url_tag is None:
        return None

    title = _text(title_tag)
    href = _attr(url_tag, "href")
    if not title or not href:
        return None

    job_id = _extract_job_id(href)
    if job_id is None:
        return None

    address_tag = box.select_one(selectors.address)
    description_tag = box.select_one(selectors.description)
    address = _text(address_tag)
    description = _text(description_tag)

    label_tag = box.select_one(selectors.label)
    labels: list[str] = []
    if isinstance(label_tag, Tag):
        labels = [_text(li) for li in label_tag.find_all("li") if _text(li)]

    # Extract the Jobcan-supplied thumbnail. Path-relative / data: URIs are
    # dropped to None here (they would fail the source_thumbnail_url validator).
    thumbnail_tag = box.select_one(selectors.thumbnail)
    source_thumbnail_url: str | None = None
    if isinstance(thumbnail_tag, Tag):
        src = _attr(thumbnail_tag, "src")
        if src:
            candidate = _normalise_jobcan_url(src)
            if candidate.startswith("http://") or candidate.startswith("https://"):
                source_thumbnail_url = candidate

    # Phase 2A.1c: pick the display thumbnail.
    # - enabled=False → keep Jobcan's source URL as-is.
    # - enabled=True  → look up category by labels, fall back to default_image.
    display_thumbnail_url = _resolve_display_thumbnail(
        job_id=job_id,
        labels=labels,
        source_thumbnail_url=source_thumbnail_url,
        thumb_cfg=thumb_cfg,
    )

    # The listing-page link points at `/aozora/job_offers/<id>?hide_breadcrumb=false`;
    # rebuild it into the proxy's canonical detail-page shape so downstream
    # code does not have to know that listing and detail use different query strings.
    detail_url = _canonical_detail_url(job_id)

    return JobListItem(
        job_id=job_id,
        title=title,
        address=address,
        description=description,
        detail_url=detail_url,
        labels=labels,
        thumbnail_url=display_thumbnail_url,
        source_thumbnail_url=source_thumbnail_url,
    )


def _pick_variant(*, job_id: str, images: Sequence[str]) -> str:
    """Deterministically map a job_id onto one image of its category's pool
    (2026-08-11, variant selection).

    MUST use a stable hash. Python's builtin `hash(str)` is salted per
    process (`PYTHONHASHSEED`, random by default since 3.3), so
    `hash(job_id) % len(images)` would re-roll every card's image on EVERY
    Cloud Run Job execution — the exact "cards shuffle on every sync"
    failure this feature exists to avoid. `hashlib.sha256` is stable across
    processes, hosts, and Python versions, forever.

    Depends only on `(job_id, images)` — never on this job's position in
    the current run, how many other jobs exist, or wall clock — so a job
    added/removed/reordered in a later sync cannot move any OTHER job's
    assigned image. Only a deliberate edit to a category's `images` list in
    `selectors.yaml` changes that category's assignments.
    """
    if not images:
        # Unreachable via `synonym_to_images` today — every pool traces back
        # to `ThumbnailCategoryEntry.images` (`min_length=1`, config-validated
        # at load). Guarded anyway: a bare `ZeroDivisionError` below would be
        # a confusing failure mode if a future refactor ever fed this
        # function a pool that skipped that validation.
        raise ValueError("_pick_variant: images pool must be non-empty")
    if len(images) == 1:
        return images[0]
    digest = hashlib.sha256(job_id.encode("utf-8")).digest()
    return images[int.from_bytes(digest, "big") % len(images)]


def _resolve_display_thumbnail(
    *,
    job_id: str,
    labels: list[str],
    source_thumbnail_url: str | None,
    thumb_cfg: ThumbnailCategoriesConfig,
) -> str | None:
    """Phase 2A.1c — pick the display thumbnail for a JobListItem.

    Order:
      1. If `thumb_cfg.enabled` is False, return the Jobcan source URL as-is.
      2. Walk `labels` in document order; the first label that exact-matches
         a category synonym wins. That category's image *pool* is then
         narrowed to one path by `_pick_variant(job_id, ...)`.
      3. No label matched → return `default_image` and emit a structured
         warning so operators can spot a new Jobcan job type that needs
         adding to `categories`.

    Codex Q2 (review): `labels[0]` was insufficient — Jobcan's label order
    is observation, not contract. Iterating all labels is the defensive form.
    """
    if not thumb_cfg.enabled:
        return source_thumbnail_url

    # The reverse `synonym -> image pool` map is computed once at
    # config-validation time on `ThumbnailCategoriesConfig` (which also
    # rejects synonym collisions across categories). The parser just looks
    # up here and picks one pool member.
    synonym_to_images = thumb_cfg.synonym_to_images
    for label in labels:
        images = synonym_to_images.get(label)
        if images is not None:
            return _pick_variant(job_id=job_id, images=images)

    # No label matched any category — fall back to default + structured warning.
    # The operator-actionable signal: job_id + the actual labels seen, so they
    # can decide whether to add a new category or leave as default.
    _logger.warning(
        "thumbnail_categories: no synonym match, using default image",
        extra={
            "job_id": job_id,
            "labels": labels,
            "default_image": thumb_cfg.default_image,
            "known_synonyms": sorted(synonym_to_images.keys()),
        },
    )
    return thumb_cfg.default_image


def _extract_job_id(href: str) -> str | None:
    """Pull the numeric job_id from `/aozora/job_offers/<id>?...` URLs."""
    match = _JOB_ID_RE.search(href)
    return match.group(1) if match else None


def _canonical_detail_url(job_id: str) -> str:
    """Build the proxy's canonical detail-page URL for a given job_id."""
    return (
        f"{JOBCAN_BASE_URL}/job_offers/{job_id}"
        "?hide_breadcrumb=true&hide_search=true"
    )


# Public aliases so `csv_ingest.py` (which has no HTML to select a detail URL
# / label-driven thumbnail from) can reuse this logic without either module
# importing the other's private names. The private names above stay as the
# canonical implementation and are unchanged everywhere else in this file.
canonical_detail_url = _canonical_detail_url
resolve_display_thumbnail = _resolve_display_thumbnail


def _extract_category_id(source_url: str) -> str | None:
    """Pull `category_id` from a Jobcan list URL's query string, if present.

    Phase 2A.1b: today no caller reads this — it is set for future use by
    Phase 2A.2 pagination / analytics. Once a consumer exists, revisit the
    silent-None branch (a typo'd `?categoryId=18773` returns None and the
    consumer silently degrades). Options at that point: log at parse time,
    or treat 'list URL without category_id' as a structure-change error
    (the CLI itself never builds such a URL, so any None comes from a hand-
    crafted fixture or a Jobcan rename).
    """
    try:
        query = urlsplit(source_url).query
    except ValueError:
        return None
    values = parse_qs(query).get("category_id")
    return values[0] if values else None
