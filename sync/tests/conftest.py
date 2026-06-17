"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobcan_responses"
SAMPLE_JOB_ID = "1777023"
SAMPLE_SOURCE_URL = (
    f"https://recruit.jobcan.jp/aozora/job_offers/{SAMPLE_JOB_ID}"
    "?hide_breadcrumb=true&hide_search=true"
)


@pytest.fixture
def sample_html() -> str:
    return (FIXTURES_DIR / f"job_{SAMPLE_JOB_ID}.html").read_text(encoding="utf-8")


@pytest.fixture
def broken_html() -> str:
    return (FIXTURES_DIR / "job_broken.html").read_text(encoding="utf-8")
