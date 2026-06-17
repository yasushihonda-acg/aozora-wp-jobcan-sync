"""Pydantic data models and exceptions for the Jobcan proxy."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class JobcanError(Exception):
    """Base exception for the sync package."""


class JobcanClientError(JobcanError):
    """Raised when fetching a Jobcan page fails (network / HTTP error)."""


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

    job_id: str = Field(..., description="Jobcan job_offer ID (numeric string)")
    title: str = Field(..., min_length=1, description="Job title")
    body_html: str = Field(..., min_length=1, description="Sanitised job description HTML")
    address: str = Field(..., min_length=1, description="Facility / branch name")
    label: str = Field(..., min_length=1, description="Job type + employment-form label")
    location: str = Field(..., min_length=1, description="Work location (commute info)")
    salary: str = Field(..., min_length=1, description="Salary text (full original)")
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
