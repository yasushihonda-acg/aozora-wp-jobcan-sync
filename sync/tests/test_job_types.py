"""Tests for `job_types.py` — the single source of truth for the 17
Jobcan category_id → 職種名 table (job-type-filter-granularity follow-up,
2026-08-09).
"""

from __future__ import annotations

from sync.crawler import KNOWN_CATEGORY_IDS
from sync.job_types import JOB_TYPE_IDS_BY_NAME, JOB_TYPE_NAMES
from sync.list_sections import LABEL_TO_CATEGORY


def test_job_type_names_has_seventeen_entries() -> None:
    assert len(JOB_TYPE_NAMES) == 17


def test_job_type_names_ids_are_unique() -> None:
    # dict keys are already unique by construction, but this also guards
    # against a copy/paste id typo silently overwriting an entry (which
    # would still leave the dict at 17 keys if the duplicate replaced a
    # distinct id — the len() check above wouldn't catch that case).
    assert len(set(JOB_TYPE_NAMES)) == len(JOB_TYPE_NAMES)


def test_job_type_names_values_are_unique() -> None:
    """`JOB_TYPE_IDS_BY_NAME` (the CSV-ingestion reverse lookup) is only safe
    if no two category_ids share a display name — a collision would make the
    reverse lookup silently pick whichever id happened to be inserted last."""
    assert len(set(JOB_TYPE_NAMES.values())) == len(JOB_TYPE_NAMES)


def test_job_type_ids_by_name_is_the_exact_reverse_of_job_type_names() -> None:
    assert len(JOB_TYPE_IDS_BY_NAME) == len(JOB_TYPE_NAMES)
    for category_id, name in JOB_TYPE_NAMES.items():
        assert JOB_TYPE_IDS_BY_NAME[name] == category_id


def test_known_category_ids_derives_from_job_type_names() -> None:
    assert KNOWN_CATEGORY_IDS == tuple(JOB_TYPE_NAMES)


def test_label_to_category_keys_match_job_type_names_values() -> None:
    """Drift guard (plan §1): `LABEL_TO_CATEGORY` (list_sections.py, the
    4-bucket colour system) is hand-maintained separately from
    `JOB_TYPE_NAMES` rather than derived from it, specifically so a 1-
    character mismatch between Jobcan's card label text and this table's
    職種名 doesn't silently drop a card's colour accent. This test is the
    other half of that trade-off — it fails loudly instead."""
    assert set(LABEL_TO_CATEGORY) == set(JOB_TYPE_NAMES.values())
