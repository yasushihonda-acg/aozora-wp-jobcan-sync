"""Pydantic data models and exceptions for the Jobcan proxy."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class JobcanError(Exception):
    """Base exception for the sync package."""


class JobcanClientError(JobcanError):
    """Raised when fetching a Jobcan page fails (network / HTTP error).

    `status_code` carries the upstream HTTP status when known (HTTP 4xx/5xx
    responses), or `None` for network-level failures (timeout, DNS, TLS).
    Callers should treat `None` the same as 5xx — neither is something the
    user can fix by retrying the canonical Jobcan URL.

    Phase 2A.3 cleanup (code-review #7): the FastAPI proxy used to reverse-
    engineer the status code from the message string; storing it as a typed
    attribute lets the route layer dispatch without parsing.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JobcanStructureChangeError(JobcanError):
    """Raised when expected CSS selectors are missing from the Jobcan HTML.

    This is the Phase 0 detection mechanism for upstream HTML changes.
    Phase 1 will wire this into Slack alerts; for now it surfaces via CLI exit code.
    """

    def __init__(self, missing: list[str], job_id: str | int | None = None) -> None:
        self.missing = missing
        self.job_id = job_id
        msg = f"Required selectors missing: {', '.join(missing)}"
        if job_id is not None:
            msg = f"{msg} (job_id={job_id})"
        super().__init__(msg)


class JobcanValidationError(JobcanError):
    """Raised when required fields are extracted as empty or malformed.

    Distinguished from StructureChangeError: the selectors were found, but the
    content fails domain validation (e.g. salary text is blank). Either case
    blocks rendering — partial display of a job posting is forbidden by Phase 0
    policy (Codex review feedback).
    """

    def __init__(self, field_errors: dict[str, str], job_id: str | int | None = None) -> None:
        self.field_errors = field_errors
        self.job_id = job_id
        msg = "; ".join(f"{k}: {v}" for k, v in field_errors.items())
        if job_id is not None:
            msg = f"{msg} (job_id={job_id})"
        super().__init__(msg)


class JobOffer(BaseModel):
    """Normalised job posting extracted from a single Jobcan job detail page.

    Required fields (validated, never empty):
        - job_id, title, body_html, address, label, location, salary, apply_url, source_url

    `body_html` is sanitised by `bleach` before storage. Only an allowlist of
    semantic tags (p, br, ul, ol, li, strong, em, h2, h3, h4) survives —
    no <script>, <style>, <form>, or event attributes are preserved.
    """

    # Required-field validation lives in `parser.parse_job_detail` rather than
    # here (Field constraints removed to avoid two redundant validation layers).
    # Constructing a JobOffer directly with empty fields is the caller's
    # responsibility — production builds always go through the parser.
    job_id: str = Field(..., description="Jobcan job_offer ID (numeric string)")
    title: str = Field(..., description="Job title")
    body_html: str = Field(..., description="Sanitised job description HTML")
    address: str = Field(..., description="Facility / branch name")
    label: str = Field(..., description="Job type + employment-form label")
    location: str = Field(..., description="Work location (commute info)")
    salary: str = Field(..., description="Salary text (full original)")
    apply_url: str = Field(..., description="Jobcan apply URL — preserved as-is")
    source_url: str = Field(..., description="Original Jobcan detail page URL")
    page_title: str | None = Field(None, description="<title> contents for SEO")

    # Optional table lines that didn't map to a fixed field (extras like 福利厚生, 休日 etc.)
    extra_lines: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Additional content-table-line entries as (header, value) tuples",
    )

    model_config = {"frozen": True}

    @field_validator("apply_url", "source_url")
    @classmethod
    def _must_be_http_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"must be an http(s) URL, got: {v!r}")
        return v


class JobListItem(BaseModel):
    """One row of a Jobcan category listing page.

    Phase 2A.1b: represents a single `.job-offer-box` extracted from
    `/aozora/list?category_id=...`. The shape is deliberately leaner than
    `JobOffer` — the listing page never contains salary or full body HTML,
    only enough to render a card linking to the detail page.

    `detail_url` currently resolves to the canonical Jobcan detail page
    (`https://recruit.jobcan.jp/aozora/job_offers/<id>?hide_breadcrumb=true&hide_search=true`).
    Phase 2A.2 (FastAPI proxy) will introduce an in-house `/jobs/{job_id}`
    route; at that point `_canonical_detail_url` will be flipped to emit the
    proxy path so card clicks stay inside the in-house design instead of
    bouncing back to Jobcan. The shape of the field stays the same — only
    the URL it produces changes.
    """

    job_id: str = Field(..., description="Jobcan job_offer ID (numeric string)")
    title: str = Field(..., description="Job title displayed on the card")
    address: str = Field(..., description="Facility / branch line under the title")
    description: str = Field(..., description="Plain-text excerpt for the card")
    detail_url: str = Field(..., description="Canonical detail-page URL (see class docstring)")
    labels: list[str] = Field(
        default_factory=list,
        description="Job-type + employment-form chips (e.g. ['介護職', '正社員'])",
    )
    thumbnail_url: str | None = Field(
        None,
        description=(
            "Card thumbnail displayed in the rendered HTML. "
            "Phase 2A.1c: when `thumbnail_categories.enabled` is True, this is "
            "the in-house category override image (relative path under `assets/`); "
            "when disabled, this is the original Jobcan-supplied URL."
        ),
    )
    source_thumbnail_url: str | None = Field(
        None,
        description=(
            "The original Jobcan-supplied thumbnail URL, preserved unchanged. "
            "Phase 2A.1c separates this from `thumbnail_url` so the proxy can "
            "rewrite the displayed image while keeping a debug trail of what "
            "Jobcan actually returned (useful when the operator needs to see "
            "why a particular card was rewritten or fell through to default)."
        ),
    )

    model_config = {"frozen": True}

    @field_validator("detail_url")
    @classmethod
    def _detail_url_must_be_http(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"detail_url must be an http(s) URL, got: {v!r}")
        return v

    @field_validator("source_thumbnail_url")
    @classmethod
    def _source_thumbnail_url_must_be_http_when_set(cls, v: str | None) -> str | None:
        # source_thumbnail_url stores the ORIGINAL Jobcan URL, so it must be
        # http(s). The display field `thumbnail_url` does not get this check
        # because it can also hold a relative in-house override path
        # (`assets/img/illust-job-care.png`).
        if v is None:
            return v
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"source_thumbnail_url must be an http(s) URL when set, got: {v!r}")
        return v


class JobListPage(BaseModel):
    """A parsed Jobcan category listing page.

    Bundles the items with the source URL so the renderer/CLI does not have
    to thread `source_url` separately. Phase 2A.2 may extend this with
    pagination metadata.
    """

    source_url: str = Field(..., description="The Jobcan list URL that produced these items")
    category_id: str | None = Field(
        None, description="The `category_id` query parameter parsed from source_url, if any"
    )
    items: list[JobListItem] = Field(default_factory=list)

    model_config = {"frozen": True}

    @field_validator("source_url")
    @classmethod
    def _must_be_http_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"must be an http(s) URL, got: {v!r}")
        return v
